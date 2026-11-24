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

#ifndef SCAN_WORDS_H
#define SCAN_WORDS_H

/** @file scan_words.h
 * @brief The scopes of a field dump, which omx-clap-core's scan domain (contract.d/scan/scan.json there, shipped by
 * omx-clap-contract) holds as the words of SCAN_FIELD_SCOPES: the first field of a dump line, `param:3`, `plugin`.
 *
 * The parser of src/describe.c knows what each scope is (which entry it makes, in which format it is read, whether it
 * carries an index) under a title the domain gives its word; the word is the domain's, read once at start-up, so no
 * scope name is a literal of the parser.
 */

#include <omxcontract/omx_domain.h>
#include <stddef.h>

/** the domain the scopes are read from */
#define SCAN_DOMAIN "scan"

/** the scopes the parser knows, by the title the domain gives their word */
enum scan_scope
{
    SCAN_SCOPE_PLUGIN,
    SCAN_SCOPE_PARAM,
    SCAN_SCOPE_AUDIO_IN,
    SCAN_SCOPE_AUDIO_OUT,
    SCAN_SCOPE_NOTE_IN,
    SCAN_SCOPE_NOTE_OUT,
    SCAN_SCOPE_PORT,
    SCAN_SCOPE_PANEL,
    SCAN_SCOPE_SECTION,
    SCAN_SCOPE_CONTROL,
    SCAN_SCOPE_ROLE,
    SCAN_SCOPE_DISPLAY,
    SCAN_SCOPE_PLACEMENT_DEFAULT,
    SCAN_SCOPE_METER,
    SCAN_SCOPE_COUNT
};

/** The scope words, read once at start-up from the scan domain; they point into the open handle, which lives until
 * scan_words_close(). */
typedef struct
{
    omx_domain *domain;                      /**< the open scan domain, which owns the words */
    const char *scope[SCAN_SCOPE_COUNT];     /**< the SCAN_FIELD_SCOPES words, by enum scan_scope */
} scan_words;

/**
 * Open the scan domain and take the scope words.
 *
 * @param dirs NULL for the installed contract directory; else a ':' list, the first directory that holds the domain wins
 *             (a command-line tool's OMX_CONTRACT_PATH, or a test build's tree)
 * @param w    receives the words
 * @param why  receives the refusal, naming the domain, the loader's code and the item, when the open fails
 * @param n    the size of why
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal; the caller ends its start-up with 78
 */
int scan_words_open(const char *dirs, scan_words *w, char *why, size_t n);

/**
 * Release the handle, and with it the words.
 *
 * @param w the words scan_words_open() filled; closing twice is harmless
 */
void scan_words_close(scan_words *w);

#endif
