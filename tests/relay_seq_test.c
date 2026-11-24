/* SPDX-License-Identifier: GPL-3.0-or-later */
/* src/relay.c under the session's seq extension: every line to the controller carries one sequence number at its
 * start. The test includes the relay, so it hands the controller's socket and the prefix in itself, and reads what an
 * ended gesture (a worker gone, an instance removed) writes: one line, numbered once, the word end after its words. */

#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "../src/relay.c"

static int failures, checks;
static unsigned g_seq;

static void check(int ok, const char *what)
{
    checks++;
    if (!ok)
    {
        failures++;
        printf("FAIL relay seq: %s\n", what);
    }
}

/* the session's seq prefix: "<n> ", one number per line */
static size_t seq_prefix(char *buf, size_t size)
{
    return (size_t)snprintf(buf, size, "%u ", ++g_seq);
}

/* whether the controller has exactly `want` and its NUL to read, and nothing after it */
static int got_line(int fd, const char *want)
{
    char got[256];
    ssize_t n = recv(fd, got, sizeof(got), MSG_DONTWAIT);

    return n == (ssize_t)strlen(want) + 1 && !memcmp(got, want, (size_t)n) && recv(fd, got, 1, MSG_DONTWAIT) < 0;
}

int main(void)
{
    int sv[2];

    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0)
    {
        perror("socketpair");
        return 1;
    }
    g_client = sv[1];

    /* positive control: a line of one part is numbered once */
    relay_set_prefix(seq_prefix);
    send_line("param_gesture 3 gain begin", sizeof("param_gesture 3 gain begin"));
    check(got_line(sv[0], "1 param_gesture 3 gain begin"), "positive control: one line, one number");

    /* an ended gesture is one line: numbered once, before its words, and the next line takes the next number */
    gesture_end("param_gesture 3 gain");
    check(got_line(sv[0], "2 param_gesture 3 gain end"), "an ended gesture is one line with one sequence number");
    send_line("xruns 0", sizeof("xruns 0"));
    check(got_line(sv[0], "3 xruns 0"), "the line after an ended gesture takes the next number: none was spent twice");

    /* without the extension, the same line, unnumbered */
    relay_set_prefix(NULL);
    gesture_end("param_gesture 4 drive");
    check(got_line(sv[0], "param_gesture 4 drive end"), "without seq, an ended gesture is the same line unnumbered");

    close(sv[0]);
    close(sv[1]);
    printf("relay seq: %d checks, %s\n", checks, failures ? "FAILED" : "ok");
    return failures ? 1 : 0;
}
