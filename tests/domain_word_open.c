/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/* domain_word_open <dir> <domain> <floor> <item> <word>: opens the domain in the installed directory <dir>
 * (omx_domain_open_at) and finds the word; exit 0 and one line on success, 1 and the reason otherwise. A test's way to
 * read an installed tree the way the loader does (tests/probe_domain.py). */
#include <omxcontract/omx_domain.h>

#include <stdio.h>

int main(int argc, char **argv)
{
    omx_domain *d = NULL;
    omx_domain_error err;
    omx_domain_word_info w;

    if (argc != 6) {
        fprintf(stderr, "usage: domain_word_open <dir> <domain> <floor> <item> <word>\n");
        return 64;
    }
    if (omx_domain_open_at(argv[1], argv[2], argv[3], &d, &err) != 0) {
        fprintf(stderr, "open: %s: %s\n", err.code, err.message);
        return 1;
    }
    if (omx_domain_word(d, argv[4], argv[5], &w) != 0) {
        fprintf(stderr, "no word %s of %s\n", argv[5], argv[4]);
        omx_domain_close(d);
        return 1;
    }
    printf("word=%s code=%d\n", w.word, w.code);
    omx_domain_close(d);
    return 0;
}
