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

/** @file proc.h
 * @brief Worker processes: spawn, connect, one command at a time over a socket, stop, and what the kernel says of them.
 */

#ifndef PROC_H
#define PROC_H

#include <sys/types.h>

#include "conf.h"

/** @brief proc_rpc: the command was sent and a reply read. */
#define RPC_OK          0
/** @brief proc_rpc: the worker went away while the command was on the wire. */
#define RPC_DIED        (-1)
/** @brief proc_rpc: it had already gone before the command was sent. */
#define RPC_WAS_DEAD    (-2)

/** @brief The cpus, nice value and thread-pool option a format's workers are started with. */
typedef struct WORKER_ENV_T {
    char cpus[128];             /**< cpu list, "" leaves the mask alone */
    int nice;                   /**< INT_MIN leaves it alone */
    int thread_pool;            /**< 1 starts the worker with --thread-pool=on; 0 passes no option, the worker's `qualified` */
} worker_env_t;

/**
 * @brief Sets an environment to "change nothing": no cpu list, nice INT_MIN, thread_pool 0.
 * @param env the environment to fill
 */
void proc_env_clear(worker_env_t *env);

/**
 * @brief Starts a worker: `bin` as "\<bin> -n -p \<port> -f \<fb_port>" (PHD_WORKER_ARGUMENTS), with PHD_WORKER_THREAD_POOL_ON after
 * them when env->thread_pool is set, on two free ports, its stdout and stderr in `logfile`.
 * @param conf the configuration (not used)
 * @param bin the worker program
 * @param world_env the name of the environment variable that carries `world`, or NULL
 * @param world the value of that variable, or NULL; set in the worker's environment only when neither is NULL
 * @param env the cpus, nice and thread-pool option the worker starts with
 * @param logfile the file that takes its stdout and stderr
 * @param[out] pid the new process
 * @param[out] port the command port it was told to bind
 * @param[out] fb_port the feedback port it was told to bind
 * @return 0, or -1 when no free ports were found or the fork failed
 */
int proc_spawn(const conf_t *conf, const char *bin, const char *world_env, const char *world, const worker_env_t *env,
               const char *logfile, pid_t *pid, int *port, int *fb_port);

/** @brief proc_connect: the process was gone before it became ready. */
#define PROC_EXITED (-2)
/**
 * @brief Waits for the worker's socket to accept and its "ready!" line, then opens its feedback port.
 *
 * PROC_EXITED means it could not bind its ports: they are picked free, then released, and another process can take
 * one in between, so a caller may spawn again on fresh ports.
 * @param conf the configuration (the wait it allows)
 * @param pid the worker's process
 * @param port its command port
 * @param fb_port its feedback port
 * @param logfile its log file
 * @param[out] fb_fd the feedback socket
 * @return the command socket; -1 when it never became ready, PROC_EXITED when the process was gone before it was
 */
int proc_connect(const conf_t *conf, pid_t pid, int port, int fb_port, const char *logfile, int *fb_fd);

/**
 * @brief Sends one command and reads one reply.
 *
 * A worker that does not answer within the timeout is killed, and counts as having died with the command on the wire.
 * @param conf the configuration (the timeout)
 * @param pid the worker's process
 * @param fd its command socket
 * @param msg the command line
 * @param[out] reply on RPC_OK, the reply, malloc'd; the caller frees it
 * @return RPC_OK, RPC_DIED or RPC_WAS_DEAD
 */
int proc_rpc(const conf_t *conf, pid_t pid, int fd, const char *msg, char **reply);

/**
 * @brief Whether `pid` has exited, without reaping it: the status stays for proc_exited.
 * @param pid the process; 0 or below counts as dead
 * @return 1 when it has exited or is no child of ours, else 0
 */
int proc_dead(pid_t pid);

/**
 * @brief Reaps `pid` if it has exited.
 * @param pid the process; 0 or below counts as exited
 * @param[out] status its wait status, when it has exited
 * @return 1 when it has exited (or is no child of ours), else 0
 */
int proc_exited(pid_t pid, int *status);

/**
 * @brief Stops a worker: SIGTERM, then SIGKILL after a grace period; the process is reaped.
 * @param pid the process
 */
void proc_stop(pid_t pid);

