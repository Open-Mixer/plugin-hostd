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

#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#include <host-errors.h>
#include <plugin-hostd/protocol.h>

#include "confine.h"
#include "descriptions.h"
#include "descriptions_open.h"
#include "descriptors.h"
#include "formats.h"
#include "proc.h"
#include "relay.h"
#include "supervisor.h"

/* the programs of the ask (omx-panel docs/descriptions-store.md, section 7): plugin-qualify's single-plugin call, then
 * omx-panel's, then the three generators of an LV2 plugin's toolkit files */
#define ASK_QUALIFY     "plugin-qualify-sync"
#define ASK_PANEL       "omx-panel"
static const char *const ASK_GENERATORS[] = { "omx-complement-sync", "omx-modgui-sync", "omx-lv2ui-sync" };
#define ASK_GENERATORS_N (sizeof(ASK_GENERATORS) / sizeof(ASK_GENERATORS[0]))
#define ASK_STEPS_MAX   (2 + ASK_GENERATORS_N)
#define ASK_ARGS_MAX    12

/* the lowest priority a child is given: nice 19, SCHED_IDLE, and the idle I/O class (linux/ioprio.h) */
#define ASK_NICE                19
#define IOPRIO_WHO_PROCESS      1
#define IOPRIO_CLASS_IDLE       3
#define IOPRIO_CLASS_SHIFT      13

/* the store entry of a plugin as an add named it: what its pages are cut from */
typedef struct KNOWN_T {
    char *uri;
    desc_groups_t *groups;      /* NULL: no grouped verdict, the declared groups */
} known_t;

enum { ASK_WAITING, ASK_RUNNING, ASK_ENDED };

/* the ask of one key: it waits for the add's scan, runs its programs one after the other, and ends once */
typedef struct ASK_T {
    descriptors_key_t key;
    char *uri;                  /* the add's uri: what description_changed names */
    int state;
    char *argv[ASK_STEPS_MAX][ASK_ARGS_MAX];
    int steps, step;
    pid_t pid;
} ask_t;

static int (*g_opener)(omx_panel_store **out, omx_panel_store_error *err);
static known_t *g_known;
static int g_nknown;
static ask_t **g_asks;
static int g_nasks;
static int g_said_absent;

void descriptions_use_opener(int (*opener)(omx_panel_store **out, omx_panel_store_error *err))
{
    g_opener = opener;
}

/* ---------------------------------------------------------------- the store */

static void groups_free(desc_groups_t *g)
{
    size_t n, m;

    if (!g)
        return;
    for (n = 0; n < g->n; n++)
    {
        free(g->group[n].symbol);
        free(g->group[n].name);
        for (m = 0; m < g->group[n].nports; m++)
            free(g->group[n].ports[m]);
        free(g->group[n].ports);
    }
    free(g->group);
    free(g);
}

/* the groups of a grouped verdict, copied; NULL for any other verdict, none, or no memory (the declared groups then) */
static desc_groups_t *groups_copy(const omx_panel_store_entry *e)
{
    desc_groups_t *g;
    size_t n, m;
    int ok = 1;

    if (!e->group_outcome || strcmp(e->group_outcome, "grouped") || e->ngroups == 0)
        return NULL;
    if (!(g = calloc(1, sizeof(*g))) || !(g->group = calloc(e->ngroups, sizeof(*g->group))))
    {
        free(g);
        return NULL;
    }
    g->n = e->ngroups;
    for (n = 0; ok && n < e->ngroups; n++)
    {
        const omx_panel_store_group *in = &e->groups[n];
        desc_group_t *out = &g->group[n];

        ok = (out->symbol = strdup(in->symbol)) && (out->name = strdup(in->name ? in->name : in->symbol)) &&
             (in->nports == 0 || (out->ports = calloc(in->nports, sizeof(*out->ports))));
        for (m = 0; ok && m < in->nports; m++)
            ok = (out->ports[out->nports++] = strdup(in->ports[m])) != NULL;
    }
    if (!ok)
    {
        groups_free(g);
        return NULL;
    }
    return g;
}

