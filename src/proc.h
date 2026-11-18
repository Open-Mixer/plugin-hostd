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

/** @brief The answer of proc_rpc when the command was sent and a reply read. */
#define RPC_OK          0
/** @brief The answer of proc_rpc when the worker went away while the command was on the wire. */
#define RPC_DIED        (-1)
/** @brief The answer of proc_rpc when the worker had already gone before the command was sent. */
#define RPC_WAS_DEAD    (-2)

/** @brief The cpus, nice value and thread-pool option a format's workers are started with. */
typedef struct WORKER_ENV_T {
    char cpus[128];             /**< cpu list, "" leaves the mask alone */
    int nice;                   /**< INT_MIN leaves it alone */
    /** 1 starts the worker with PHD_WORKER_THREAD_POOL_ON; 0 passes no option, the worker's `qualified` */
    int thread_pool;
} worker_env_t;

/**
 * @brief Sets an environment to "change nothing": no cpu list, nice INT_MIN, thread_pool 0.
 *
 * @param[out] env the environment to fill
 * @pre env is not NULL.
 */
void proc_env_clear(worker_env_t *env);

/**
 * @brief Starts a worker process on two free loopback ports, its stdout and stderr in a log file.
 *
 * The child runs `bin` as "\<bin\> -n -p \<port\> -f \<fb_port\>" (PHD_WORKER_ARGUMENTS), with
 * PHD_WORKER_THREAD_POOL_ON after them when env->thread_pool is set. Before the exec it takes /dev/null as stdin,
 * the cpus and nice of `env`, and the confinement of proc_confine; it is sent SIGTERM when the daemon dies. A child
 * that cannot be confined or cannot exec exits 127.
 *
 * @param conf the configuration (not used)
 * @param bin the worker program, a path or a name on PATH
 * @param world_env the name of the environment variable that carries `world`, or NULL
 * @param world the value of that variable, or NULL; set in the worker's environment only when neither is NULL
 * @param env the cpus, nice and thread-pool option the worker starts with, or NULL for none
 * @param logfile the file that takes its stdout and stderr, made or emptied
 * @param[out] pid the new process, written on 0 only
 * @param[out] port the command port it was told to bind, -1 when none was found
 * @param[out] fb_port the feedback port it was told to bind, -1 when none was found
 * @return 0, or -1 when no free ports were found, the log file could not be opened or the fork failed
 * @pre bin, logfile, pid, port and fb_port are not NULL.
 */
int proc_spawn(const conf_t *conf, const char *bin, const char *world_env, const char *world, const worker_env_t *env,
               const char *logfile, pid_t *pid, int *port, int *fb_port);

/** @brief The answer of proc_connect when the process was gone before it became ready. */
#define PROC_EXITED (-2)
/**
 * @brief Waits for the worker's socket to accept and its ready marker in the log, then opens its feedback port.
 *
 * PROC_EXITED means it could not bind its ports: they are picked free, then released, and another process can take
 * one in between, so a caller may spawn again on fresh ports. A process found exited is reaped.
 *
 * @param conf the configuration (ready_timeout_ms, the wait it allows)
 * @param pid the worker's process
 * @param port its command port
 * @param fb_port its feedback port
 * @param logfile its log file
 * @param[out] fb_fd the feedback socket, -1 when the call fails
 * @return the command socket; -1 when it never became ready, PROC_EXITED when the process was gone before it was
 * @pre conf, logfile and fb_fd are not NULL.
 */
int proc_connect(const conf_t *conf, pid_t pid, int port, int fb_port, const char *logfile, int *fb_fd);

