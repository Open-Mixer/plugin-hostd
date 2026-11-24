/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * plugin-hostd is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * plugin-hostd is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with plugin-hostd.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Copyright (C) 2026 Pau Aliagas
 */

/* A worker the daemon ends is asked to end first. Each worker holds a JACK client, and a JACK client that dies without
 * jack_client_close strands the mutexes of its metadata environment in jackd for good (the pool is fixed, a handful of
 * unclean deaths exhaust it). So proc_rpc, which gives up on a worker that does not answer, sends SIGTERM and returns at
 * once, and the supervisor's tick (proc_term_poll) sends SIGKILL to one that is still there when PROC_TERM_GRACE_MS has
 * passed: a worker that closes on SIGTERM leaves as a process that exited (here with status 42, the way a worker closes
 * its client and returns), and one that ignores SIGTERM is killed once the grace has passed, not before and not much
 * after. proc_rpc never waits out the grace: the supervisor serves the others meanwhile. The workers here are forked
 * children that never answer. */

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#include "conf.h"
#include "proc.h"

static int failures;

static void check(int ok, const char *what)
{
    if (!ok)
    {
        failures++;
        printf("FAIL proc_term: %s\n", what);
    }
}

static void on_term(int sig)
{
    (void)sig;
    _exit(42);
}

/* a worker that never answers: with `closes` it leaves with status 42 on SIGTERM (the worker closing its client), else
 * it ignores SIGTERM. The pid, and the daemon's end of a socket pair whose other end the worker holds. */
static pid_t spawn_mute(int closes, int *fd)
{
    int pair[2];
    pid_t pid;

    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0)
        return -1;
    pid = fork();
    if (pid == 0)
    {
        struct sigaction sa;

        memset(&sa, 0, sizeof(sa));
        sa.sa_handler = closes ? on_term : SIG_IGN;
        sigemptyset(&sa.sa_mask);
        sigaction(SIGTERM, &sa, NULL);
        close(pair[0]);
        for (;;)
            pause();
    }
    close(pair[1]);
    *fd = pair[0];
    return pid;
}

static volatile sig_atomic_t g_ticks;

static void on_tick(int sig)
{
    (void)sig;
    g_ticks++;
}

/* A handled signal is no timeout (plugin-hostd#146 4): a worker that answers after 300 ms while a handler without
 * SA_RESTART fires every 20 ms gets its answer read, is not ended and is not reported unanswered. */
static void a_handled_signal_is_no_timeout(void)
{
    struct sigaction sa, old_sa;
    struct itimerval every = { { 0, 20000 }, { 0, 20000 } }, off = { { 0, 0 }, { 0, 0 } };
    conf_t conf;
    char *reply = NULL;
    int pair[2], result, status = 0;
    pid_t pid;

    if (socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0)
    {
        check(0, "a socket pair for the slow worker");
        return;
    }
    pid = fork();
    if (pid == 0)
    {
        char line[64];

        close(pair[0]);
        if (recv(pair[1], line, sizeof(line), 0) <= 0)
            _exit(1);
        usleep(300000);
        send(pair[1], "resp 0", 7, MSG_NOSIGNAL);
        pause();
        _exit(0);
    }
    close(pair[1]);
    conf_defaults(&conf);
    conf.rpc_timeout_ms = 2000;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_tick;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGALRM, &sa, &old_sa);
    g_ticks = 0;
    setitimer(ITIMER_REAL, &every, NULL);
    result = proc_rpc(&conf, pid, pair[0], "ping", &reply);
    setitimer(ITIMER_REAL, &off, NULL);
    sigaction(SIGALRM, &old_sa, NULL);
    check(g_ticks > 0, "positive control: the handler ran during the call");
    check(result == RPC_OK && reply && !strcmp(reply, "resp 0"), "a call a signal cut answers the worker's reply");
    free(reply);
    kill(pid, SIGKILL);
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR)
        ;
    close(pair[0]);
}

