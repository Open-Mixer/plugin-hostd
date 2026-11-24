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


/* src/lv2.c's refusal and pick tables, and its param_info answer, when memory runs out. lv2.c is built for this test with
 * its realloc and asprintf calls renamed to alloc_test_realloc and alloc_test_asprintf (the Makefile's -D), so the test
 * decides which allocation fails. The stubs below stand for the daemon parts lv2.c calls: an instance is the bundle the
 * test writes, and a reply is mod-host's resp line. */

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <stdarg.h>
#include <unistd.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <host-errors.h>
#include <plugin-hostd/protocol.h>

#include "conf.h"
#include "formats.h"
#include "pins.h"
#include "proc.h"
#include "supervisor.h"

static int failures, checks;

/* how many reallocs succeed before the next one fails; -1 is never */
static int g_fail_after = -1;

/* whether the next asprintf of lv2.c fails */
static int g_asprintf_fails;

/* the bundle the test wrote, which every instance is */
static char g_bundle[64];

void *alloc_test_realloc(void *ptr, size_t size);
int alloc_test_asprintf(char **out, const char *fmt, ...);

int alloc_test_asprintf(char **out, const char *fmt, ...)
{
    va_list ap;
    int n;

    if (g_asprintf_fails)
        return -1;
    va_start(ap, fmt);
    n = vasprintf(out, fmt, ap);
    va_end(ap);
    return n;
}

void *alloc_test_realloc(void *ptr, size_t size)
{
    if (g_fail_after == 0)
        return NULL;
    if (g_fail_after > 0)
        g_fail_after--;
    return realloc(ptr, size);
}

int format_by_name(const char *name)
{
    (void)name;
    return 0;
}

int pin_refuse(const char *uri, const char *path, const char *why)
{
    (void)uri;
    (void)path;
    (void)why;
    return 0;
}

char *proc_find_lv2_bundle(const char *lv2_path, const char *uri, proc_lv2_version_fn version)
{
    (void)lv2_path;
    (void)uri;
    (void)version;
    return g_bundle[0] ? strdup(g_bundle) : NULL;
}

int proc_lv2_preset_bundles(const char *lv2_path, const char *uri, int (*fn)(void *ctx, const char *bundle), void *ctx)
{
    (void)lv2_path;
    (void)uri;
    (void)fn;
    (void)ctx;
    return 0;
}

const char *sup_instance_uri(int id)
{
    return id == 0 && g_bundle[0] ? "urn:test:param" : NULL;
}

const char *sup_instance_search(int id)
{
    return id == 0 && g_bundle[0] ? g_bundle : NULL;
}

char *sup_call(int id, const char *line)
{
    (void)id;
    (void)line;
    return NULL;
}

int sup_reply_code(const char *reply)
{
    (void)reply;
    return 0;
}

char *sup_resp(int code)
{
    char *reply = NULL;

    return asprintf(&reply, "resp %d", code) < 0 ? NULL : reply;
}

static void check(int ok, const char *what)
{
    checks++;
    if (!ok)
    {
        failures++;
        printf("FAIL lv2 tables: %s\n", what);
    }
}

static void write_file(const char *dir, const char *name, const char *text)
{
    char path[128];
    FILE *f;

    snprintf(path, sizeof(path), "%s/%s", dir, name);
    f = fopen(path, "w");
    if (f)
    {
        fputs(text, f);
        fclose(f);
    }
}

/* a bundle of one plugin with one control input, gain, ranged 0..1 */
static int bundle_write(void)
{
    snprintf(g_bundle, sizeof(g_bundle), "/tmp/lv2-alloc-test-XXXXXX");
    if (!mkdtemp(g_bundle))
    {
        g_bundle[0] = '\0';
        return -1;
    }
    write_file(g_bundle, "manifest.ttl",
               "@prefix lv2: <http://lv2plug.in/ns/lv2core#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
               "<urn:test:param> a lv2:Plugin ; lv2:binary <param.so> ; rdfs:seeAlso <param.ttl> .\n");
    write_file(g_bundle, "param.ttl",
               "@prefix lv2: <http://lv2plug.in/ns/lv2core#> .\n<urn:test:param> a lv2:Plugin ; lv2:port [ a lv2:InputPort , "
               "lv2:ControlPort ; lv2:index 0 ; lv2:symbol \"gain\" ; lv2:name \"Gain\" ;\n  lv2:minimum 0 ; lv2:maximum 1 ; "
               "lv2:default 0.5 ] .\n");
    return 0;
}

static void bundle_remove(void)
{
    char path[128];

    snprintf(path, sizeof(path), "%s/manifest.ttl", g_bundle);
    unlink(path);
    snprintf(path, sizeof(path), "%s/param.ttl", g_bundle);
    unlink(path);
    rmdir(g_bundle);
    g_bundle[0] = '\0';
}

/* param_info of a ranged control port with no memory for its answer: mod-host's ERR_MEMORY_ALLOCATION, not -511, which
 * would tell the controller the port has no contract */
static void param_info_without_memory(void)
{
    char *reply, want[32];

    if (bundle_write() != 0)
    {
        check(0, "a bundle in /tmp");
        return;
    }
    reply = lv2_param_info(0, "gain");
    check(reply && !strncmp(reply, "resp 0 ", 7), "positive control: a ranged port's param_info answers resp 0");
    free(reply);
    g_asprintf_fails = 1;
    reply = lv2_param_info(0, "gain");
    g_asprintf_fails = 0;
    snprintf(want, sizeof(want), "resp %d", ERR_MEMORY_ALLOCATION);
    check(reply && !strcmp(reply, want), "param_info with no memory for its answer answers ERR_MEMORY_ALLOCATION");
    free(reply);
    bundle_remove();
}

static const char *route(const char *uri, const char *worker)
{
    conf_t conf;

    memset(&conf, 0, sizeof(conf));
    snprintf(conf.lv2_worker, sizeof(conf.lv2_worker), "%s", worker);
    return lv2_route(&conf, uri);
}

int main(void)
{
    const char *u1 = "urn:test:one", *u2 = "urn:test:two";
    const char *clap = "omx-clap-host";

    check(lv2_worker_pick(u1, "auto") == -1, "auto is no worker: a pick of it is refused");
    /* the pick table: under mod-host a uri is on the lv2 row (no route) unless a pick sends it to the CLAP worker */
    check(lv2_worker_pick(u1, clap) == 0 && route(u1, "mod-host") != NULL, "positive control: a pick is kept with memory");
    g_fail_after = 0;
    check(lv2_worker_pick(u2, clap) == -1, "a pick with no memory is refused");
    g_fail_after = -1;
    check(route(u2, "mod-host") == NULL, "the refused pick left no entry: the uri still follows the lv2_worker setting");
    check(route(u1, "mod-host") != NULL, "the pick held before is still there");
    check(lv2_worker_pick(u2, clap) == 0 && route(u2, "mod-host") != NULL, "with memory again the pick is kept");
    check(lv2_worker_pick(u1, PHD_WORD_NONE) == 0 && route(u1, "mod-host") == NULL, "a pick is taken back");

    param_info_without_memory();

    printf("lv2 tables: %d checks, %s\n", checks, failures ? "FAILED" : "ok");
    return failures ? 1 : 0;
}
