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

#ifndef PLUGIN_HOSTD_DOMAIN_WORDS_H
#define PLUGIN_HOSTD_DOMAIN_WORDS_H
/** @file domain_words.h
 * @brief The one read of a contract domain through omx-contract's C loader (libomx-domain), for the words this package
 * writes that a domain declares.
 *
 * A reader opens its domain once at start-up, never in a real-time path, and refuses to start by name when the domain is
 * absent or invalid; it asks the domain for no version. No function here reads the environment: a command-line tool passes
 * OMX_CONTRACT_PATH as @c dirs (its test entry), a library entry passes NULL.
 */
#include <omxcontract/omx_domain.h>
#include <stddef.h>

/**
 * Open a domain.
 *
 * @param domain the domain's name
 * @param dirs   NULL for the installed contract directory; else a ':' list of directories, the first that holds the domain
 *               wins (a directory that holds it but is invalid is refused, not skipped); no version is asked of the domain
 * @param out    receives the handle, which owns every string the lookups return until omx_domain_close()
 * @param why    receives the refusal, "<code>: <message>", when the open fails
 * @param n      the size of why
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal
 */
int domain_words_open(const char *domain, const char *dirs, omx_domain **out, char *why, size_t n);

/**
 * Every word of an item, in the domain's order (its x-code order, which is the index), in a newly allocated array of
 * pointers into the handle.
 *
 * @param d     the open handle
 * @param item  the item's name, e.g. MACHINE_CORE_BANDS
 * @param out   receives the array (free() it), NULL when the item is not in the domain
 * @param count receives the number of words
 * @return 0, or the OMX_CONTRACT_CODE_* value of the refusal
 */
int domain_words_list(const omx_domain *d, const char *item, const char ***out, size_t *count);

#endif
