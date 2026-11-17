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

/** @file supervisor.h
 * @brief The daemon's supervisor: the instance ledger, the workers that hold the instances, respawn and replay.
 *
 * Every instance the controller adds lives in a worker process. The supervisor keeps, for each instance, the lines
 * that rebuild it (the ledger); when a worker dies it respawns the worker with backoff and replays the ledger into it.
 * Verbs reach the workers through the sup_* functions below. Unless a function says otherwise, a char * result is a
 * reply line ("resp \<code> ..."), allocated with malloc, and the caller frees it.
 */

#ifndef SUPERVISOR_H
#define SUPERVISOR_H

#include <stdint.h>

#include "conf.h"
#include "formats.h"
#include "proc.h"
#include <plugin-hostd/protocol.h>

/** @brief The number of instance ids: an id is valid from 0 up to, not including, this. */
#define MAX_INSTANCE 10000

/** @brief The states of a worker, one enumerator W_\<id> for each PHD_WORKER_STATES row, then W_COUNT. */
enum {
/**
 * @brief Declares the enumerator W_\<id> of one worker state.
 * @param id the state's identifier
 * @param name the word worker_list prints for it (unused here)
 * @param meaning its meaning (unused here)
 */
#define X(id, name, meaning) W_##id,
    PHD_WORKER_STATES(X)
#undef X
    W_COUNT
};

/* what a recorded verb is, for the checkpoint: STATE is what the plugin's own state holds and a checkpoint
 * replaces; HOST is what only the host knows and the ledger always keeps */
enum { KIND_STATE, KIND_HOST };

/** @brief One line of an instance's ledger: a verb kept to be replayed into a new worker. */
typedef struct ENTRY_T {
    char *line;                 /**< the verb line as the worker was sent it, malloc'd */
    char *key;                  /**< the entry's key, "<verb> <argument>": a later line with the same key replaces this one; NULL for an entry that is never replaced */
    int kind;                   /**< KIND_STATE or KIND_HOST */
} entry_t;

struct WORKER_T;
struct CHAIN_T;

/** @brief One plugin instance the controller added: what it is, where it runs and what rebuilds it. */
typedef struct INSTANCE_T {
    int id;                     /**< the instance number the controller gave it, 0 to MAX_INSTANCE - 1 */
    int fmt;                    /**< the row of formats.h that hosts it (format_at) */
    char *uri;                  /**< as it goes to a worker, no lv2: prefix */
    char *add_line;             /**< the line as it goes to a worker */
    char *client;               /**< the jack client the worker makes */
    struct WORKER_T *w;         /**< the worker that holds it */
    entry_t *tail;              /**< the ledger: the verbs it took since its add, in order, replayed after the add */
    int ntail,                  /**< the entries in tail */
        captail;                /**< the room allocated for tail, in entries */
    char **conns;               /**< the jack connections made to its ports, each as the connect line, malloc'd */
    int nconns,                 /**< the lines in conns */
        capconns;               /**< the room allocated for conns, in lines */
    int dirty;                  /**< 1 when it took a verb that changes its state since the last checkpoint */
    int64_t changed_ms;         /**< when it last became dirty, on the clock of proc_now_ms */
    char *sus_line;             /**< the last verb it answered and the ledger kept, the suspect of a death that follows soon */
    char *sus_prev;             /**< the ledger line that verb replaced, put back when it is dropped */
    int64_t sus_ms;             /**< when sus_line was kept, on the clock of proc_now_ms */
    int64_t sus_seq;            /**< the order of the verbs across instances, which the millisecond clock cannot give */
    int has_ckpt;               /**< 1 when a checkpoint of its state is on disk */
    int unreplayed;             /**< its pin refused the add of the last replay: the worker does not hold it */
    int pin_refused;            /**< the pins read again refuse its files; it keeps running, worker_list marks it */
    char *node_label;           /**< the latest node_label with a label it took, replayed after its add (#35) */
    char *track_info;           /**< the latest track_info it took, replayed after its add, never to an LV2 worker */
    struct CHAIN_T *chain;      /**< the chain it is a member of, NULL for none */
} instance_t;