/* The entry of the key, with the plugin's source as installed (3.6: a stale entry is absent): 0 with its layer and its
 * groups (NULL for none), 1 when no layer holds it or no source can be made (a CLAP plugin whose descriptor is not in
 * place), -1 when there is no store to read (no base installed, a layer refused). The store is opened for the read
 * and closed after it: an add is rare, and a layer a writer replaced meanwhile is read as it is now. */
static int store_read(const descriptors_key_t *k, char *layer, size_t lsize, desc_groups_t **groups)
{
    omx_panel_store *s = NULL;
    omx_panel_store_error err = { NULL, "" };
    omx_panel_store_key key = { k->sha256, k->format, k->id };
    omx_panel_store_entry e;
    char source[65];
    int rc;

    if (groups)
        *groups = NULL;
    rc = g_opener ? g_opener(&s, &err) : omx_panel_store_open(geteuid() == 0 ? OMX_PANEL_STORE_SCOPE_SYSTEM : OMX_PANEL_STORE_SCOPE_USER, &s, &err);
    if (rc != OMX_PANEL_STORE_OK)
        return -1;
    /* no source, no entry: a CLAP plugin whose scan has not written its descriptor yet is held by no entry it can be
     * read by, and is unknown until it is */
    if (!*k->source || omx_panel_store_source(k->format, k->source, source) != 0)
    {
        omx_panel_store_close(s);
        return 1;
    }
    memset(&e, 0, sizeof(e));
    rc = omx_panel_store_get(s, &key, source, &e);
    if (rc == OMX_PANEL_STORE_OK)
    {
        snprintf(layer, lsize, "%s", e.layer);
        if (groups)
            *groups = groups_copy(&e);
    }
    omx_panel_store_close(s);
    return rc == OMX_PANEL_STORE_OK ? 0 : rc == OMX_PANEL_STORE_NO_ENTRY ? 1 : -1;
}

/* the uri as the instance keeps it (the worker's form: an LV2 URI without its lv2: prefix), whichever form the add used */
static const char *worker_form(const char *uri)
{
    const char *fwd = uri;

    format_of_uri(uri, &fwd);
    return fwd;
}

/* what the store holds for the plugin as uri names it, kept for its pages */
static void known_set(const char *add_uri, desc_groups_t *groups)
{
    const char *uri = worker_form(add_uri);
    known_t *grown;
    char *copy;
    int n;

    for (n = 0; n < g_nknown; n++)
        if (!strcmp(g_known[n].uri, uri))
        {
            groups_free(g_known[n].groups);
            g_known[n].groups = groups;
            return;
        }
    if (!groups)
        return;
    if (!(copy = strdup(uri)) || !(grown = realloc(g_known, (size_t)(g_nknown + 1) * sizeof(*g_known))))
    {
        free(copy);
        groups_free(groups);
        return;
    }
    g_known = grown;
    g_known[g_nknown].uri = copy;
    g_known[g_nknown++].groups = groups;
}

const desc_groups_t *descriptions_groups(const char *instance_uri)
{
    const char *uri = worker_form(instance_uri);
    int n;

    for (n = 0; n < g_nknown; n++)
        if (!strcmp(g_known[n].uri, uri))
            return g_known[n].groups;
    return NULL;
}

/* ---------------------------------------------------------------- the ask */

static ask_t *ask_of(const descriptors_key_t *k)
{
    int n;

    for (n = 0; n < g_nasks; n++)
        if (!strcmp(g_asks[n]->key.sha256, k->sha256) && !strcmp(g_asks[n]->key.format, k->format) &&
            !strcmp(g_asks[n]->key.id, k->id))
            return g_asks[n];
    return NULL;
}

/* one program of the ask, its words copied; the program is left out when it is not installed */
static void step_add(ask_t *a, const char *const *words)
{
    int n;

    if (!proc_have_binary(words[0]))
        return;
    for (n = 0; words[n] && n < ASK_ARGS_MAX - 1; n++)
        a->argv[a->steps][n] = strdup(words[n]);
    a->steps++;
}

/* The programs, for this plugin only, once its scan has ended (its descriptor is the one describe is given): the
 * qualification, the description, and the generators of an LV2 plugin's bundle; a program not installed is skipped. */
