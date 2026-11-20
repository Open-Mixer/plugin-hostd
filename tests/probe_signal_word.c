/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/* probe_signal_word [dirs]: opens the probe domain through probe_words_open() with dirs (NULL when none is given) and prints
 * "<signal>=<word> ..." for the thirteen signals the probe names, "other=<word>" for one it does not (SIGUSR1) and
 * "slots=<n>", the words one handle holds for the signals, and exit 0; or "refused: <why>" and exit 1 (tests/probe_domain.py,
 * arm 7). */
#include "probe_words.h"

#include <signal.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    static const struct
    {
        const char *name;
        int sig;
    } named[] = { { "SIGSEGV", SIGSEGV }, { "SIGABRT", SIGABRT }, { "SIGBUS", SIGBUS },   { "SIGFPE", SIGFPE },   { "SIGILL", SIGILL },
                  { "SIGKILL", SIGKILL }, { "SIGTERM", SIGTERM }, { "SIGXCPU", SIGXCPU }, { "SIGXFSZ", SIGXFSZ }, { "SIGSYS", SIGSYS },
                  { "SIGPIPE", SIGPIPE }, { "SIGINT", SIGINT },   { "SIGHUP", SIGHUP } };
    probe_words w;
    char why[512];
    size_t i;

    if (probe_words_open(argc > 1 ? argv[1] : NULL, &w, why, sizeof(why)) != 0)
    {
        printf("refused: %s\n", why);
        return 1;
    }
    for (i = 0; i < sizeof(named) / sizeof(*named); i++)
        printf("%s=%s ", named[i].name, probe_signal_word(&w, named[i].sig));
    printf("other=%s slots=%zu\n", probe_signal_word(&w, SIGUSR1), sizeof(w.signal) / sizeof(*w.signal));
    probe_words_close(&w);
    return 0;
}