/**
 * @brief Sends one command and reads one reply.
 *
 * A worker that does not answer within the timeout, or whose reply there is no memory for, is stopped as proc_term_wait
 * stops it (SIGTERM, then SIGKILL after PROC_TERM_GRACE_MS) and counts as having died with the command on the wire; it
 * is not reaped here.
 *
 * @param conf the configuration (rpc_timeout_ms, the timeout)
 * @param pid the worker's process
 * @param fd its command socket
 * @param msg the command line
 * @param[out] reply on RPC_OK, the reply, malloc'd; the caller frees it. Not written otherwise
 * @return RPC_OK, RPC_DIED or RPC_WAS_DEAD
 * @pre conf, msg and reply are not NULL.
 */
int proc_rpc(const conf_t *conf, pid_t pid, int fd, const char *msg, char **reply);

/**
 * @brief Whether `pid` has exited, without reaping it: the status stays for proc_exited.
 *
 * @param pid the process; 0 or below counts as dead
 * @return 1 when it has exited or is no child of ours, else 0
 */
int proc_dead(pid_t pid);

/**
 * @brief Reaps `pid` if it has exited.
 *
 * @param pid the process; 0 or below counts as exited
 * @param[out] status its wait status, written only when the call reaped it
 * @return 1 when it has exited (or is no child of ours), else 0
 * @pre status is not NULL.
 */
int proc_exited(pid_t pid, int *status);

/** How long a worker has to leave on SIGTERM before it is sent SIGKILL. Every worker holds a JACK client, and one that is
 * killed without closing it strands the mutexes of its metadata environment in jackd for good (a pool of a few hundred,
 * nine to a client), so the worker is always asked first and closes the client in its own SIGTERM path. A worker that
 * has not left in two seconds is wedged, and killing it is all that is left. */
#define PROC_TERM_GRACE_MS 2000

/**
 * @brief Ends a worker the way it can close its JACK client: SIGTERM, then SIGKILL once PROC_TERM_GRACE_MS has passed
 * with the process still there. The process is not reaped: its status stays for proc_exited.
 *
 * @param pid the process; 0 or below, or one that has already exited, does nothing
 */
void proc_term_wait(pid_t pid);

/**
 * @brief Whether proc_term_wait sent this process a signal: the daemon ended it, it did not die of its own. A worker
 * that exits on SIGTERM leaves with status 0, which looks like no crash at all, so the supervisor asks this before it
 * reads the death as one that blames the last verb. Asking clears the answer, and the process is reaped after.
 *
 * @param pid the process
 * @return 1 when the daemon stopped it, 0 when not
 */
int proc_stopped_by_us(pid_t pid);

/**
 * @brief Stops a worker as proc_term_wait does, and reaps it.
 *
 * @param pid the process; 0 or below does nothing
 */
void proc_stop(pid_t pid);

/**
 * @brief Applies the cpu list and the nice value of `env` to every thread of the process.
 *
 * @param pid the process
 * @param env the environment; a field that leaves things alone is skipped, and so is a cpu list that does not parse
 * @pre env is not NULL.
 */
void proc_apply_env(pid_t pid, const worker_env_t *env);

/**
 * @brief Logs on stderr a nice of `env` that the worker `pid` does not have.
 *
 * setpriority is refused to a process without privilege that lowers a nice below its own.
 *
 * @param pid the process
 * @param env the environment
 * @pre env is not NULL.
 */
void proc_env_report(pid_t pid, const worker_env_t *env);

/**
 * @brief A function that reads the version the data of `bundle` gives the plugin `uri`.
 *
 * The version is the plugin's lv2:minorVersion and lv2:microVersion; proc_find_lv2_bundle sets both to 0 before the
 * call, so one that is not stated may be left alone.
 *
 * @param bundle the bundle's directory
 * @param uri the plugin's uri
 * @param[out] minor the minor version
 * @param[out] micro the micro version
 */
typedef void (*proc_lv2_version_fn)(const char *bundle, const char *uri, long *minor, long *micro);

