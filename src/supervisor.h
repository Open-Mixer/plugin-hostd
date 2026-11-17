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
 * reply line ("resp \<code\> ..."), allocated with malloc, and the caller frees it. The supervisor's state is a set of
 * globals with no lock: every function that uses it is for the daemon's main thread only.
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

/** @brief The states of a worker, one enumerator W_\<id\> for each PHD_WORKER_STATES row, then W_COUNT. */
enum {
/**
 * @brief The enumerator W_\<id\> of one worker state.
 *
 * @param id the state's identifier
 * @param name the word worker_list prints for it (unused here)
 * @param meaning its meaning (unused here)
 */
#define X(id, name, meaning) W_##id,
    PHD_WORKER_STATES(X)
#undef X
    W_COUNT
};

/** @brief What a recorded verb is, for the checkpoint. */
enum {
    KIND_STATE, /**< what the plugin's own state holds and a checkpoint replaces */
    KIND_HOST   /**< what only the host knows and the ledger always keeps */
};

/** @brief One line of an instance's ledger: a verb kept to be replayed into a new worker. */
typedef struct ENTRY_T {
    char *line;                 /**< the verb line as the worker was sent it, malloc'd */
    /** the entry's key, "\<verb\> \<argument\>": a later line with the same key replaces this one; NULL for an entry
     * that is never replaced */
    char *key;
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
    /** the last verb it answered and the ledger kept, the suspect of a death that follows soon */
    char *sus_line;
    char *sus_prev;             /**< the ledger line that verb replaced, put back when it is dropped */
    int64_t sus_ms;             /**< when sus_line was kept, on the clock of proc_now_ms */
    int64_t sus_seq;            /**< the order of the verbs across instances, which the millisecond clock cannot give */
    int has_ckpt;               /**< 1 when a checkpoint of its state is on disk */
    int unreplayed;             /**< its pin refused the add of the last replay: the worker does not hold it */
    int pin_refused;            /**< the pins read again refuse its files; it keeps running, worker_list marks it */
    char *node_label;           /**< the latest node_label with a label it took, replayed after its add */
    char *track_info;           /**< the latest track_info it took, replayed after its add, never to an LV2 worker */
    struct CHAIN_T *chain;      /**< the chain it is a member of, NULL for none */
} instance_t;

/** @brief One worker process, or the place one is to run again: its sockets, its instances and its death record. */
typedef struct WORKER_T {
    int k;                      /**< its number, as "w\<k\>" in worker_list; from 1, never used twice */
    int fmt;                    /**< the row of formats.h it runs */
    pid_t pid;                  /**< its process, meaningful while it runs */
    int fd;                     /**< its command socket, -1 for none */
    int port;                   /**< the port of its command socket, as proc_spawn reported it */
    int fb_fd;                  /**< its feedback socket, read by the relay */
    int fb_port;                /**< the port of its feedback socket */
    int state;                  /**< one of the W_ states */
    int pool;                   /**< 1 when place is a pool */
    /** 1 once the worker refused chain_expect: its chain adds take the add and the order */
    int no_chain_expect;
    int thread_pool;            /**< 1 when the process was started with --thread-pool=on (its pin: pool=cores) */
    char place[48];             /**< own | pool:\<name\> */
    int from_split;             /**< an own worker born of a pool that died without a culprit */
    instance_t **inst;          /**< the instances it holds */
    int ninst,                  /**< the entries in inst */
        capinst;                /**< the room allocated for inst, in entries */
    /** when it died, on the clock of proc_now_ms; only those inside the storm window are kept */
    int64_t deaths[64];
    int ndeaths;                /**< the entries in deaths */
    int backoff_ms;             /**< the wait before its last respawn was scheduled */
    int64_t next_try_ms;        /**< when the tick respawns it, while it is in W_BACKOFF */
    /** connects a replay could not make yet: the peer port may not be visible to the new client */
    char **pend;
    int npend;                  /**< the lines in pend */
    int64_t pend_until_ms;      /**< when the tick gives up retrying pend */
    struct CHAIN_T *chain;      /**< the chain this worker runs, its members in w->inst in the chain's order */
    pid_t hist_pid;             /**< the process the running history's window belongs to, 0 for none (src/history.c) */
    int64_t hist_start_ms;      /**< when the window began, on the clock of proc_now_ms */
    double hist_cpu0;           /**< its CPU seconds when the window began */
    int hist_ninst;             /**< its members then: a window in which they changed is not counted */
    /** the mid-window sample, 0 before it: what a window that ends in a death is counted from */
    int64_t hist_half_ms;
    double hist_half_cpu;       /**< its CPU seconds at the mid-window sample */
    long long hist_half_pss_kb; /**< its PSS in kilobytes at the mid-window sample, 0 before it */
    pid_t xr_pid;               /**< the process xr_base is of */
    int xr_known;               /**< 1 once a count of xr_pid was read, so xr_base is a baseline */
    /** the last xrun count (PHD_EVENT_XRUNS) read from the process: the count the last window ended at and the
     * baseline of the next; the first count a process writes is only that baseline */
    unsigned long long xr_base;
} worker_t;

