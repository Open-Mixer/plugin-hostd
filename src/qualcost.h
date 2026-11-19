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

/* the scope the daemon reads the store in: the system's when it runs as root (a system service), the user's otherwise */
pqdb_scope qualcost_scope(void);

/* the store of that scope, opened for one verb's reads (close it with qualcost_close); NULL when it cannot be opened, which
 * is no figure for any plugin, and says so on stderr once per refusal, by its qualification-db.* name */
pqdb *qualcost_open(void);
void qualcost_close(pqdb *db);

/* a refusal of pqdb_open as "<code>: <message>", the code by name (err->code, else pqdb_code(status)), the message naming the
 * file; into out of size bytes */
void qualcost_refusal(int status, const pqdb_error *err, char *out, size_t size);

/* where the store is opened from, when it is not the installed one: set only by the test build of the daemon (src/main.c,
 * OMX_QUALIFICATION_TEST_STORE), never by a packaged one. NULL puts it back to pqdb_open. */
void qualcost_use_opener(int (*opener)(pqdb **db, pqdb_error *err));

/* The cost of the plugin with this id (the CLAP id, or the LV2 URI) at this rate and quantum, as a fraction of one core:
 * the 95th-percentile nanoseconds per sample of the grid point, times the rate, over 1e9. When several records hold
 * the point (a plugin tested in several versions) the largest wins, since the planner must not be optimistic. -1.0
 * when the store holds no point, there is no store (db NULL), or the arguments are none. */
double qualcost_read(pqdb *db, const char *id, int rate, int quantum);

/* What the records of a plugin hold at one rate and quantum, as the estimate verb reads them: the grid point's cost
 * median, in nanoseconds per sample, and its latency, the measured frames, else the declared ones. */
typedef struct QUALCOST_CELL_T {
    double median_ns;       /**< the cost median, nanoseconds per sample */
    double latency_frames;  /**< the latency, measured frames else declared */
} qualcost_cell_t;

/* What the records of a plugin say it holds at one rate and quantum, in KB, as plugin-qualify worked it out from the
 * measured footprint: first_kb, one instance and what all its instances share; per_instance_kb, one more instance
 * beside it. */
typedef struct QUALCOST_MEMORY_T {
    double first_kb;         /**< one instance and what all its instances share */
    double per_instance_kb;  /**< one more instance beside it */
} qualcost_memory_t;

enum {
    QUALCOST_CELL_FOUND,        /* a record holds the point with both figures */
    QUALCOST_CELL_NO_RECORD,    /* no record names the plugin (or there is no store) */
    QUALCOST_CELL_NO_POINT      /* a record names it, none holds the point with both figures */
};

/* The cell of the plugin with this id at this rate and quantum into *out, QUALCOST_CELL_*. When several records hold
 * the point the largest of each figure stands, as qualcost_read takes the largest cost. */
int qualcost_cell(pqdb *db, const char *id, int rate, int quantum, qualcost_cell_t *out);

/* The memory of the plugin at this rate and quantum into *out: 0, or -1 when no record holds both figures there, which is
 * unknown and never 0. When several records hold them the largest of each stands. */
int qualcost_memory(pqdb *db, const char *id, int rate, int quantum, qualcost_memory_t *out);

#endif