/**
 * @brief Applies the cpu list and the nice value of `env` to every thread of the process.
 * @param pid the process
 * @param env the environment; a field that leaves things alone is skipped
 */
void proc_apply_env(pid_t pid, const worker_env_t *env);

/**
 * @brief Logs on stderr a nice of `env` that the worker `pid` does not have.
 *
 * setpriority is refused to a process without privilege that lowers a nice below its own.
 * @param pid the process
 * @param env the environment
 */
void proc_env_report(pid_t pid, const worker_env_t *env);

/**
 * @brief The version the data of `bundle` gives the plugin `uri`: its lv2:minorVersion and lv2:microVersion, each left 0
 * when not stated.
 * @param bundle the bundle's directory
 * @param uri the plugin's uri
 * @param[out] minor the minor version
 * @param[out] micro the micro version
 */
typedef void (*proc_lv2_version_fn)(const char *bundle, const char *uri, long *minor, long *micro);

/**
 * @brief The bundle of LV2_PATH that is the plugin `uri`, by plugin-db's declared rule (PLUGIN_DB_BUNDLE_RULES,
 * newest-version).
 *
 * Of the bundles whose manifest realises it (or, when none does, that name it), the highest version `version` reads (none
 * read, NULL, is all of version 0), and of equal versions the first in the path, each directory's bundles in byte order
 * of their names.
 * @param lv2_path the search path
 * @param uri the plugin's uri
 * @param version reads a bundle's version, or NULL for none
 * @return the bundle's directory, malloc'd; NULL if none
 */
char *proc_find_lv2_bundle(const char *lv2_path, const char *uri, proc_lv2_version_fn version);
/**
 * @brief Every bundle of LV2_PATH whose manifest names `uri` and holds no binary (a preset bundle, the user's or one a
 * distribution ships, a MOD GUI), each handed to `fn` until it answers non-zero.
 *
 * The walk is remembered by search path and uri, and while no directory of the path has changed since (no bundle
 * added or removed) the bundles it found are handed on again with no manifest read.
 * @param lv2_path the search path
 * @param uri the plugin's uri
 * @param fn called for each bundle with `ctx` and the bundle's directory; non-zero stops the walk
 * @param ctx handed to `fn`
 * @return how many bundles, or -1 when stopped or short of memory
 */
int proc_lv2_preset_bundles(const char *lv2_path, const char *uri, int (*fn)(void *ctx, const char *bundle), void *ctx);
/** @brief How many manifests the lookups have read: what a test counts to see the path not walked again. */
extern unsigned long proc_manifest_reads;

/**
 * @brief Whether `bin` is executable, by path or on PATH.
 * @param bin the program
 * @return non-zero when it is
 */
int proc_have_binary(const char *bin);

/**
 * @brief The monotonic clock, in milliseconds.
 * @return the time
 */
int64_t proc_now_ms(void);

/* What the kernel says of a worker: the CPU time it has used and its memory, for the running history. The first two
 * read the text of /proc/<pid>/stat and /proc/<pid>/smaps_rollup. 0, or -1 when the text is not what the kernel writes. */

/**
 * @brief utime and stime of a stat line, in clock ticks: the fields after the last ')', since the command name before it
 * may hold spaces and parentheses.
 * @param text the text of /proc/\<pid>/stat
 * @param[out] utime the user time
 * @param[out] stime the system time
 * @return 0, or -1 when the text is not what the kernel writes
 */
int proc_parse_stat(const char *text, long long *utime, long long *stime);
/**
 * @brief The Pss line of smaps_rollup, in kB.
 * @param text the text of /proc/\<pid>/smaps_rollup
 * @param[out] kb the value
 * @return 0, or -1 when there is no Pss line in the form the kernel writes
 */
int proc_parse_pss(const char *text, long long *kb);
/**
 * @brief Seconds of CPU (utime + stime) the process has used.
 * @param pid the process
 * @param[out] seconds the CPU time
 * @return 0, or -1 when the process or the file is gone
 */
int proc_cpu_seconds(pid_t pid, double *seconds);
/**
 * @brief The Pss of the process, in kB.
 * @param pid the process
 * @param[out] kb the value
 * @return 0, or -1 when the process or the file is gone
 */
int proc_pss_kb(pid_t pid, long long *kb);

#endif
