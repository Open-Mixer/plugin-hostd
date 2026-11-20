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
#ifndef PLUGIN_HOSTD_QUALIFICATION_WORDS_H
#define PLUGIN_HOSTD_QUALIFICATION_WORDS_H
/** @file
 * @brief The qualification words the probe and the schema generator write, read from the qualification domain, which plugin-hostd owns.
 *
 * The qualification domain (contract.d/qualification/qualification.json, items QUALIFICATION_*) is plugin-qualify's:
 * this package ships no copy and no render of it. It is read once at start-up through the C loader of omx-contract
 * (libomx-domain, through domain_words_open), never in a real-time path, and refused loudly by name when it is absent, invalid or below QW_FLOOR.
 */
#include "domain_words.h"
#include <omxcontract/omx_domain.h>
#include <stddef.h>

/** the domain's name */
#define QW_DOMAIN "qualification"
/** the lowest info.version of the domain this package reads */
#define QW_FLOOR "1.1.0"

/**
 * Open the qualification domain: domain_words_open with this domain's name and floor.
 *
 * @param dirs  NULL for the installed contract directory; else a ':' list of directories, the first that holds the domain
 *              wins (the test entry: a directory that holds it but is invalid or too old is refused, not skipped)
 * @param out   receives the handle, which owns every string the lookups return until omx_domain_close()
 * @param why   receives the refusal, "<code>: <message>", when the open fails
 * @param n     the size of why
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal
 */
int qw_open(const char *dirs, omx_domain **out, char *why, size_t n);

/**
 * The word of an item whose key (its `title`) is key: the word as the domain writes it today.
 *
 * @param d    the open handle
 * @param item the item's name, e.g. QUALIFICATION_RESOURCE_THREAD_SCHEDULING
 * @param key  the word's key
 * @return the word, owned by the handle; NULL when the item or the key is not in the domain
 */
const char *qw_word(const omx_domain *d, const char *item, const char *key);

#endif
