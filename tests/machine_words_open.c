/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/* machine_words_open [dirs]: opens the machine domain through machine_words_open() with dirs (NULL when none is given: the
 * library entry, which ignores the environment) and prints "core=<words> clock=<words> family=<word>:<id>,... counts=<core>,
 * <clock>,<families>" (the ids are the enum machine_family values) and exit 0, or "refused: <why>" and exit 1
 * (tests/machine_domain.py, arms 5, 6 and 9). */
#include "machine.h"

#include <stdio.h>

int main(int argc, char **argv)
{
    machine_words w;
    char why[512];
    int i;

    if (machine_words_open(argc > 1 ? argv[1] : NULL, &w, why, sizeof(why)) != 0)
    {
        printf("refused: %s\n", why);
        return 1;
    }
    printf("core=");
    for (i = 0; i < MACHINE_CORE_BAND_COUNT; i++)
        printf("%s%s", i ? "," : "", w.core[i]);
    printf(" clock=");
    for (i = 0; i < MACHINE_CLOCK_BAND_COUNT; i++)
        printf("%s%s", i ? "," : "", w.clock[i]);
    printf(" family=%s:%d,%s:%d,%s:%d,%s:%d", w.family[MACHINE_FAMILY_INTEL], MACHINE_FAMILY_INTEL, w.family[MACHINE_FAMILY_AMD],
           MACHINE_FAMILY_AMD, w.family[MACHINE_FAMILY_ARM], MACHINE_FAMILY_ARM, w.family[MACHINE_FAMILY_UNKNOWN],
           MACHINE_FAMILY_UNKNOWN);
    printf(" counts=%d,%d,%d\n", MACHINE_CORE_BAND_COUNT, MACHINE_CLOCK_BAND_COUNT, MACHINE_FAMILY_COUNT);
    machine_words_close(&w);
    return 0;
}
