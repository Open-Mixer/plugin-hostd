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

/** @file history.h
 * @brief The running history: what each plugin did on this machine, per plugin, per binary and per host class.
 *
 * The grouping-planner design note, The history record. The file holds one line per \<uri\> \<binary digest\> \<host
 * class\>: history \<uri\> \<digest\> \<class\> key=value ...; the keys are PLUGIN_HOSTD_HISTORY_KEYS
 * (data/history.json), the first line PHD_HISTORY_HEADER. It is written only by the daemon, through the writer,
 * atomically, mode 0600, and is local to the machine. Nothing here reads a clock or a /proc file: the caller says what
 * the window measured and what time it is. The history is a table of globals with no lock: unless a function says it
 * reads only its arguments, it is for the daemon's main thread only.
 */

#ifndef HISTORY_H
#define HISTORY_H

#include <stddef.h>

#include <plugin-db/pin.h>

/** @brief The record of one plugin binary on one host class: what one line of the history holds. */
typedef struct HISTORY_REC_T {
    char *uri;                              /**< the plugin's uri, malloc'd */
    char digest[PHD_SHA256_HEX_LEN + 1];    /**< the digest of its binary, in hex */
    char *klass;                            /**< the host class, malloc'd */
    long long first,                        /**< when it was first counted, UTC seconds */
        last,                               /**< when it was last counted, UTC seconds */
        last_crash,                         /**< its last crash alone, UTC seconds */
        last_crash_grouped;                 /**< its last crash in a group, UTC seconds */
    long long windows_solo,                 /**< the windows it ran alone */
        windows_grouped;                    /**< the windows it ran in a group */
    long long xrun_windows_solo,            /**< the windows alone in which an xrun was counted */
        xrun_windows_grouped;               /**< the windows in a group in which an xrun was counted */
    long long crashes_solo,                 /**< the worker deaths blamed on it while alone */
        crashes_grouped,                    /**< the worker deaths blamed on it while in a group */
        restarts_grouped,                   /**< the deaths of its group that were not its own fault */
        quarantines;                        /**< the times it was quarantined */
    double cpu_p95_solo,                    /**< its estimated 95th percentile of CPU alone, percent of one core */
        cpu_max_solo;                       /**< the most CPU a window alone used, percent of one core */
    double pss_mb_solo;                     /**< the most Pss a window alone held, MiB */
} history_rec_t;

/**
 * @brief Starts the history: reads its file and sets the class and the save interval.
 *
 * A history started before is finished first, as history_finish. A missing file is an empty history. A file that
 * cannot be read, or whose first line is not PHD_HISTORY_HEADER (an unknown version among them), blocks reading and
 * saving it: stderr says why, the history is unavailable, and the file is not touched. With no file name to use (no
 * `file`, $XDG_STATE_HOME or $HOME) the history is unavailable as well. A line outside the grammar, a second line of
 * one binary and class, or a line with a key this version does not know, is kept verbatim by every save and not read.
 *
 * @param file the history file; empty is $XDG_STATE_HOME/plugin-hostd/history, else
 *        $HOME/.local/state/plugin-hostd/history
 * @param klass the host class this daemon records under; copied
 * @param save_s the least seconds between two saves
 * @return always 0: the daemon runs without a history
 * @pre file and klass are not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
int history_init(const char *file, const char *klass, int save_s);

/**
 * @brief Whether the history is started and not blocked: it is read and saved.
 *
 * @return non-zero when it is
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
int history_available(void);

/**
 * @brief The record of a plugin binary on this host class.
 *
 * @param uri the plugin's uri, or NULL
 * @param digest the digest of its binary, or NULL
 * @return the record, owned by the history and valid until the next call that adds or clears a record; NULL when there
 *         is none or the history is unavailable
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
const history_rec_t *history_find(const char *uri, const char *digest);

/**
 * @brief Counts a closed window of the worker that ran the plugin.
 *
 * A grouped window counts the window and whether it had an xrun. A window alone also folds its CPU into the estimate
 * of the 95th percentile and the maximum, and keeps the largest Pss. The record is made when there is none; nothing is
 * counted when the history is unavailable, the uri is empty or holds a quote or a line end, the digest is not a
 * SHA-256 in hex, or memory ran out.
 *
 * @param uri the plugin's uri
 * @param digest the digest of its binary
 * @param grouped 0 when it ran alone, non-zero in a group of two or more
 * @param cpu_pct its CPU as percent of one core over the window; a value that is not 0 or above counts as 0
 * @param pss_mb its Pss in MiB
 * @param xruns the xruns JACK counted in the window (the worker's report; 0 when it makes none)
 * @param now the time, UTC seconds
 * @pre digest is not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_window(const char *uri, const char *digest, int grouped, double cpu_pct, double pss_mb, long xruns,
                    long long now);

/**
 * @brief Counts a worker death the daemon blamed on the plugin.
 *
 * Nothing is counted in the cases history_window names.
 *
 * @param uri the plugin's uri
 * @param digest the digest of its binary
 * @param grouped 0 when it ran alone, non-zero in a group
 * @param now the time, UTC seconds; it becomes the record's last crash, alone or grouped
 * @pre digest is not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_crash(const char *uri, const char *digest, int grouped, long long now);
/**
 * @brief Counts a death of the plugin's group that was not its own fault.
 *
 * Nothing is counted in the cases history_window names.
 *
 * @param uri the plugin's uri
 * @param digest the digest of its binary
 * @param grouped non-zero in a group; with 0 nothing is counted
 * @param now the time, UTC seconds
 * @pre digest is not NULL when grouped is not 0.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_restart(const char *uri, const char *digest, int grouped, long long now);
/**
 * @brief Counts a quarantine of the plugin.
 *
 * Nothing is counted in the cases history_window names.
 *
 * @param uri the plugin's uri
 * @param digest the digest of its binary
 * @param now the time, UTC seconds
 * @pre digest is not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_quarantine(const char *uri, const char *digest, long long now);

/**
 * @brief Whether a record says crashed: the daemon's rule, which plugin-qualify's adjust --history copies.
 *
 * @param rec the record
 * @param now the time, UTC seconds
 * @return non-zero when it counts a crash, alone or grouped, and the later of its two last crashes is within
 *         PHD_HISTORY_KEEP_DAYS of `now`
 * @pre rec is not NULL.
 * @note It reads only its arguments.
 */
