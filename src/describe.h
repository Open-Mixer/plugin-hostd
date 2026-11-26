/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/* plugin-hostd-probe describe: a plugin's field dump (omx-clap-scan --fields) through its format's table and the
 * transforms it names, written as a scanned descriptor (docs/formats.md). */

/** @file describe.h
 * @brief The declarations of describe.h.
 */

#ifndef PLUGIN_HOSTD_DESCRIBE_H
#define PLUGIN_HOSTD_DESCRIBE_H

#include <stddef.h>

#include "json.h"
#include "scan_words.h"

/**
 * @brief Set the scopes of a field dump: the scan domain's words, as scan_words_open read them.
 *
 * The parser reads them where it reads a dump, so they are set before describe_dump or describe_pages is called, and
 * kept (not copied) until the next call. Without them a dump is refused by name.
 *
 * @param words the scan domain's words (SCAN_FIELD_SCOPES), alive until the next call
 */
void describe_scopes(const scan_words *words);

/**
 * @brief Set where the format owners' domains are read from: the mappings a unit-id or designation-meaning row reads
 * (docs/formats.md, Lookup values the owners publish).
 *
 * A ':' list of contract directories, the first that holds a domain wins (one that holds it but cannot be read is
 * refused, not skipped). Kept (not copied) until the next call; NULL reads none, and a row that needs a mapping is then
 * refused by name.
 *
 * @param dirs the ':' list, alive until the next call
 */
void describe_owners(const char *dirs);

/** @brief the format of a target, clap:\<path\>#\<id\> or lv2:\<uri\>
 *
 * @param target the target, NUL-terminated.
 * @return "clap", "lv2", or NULL.
 */
const char *describe_format(const char *target);

/** @brief the plugin id a target names: the CLAP id after its last '#', or the LV2 URI
 *
 * @param target the target, NUL-terminated.
 * @return a pointer into target, or NULL.
 */
const char *describe_id(const char *target);

/** @brief the scanned descriptor of a field dump
 *
 * @param table_text the format table's text.
 * @param dump_text the dump's text.
 * @param target the target asked for, clap:\<path\>#\<id\> or lv2:\<uri\>.
 * @param roles_dir the contract directory's major, \<contract dir\>/\<major\>, whose role tables a role-to-meaning row
 *        reads; NULL for none.
 * @param[out] out the descriptor.
 * @param[out] why the reason of a refusal, NUL-terminated.
 * @param why_size the size of why, in bytes.
 * @return 0 with the descriptor in out; -1 refused (a table it cannot read, a dump it refuses, a role table it
 *         refuses) with why.
 */
int describe_dump(const char *table_text, const char *dump_text, const char *target, const char *roles_dir, sb_t *out,
                  char *why, size_t why_size);

/** @brief the panel document of a CLAP target (docs/panel.md)
 *
 * The panel object omx-clap-scan --json prints for the target's id, its bytes as the scan wrote them, null when the
 * plugin serves none. An LV2 target's panel is null, scan_json unread.
 *
 * @param scan_json what omx-clap-scan --json printed.
 * @param target the target, clap:\<path\>#\<id\> or lv2:\<uri\>.
 * @param[out] out the document.
 * @param[out] why the reason of a refusal, NUL-terminated.
 * @param why_size the size of why, in bytes.
 * @return 0 with the document in out; -1 refused (no JSON, no such plugin, a plugin the scan states no panel for)
 *         with why.
 */
int describe_panel(const char *scan_json, const char *target, sb_t *out, char *why, size_t why_size);

/** @brief the pages of a target's descriptor (docs/formats.md\#the-pages-describe-pages-writes)
 *
 * Every control on exactly one page of its group's run, in declared order, cut at PAGE_SLOTS (src/pages.h).
 *
 * @param table_text the format table's text, as describe_dump reads it.
 * @param dump_text the dump's text.
 * @param target the target asked for.
 * @param roles_dir the contract directory's major, as describe_dump reads it; NULL for none.
 * @param[out] out the pages.
 * @param[out] why the reason of a refusal, NUL-terminated.
 * @param why_size the size of why, in bytes.
 * @return 0 with the pages in out; -1 refused as describe_dump refuses, with why.
 */
int describe_pages(const char *table_text, const char *dump_text, const char *target, const char *roles_dir,
                   sb_t *out, char *why, size_t why_size);

#endif