/** @brief One worker process, or the place one is to run again: its sockets, its instances and its death record. */
typedef struct WORKER_T {
    int k;                      /**< its number, as "w<k>" in worker_list; from 1, never used twice */
    int fmt;                    /**< the row of formats.h it runs */
    pid_t pid;                  /**< its process, meaningful while it runs */
    int fd;                     /**< its command socket, -1 for none */
    int port;                   /**< the port of its command socket, as proc_spawn reported it */
    int fb_fd;                  /**< its feedback socket, read by the relay */
    int fb_port;                /**< the port of its feedback socket */
    int state;                  /**< one of the W_ states */
    int pool;                   /**< 1 when place is a pool */
    int no_chain_expect;        /**< 1 once the worker refused chain_expect: its chain adds take the add and the order */
    int thread_pool;            /**< 1 when the process was started with --thread-pool=on (its pin: pool=cores) */
    char place[48];             /**< own | pool:\<name> */
    int from_split;             /**< an own worker born of a pool that died without a culprit */
    instance_t **inst;          /**< the instances it holds */
    int ninst,                  /**< the entries in inst */
        capinst;                /**< the room allocated for inst, in entries */
    int64_t deaths[64];         /**< when it died, on the clock of proc_now_ms; only those inside the storm window are kept */
    int ndeaths;                /**< the entries in deaths */
    int backoff_ms;             /**< the wait before its last respawn was scheduled */
    int64_t next_try_ms;        /**< when the tick respawns it, while it is in W_BACKOFF */
    char **pend;                /**< connects a replay could not make yet: the peer port may not be visible to the new client */
    int npend;                  /**< the lines in pend */
    int64_t pend_until_ms;      /**< when the tick gives up retrying pend */
    struct CHAIN_T *chain;      /**< the chain this worker runs, its members in w->inst in the chain's order */
    /* the running history's window of this worker (src/history.c): what it has used since hist_start_ms */
    pid_t hist_pid;             /**< the process the window belongs to, 0 for none */
    int64_t hist_start_ms;      /**< when the window began, on the clock of proc_now_ms */
    double hist_cpu0;           /**< its CPU seconds when the window began */
    int hist_ninst;             /**< its members then: a window in which they changed is not counted */
    int64_t hist_half_ms;       /**< the mid-window sample, 0 before it: what a window that ends in a death is counted from */
    double hist_half_cpu;       /**< its CPU seconds at the mid-window sample */
    long long hist_half_pss_kb; /**< its PSS in kilobytes at the mid-window sample, 0 before it */
    /* its xruns (PHD_EVENT_XRUNS): the count the last window ended at, the baseline of the next; the first count a
     * process writes is only that baseline */
    pid_t xr_pid;               /**< the process xr_base is of (its xruns: see xr_base) */
    int xr_known;               /**< 1 once a count of xr_pid was read, so xr_base is a baseline */
    unsigned long long xr_base; /**< the last xrun count read from the process */
} worker_t;

/** @brief The instances a chain verb declared, in order; the ones not quarantined run in its worker. */
typedef struct CHAIN_T {
    int id;                     /**< the chain's number: the id of the chain verb, or of the plan it is a segment of */
    int *ids;                   /**< the member instance ids, in the order declared */
    int n;                      /**< the entries in ids */
    worker_t *w;                /**< NULL while no worker holds it */
    int rejoin;                 /**< its members are to be gathered in one worker again, by the tick */
    int refused;                /**< the code the worker answered the chain line with, 0 for none: the chain ends at once
                                 * (chain_answered, or the tick when it came on a respawn) */
    int planned;                /**< a segment of a plan, not a chain the controller declared: id is the plan's number, seg the
                                 * segment's place in the plan, and no g_chain row holds it */
    int seg;                    /**< the segment's place in the plan when planned */
    /* while it forms: since when (0 when formed), whether chain_stalled was said for this attempt, and what last held it */
    int64_t forming_ms;         /**< when its forming began, on the clock of proc_now_ms; 0 once formed */
    int stall_said;             /**< 1 once the chain_stalled event was said for this attempt */
    int stall_member;           /**< -1 for no one member */
    int stall_code;             /**< the code of the step that held it, 0 for none */
    char stall_step[8];         /**< the step that held it, such as "spawn" or "memory" */
} chain_t;

/**
 * @brief Takes the configuration and makes the daemon's own directory under state_root.
 * @param conf the configuration; copied, the caller keeps it
 * @pre Called once, before any other sup_ function.
 * @post The directory state_root/plugin-hostd/\<pid> exists and is empty, with a ckpt directory in it; every format's
 *       placement policy is own and its worker environment is clear. A format whose worker program is not installed
 *       is named once on stderr.
 */
void sup_init(const conf_t *conf);
/**
 * @brief Sets the placement spread: the audio cores, and every thread of the daemon on the reserved ones.
 * @return 0 (also when the spread is off), or -1 with the reason on stderr for an audio_cores outside the daemon's cpus
 */
