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
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include <plugin-hostd/protocol.h>

#include "relay.h"

/* a worker line longer than this, with no NUL in it, is not a line of the protocol: it is dropped; the fuzz harness
 * (fuzz/fuzz_reply.c) builds the relay with a smaller one, so its inputs reach the drop */
#ifndef LINE_LIMIT
#define LINE_LIMIT (1024 * 1024)
#endif

typedef struct SOURCE_T {
    int fd;
    int eof;                    /* the worker closed it: not polled again, closed when the supervisor says so */
    int skip;                   /* the start of the line being read was dropped as too long: drop its end too */
    char *buf;
    size_t used, cap;
    /* the gestures the worker began and has not ended, each its line up to the last word */
    char **held;
    int nheld;
    /* the worker's last xruns line (PHD_EVENT_XRUNS), a cumulative count; counted is 0 until one was read */
    int counted;
    unsigned long long xruns;
    /* the instances the worker said abi_clobber of (PHD_EVENT_ABI_CLOBBER), not yet taken by the supervisor: each once,
     * as many as there are (a pool has no size limit by default) */
    int *abi;
    int nabi, capabi;
    /* the instances whose plugin moved a value of its own (a param_set line the worker wrote: a preset the plugin loaded, an
     * LFO, a knob on its own window), not yet taken by the supervisor: each once. The state the plugin holds now is not the
     * state the last checkpoint saved, so the supervisor checkpoints it */
    int *moved;
    int nmoved, capmoved;
} source_t;

static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
/* the one line relay_watch waits for: the first a worker's feedback socket gives that starts with the prefix */
static struct {
    int fd;
    char *prefix;
    char *line;
} g_watch = { -1, NULL, NULL };
static pthread_cond_t g_watch_seen;
static pthread_once_t g_watch_once = PTHREAD_ONCE_INIT;
static pthread_t g_thread;
static int g_thread_up;
static volatile int g_stop;
static int g_listen = -1;
static int g_client = -1;
static int g_client_broken;
static int g_wake[2] = { -1, -1 };
static source_t *g_src;
static int g_nsrc, g_capsrc;

static size_t (*g_prefix)(char *buf, size_t size);

void relay_set_prefix(size_t (*prefix)(char *buf, size_t size))
{
    g_prefix = prefix;
}

/* one NUL-terminated line to the controller, whole or not at all; g_lock is held. Under the session's seq every line
 * is numbered, also one that could not be sent: the gap is how the controller knows */
static void send_line(const char *line, size_t len)
{
    size_t sent = 0;
    char head[32];
    size_t head_len = 0;

    if (g_prefix)
        head_len = g_prefix(head, sizeof(head));
    if (g_client < 0 || g_client_broken)
        return;
    while (sent < head_len)
    {
        ssize_t n = send(g_client, head + sent, head_len - sent, MSG_NOSIGNAL);

        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
        {
            g_client_broken = 1;
            return;
        }
        sent += n;
    }
    sent = 0;
    while (sent < len)
    {
        ssize_t n = send(g_client, line + sent, len - sent, MSG_NOSIGNAL);

        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
        {
            /* the controller closed its feedback port: nothing more goes to it until the next one opens its own */
            g_client_broken = 1;
            return;
        }
        sent += n;
    }
}

/* a param_gesture line the worker wrote: a begin is held until its end; any other line is none of this */
static void gesture_seen(source_t *s, const char *line)
{
    size_t verb = strlen(PHD_EVENT_PARAM_GESTURE);
    const char *last = strrchr(line, ' ');
    int n, begin;

    if (strncmp(line, PHD_EVENT_PARAM_GESTURE, verb) || line[verb] != ' ' || !last || last == line + verb)
        return;
    begin = !strcmp(last + 1, PHD_GESTURE_BEGIN);
    if (!begin && strcmp(last + 1, PHD_GESTURE_END))
        return;
    for (n = 0; n < s->nheld; n++)
        if (strlen(s->held[n]) == (size_t)(last - line) && !strncmp(s->held[n], line, last - line))
            break;
    if (begin && n == s->nheld)
    {
        /* no memory for one more: the table keeps what it holds and this gesture is not remembered */
        char **held = realloc(s->held, (s->nheld + 1) * sizeof(char *));
        char *copy;

        if (held == NULL)
            return;
        s->held = held;
        copy = strndup(line, last - line);
        if (copy != NULL)
            s->held[s->nheld++] = copy;
    }
    else if (!begin && n < s->nheld)
    {
        free(s->held[n]);
        s->held[n] = s->held[--s->nheld];
    }
}