/** @brief The instances a chain verb declared, in order; the ones not quarantined run in its worker. */
typedef struct CHAIN_T {
    int id;                     /**< the chain's number: the id of the chain verb, or of the plan it is a segment of */
    int *ids;                   /**< the member instance ids, in the order declared */
    int n;                      /**< the entries in ids */
    worker_t *w;                /**< NULL while no worker holds it */
    int rejoin;                 /**< its members are to be gathered in one worker again, by the tick */
    /** the code the worker answered the chain line with, 0 for none: the chain ends at once (in sup_chain, or in the
     * tick when it came on a respawn) */
    int refused;
    /** a segment of a plan, not a chain the controller declared: id is the plan's number, seg the segment's place in
     * the plan, and no row of the table of chains holds it */
    int planned;
    int seg;                    /**< the segment's place in the plan when planned */
    int64_t forming_ms;         /**< when its forming began, on the clock of proc_now_ms; 0 once formed */
    int stall_said;             /**< 1 once the chain_stalled event was said for this attempt */
    int stall_member;           /**< the member that last held its forming; -1 for no one member */
    int stall_code;             /**< the code of the step that held it, 0 for none */
    char stall_step[8];         /**< the step that held it, such as "spawn" or "memory" */
} chain_t;

/**
 * @brief Takes the configuration and makes the daemon's own directory under state_root.
 *
 * The directory state_root/plugin-hostd/\<pid\> is removed with what it holds and made again, with a ckpt directory in
 * it; no mkdir result is checked. Every format's placement policy is set to own and its worker environment cleared.
 * A format whose worker program is not installed is named once on stderr.
 *
 * @param conf the configuration; copied, the caller keeps it
 * @pre conf is not NULL. Called before any other sup_ function that reads the configuration or the directory.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_init(const conf_t *conf);
/**
 * @brief Sets the placement spread: the audio cores for the workers, and the daemon's threads on the reserved cpus.
 *
 * With the spread off nothing is done. The daemon's threads are moved only when there is both an audio core and a
 * reserved cpu; what was decided is said on stderr.
 *
 * @return 0 (also when the spread is off); -1, with the reason on stderr, when the daemon's cpus cannot be read, when
 *         audio_cores is no cpu list inside them, or when the audio cores make a list too long to keep
 * @pre sup_init was called.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
int sup_placement_init(void);
/**
 * @brief This daemon's own directory under state_root: its checkpoints and the logs of its workers and scans.
 *
 * @return the path, in a buffer of the supervisor that sup_init writes; never freed by the caller
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
const char *sup_root(void);
/**
 * @brief Ends every worker and removes the daemon's directory.
 *
 * Each worker with a process is sent SIGTERM, then each is stopped and reaped as proc_stop does; the directory of
 * sup_root is deleted with what it holds; the pins are closed (pins_finish).
 *
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_finish(void);

/**
 * @brief The text "resp \<code\>": a reply line that holds a code alone.
 *
 * @param code the code
 * @return the text, malloc'd; NULL when memory ran out
 */
