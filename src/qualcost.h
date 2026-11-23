/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/* What a plugin costs, as plugin-qualify measured it: the figures of the qualification store, read through
 * libplugin-qualification-db (pqdb_open, pqdb_each), one grid point per rate and quantum. The daemon reads them and writes
 * none; a record gates no add. It reads the store and nothing else: no directory of record files, no fallback to one. */

/** @file qualcost.h
 * @brief The declarations of qualcost.h.
 */

#ifndef PLUGIN_HOSTD_QUALCOST_H
#define PLUGIN_HOSTD_QUALCOST_H

#include <stddef.h>

#include <plugin-qualification-db/pqdb.h>

/** The scope the daemon reads the store in: the system's when it runs as root (a system service), the user's otherwise.
 * @return the scope pqdb_open is given
 */
pqdb_scope qualcost_scope(void);

/** The store of that scope, opened for one verb's reads (closed with qualcost_close).
 * @return the open store, or NULL when it cannot be opened, which is no figure for any plugin; the refusal is said once on
 *         stderr, by its qualification-db.* name
 */
pqdb *qualcost_open(void);

/** Close a store qualcost_open returned.
 * @param db the store, or NULL for none
 */
void qualcost_close(pqdb *db);

/** A refusal of pqdb_open as "<code>: <message>", the code by name (err->code, else pqdb_code(status)), the message naming
 * the file.
 * @param status the status pqdb_open answered
 * @param err the error it filled, or NULL
 * @param out where the text goes
 * @param size the size of out
 */
void qualcost_refusal(int status, const pqdb_error *err, char *out, size_t size);

/** Where the store is opened from when it is not the installed one: set only by the test build of the daemon (src/main.c,
 * OMX_QUALIFICATION_TEST_STORE), never by a packaged one.
 * @param opener opens the store, 0 or the refusal pqdb_open_at answers; NULL puts the installed store back
 */
void qualcost_use_opener(int (*opener)(pqdb **db, pqdb_error *err));

/** The cost of the plugin with this id (the CLAP id, or the LV2 URI) at this rate and quantum, as a fraction of one core:
 * the 95th-percentile nanoseconds per sample of the grid point, times the rate, over 1e9. When several records hold the
 * point (a plugin tested in several versions) the largest wins, since the planner must not be optimistic.
 * @param db the open store, or NULL for none
 * @param id the CLAP id or the LV2 URI, in either spelling of an IRI
 * @param rate the rate in Hz
 * @param quantum the quantum in frames
 * @return the fraction of one core, or -1.0 when the store holds no point, there is no store, or the arguments are none
 */
double qualcost_read(pqdb *db, const char *id, int rate, int quantum);

/** What the records of a plugin hold at one rate and quantum, as the estimate verb reads them. */
typedef struct QUALCOST_CELL_T {
    double median_ns;       /**< the grid point's cost median, nanoseconds per sample */
    double latency_frames;  /**< its latency: the measured frames, else the declared ones */
} qualcost_cell_t;

/** What the records of a plugin say it holds at one rate and quantum, in KB, as plugin-qualify worked it out from the
 * measured footprint. */
typedef struct QUALCOST_MEMORY_T {
    double first_kb;         /**< one instance and what all its instances share */
    double per_instance_kb;  /**< one more instance beside it */
} qualcost_memory_t;

/** What qualcost_cell answers. */
enum {
    QUALCOST_CELL_FOUND,        /**< a record holds the point with both figures */
    QUALCOST_CELL_NO_RECORD,    /**< no record names the plugin (or there is no store) */
    QUALCOST_CELL_NO_POINT      /**< a record names it, none holds the point with both figures */
};

/** The cell of the plugin with this id at this rate and quantum. When several records hold the point the largest of each
 * figure stands, as qualcost_read takes the largest cost.
 * @param db the open store, or NULL for none
 * @param id the CLAP id or the LV2 URI
 * @param rate the rate in Hz
 * @param quantum the quantum in frames
 * @param out the cell, set for QUALCOST_CELL_FOUND only
 * @return QUALCOST_CELL_FOUND, QUALCOST_CELL_NO_RECORD or QUALCOST_CELL_NO_POINT
 */
int qualcost_cell(pqdb *db, const char *id, int rate, int quantum, qualcost_cell_t *out);

/** The memory of the plugin at this rate and quantum. When several records hold both figures the largest of each stands.
 * @param db the open store, or NULL for none
 * @param id the CLAP id or the LV2 URI
 * @param rate the rate in Hz
 * @param quantum the quantum in frames
 * @param out the memory, set for 0 only
 * @return 0, or -1 when no record holds both figures there, which is unknown and never 0
 */
int qualcost_memory(pqdb *db, const char *id, int rate, int quantum, qualcost_memory_t *out);

#endif