int history_crashed(const history_rec_t *rec, long long now);
/**
 * @brief Whether a record says raises_xruns: the daemon's rule, which plugin-qualify's adjust --history copies.
 *
 * @param rec the record
 * @return non-zero when it has PHD_HISTORY_MIN_WINDOWS grouped windows and its share of xrun windows grouped exceeds
 *         its share alone by more than PHD_HISTORY_XRUN_MARGIN_PCT percentage points, or exceeds that percent when it
 *         never ran alone
 * @pre rec is not NULL.
 * @note It reads only its arguments.
 */
int history_raises_xruns(const history_rec_t *rec);

/**
 * @brief The summary history_get answers for a plugin binary on this host class.
 *
 * One word: "digest=\<digest\>,class=\<class\>,crashed=\<0|1\>,raises_xruns=\<0|1\>,key=value,..." with every key of
 * the record, crashed and raises_xruns as history_crashed and history_raises_xruns give them.
 *
 * @param uri the plugin's uri
 * @param digest the digest of its binary
 * @param now the time, UTC seconds
 * @return the summary, malloc'd; NULL for no record, or when memory ran out
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
char *history_summary(const char *uri, const char *digest, long long now);

/**
 * @brief The idle tick: hands the history to the writer when it changed and `save_s` have passed.
 *
 * The seconds are counted since the last save, or since the first tick for the first one. Nothing is done while the
 * history is unavailable.
 *
 * @param now the time in seconds, of any steady origin
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_tick(long long now);

/**
 * @brief Clears the lines of one uri, or all of them, at once, and hands the history to the writer (history_clear).
 *
 * The lines of a uri are every binary and class of it, and a held line that names it.
 *
 * @param uri the plugin's uri, or PHD_WORD_ALL
 * @return 0, also when nothing was cleared or the writer refused the write; -1 when the history is unavailable
 * @pre uri is not NULL.
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
int history_clear(const char *uri);

/**
 * @brief Hands the history to the writer now if it changed, and frees it.
 *
 * The history is not started after it. A history never started is only freed.
 *
 * @note Not thread-safe: the history has no lock; call on the daemon's main thread only.
 */
void history_finish(void);

/**
 * @brief The line of a record, "history \<uri\> \<digest\> \<class\> key=value ...\\n"; for the tests of the grammar.
 *
 * A uri with a blank or a quote in it is written in quotes.
 *
 * @param rec the record
 * @return the line, malloc'd; NULL on a failure of memory
 * @pre rec is not NULL, and neither are its uri and klass.
 * @note It reads only its arguments.
 */
char *history_line(const history_rec_t *rec);

#endif