char *sup_resp(int code);
/**
 * @brief The code of a "resp \<code\> ..." reply.
 *
 * @param reply the reply, or NULL
 * @return the code, read as atoi reads it; ERR_MEMORY_ALLOCATION for NULL (an answer there was no memory for), -999
 *         for text that does not start with "resp "
 */
int sup_reply_code(const char *reply);

/**
 * @brief Adds an instance: picks its worker, starts one if needed, sends the add and records it in the ledger.
 *
 * @param uri the plugin's uri, with its format's prefix; it routes the add to a format's row
 * @param id the instance number, 0 to MAX_INSTANCE - 1 and not in use
 * @param placement own, pool:\<name\>, chain:\<id\> or the default word; NULL is the default
 * @param client the jack client name for the instance, or NULL
 * @return the worker's reply, or a refusal (instance invalid or already existing, placement invalid, no backend, gave
 *         up, a pin refusal, no memory, ...); malloc'd
 * @pre uri is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_add(const char *uri, int id, const char *placement, const char *client);

/**
 * @brief Sends a command that names one instance to its worker.
 *
 * When the reply's code is 0 or above the ledger keeps the line if it is a recorded verb; if the ledger cannot, the
 * reply is a memory refusal.
 *
 * @param id the instance
 * @param line the whole verb line
 * @return the worker's reply; instance-non-exists when there is no such instance; gave-up or worker-spawn while its
 *         worker is not up; worker-spawn when the worker was found dead before the line was sent; verb-dropped when
 *         it died with the line on the wire
 * @pre line is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_call(int id, const char *line);
/**
 * @brief Removes an instance from its worker and from the ledger.
 *
 * A worker that is not up is not asked: the instance leaves the ledger alone. A worker left with no instance is
 * retired.
 *
 * @param id the instance
 * @return success, also when there is no such instance and when the worker died on the removal; the worker's refusal
 *         when it refuses the removal, the instance then stays
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_remove(int id);
/**
 * @brief Removes every instance, as sup_remove does for each.
 *
 * @return success, whatever each removal answered
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_remove_all(void);
/**
 * @brief Sends a connect or disconnect to the worker of one of the two ports' instances, and keeps it in the ledger.
 *
 * The worker is the one of the instance whose client the first port names when it is up, else the second's when it is
 * up; when neither port names an instance, the first worker that is up. When the reply's code is 0 or above the
 * connection is added to, or for a disconnect removed from, the ledger of each instance that owns a port.
 *
 * @param verb the verb of the line
 * @param line the whole line
 * @param port_a the first port, as "\<client\>:\<port\>"
 * @param port_b the second port
 * @return the worker's reply; gave-up or worker-spawn when a port names an instance and no worker of the two is up;
 *         invalid-operation when neither names one and no worker is up; worker-spawn when the worker died on the
 *         line; a memory refusal when the ledger cannot keep a connect the worker made
 * @pre No argument is NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_connect(const char *verb, const char *line, const char *port_a, const char *port_b);
/**
 * @brief Sends a line to every worker that is up.
 *
 * After a state load that answered 0 or above every instance is marked dirty.
 *
 * @param line the whole line
 * @return the first refusal, else the first answer; success when no worker answered
 * @pre line is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_broadcast(const char *line);
/**
 * @brief Routes a preset_show line.
 *
 * preset_show has two forms, told apart by their number of words as the worker reads them, a quoted word one word
 * (the plugin-hostd protocol's verb table): preset_show \<instance\> \<key\>, plugin-hostd's, is the instance's
 * worker's to answer, as sup_call; preset_show \<uri\>, mod-host's, names no instance and reaches every worker that is
 * up, and its answer is that of a worker whose format searches the LV2 path, one that answers 0 or above before one
 * that refuses, whatever a worker of another format says. A line of any other number of words goes as sup_broadcast.
 *
 * @param line the whole line
 * @return the answer; invalid-operation when the instance word of the three-word form is not a number from -1000000
 *         to 1000000; a memory refusal
 * @pre line is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_preset_show(const char *line);
/**
 * @brief Keeps a command every worker shares, to hand it to each worker started from now on.
 *
 * The line is kept when its verb is one of PHD_HOST_SETTINGS and its words fit that verb's format, and it replaces an
 * earlier line of the same verb. Any other line is ignored; with no memory the line is not kept, and stderr says so.
 *
 * @param line the whole line
 * @param tok the line's words
 * @param ntok the number of words
 * @pre line and tok are not NULL; ntok is at least 1.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_host_setting(const char *line, char **tok, int ntok);
/**
 * @brief The instance's uri as it goes to a worker.
 *
 * @param id the instance
 * @return the uri, owned by the supervisor until the instance is removed; NULL for no such instance
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
const char *sup_instance_uri(int id);
/**
 * @brief Where the plugins of the instance's format are searched.
 *
 * @param id the instance
 * @return the search path, owned by the supervisor; NULL for no such instance
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
const char *sup_instance_search(int id);
/**
 * @brief Answers a verb of PHD_INSTANCE_VERBS: sent to the worker of a format that answers them, answered here for
 *        the others.
 *
 * @param line the whole line, "\<verb\> \<instance\> ..."
 * @param ledger PHD_LEDGER_REPLACE to keep the latest node_label and track_info a worker took in the instance; any
 *        other value keeps none of a worker's
 * @return the answer; invalid-operation when the line is malformed or the verb is not one the instance's format
 *         takes; instance-non-exists for an unknown instance; a memory refusal
 * @pre line is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_instance_verb(const char *line, int ledger);

/**
 * @brief The worker list: every worker, sorted by number, with its pid, format, state, place and instances.
 *
 * @return "resp \<count\> w\<k\>:\<pid\>:\<format\>:\<state\>:..." as worker_list prints it, malloc'd; NULL when memory
 *         ran out
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_worker_list(void);
/**
 * @brief What the supervisor knows of one instance: its worker, that worker's pid and state, its crashes and whether
 *        it is quarantined.
 *
 * @param id the instance
 * @return "resp 0 w\<k\> \<pid\> \<state\> \<crashes\> \<quarantined\>"; instance-non-exists for no such instance
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_instance_info(int id);
/**
 * @brief Forgets the deaths of one worker or of all.
 *
 * A worker that had given up is put back to wait for its respawn, due now; with all, the deaths of every instance are
 * forgotten as well.
 *
 * @param which "w\<k\>" for one worker, the all word (or NULL, or empty) for all
 * @return success; no-such-worker when "w\<k\>" names none
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_reset(const char *which);
/**
 * @brief Lifts the quarantine of one instance or of all.
 *
 * The plans that held a member back are marked to be made again, and its chain to be gathered again, by the tick.
 *
 * @param which an instance number, read as atoi reads it, or the all word
 * @return success; instance-non-exists for a number out of range or with no instance and no quarantine
 * @pre which is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_quarantine_clear(const char *which);
/**
 * @brief Sets the placement an add without one takes.
 *
 * @param format a format's name, or PHD_FORMAT_ANY for every format
 * @param place own or pool:\<name\>
 * @return success; placement-invalid for another place; invalid-operation for an unknown format
 * @pre Neither argument is NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_policy_set(const char *format, const char *place);
/**
 * @brief Reads the pins again from their files and puts them in at once (pin_reload, and the sync's pin_changed).
 *
 * Instances that run keep running; one whose files the new pins refuse is logged and marked in worker_list.
 *
 * @return success, or invalid-operation when pins are not required or the pins could not be read; the earlier pins
 *         are then left as they are
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_pin_reload(void);
/**
 * @brief Reads the pins again, as sup_pin_reload, when the pin file or a pins_dir file changed since they were read.
 *
 * Nothing is done when pins are not required, and nothing is read while a write of the writer waits; the next call
 * looks again.
 *
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_pins_poll(void);

/**
 * @brief Makes the plugin's files as they are now its pin (pin_accept); only under pin_mode first-use.
 *
 * @param uri the plugin's uri
 * @return success, the refusal of the pin store, or invalid-operation when pins are not required or the mode is not
 *         first-use
 * @pre uri is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_pin_accept(const char *uri);
/**
 * @brief Sets how many workers a named pool may hold.
 *
 * @param name the pool's name
 * @param max the most workers, at least 1
 * @return success; placement-invalid for a bad name; invalid-operation for max below 1 or when the table of pools is
 *         full
 * @pre name is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_pool_config(const char *name, int max);
/**
 * @brief Sets the worker of one LV2 plugin, for its adds from now on (lv2_worker_set).
 *
 * @param uri the plugin's uri
 * @param worker the worker's word, or PHD_WORD_NONE to take the override back
 * @return success, or invalid-operation when the worker cannot be picked
 * @pre Neither argument is NULL.
 * @note Not thread-safe: the override table has no lock; call on the daemon's main thread only.
 */