/* an xruns line the worker wrote: the word, a space and one whole number, nothing else; any other line is none of this. A
 * count that does not fit is no count either */
static void xruns_seen(source_t *s, const char *line)
{
    size_t word = strlen(PHD_EVENT_XRUNS);
    const char *digits = line + word + 1;
    unsigned long long count;
    char *end;

    if (strncmp(line, PHD_EVENT_XRUNS, word) || line[word] != ' ' || *digits < '0' || *digits > '9')
        return;
    errno = 0;
    count = strtoull(digits, &end, 10);
    if (errno != 0 || *end != '\0')
        return;
    s->xruns = count;
    s->counted = 1;
}

/* an abi_clobber line the worker wrote: the word, a space and the instance number first; the rest is the controller's to
 * read. The instance is kept for the supervisor until it takes it; past the table, none is kept */
static void abi_seen(source_t *s, const char *line)
{
    size_t word = strlen(PHD_EVENT_ABI_CLOBBER);
    const char *digits = line + word + 1;
    long id;
    char *end;

    if (strncmp(line, PHD_EVENT_ABI_CLOBBER, word) || line[word] != ' ' || !isdigit((unsigned char)*digits))
        return;
    id = strtol(digits, &end, 10);
    if (*end != ' ' || id > INT_MAX)
        return;
    for (int n = 0; n < s->nabi; n++)
        if (s->abi[n] == (int)id)
            return;
    if (s->nabi == s->capabi)
    {
        int cap = s->capabi ? 2 * s->capabi : 16, *grown = realloc(s->abi, (size_t)cap * sizeof(int));

        if (!grown)
        {
            fprintf(stderr, "plugin-hostd: out of memory: the abi_clobber of instance %ld is not kept, it is not isolated\n", id);
            return;
        }
        s->abi = grown;
        s->capabi = cap;
    }
    s->abi[s->nabi++] = (int)id;
}

/* a param_set line the worker wrote: its instance is kept for the supervisor until it takes it; past memory, none is kept
 * (the next move of the same instance says it again) */
static void moved_seen(source_t *s, const char *line)
{
    size_t word = strlen(PHD_EVENT_PARAM_SET);
    const char *digits = line + word + 1;
    long id;
    char *end;

    if (strncmp(line, PHD_EVENT_PARAM_SET, word) || line[word] != ' ' || !isdigit((unsigned char)*digits))
        return;
    id = strtol(digits, &end, 10);
    if (*end != ' ' || id > INT_MAX)
        return;
    for (int n = 0; n < s->nmoved; n++)
        if (s->moved[n] == (int)id)
            return;
    if (s->nmoved == s->capmoved)
    {
        int cap = s->capmoved ? 2 * s->capmoved : 16, *grown = realloc(s->moved, (size_t)cap * sizeof(int));

        if (!grown)
            return;
        s->moved = grown;
        s->capmoved = cap;
    }
    s->moved[s->nmoved++] = (int)id;
}

/* a line the watch waits for is kept; g_lock is held */
static void watch_seen(source_t *s, const char *line)
{
    if (g_watch.fd != s->fd || !g_watch.prefix || g_watch.line || strncmp(line, g_watch.prefix, strlen(g_watch.prefix)))
        return;
    g_watch.line = strdup(line);
    if (g_watch.line)
        pthread_cond_broadcast(&g_watch_seen);
}

/* the end of a held gesture, its line up to the last word and the word end, as one line of whatever length; g_lock is
 * held, so nothing is written between the two parts */
static void gesture_end(const char *held)
{
    send_line(held, strlen(held));
    send_line(" " PHD_GESTURE_END, sizeof(" " PHD_GESTURE_END));
}

/* a worker that is gone ends every gesture it held, so no control stays held at the controller; g_lock is held */
static void gestures_end(source_t *s)
{
    int n;

    for (n = 0; n < s->nheld; n++)
    {
        gesture_end(s->held[n]);
        free(s->held[n]);
    }
    free(s->held);
    s->held = NULL;
    s->nheld = 0;
}