int sup_placement_init(void);
/**
 * @brief This daemon's own directory under state_root: its checkpoints and the logs of its workers and scans.
 * @return the path; owned by the supervisor, valid until sup_init is called again
 */
const char *sup_root(void);
/**
 * @brief Ends every worker and removes the daemon's directory.
 * @post Each worker still running was sent SIGTERM and stopped; the directory of sup_root is deleted; the pins are
 *       closed.
 */
void sup_finish(void);

/**
 * @brief mod-host's own "resp \<code>" text for a refusal.
 * @param code the code
 * @return the text, malloc'd; NULL when memory ran out
 */
char *sup_resp(int code);
/**
 * @brief The code of a "resp \<code> ..." reply.
 * @param reply the reply, or NULL
 * @return the code; ERR_MEMORY_ALLOCATION for NULL (an answer there was no memory for), -999 for text that does not
 *         start with "resp "
 */
int sup_reply_code(const char *reply);

/**
 * @brief Adds an instance: picks its worker, starts one if needed, sends the add and records it in the ledger.
 * @param uri the plugin's uri, with its format's prefix; it routes the add to a format's row
 * @param id the instance number, 0 to MAX_INSTANCE - 1 and not in use
 * @param placement own, pool:\<name>, chain:\<id> or the default word; NULL is the default
 * @param client the jack client name for the instance, or NULL
 * @return the worker's reply, or a refusal (instance invalid or already existing, placement invalid, no backend, gave
 *         up, a pin refusal, no memory, ...); malloc'd
 */
char *sup_add(const char *uri, int id, const char *placement, const char *client);

/**
 * @brief Sends a command that names one instance to its worker.
 * @param id the instance
 * @param line the whole verb line
 * @return the worker's reply; instance-non-exists when there is no such instance; a worker-not-up refusal while its
 *         worker is not up; verb-dropped when the worker died on the line. When the reply is a success the ledger
 *         keeps the line if it is a recorded verb; if the ledger cannot, the reply is a memory refusal.
 */
char *sup_call(int id, const char *line);
/**
 * @brief Removes an instance from its worker and from the ledger.
 * @param id the instance
 * @return success, also when there is no such instance; the worker's refusal when it refuses the removal. A worker
 *         left with no instance is retired.
 */
char *sup_remove(int id);
/**
 * @brief Removes every instance, as sup_remove does for each.
 * @return success
 */
char *sup_remove_all(void);
/**
 * @brief Sends a connect or disconnect to the worker of one of the two ports' instances, and keeps it in the ledger.
 * @param verb the verb of the line
 * @param line the whole line
 * @param port_a the first port, as "\<client>:\<port>"
 * @param port_b the second port
 * @return the worker's reply. The worker is the one of the instance whose client the first port names, else the
 *         second's; when neither names an instance, the first worker that is up. On a success the connection is added
 *         to, or for a disconnect removed from, the ledger of each instance that owns a port.
 */
char *sup_connect(const char *verb, const char *line, const char *port_a, const char *port_b);
/**
 * @brief Sends a line to every worker that is up.
 * @param line the whole line
 * @return the first refusal, else the first answer; success when no worker is up. After a successful state load every
 *         instance is marked dirty.
 */
char *sup_broadcast(const char *line);
/**
 * @brief Routes a preset_show line.
 *
 * preset_show has two forms, told apart by their number of words as the worker reads them, a quoted word one word
 * (the plugin-hostd protocol's verb table): preset_show \<instance> \<key>, plugin-hostd's, is the instance's worker's
 * to answer; preset_show \<uri>, mod-host's, names no instance and reaches every worker, and its answer is mod-host's
 * own, the first LV2 worker's that is up, whatever a worker of another format says to a line of a form it does not
 * take.
 * @param line the whole line
 * @return the answer; an invalid-operation refusal when the instance word of the three-word form is not a number
 */
char *sup_preset_show(const char *line);
/**
 * @brief Keeps a command every worker shares: kept when it is one of PHD_HOST_SETTINGS and its words are its grammar.
 * @param line the whole line
 * @param tok the line's words
 * @param ntok the number of words
 * @post A worker started from now on is handed the line; one that is not a host setting, or is malformed, is ignored.
 */
void sup_host_setting(const char *line, char **tok, int ntok);
/**
 * @brief The instance's uri as it goes to a worker.
 * @param id the instance
 * @return the uri, owned by the supervisor; NULL for no such instance
 */
const char *sup_instance_uri(int id);
/**
 * @brief Where its format's plugins are searched.
 * @param id the instance
 * @return the search path, owned by the supervisor; NULL for no such instance
 */