char *sup_lv2_worker_set(const char *uri, const char *worker);
/**
 * @brief Sets the cpus and the nice value of a format's workers.
 *
 * The workers of the format that are up take the new environment at once, and those started later.
 *
 * @param format a format's name, or PHD_FORMAT_ANY for every format
 * @param cpus a cpu list of digits, commas and dashes, shorter than 128 bytes, or PHD_WORD_NONE to leave it
 * @param nice -20 to 19, read as atoi reads it, or PHD_WORD_NONE to leave it
 * @return success; invalid-operation for an unknown format, a bad list or a nice out of range
 * @pre No argument is NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_worker_env(const char *format, const char *cpus, const char *nice);
/**
 * @brief Declares a chain: the instances ids, in order, run in one worker.
 *
 * A chain of the same number is replaced, and a member the new order leaves out goes back to a worker of its own.
 *
 * @param id the chain's number, 0 to MAX_INSTANCE - 1
 * @param ids the member instance ids, in order
 * @param n the number of members, at least PHD_CHAIN_MEMBERS_MIN
 * @return success; invalid-operation for a bad id or too few members; chain-unknown-instance, chain-duplicate,
 *         chain-instance-busy, chain-mixed-format or placement-invalid when the members cannot be one chain;
 *         placement-invalid when the worker refuses the chain, which then ends; a memory refusal
 * @pre ids holds n ids.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_chain(int id, const int *ids, int n);
/**
 * @brief Forgets a chain, each member that runs in its worker moved to a worker of its own.
 *
 * @param id the chain's number
 * @return success; no-such-chain when there is none
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_chain_clear(int id);
/**
 * @brief The chain's worker, its members as declared and the ones its worker runs, each in order (chain_get).
 *
 * @param id the chain's number
 * @return "resp 0 \<w\<k\>|none\> \<declared ids\> \<running ids|none\>", none being PHD_WORD_NONE; no-such-chain when
 *         there is none; NULL when memory ran out
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_chain_get(int id);
/**
 * @brief Plans the instances ids, in signal order, into segments (src/planner.c).
 *
 * Applied as chains of place chain:\<id\>.\<k\> and workers of their own while grouping is on, answered and kept while
 * it is off. sup_plan_get reads the last plan back, sup_plan_clear gives each member a worker of its own.
 *
 * @param id the plan's number, 0 to MAX_INSTANCE - 1
 * @param ids the member instance ids, in signal order
 * @param n the number of members, from PHD_CHAIN_MEMBERS_MIN to PLANNER_MEMBERS_MAX
 * @return "resp 0 \<segments\> \<cores\>"; invalid-operation for a bad id or count; chain-unknown-instance,
 *         chain-duplicate or chain-instance-busy for a member that cannot be planned; the planner's refusal; NULL when
 *         memory ran out
 * @pre ids holds n ids.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_plan(int id, const int *ids, int n);
/**
 * @brief Reads the last plan of a number back.
 *
 * @param id the plan's number
 * @return "resp 0 \<segments\> \<reasons\> \<cores\>"; no-such-plan when there is none; NULL when memory ran out
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_plan_get(int id);
/**
 * @brief Forgets a plan and its segments, each member in a worker of its own.
 *
 * @param id the plan's number
 * @return success; no-such-plan when there is none
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_plan_clear(int id);

/**
 * @brief Estimates what n plugins, in signal order, would cost at a rate and quantum (estimate).
 *
 * The figures come from the qualification records and the history, and the workers are how many plan would place the
 * plugins in; nothing is loaded and nothing moves.
 *
 * @param rate the sample rate, above 0
 * @param quantum the block size in frames, above 0
 * @param uris the plugins' uris, in signal order
 * @param n the number of uris, from 1 to PLANNER_MEMBERS_MAX
 * @return "resp 0 \<latency\> \<cpu percent\> \<ram\> \<workers\> \<unknown count\> \<unknown list\> \<ram used\>
 *         \<ram added\> \<ram budget\> \<ram unknown\>"; invalid-operation for a count, a rate or a quantum out of
 *         range; NULL when memory ran out
 * @pre uris holds n uris, none NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
char *sup_estimate(int rate, int quantum, const char *const *uris, int n);

/**
 * @brief The history summary of the binary the uri's pin holds, on this host class (history_get, src/history.c).
 *
 * @param uri the plugin's uri
 * @return "resp 0 \<summary\>"; "resp 0 " and PHD_WORD_UNAVAILABLE when there is no history; "resp 0 " and
 *         PHD_WORD_NONE when the plugin has no pin digest or no summary; a memory refusal
 * @pre uri is not NULL.
 * @note Not thread-safe: the history and the pins have no lock; call on the daemon's main thread only.
 */