static void drain(source_t *s);

/* an instance removed ends the gestures it held, once each, whichever worker held them; g_lock is held */
static void gestures_end_instance(source_t *s, int id)
{
    char prefix[48];
    size_t plen;
    int n = 0;

    snprintf(prefix, sizeof(prefix), "%s %d ", PHD_EVENT_PARAM_GESTURE, id);
    plen = strlen(prefix);
    while (n < s->nheld)
    {
        if (strncmp(s->held[n], prefix, plen))
        {
            n++;
            continue;
        }
        gesture_end(s->held[n]);
        free(s->held[n]);
        s->held[n] = s->held[--s->nheld];
    }
}

/* everything the worker has written so far, its complete lines sent in order; g_lock is held */
static void drain(source_t *s)
{
    for (;;)
    {
        ssize_t n;
        char *start, *nul;

        if (s->cap - s->used < 4096)
        {
            size_t cap = s->cap ? s->cap * 2 : 8192;
            char *buf = realloc(s->buf, cap);

            if (buf == NULL)
            {
                /* no memory to read the worker into: read it no more, as for a worker that closed it, and say so to
                 * the worker, whose writes now fail instead of blocking on a full socket; the socket stays open
                 * until the supervisor removes it */
                shutdown(s->fd, SHUT_RDWR);
                s->eof = 1;
                return;
            }
            s->buf = buf;
            s->cap = cap;
        }
        n = recv(s->fd, s->buf + s->used, s->cap - s->used, MSG_DONTWAIT);
        if (n < 0 && errno == EINTR)
            continue;
        if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK))
            s->eof = 1;
        if (n <= 0)
            return;
        s->used += n;
        start = s->buf;
        while ((nul = memchr(start, '\0', s->used - (start - s->buf))))
        {
            /* a line too long to relay is dropped whole: its end after a dropped start, or all of it at once */
            if (s->skip || (size_t)(nul - start) > LINE_LIMIT)
                s->skip = 0;
            else
            {
                send_line(start, nul - start + 1);
                gesture_seen(s, start);
                xruns_seen(s, start);
                abi_seen(s, start);
                moved_seen(s, start);
                watch_seen(s, start);
            }
            start = nul + 1;
        }
        s->used -= start - s->buf;
        memmove(s->buf, start, s->used);
        if (s->used > LINE_LIMIT)
        {
            s->used = 0;
            s->skip = 1;
        }
    }
}

static void wake(void)
{
    char c = 0;

    /* a full pipe means the thread is awake already */
    if (g_wake[1] >= 0 && write(g_wake[1], &c, 1) < 0)
        return;
}

static void *relay_thread(void *arg)
{
    struct pollfd *pfd = NULL;
    int cap = 0, first = 0;

    (void)arg;
    while (!g_stop)
    {
        int n, count = 1, i, j;

        pthread_mutex_lock(&g_lock);
        if (cap < g_nsrc + 1)
        {
            struct pollfd *bigger = realloc(pfd, (g_nsrc + 16) * sizeof(*pfd));

            if (bigger)
            {
                pfd = bigger;
                cap = g_nsrc + 16;
            }
        }
        if (cap == 0)
        {
            /* no memory for even the wake-up: try again in a while */
            pthread_mutex_unlock(&g_lock);
            usleep(10000);
            continue;
        }
        pfd[0].fd = g_wake[0];
        pfd[0].events = POLLIN;
        /* with no memory for a bigger set, the sources that fit are read this round and the next ones on the next */
        for (j = 0; j < g_nsrc && count < cap; j++)
        {
            i = (first + j) % g_nsrc;
            if (!g_src[i].eof)
            {
                pfd[count].fd = g_src[i].fd;
                pfd[count].events = POLLIN;
                count++;
            }
        }
        first = g_nsrc ? (first + j) % g_nsrc : 0;
        pthread_mutex_unlock(&g_lock);

        n = poll(pfd, count, -1);
        if (n < 0)
            continue;
        if (pfd[0].revents)
        {
            char junk[64];

            while (read(g_wake[0], junk, sizeof(junk)) > 0)
                ;
        }
        pthread_mutex_lock(&g_lock);
        for (i = 1; i < count; i++)
        {
            int k;

            if (!pfd[i].revents)
                continue;
            /* the supervisor may have closed it since: only a socket still in the table is read */
            for (k = 0; k < g_nsrc; k++)
                if (g_src[k].fd == pfd[i].fd && !g_src[k].eof)
                {
                    drain(&g_src[k]);
                    break;
                }
        }
        pthread_mutex_unlock(&g_lock);
    }
    free(pfd);
    return NULL;
}

