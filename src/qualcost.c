/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <plugin-hostd/protocol.h>

#include "qualcost.h"

static int (*g_opener)(pqdb **db, pqdb_error *err);

pqdb_scope qualcost_scope(void)
{
    return geteuid() == 0 ? PQDB_SCOPE_SYSTEM : PQDB_SCOPE_USER;
}

void qualcost_refusal(int status, const pqdb_error *err, char *out, size_t size)
{
    const char *code = err && err->code ? err->code : pqdb_code(status);

    snprintf(out, size, "%s: %s", code ? code : "qualification-db.refused", err ? err->message : "");
}

void qualcost_use_opener(int (*opener)(pqdb **db, pqdb_error *err))
{
    g_opener = opener;
}

pqdb *qualcost_open(void)
{
    static char last[96];
    pqdb *db = NULL;
    pqdb_error err = { NULL, "" };
    int status = g_opener ? g_opener(&db, &err) : pqdb_open(qualcost_scope(), &db, &err);

    if (status == 0)
    {
        last[0] = '\0';
        return db;
    }
    /* a store that cannot be read is no figure for any plugin; the refusal is said once by its name, not at every read */
    if (!err.code || strcmp(err.code, last))
    {
        char why[512];

        qualcost_refusal(status, &err, why, sizeof(why));
        fprintf(stderr, "plugin-hostd: the qualification store is not read: %s\n", why);
        snprintf(last, sizeof(last), "%s", err.code ? err.code : "");
    }
    return NULL;
}

void qualcost_close(pqdb *db)
{
    if (db)
        pqdb_close(db);
}

/* the id with each %XX escape of an IRI replaced by its byte, by the protocol's phd_pin_path_decode: LV2 URIs reach the
 * daemon percent-encoded as often as not, and the store holds the URI as plugin-qualify wrote it, in either spelling.
 * An id the codec refuses (a stray %) is its own spelling. */
static void decode(const char *id, char *out, size_t size)
{
    if (phd_pin_path_decode(id, out, size) != 0)
        snprintf(out, size, "%s", id);
}

/* calls each for every result of the plugin at the rate and quantum (-1: any), in each spelling of its id */
static int each_result(pqdb *db, const char *id, int rate, int quantum, int (*each)(const pqdb_result *, void *), void *ctx)
{
    char plain[PATH_MAX];
    pqdb_query q = PQDB_QUERY_ANY; /* a zeroed query asks for rate 0 and quantum 0 and matches nothing */
    int status;

    if (!db || !id || !*id)
        return 0;
    q.rate = rate;
    q.quantum = quantum;
    q.uri = id;
    if ((status = pqdb_each(db, &q, each, ctx)) != 0)
        return status;
    decode(id, plain, sizeof(plain));
    if (strcmp(plain, id))
    {
        q.uri = plain;
        return pqdb_each(db, &q, each, ctx);
    }
    return 0;
}

struct cost_ctx {
    double best;
};

static int cost_of(const pqdb_result *r, void *ctx)
{
    struct cost_ctx *c = ctx;
    double fraction;

    if (!r->has_cost || r->cost_p_ns < 0)
        return 0;
    fraction = r->cost_p_ns * r->rate / 1e9;
    if (fraction > c->best)
        c->best = fraction;
    return 0;
}

double qualcost_read(pqdb *db, const char *id, int rate, int quantum)
{
    struct cost_ctx c = { -1.0 };

    if (rate <= 0 || quantum <= 0 || each_result(db, id, rate, quantum, cost_of, &c) != 0)
        return -1.0;
    return c.best;
}

struct cell_ctx {
    int found;
    qualcost_cell_t cell;
};

static int cell_of(const pqdb_result *r, void *ctx)
{
    struct cell_ctx *c = ctx;

    if (!r->has_cost || r->cost_median_ns < 0 || !r->has_latency || r->latency_frames < 0)
        return 0;
    if (!c->found || r->cost_median_ns > c->cell.median_ns)
        c->cell.median_ns = r->cost_median_ns;
    if (!c->found || r->latency_frames > c->cell.latency_frames)
        c->cell.latency_frames = (double)r->latency_frames;
    c->found = 1;
    return 0;
}

static int any_of(const pqdb_result *r, void *ctx)
{
    (void)r;
    *(int *)ctx = 1;
    return 1; /* one is enough: stop the walk */
}

int qualcost_cell(pqdb *db, const char *id, int rate, int quantum, qualcost_cell_t *out)
{
    struct cell_ctx c = { 0, { 0, 0 } };
    int named = 0;

    *out = c.cell;
    if (rate <= 0 || quantum <= 0)
        return QUALCOST_CELL_NO_RECORD;
    each_result(db, id, rate, quantum, cell_of, &c);
    if (c.found)
    {
        *out = c.cell;
        return QUALCOST_CELL_FOUND;
    }
    /* a record that holds the plugin at any grid point names it: no point here, not no record */
    each_result(db, id, -1, -1, any_of, &named);
    return named ? QUALCOST_CELL_NO_POINT : QUALCOST_CELL_NO_RECORD;
}

struct memory_ctx {
    int found;
    qualcost_memory_t memory;
};

static int memory_of(const pqdb_result *r, void *ctx)
{
    struct memory_ctx *c = ctx;

    if (!r->has_memory || r->mem_first_kb < 0 || r->mem_per_instance_kb < 0)
        return 0;
    if (!c->found || r->mem_first_kb > c->memory.first_kb)
        c->memory.first_kb = (double)r->mem_first_kb;
    if (!c->found || r->mem_per_instance_kb > c->memory.per_instance_kb)
        c->memory.per_instance_kb = (double)r->mem_per_instance_kb;
    c->found = 1;
    return 0;
}

int qualcost_memory(pqdb *db, const char *id, int rate, int quantum, qualcost_memory_t *out)
{
    struct memory_ctx c = { 0, { 0, 0 } };

    if (rate > 0 && quantum > 0)
        each_result(db, id, rate, quantum, memory_of, &c);
    *out = c.memory;
    return c.found ? 0 : -1;
}