/**
 * @brief The bundle of LV2_PATH that is the plugin `uri`, by plugin-db's declared rule (PLUGIN_DB_BUNDLE_RULES,
 *        newest-version).
 *
 * Of the bundles whose manifest realises it (or, when none does, that name it), the highest version `version` reads
 * (none read, NULL, is all of version 0), and of equal versions the first in the path, each directory's bundles in
 * byte order of their names. A bundle found realising the plugin is remembered by search path and uri, and answered
 * again with only its manifest read while no directory of the path has changed.
 *
 * @param lv2_path the search path
 * @param uri the plugin's uri
 * @param version reads a bundle's version, or NULL for none
 * @return the bundle's directory, malloc'd; NULL if none, or when memory ran out
 * @pre lv2_path and uri are not NULL.
 * @note Not thread-safe: the remembered bundles have no lock; the daemon calls it on its main thread only.
 */
char *proc_find_lv2_bundle(const char *lv2_path, const char *uri, proc_lv2_version_fn version);
/**
 * @brief Hands every data bundle of the plugin `uri` to `fn`, until `fn` answers non-zero.
 *
 * A data bundle is a bundle of LV2_PATH whose manifest names `uri` and holds no binary (a preset bundle, the user's
 * or one a distribution ships, a MOD GUI). The walk is remembered by search path and uri, and while no directory of
 * the path has changed since (no bundle added or removed) the bundles it found are handed on again with no manifest
 * read.
 *
 * @param lv2_path the search path
 * @param uri the plugin's uri
 * @param fn called for each bundle with `ctx` and the bundle's directory; non-zero stops the walk
 * @param ctx handed to `fn`
 * @return how many bundles, or -1 when stopped or short of memory
 * @pre lv2_path, uri and fn are not NULL.
 * @note Not thread-safe: the remembered walks have no lock; the daemon calls it on its main thread only.
 */
int proc_lv2_preset_bundles(const char *lv2_path, const char *uri, int (*fn)(void *ctx, const char *bundle), void *ctx);
/** @brief How many manifests the lookups have read: what a test counts to see the path not walked again. */
extern unsigned long proc_manifest_reads;

/**
 * @brief Whether `bin` is executable, by path or on PATH.
 *
 * @param bin the program; a name with a slash is a path
 * @return non-zero when it is
 * @pre bin is not NULL.
 */
int proc_have_binary(const char *bin);

/**
 * @brief The monotonic clock, in milliseconds.
 *
 * @return the time
 */
int64_t proc_now_ms(void);

/**
 * @brief utime and stime of the text of /proc/\<pid\>/stat, in clock ticks.
 *
 * They are read from the fields after the last ')', since the command name before it may hold spaces and parentheses.
 *
 * @param text the text of /proc/\<pid\>/stat
 * @param[out] utime the user time; may be written when the call fails
 * @param[out] stime the system time, written on 0 only
 * @return 0, or -1 when the text is not what the kernel writes
 * @pre No argument is NULL.
 */
int proc_parse_stat(const char *text, long long *utime, long long *stime);
/**
 * @brief The Pss line of the text of /proc/\<pid\>/smaps_rollup, in kB.
 *
 * @param text the text of /proc/\<pid\>/smaps_rollup
 * @param[out] kb the value, written on 0 only
 * @return 0, or -1 when there is no Pss line in the form the kernel writes
 * @pre kb is not NULL.
 */
int proc_parse_pss(const char *text, long long *kb);
/**
 * @brief Seconds of CPU (utime + stime) the process has used.
 *
 * @param pid the process
 * @param[out] seconds the CPU time, written on 0 only
 * @return 0, or -1 when the process or the file is gone, or its text is not what the kernel writes
 * @pre seconds is not NULL.
 */
int proc_cpu_seconds(pid_t pid, double *seconds);
/**
 * @brief The Pss of the process, in kB.
 *
 * @param pid the process
 * @param[out] kb the value, written on 0 only
 * @return 0, or -1 when the process or the file is gone, or it holds no Pss line
 * @pre kb is not NULL.
 */
int proc_pss_kb(pid_t pid, long long *kb);

#endif