int relay_start(int port, const char *address)
{
    if (pipe2(g_wake, O_NONBLOCK | O_CLOEXEC) != 0)
        return -1;
    if (port)
    {
        struct sockaddr_in addr;
        int one = 1;

        g_listen = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
        if (g_listen < 0)
            return -1;
        setsockopt(g_listen, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        if (inet_pton(AF_INET, address, &addr.sin_addr) != 1)
        {
            fprintf(stderr, "feedback port: '%s' is not an IPv4 address\n", address);
            return -1;
        }
        addr.sin_port = htons(port);
        if (bind(g_listen, (struct sockaddr *)&addr, sizeof(addr)) < 0 || listen(g_listen, 4) < 0)
        {
            perror("feedback port");
            return -1;
        }
    }
    if (pthread_create(&g_thread, NULL, relay_thread, NULL) != 0)
        return -1;
    g_thread_up = 1;
    return 0;
}

void relay_finish(void)
{
    int i;

    if (g_thread_up)
    {
        g_stop = 1;
        wake();
        pthread_join(g_thread, NULL);
        g_thread_up = 0;
    }
    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
    {
        close(g_src[i].fd);
        free(g_src[i].buf);
        free(g_src[i].abi);
        free(g_src[i].moved);
        gestures_end(&g_src[i]);
    }
    g_nsrc = 0;
    if (g_client >= 0)
        close(g_client);
    g_client = -1;
    if (g_listen >= 0)
        close(g_listen);
    g_listen = -1;
    pthread_mutex_unlock(&g_lock);
}

void relay_await_controller(volatile int *running)
{
    int have;

    if (g_listen < 0)
        return;
    pthread_mutex_lock(&g_lock);
    have = g_client >= 0;
    pthread_mutex_unlock(&g_lock);
    while (!have && *running)
    {
        struct pollfd p = { g_listen, POLLIN, 0 };
        int fd;

        if (poll(&p, 1, 100) <= 0)
            continue;
        fd = accept4(g_listen, NULL, NULL, SOCK_CLOEXEC);
        if (fd < 0)
            continue;
        pthread_mutex_lock(&g_lock);
        g_client = fd;
        g_client_broken = 0;
        pthread_mutex_unlock(&g_lock);
        have = 1;
    }
}

void relay_controller_gone(void)
{
    pthread_mutex_lock(&g_lock);
    if (g_client >= 0)
        close(g_client);
    g_client = -1;
    pthread_mutex_unlock(&g_lock);
}

void relay_event(const char *line)
{
    pthread_mutex_lock(&g_lock);
    send_line(line, strlen(line) + 1);
    pthread_mutex_unlock(&g_lock);
}

int relay_add(int fd)
{
    if (fd < 0)
        return -1;
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
    pthread_mutex_lock(&g_lock);
    if (g_nsrc == g_capsrc)
    {
        int cap = g_capsrc ? g_capsrc * 2 : 16;
        source_t *src = realloc(g_src, cap * sizeof(source_t));

        if (src == NULL)
        {
            /* a socket left open and unread would block the worker on its next write: close it, so the write fails */
            pthread_mutex_unlock(&g_lock);
            fprintf(stderr, "relay: no memory to follow the feedback of fd %d\n", fd);
            close(fd);
            return -1;
        }
        g_src = src;
        g_capsrc = cap;
    }
    memset(&g_src[g_nsrc], 0, sizeof(source_t));
    g_src[g_nsrc++].fd = fd;
    pthread_mutex_unlock(&g_lock);
    wake();
    return 0;
}

int relay_xruns(int fd, unsigned long long *count)
{
    int i, counted = 0;

    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
        if (g_src[i].fd == fd)
        {
            if (!g_src[i].eof)
                drain(&g_src[i]);
            counted = g_src[i].counted;
            if (counted)
                *count = g_src[i].xruns;
            break;
        }
    pthread_mutex_unlock(&g_lock);
    return counted;
}

int relay_abi_clobbers(int fd, int *ids, int max)
{
    int i, n = 0;

    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
        if (g_src[i].fd == fd)
        {
            /* the relay thread reads the worker; reading it here too would read a worker no controller listens to */
            for (n = 0; n < g_src[i].nabi && n < max; n++)
                ids[n] = g_src[i].abi[n];
            /* what did not fit waits for the next call */
            memmove(g_src[i].abi, g_src[i].abi + n, (size_t)(g_src[i].nabi - n) * sizeof(int));
            g_src[i].nabi -= n;
            break;
        }
    pthread_mutex_unlock(&g_lock);
    return n;
}

int relay_param_moves(int fd, int *ids, int max)
{
    int i, n = 0;

    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
        if (g_src[i].fd == fd)
        {
            for (n = 0; n < g_src[i].nmoved && n < max; n++)
                ids[n] = g_src[i].moved[n];
            memmove(g_src[i].moved, g_src[i].moved + n, (size_t)(g_src[i].nmoved - n) * sizeof(int));
            g_src[i].nmoved -= n;
            break;
        }
    pthread_mutex_unlock(&g_lock);
    return n;
}

static void watch_init(void)
{
    pthread_condattr_t attr;

    pthread_condattr_init(&attr);
    pthread_condattr_setclock(&attr, CLOCK_MONOTONIC);
    pthread_cond_init(&g_watch_seen, &attr);
    pthread_condattr_destroy(&attr);
}

int relay_watch(int fd, const char *prefix)
{
    char *copy = strdup(prefix);

    pthread_once(&g_watch_once, watch_init);
    if (!copy)
        return -1;
    pthread_mutex_lock(&g_lock);
    free(g_watch.prefix);
    free(g_watch.line);
    g_watch.fd = fd;
    g_watch.prefix = copy;
    g_watch.line = NULL;
    pthread_mutex_unlock(&g_lock);
    return 0;
}

char *relay_watched(int ms)
{
    struct timespec until;
    char *line;
    int i;

    pthread_once(&g_watch_once, watch_init);
    clock_gettime(CLOCK_MONOTONIC, &until);
    until.tv_sec += ms / 1000;
    until.tv_nsec += (long)(ms % 1000) * 1000000L;
    if (until.tv_nsec >= 1000000000L)
    {
        until.tv_sec++;
        until.tv_nsec -= 1000000000L;
    }
    pthread_mutex_lock(&g_lock);
    for (i = 0; ms > 0 && !g_watch.line && i < g_nsrc; i++)
        if (g_src[i].fd == g_watch.fd && !g_src[i].eof)
            drain(&g_src[i]);
    while (ms > 0 && g_watch.prefix && !g_watch.line)
        if (pthread_cond_timedwait(&g_watch_seen, &g_lock, &until) == ETIMEDOUT)
            break;
    line = g_watch.line;
    free(g_watch.prefix);
    g_watch.fd = -1;
    g_watch.prefix = NULL;
    g_watch.line = NULL;
    pthread_mutex_unlock(&g_lock);
    return line;
}

void relay_instance_gone(int id)
{
    int i;

    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
    {
        if (!g_src[i].eof)
            drain(&g_src[i]);
        gestures_end_instance(&g_src[i], id);
        /* a report of the removed instance is not one of whatever takes its number next */
        for (int n = 0; n < g_src[i].nabi; n++)
            if (g_src[i].abi[n] == id)
            {
                g_src[i].abi[n--] = g_src[i].abi[--g_src[i].nabi];
            }
        for (int n = 0; n < g_src[i].nmoved; n++)
            if (g_src[i].moved[n] == id)
                g_src[i].moved[n--] = g_src[i].moved[--g_src[i].nmoved];
    }
    pthread_mutex_unlock(&g_lock);
}

void relay_remove(int fd)
{
    int i;

    if (fd < 0)
        return;
    pthread_mutex_lock(&g_lock);
    for (i = 0; i < g_nsrc; i++)
        if (g_src[i].fd == fd)
        {
            if (!g_src[i].eof)
                drain(&g_src[i]);
            gestures_end(&g_src[i]);
            free(g_src[i].buf);
            free(g_src[i].abi);
            free(g_src[i].moved);
            g_src[i] = g_src[--g_nsrc];
            break;
        }
    close(fd);
    pthread_mutex_unlock(&g_lock);
    wake();
}
