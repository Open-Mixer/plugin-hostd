/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com> */
/* machine_domain_open <dir> <item> <word> <text key> <lang>: opens the domain `machine` in the installed
 * directory <dir> (omx_domain_open_at), finds the word and one catalog text; exit 0 and one line on success, 1 and the
 * reason otherwise. A test's way to read an installed tree the way the loader does (tests/machine_domain.py). */
#include <omxcontract/omx_domain.h>

#include <stdio.h>

int main(int argc, char **argv)
{
    if (argc != 6) {
        fprintf(stderr, "usage: machine_domain_open <dir> <item> <word> <text key> <lang>\n");
        return 64;
    }
    omx_domain *d = NULL;
    omx_domain_error err;
    if (omx_domain_open_at(argv[1], "machine", NULL, &d, &err) != 0) {
        fprintf(stderr, "open: %s: %s\n", err.code, err.message);
        return 1;
    }
    omx_domain_word_info w;
    if (omx_domain_word(d, argv[2], argv[3], &w) != 0) {
        fprintf(stderr, "no word %s of %s\n", argv[3], argv[2]);
        omx_domain_close(d);
        return 1;
    }
    const char *t = omx_domain_text(d, argv[4], argv[5]);
    if (t == NULL || *t == '\0') {
        fprintf(stderr, "no text %s in %s\n", argv[4], argv[5]);
        omx_domain_close(d);
        return 1;
    }
    printf("word=%s code=%d text=%s\n", w.word, w.code, t);
    omx_domain_close(d);
    return 0;
}