/* proc_rpc to a mute worker: the wait status of the worker after, and how long the call took */
static void rpc_to_mute(int closes, int *status, int64_t *rpc_ms, int64_t *took_ms, int *result)
{
    conf_t conf;
    char *reply = NULL;
    int fd = -1;
    int64_t start;
    pid_t pid;

    conf_defaults(&conf);
    conf.rpc_timeout_ms = 200;
    pid = spawn_mute(closes, &fd);
    /* the child has to have installed its handler before the timeout asks it to leave */
    usleep(100000);
    start = proc_now_ms();
    *result = proc_rpc(&conf, pid, fd, "ping", &reply);
    *rpc_ms = proc_now_ms() - start;
    free(reply);
    /* the tick: SIGKILL for the one past its grace, and the reap once it is gone */
    for (;;)
    {
        pid_t r;

        proc_term_poll();
        r = waitpid(pid, status, WNOHANG);
        if (r == pid || (r < 0 && errno != EINTR))
            break;
        usleep(10000);
    }
    *took_ms = proc_now_ms() - start;
    close(fd);
}

/* more workers stopped at once than any fixed table held (it held 64): every one is still known as stopped by us when it
 * is reaped, the first as much as the last. The workers close on SIGTERM and are left unreaped, as on_death leaves them. */
#define MANY 200
static void many_stopped(void)
{
    pid_t pids[MANY];
    int fds[MANY], n, ours = 0, status;

    for (n = 0; n < MANY; n++)
        pids[n] = spawn_mute(1, &fds[n]);
    usleep(200000); /* the handlers are installed before the first SIGTERM */
    for (n = 0; n < MANY; n++)
        proc_term(pids[n]);
    for (n = 0; n < MANY; n++)
    {
        while (waitpid(pids[n], &status, 0) < 0 && errno == EINTR)
            ;
        ours += proc_stopped_by_us(pids[n]);
        close(fds[n]);
    }
    check(ours == MANY, "every one of 200 workers stopped at once is still known as stopped by us (not just the last 64)");
    check(proc_stopped_by_us(pids[0]) == 0, "and an entry is consumed once, not kept for a pid that is gone");
}

/* a worker stopped twice (the supervisor's paths can reach one pid more than once) has ONE entry: the second proc_term
 * adds none and keeps the first's kill time, so once it is reaped no entry is left to read a reused pid as stopped by us. */
static void term_twice(void)
{
    int fd, status;
    pid_t pid = spawn_mute(0, &fd);

    usleep(200000);
    proc_term(pid);
    proc_term(pid);
    kill(pid, SIGKILL);
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR)
        ;
    check(proc_stopped_by_us(pid) == 1, "a worker stopped twice is known as stopped by us");
    check(proc_stopped_by_us(pid) == 0, "and has one entry, not a duplicate left behind after it is reaped");
    close(fd);
}

int main(void)
{
    int status = 0, result = 0;
    int64_t took = 0, rpc = 0;

    rpc_to_mute(1, &status, &rpc, &took, &result);
    check(result == RPC_DIED, "a worker that does not answer counts as died");
    check(WIFEXITED(status) && WEXITSTATUS(status) == 42,
          "a worker that does not answer got SIGTERM and left on its own, not a SIGKILL with no SIGTERM first");
    check(took < PROC_TERM_GRACE_MS, "a worker that leaves on SIGTERM is not waited for the whole grace");
    check(rpc < PROC_TERM_GRACE_MS / 2, "proc_rpc returns when the timeout ends, with the worker still leaving");

    rpc_to_mute(0, &status, &rpc, &took, &result);
    check(result == RPC_DIED, "a worker that ignores SIGTERM counts as died");
    check(WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL, "a worker that ignores SIGTERM is killed after the grace");
    check(rpc < PROC_TERM_GRACE_MS / 2, "proc_rpc returns when the timeout ends, not after the grace");
    check(took >= 200 + PROC_TERM_GRACE_MS - 50 && took < 200 + PROC_TERM_GRACE_MS + 1500,
          "and the kill comes with the grace, bounded: not before it, and not long after");

    many_stopped();
    term_twice();
    a_handled_signal_is_no_timeout();

    if (failures)
        printf("proc_term: %d failed\n", failures);
    else
        printf("ok   proc_term_test\n");
    return failures ? 1 : 0;
}
