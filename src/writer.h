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
 * @brief The writer: one thread that writes the daemon's files on disk, first in first out.
 *
 * The files are the history, the pin store and its accepted list, and the descriptors. The command loop hands over a
 * copy of the bytes and goes on, so it never waits on the disk; nothing the loop changes afterwards is read by the
 * writer. docs/durable-writes.md has the rules and why. The queue is shared with the thread under a lock; the groups
 * of the verbs are the loop's own, with no lock, so every function but writer_busy is for the loop's thread only.
 */

#ifndef WRITER_H
#define WRITER_H

#include <stddef.h>

/**
 * @brief A function the loop is told the end of a write with.
 *
 * It is called on the loop's thread, in the order the writes ended.
 *
 * @param arg the pointer the write was handed over with
 * @param err 0, or the errno of the step that failed
 */
typedef void (*writer_done_fn)(void *arg, int err);

/**
 * @brief The flag of writer_put that marks a periodic snapshot.
 *
 * While such a write waits as the last write of its file, a later one of the same file replaces its bytes: the latest
 * wins, and the later write's own done is not called.
 */
#define WRITER_COALESCE 1

/** @brief The most writes that wait; a write past it is refused. */
#define WRITER_JOBS_MAX  64
/** @brief The most bytes the waiting writes hold; a write past it is refused. */
#define WRITER_BYTES_MAX (64u << 20)

/**
 * @brief Starts the writer thread.
 *
 * Before it starts, and after writer_finish, a write is done at once on the caller's thread. The thread blocks every
 * signal. A second call while the thread runs does nothing.
 *
 * @return 0, or -1, with the reason on stderr, when the thread could not be started
 * @note Not thread-safe: call on the loop's thread.
 */
int writer_start(void);

/**
 * @brief Drains what is queued, says each end, and stops the thread.
 *
 * @note Not thread-safe: call on the loop's thread.
 */
void writer_finish(void);

/**
 * @brief Hands over bytes to be written as the whole of path.
 *
 * The writer owns bytes from here, also on a refusal. Inside a verb that promises its writes (writer_verb_begin) the
 * write joins the verb's group, and a refusal marks the verb refused. A write that fails is said on stderr.
 *
 * @param path the file; copied
 * @param bytes the contents, malloc'd; the writer frees them
 * @param len their length
 * @param flags 0 or WRITER_COALESCE
 * @param done told when the write ends, or NULL
 * @param arg handed to done
 * @param what the line said when the write fails, after "plugin-hostd: can't write ": a printf format of the path and
 *        the reason, in that order (two \%s), as "the history \%s: \%s; it is kept in memory"; NULL for "\<path\>:
 *        \<reason\>"
 * @return 0, or -1 when the queue is full (WRITER_JOBS_MAX or WRITER_BYTES_MAX) or there is no memory for the write,
 *         in which case nothing is written and done is not called
 * @pre path is not NULL; what is not copied and stays valid until the write ends (a string literal).
 * @note Not thread-safe: call on the loop's thread.
 */
int writer_put(const char *path, char *bytes, size_t len, int flags, writer_done_fn done, void *arg, const char *what);

/**
 * @brief Hands over a file to be synced and renamed into place; final is kept if it is there.
 *
 * The same refusal and the same end as writer_put.
 *
 * @param tmp the file to place; the name is copied
 * @param final where it goes; copied
 * @param done told when the write ends, or NULL
 * @param arg handed to done
 * @param what the line said when it fails, as for writer_put
 * @return 0, or -1 as writer_put
 * @pre tmp and final are not NULL; what stays valid until the write ends.
 * @note Not thread-safe: call on the loop's thread.
 */
int writer_place(const char *tmp, const char *final, writer_done_fn done, void *arg, const char *what);

/**
 * @brief Tells each done the ends the thread has reached since the last call.
 *
 * A write that failed is said on stderr here, and its group takes its error.
 *
 * @note Not thread-safe: call on the loop's thread.
 */
void writer_poll(void);

/**
 * @brief Whether writes were handed over whose end the loop has not been told yet (writer_poll).
 *
 * @return non-zero when there are
 * @note Thread-safe: it reads the queue under the writer's lock.
 */
int writer_busy(void);

/**
 * @brief Blocks the loop until nothing waits, then says the ends as writer_poll.
 *
 * @note Not thread-safe: call on the loop's thread.
 */
void writer_drain(void);

/**
 * @brief Begins a verb: the writes a verb that promises them hands over until writer_verb_end are one group.
 *
 * @param promises non-zero when the verb promises its writes; zero makes no group
 * @note Not thread-safe: call on the loop's thread.
 */
void writer_verb_begin(int promises);
/**
 * @brief Ends the group of the verb begun by writer_verb_begin.
 *
 * @return 0 when the verb handed over nothing or promises nothing (its writes are best effort, said on failure, and its
 *         reply does not wait), -1 when one of its writes was refused, else the group, whose state writer_group asks
 * @note Not thread-safe: call on the loop's thread.
 */
int writer_verb_end(void);

/**
 * @brief The state of a group.
 *
 * @param group the group writer_verb_end answered
 * @param[out] err the errno of its first failure, 0 when all landed, a write still waits or the group is unknown
 * @return 0 while a write of the group waits, else 1; a group answered 1 is forgotten, and an unknown group answers 1
 * @pre err is not NULL.
 * @note Not thread-safe: call on the loop's thread.
 */
int writer_group(int group, int *err);

/**
 * @brief Forgets a group nobody will ask about again (its controller is gone), once its writes end.
 *
 * @param group the group; an unknown one does nothing
 * @note Not thread-safe: call on the loop's thread.
 */
void writer_forget(int group);

#endif
