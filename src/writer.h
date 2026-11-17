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

/** @file writer.h
 * @brief The declarations of writer.h.
 */

#ifndef WRITER_H
#define WRITER_H

#include <stddef.h>

/* The daemon's files on disk (the history, the pin store and its accepted list, the descriptors) are written by one
 * thread of their own, first in first out, so the command loop never waits on the disk. The loop hands over a copy of
 * the bytes and goes on; nothing the loop changes afterwards is read by the writer. docs/durable-writes.md has the rules
 * and why. */

/**
 * @brief What the loop is told when a write ends: on the loop's thread, in the order the writes were handed over.
 * @param arg the pointer the write was handed over with
 * @param err 0, or the errno of the step that failed
 */
typedef void (*writer_done_fn)(void *arg, int err);

/** @brief Flag of writer_put: a periodic snapshot; while it waits it is replaced by a later one of the same file, the latest wins. */
#define WRITER_COALESCE 1

/** @brief At most this many writes wait; a write past it is refused. */
#define WRITER_JOBS_MAX  64
/** @brief The waiting writes hold at most this many bytes; a write past it is refused. */
#define WRITER_BYTES_MAX (64u << 20)

/**
 * @brief Starts the writer thread; before it starts, and after writer_finish, a write is done at once on the caller's thread.
 * @return 0, or -1 when the thread could not be started
 */
int writer_start(void);

/**
 * @brief Drains what is queued, says each end, and stops the thread.
 */
void writer_finish(void);

/**
 * @brief Writes bytes as the whole of path.
 *
 * The writer owns bytes (malloc'd) from here, also on a refusal.
 * @param path the file
 * @param bytes the contents, malloc'd
 * @param len their length
 * @param flags 0 or WRITER_COALESCE
 * @param done told when the write ends, or NULL
 * @param arg handed to done
 * @param what the line said when the write fails, after "plugin-hostd: can't write ": a format of the path and the
 *        reason, in that order (two %s), as "the history %s: %s; it is kept in memory"
 * @return 0, or -1 when the queue is full (WRITER_JOBS_MAX or WRITER_BYTES_MAX), in which case nothing is written and
 *         done is not called
 */
int writer_put(const char *path, char *bytes, size_t len, int flags, writer_done_fn done, void *arg, const char *what);

/**
 * @brief Syncs tmp and renames it to final; final is kept if it is there.
 *
 * The same refusal and the same end as writer_put.
 * @param tmp the file to place
 * @param final where it goes
 * @param done told when the write ends, or NULL
 * @param arg handed to done
 * @param what the line said when it fails, as for writer_put
 * @return 0, or -1 as writer_put
 */
int writer_place(const char *tmp, const char *final, writer_done_fn done, void *arg, const char *what);

/**
 * @brief On the loop: tells each done the ends the thread has reached since the last call.
 */
void writer_poll(void);

/**
 * @brief Whether writes were handed over whose end the loop has not been told yet (writer_poll).
 * @return non-zero when there are
 */
int writer_busy(void);

/**
 * @brief Blocks the loop until nothing waits (quit only), then says the ends.
 */
void writer_drain(void);

/**
 * @brief The writes a verb that promises them hands over are a group: begin before the verb, end after it.
 * @param promises non-zero when the verb promises its writes; zero makes no group
 */
void writer_verb_begin(int promises);
/**
 * @brief Ends the group of the verb begun by writer_verb_begin.
 * @return 0 when the verb handed over nothing or promises nothing (its writes are best effort, said on failure, and its
 *         reply does not wait), -1 when one of its writes was refused, else the group, whose state writer_group asks
 */
int writer_verb_end(void);

/**
 * @brief The state of a group.
 * @param group the group writer_verb_end answered
 * @param[out] err the errno of its first failure, 0 when all landed or none is known
 * @return 0 while a write of the group waits, else 1; a group answered 1 is forgotten, and an unknown group answers 1
 */
int writer_group(int group, int *err);

/**
 * @brief Forgets a group nobody will ask about again (its controller is gone), once its writes end.
 * @param group the group
 */
void writer_forget(int group);

#endif