const char *sup_instance_search(int id);
/**
 * @brief A verb of PHD_INSTANCE_VERBS: routed to a CLAP worker, answered here for an LV2 instance.
 * @param line the whole line, "\<verb> \<instance> ..."
 * @param ledger PHD_LEDGER_REPLACE to keep the latest node_label and track_info in the instance; any other value keeps
 *        none
 * @return the answer; invalid-operation when the line is malformed or the verb is not one the instance's format
 *         takes; instance-non-exists for an unknown instance
 */
char *sup_instance_verb(const char *line, int ledger);

/**
 * @brief The worker list: every worker, sorted by number, with its pid, format, state, place and instances.
 * @return "resp \<count> w\<k>:\<pid>:\<format>:\<state>:..." as worker_list prints it, malloc'd; NULL when memory ran out
 */
char *sup_worker_list(void);
/**
 * @brief What the supervisor knows of one instance: its worker, that worker's pid and state, its crashes and whether it
 *        is quarantined.
 * @param id the instance
 * @return "resp 0 w\<k> \<pid> \<state> \<crashes> \<quarantined>"; instance-non-exists for no such instance
 */
char *sup_instance_info(int id);
/**
 * @brief Forgets the deaths of one worker or of all.
 * @param which "w\<k>" for one worker, "all" (or NULL, or empty) for all
 * @return success; no-such-worker when "w\<k>" names none. A worker that had given up is put back to wait for its
 *         respawn, due now; with all, the deaths of every instance are forgotten as well.
 */
char *sup_reset(const char *which);
/**
 * @brief Lifts the quarantine of one instance or of all.
 * @param which an instance number or "all"
 * @return success; instance-non-exists for a number with no instance and no quarantine. The plans that held a member
 *         back are made again, and its chain is gathered again, by the tick.
 */
char *sup_quarantine_clear(const char *which);
/**
 * @brief Sets the placement an add without one takes.
 * @param format a format's name, or the any word for every format
 * @param place own or pool:\<name>
 * @return success; placement-invalid for another place; invalid-operation for an unknown format
 */
char *sup_policy_set(const char *format, const char *place);
/**
 * @brief pin_reload (and the sync's pin_changed): the pins read again from their files and put in at once.
 *
 * Instances that run keep running; one whose files the new pins refuse is logged and marked in worker_list.
 * @return SUCCESS, or invalid-operation when pins are not required or the pins could not be read; the earlier pins
 *         are then left as they are
 */
char *sup_pin_reload(void);
/**
 * @brief The same when the pin file or a pins_dir file changed since the pins were read; cheap (a stat of each)
 *        otherwise.
 *
 * Nothing is read while a write of the pin store is waiting; the next tick looks again.
 */
void sup_pins_poll(void);

/**
 * @brief pin_accept: the plugin's files as they are now become its pin; only under pin_mode first-use.
 * @param uri the plugin's uri
 * @return success, the refusal of the pin store, or invalid-operation when pins are not required or the mode is not
 *         first-use
 */
char *sup_pin_accept(const char *uri);
/**
 * @brief Sets how many workers a named pool may hold.
 * @param name the pool's name
 * @param max the most workers, at least 1
 * @return success; placement-invalid for a bad name; invalid-operation for max below 1 or when the table of pools is
 *         full
 */
char *sup_pool_config(const char *name, int max);
/**
 * @brief lv2_worker_set: the worker of one LV2 plugin, for its adds from now on.
 * @param uri the plugin's uri
 * @param worker the worker row's name
 * @return success, or invalid-operation when the worker cannot be picked
 */
char *sup_lv2_worker_set(const char *uri, const char *worker);
/**
 * @brief Sets the cpus and the nice value of a format's workers.
 * @param format a format's name or the any word
 * @param cpus a cpu list of digits, commas and dashes, or the none word to leave it
 * @param nice -20 to 19, or the none word to leave it
 * @return success; invalid-operation for an unknown format, a bad list or a nice out of range. The workers of the
 *         format that are up take the new environment at once, and those started later.
 */
char *sup_worker_env(const char *format, const char *cpus, const char *nice);
/**
 * @brief chain: the instances ids, in order, are one chain run in one worker; chain_clear gives each a worker of its own.
 * @param id the chain's number, 0 to MAX_INSTANCE - 1
 * @param ids the member instance ids, in order
 * @param n the number of members, at least PHD_CHAIN_MEMBERS_MIN
 * @return success; invalid-operation for a bad id or too few members; chain-unknown-instance, chain-duplicate,
 *         chain-instance-busy, chain-mixed-format or placement-invalid when the members cannot be one chain; a
 *         memory refusal. A member the new order leaves out goes back to a worker of its own.
 */