char *sup_history_get(const char *uri);
/**
 * @brief Clears the history lines of one uri or all of them (history_clear).
 *
 * @param uri the plugin's uri, or PHD_WORD_ALL
 * @return success, or invalid-operation when the history could not be cleared
 * @pre uri is not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
char *sup_history_clear(const char *uri);

/**
 * @brief The idle tick: reap the dead, respawn the due, checkpoint the quiet.
 *
 * Also reads the pins again if they changed, runs the history windows, makes the plans again that are due, gathers the
 * chains that are to rejoin, says a chain that stays forming past its timeout and ends a chain its worker refused.
 *
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_tick(void);

/**
 * @brief Checkpoints what a preset or patch just changed, after its reply has gone to the controller.
 *
 * The instance's worker is checkpointed when the verb is a preset load or a patch set, the instance is dirty and its
 * worker is up; nothing is done otherwise.
 *
 * @param id the instance
 * @param verb the verb that was answered
 * @pre verb is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_after_reply(int id, const char *verb);

/**
 * @brief The number of workers, whatever their state.
 *
 * @return the count
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
int sup_worker_count(void);

/**
 * @brief Ends every monitor_output the ledgers hold, as the connection that set them ends (monitor_output_off).
 *
 * As doc/protocol.md's Monitors rules: the worker is told while it is up, and the ledger forgets the line either way,
 * so a respawn after this does not replay it.
 *
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
void sup_monitors_disconnect(void);

/**
 * @brief Whether the ledger of an instance holds a monitor on one of its outputs.
 *
 * sup_monitors_disconnect empties the monitors as a connection ends, so one that is held was set by the connection
 * now open.
 *
 * @param id the instance
 * @param symbol the output's port symbol
 * @return 1 when the instance's ledger holds the monitor_output entry, else 0, also for an instance that does not exist
 * @pre symbol is not NULL.
 * @note Not thread-safe: the supervisor's state has no lock; call on the daemon's main thread only.
 */
int sup_monitor_held(int id, const char *symbol);

#endif