static void ask_plan(ask_t *a)
{
    const char *bundle = strrchr(a->key.bundle, '/');
    size_t g;

    {
        const char *w[] = { ASK_QUALIFY, "--plugin", a->key.target, "--under-load", geteuid() == 0 ? "--system" : NULL, NULL };
        step_add(a, w);
    }
    {
        /* the descriptor the scan wrote, when it wrote one: describe finds one itself otherwise */
        const char *w[] = { ASK_PANEL, "describe", "--plugin", a->key.target, "--descriptor", a->key.descriptor,
                            "--sha256", a->key.sha256, "--store", NULL };
        const char *bare[] = { ASK_PANEL, "describe", "--plugin", a->key.target, "--sha256", a->key.sha256, "--store", NULL };

        step_add(a, *a->key.descriptor ? w : bare);
    }
    for (g = 0; bundle && bundle[1] && g < ASK_GENERATORS_N; g++)
    {
        const char *w[] = { ASK_GENERATORS[g], "--only", bundle + 1, NULL };
        step_add(a, w);
    }
}

/* the child of a step: the lowest priority, then confined, then the program */
static pid_t step_start(ask_t *a)
{
    char log[PATH_MAX];
    int out, null;
    pid_t pid;

    snprintf(log, sizeof(log), "%s/ask-%s-%s.log", sup_root(), a->key.format, a->key.sha256);
    out = open(log, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    null = open("/dev/null", O_RDWR | O_CLOEXEC);
    pid = fork();
    if (pid == 0)
    {
        struct sched_param idle = { 0 };

        prctl(PR_SET_PDEATHSIG, SIGTERM);
        if (getppid() == 1)
            _exit(127);
        dup2(null, STDIN_FILENO);
        dup2(out >= 0 ? out : null, STDOUT_FILENO);
        dup2(out >= 0 ? out : null, STDERR_FILENO);
        signal(SIGPIPE, SIG_DFL);
        if (setpriority(PRIO_PROCESS, 0, ASK_NICE) != 0 || sched_setscheduler(0, SCHED_IDLE, &idle) != 0 ||
            syscall(SYS_ioprio_set, IOPRIO_WHO_PROCESS, 0, IOPRIO_CLASS_IDLE << IOPRIO_CLASS_SHIFT) != 0)
            _exit(126);
        if (proc_confine(NULL, 0) != 0)
            _exit(127);
        execvp(a->argv[a->step][0], a->argv[a->step]);
        _exit(127);
    }
    if (out >= 0)
        close(out);
    if (null >= 0)
        close(null);
    return pid;
}

/* the ask ended, whatever its programs did: the key is not asked again while the daemon runs. Its entry is read
 * again, the plugin's next pages are cut from it, and the clients are told when there is one */
static void ask_end(ask_t *a, const char *why)
{
    descriptors_key_t k;
    desc_groups_t *groups = NULL;
    char layer[16];

    a->state = ASK_ENDED;
    a->pid = 0;
    if (why)
        fprintf(stderr, "plugin-hostd: %s: the ask ended: %s\n", a->uri, why);
    if (descriptors_key(a->uri, &k) == 0 && store_read(&k, layer, sizeof(layer), &groups) == 0)
    {
        known_set(a->uri, groups);
        {
            char line[PATH_MAX + 64];

            snprintf(line, sizeof(line), PHD_EVENT_DESCRIPTION_CHANGED_FMT, a->uri);
            relay_event(line);
        }
    }
}

static void ask_next(ask_t *a)
{
    for (; a->step < a->steps; a->step++)
    {
        if ((a->pid = step_start(a)) > 0)
            return;
        fprintf(stderr, "plugin-hostd: %s: %s could not be started\n", a->uri, a->argv[a->step][0]);
    }
    ask_end(a, NULL);
}

void descriptions_add(const char *uri, int ask)
{
    descriptors_key_t k;
    desc_groups_t *groups = NULL;
    ask_t *a, **grown;
    char layer[16];
    int known;

    if (descriptors_key(uri, &k) != 0)
        return;
    known = store_read(&k, layer, sizeof(layer), &groups);
    known_set(uri, groups);
    /* a known key asks nothing; with no store to read (no base installed) the daemon pages by the declared groups and
     * asks nothing either: no store, no entry an ask could be answered by */
    if (known != 1 || ask == DESC_ASK_NO || ask_of(&k))
        return;
    /* ask_unknown auto: asked when plugin-qualify-sync is installed, and quietly not when it is absent; an add's ask
     * word forces it, and is said once when there is nothing to run */
    if (!proc_have_binary(ASK_QUALIFY))
    {
        if (ask == DESC_ASK_YES && !g_said_absent)
        {
            g_said_absent = 1;
            fprintf(stderr, "plugin-hostd: %s: the ask runs no child: " ASK_QUALIFY " is not installed\n", uri);
        }
        return;
    }
    if (!(a = calloc(1, sizeof(*a))) || !(a->uri = strdup(uri)) ||
        !(grown = realloc(g_asks, (size_t)(g_nasks + 1) * sizeof(*g_asks))))
    {
        if (a)
            free(a->uri);
        free(a);
        return;
    }
    g_asks = grown;
    a->key = k;
    a->state = ASK_WAITING;
    g_asks[g_nasks++] = a;
}

void descriptions_tick(void)
{
    int n, status;

    for (n = 0; n < g_nasks; n++)
    {
        ask_t *a = g_asks[n];

        if (a->state == ASK_WAITING && !descriptors_busy(a->uri))
        {
            /* the scan ended: the key again, with the descriptor it wrote */
            if (descriptors_key(a->uri, &a->key) != 0)
            {
                ask_end(a, "the plugin's files are gone");
                continue;
            }
            /* a CLAP plugin is read by the descriptor its scan wrote: one a layer holds asks nothing */
            {
                char layer[16];

                if (store_read(&a->key, layer, sizeof(layer), NULL) == 0)
                {
                    ask_end(a, NULL);
                    continue;
                }
            }
            a->state = ASK_RUNNING;
            ask_plan(a);
            ask_next(a);
        }
        else if (a->state == ASK_RUNNING && a->pid > 0 && waitpid(a->pid, &status, WNOHANG) == a->pid)
        {
            a->pid = 0;
            if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
            {
                char why[PATH_MAX];

                snprintf(why, sizeof(why), "%s %s %d", a->argv[a->step][0], WIFSIGNALED(status) ? "was killed by signal" : "exited",
                         WIFSIGNALED(status) ? WTERMSIG(status) : WEXITSTATUS(status));
                ask_end(a, why);
                continue;
            }
            a->step++;
            ask_next(a);
        }
    }
}

/* ---------------------------------------------------------------- description_get */

char *descriptions_get(const char *uri)
{
    descriptors_key_t k;
    ask_t *a;
    char layer[16], *reply = NULL;

    if (descriptors_key(uri, &k) != 0)
        return sup_resp(OMX_REPLY_PLUGIN_HOSTD_DESCRIPTOR_ABSENT_RESP);
    if (store_read(&k, layer, sizeof(layer), NULL) == 0)
    {
        if (asprintf(&reply, "resp 0 %s %s %s %s", k.sha256, k.format, k.id, layer) < 0)
            return sup_resp(ERR_MEMORY_ALLOCATION);
        return reply;
    }
    a = ask_of(&k);
    return sup_resp(a && a->state != ASK_ENDED ? OMX_REPLY_PLUGIN_HOSTD_DESCRIPTOR_PENDING_RESP : OMX_REPLY_PLUGIN_HOSTD_DESCRIPTOR_ABSENT_RESP);
}

void descriptions_finish(void)
{
    int n;
    size_t s, w;

    for (n = 0; n < g_nasks; n++)
    {
        if (g_asks[n]->pid > 0)
        {
            kill(g_asks[n]->pid, SIGTERM);
            waitpid(g_asks[n]->pid, NULL, 0);
        }
        for (s = 0; s < ASK_STEPS_MAX; s++)
            for (w = 0; w < ASK_ARGS_MAX; w++)
                free(g_asks[n]->argv[s][w]);
        free(g_asks[n]->uri);
        free(g_asks[n]);
    }
    free(g_asks);
    g_asks = NULL;
    g_nasks = 0;
    for (n = 0; n < g_nknown; n++)
    {
        free(g_known[n].uri);
        groups_free(g_known[n].groups);
    }
    free(g_known);
    g_known = NULL;
    g_nknown = 0;
}