char *sup_chain(int id, const int *ids, int n);
/**
 * @brief Forgets a chain, each member in a worker of its own.
 * @param id the chain's number
 * @return success; no-such-chain when there is none
 */
char *sup_chain_clear(int id);
/**
 * @brief chain_get: the chain's worker, its members as declared and the ones its worker runs, each in order.
 * @param id the chain's number
 * @return "resp 0 \<w\<k>|none> \<declared ids> \<running ids|none>"; no-such-chain when there is none; NULL when memory
 *         ran out
 */
char *sup_chain_get(int id);
/**
 * @brief plan: the instances ids, in signal order, planned into segments (src/planner.c).
 *
 * Applied as chains of place chain:\<id>.\<k> and workers of their own while grouping is on, answered and kept while it
 * is off. plan_get reads the last plan back, plan_clear gives each member a worker of its own.
 * @param id the plan's number, 0 to MAX_INSTANCE - 1
 * @param ids the member instance ids, in signal order
 * @param n the number of members, from PHD_CHAIN_MEMBERS_MIN to PLANNER_MEMBERS_MAX
 * @return "resp 0 \<segments> \<cores>"; invalid-operation for a bad id or count; chain-unknown-instance,
 *         chain-duplicate or chain-instance-busy for a member that cannot be planned; the planner's refusal; NULL when
 *         memory ran out
 */
char *sup_plan(int id, const int *ids, int n);
/**
 * @brief Reads the last plan of a number back.
 * @param id the plan's number
 * @return "resp 0 \<segments> \<reasons> \<cores>"; no-such-plan when there is none; NULL when memory ran out
 */
char *sup_plan_get(int id);
/**
 * @brief Forgets a plan and its segments, each member in a worker of its own.
 * @param id the plan's number
 * @return success; no-such-plan when there is none
 */
char *sup_plan_clear(int id);

/**
 * @brief estimate: what the n plugins, in signal order, would cost at the rate and quantum, from the qualification
 *        records and the history, and how many workers plan would place them in; nothing is loaded and nothing moves.
 * @param rate the sample rate, above 0
 * @param quantum the block size in frames, above 0
 * @param uris the plugins' uris, in signal order
 * @param n the number of uris, from 1 to PLANNER_MEMBERS_MAX
 * @return "resp 0 \<latency> \<cpu percent> \<ram> \<workers> \<unknown count> \<unknown list> \<ram used> \<ram added>
 *         \<ram budget> \<ram unknown>"; invalid-operation for a count or a rate out of range; NULL when memory ran out
 */
char *sup_estimate(int rate, int quantum, const char *const *uris, int n);

/**
 * @brief history_get: the summary of the binary the uri's pin holds, on this host class (src/history.c).
 * @param uri the plugin's uri
 * @return "resp 0 \<summary>"; "resp 0 unavailable" when there is no history; "resp 0 none" when the plugin has no
 *         summary; a memory refusal
 */
char *sup_history_get(const char *uri);
/**
 * @brief history_clear: the lines of one uri or all of them.
 * @param uri the plugin's uri, or the all word
 * @return success, or invalid-operation when the history could not be cleared
 */
char *sup_history_clear(const char *uri);

/**
 * @brief The idle tick: reap the dead, respawn the due, checkpoint the quiet.
 *
 * Also reads the pins again if they changed, runs the history windows, makes the plans again that are due, gathers the
 * chains that are to rejoin and says a chain that stays forming past its timeout.
 */
void sup_tick(void);

/**
 * @brief After a reply has gone to the controller: checkpoint what a preset or patch just changed.
 * @param id the instance
 * @param verb the verb that was answered
 * @post When the verb is a preset load or a patch set, the instance is dirty and its worker is up, the worker is
 *       checkpointed.
 */
void sup_after_reply(int id, const char *verb);

/**
 * @brief The number of workers, whatever their state.
 * @return the count
 */
int sup_worker_count(void);

/**
 * @brief Ends every monitor_output the connection now ending set (monitor_output_off).
 *
 * As doc/protocol.md's Monitors rules: the worker is told while it is up, and the ledger forgets the line either way,
 * so a respawn after this does not replay it.
 */
void sup_monitors_disconnect(void);

/**
 * @brief Whether the connection now open holds a monitor on this output of this instance (monitor_output_off refuses
 *        -543 when it does not).
 * @param id the instance
 * @param symbol the output's port symbol
 * @return 1 when the instance's ledger holds the monitor_output entry, else 0, also for an instance that is not up
 */
int sup_monitor_held(int id, const char *symbol);

#endif
