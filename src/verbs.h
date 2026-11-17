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

/** @file verbs.h
 * @brief The daemon's command loop: one message of the controller in, its reply out, and the answers that wait.
 *
 * verb_len and verb_is keep no state. The other functions share the queue of waiting answers, which has no lock: they
 * are for the daemon's main thread only.
 */

#ifndef VERBS_H
#define VERBS_H

#include <string.h>

#include <utils.h>

/**
 * @brief The length of the verb of a command format.
 *
 * mod-host.h declares each command as a format; its verb is the first word of the format.
 *
 * @param format the format
 * @return the length of its first word, up to the first space
 * @pre format is not NULL.
 */
static inline int verb_len(const char *format)
{
    return (int)strcspn(format, " ");
}

/**
 * @brief Whether the first word of text, a token or a whole command line, is the verb of format.
 *
 * @param text the token or the line; its first word ends at a space or a tab
 * @param format the command format
 * @return non-zero when it is
 * @pre Neither argument is NULL.
 */
static inline int verb_is(const char *text, const char *format)
{
    size_t n = strcspn(format, " ");

    return strcspn(text, " \t") == n && !strncmp(text, format, n);
}

/**
 * @brief Runs one message of the controller and sends its reply: the socket's receive callback.
 *
 * While an answer waits, the command is queued behind it, or refused with a memory refusal in its place when too many
 * wait or there is no memory to queue it; with no memory to count that refusal either, it is dropped unanswered. A
 * command that reads the daemon's own files back is queued while a write of the writer waits. The reply of a verb
 * that promises its writes waits until they have landed.
 *
 * @param msg the message; its sender and data are read
 * @pre msg is not NULL.
 * @note Not thread-safe: the queue has no lock; call on the daemon's main thread only.
 */
void verbs_receive(msg_t *msg);

/** @brief The flag QUIT sets, which stops the main loop. */
extern volatile int g_quitting;

/**
 * @brief Sends the answers that wait, as far as they can go.
 *
 * From the front of the queue: a reply whose writes have ended is sent, as invalid-operation when a write failed and
 * the verb had succeeded; a queued command is run; the refusals counted in its place are sent. It stops at a reply
 * whose writes still wait, and at a command that reads files while a write waits.
 *
 * @note Not thread-safe: the queue has no lock; call on the daemon's main thread only.
 */
void verbs_flush(void);

/**
 * @brief Whether an answer or a queued command waits.
 *
 * @return non-zero when one does
 * @note Not thread-safe: the queue has no lock; call on the daemon's main thread only.
 */
int verbs_waiting(void);

/**
 * @brief Forgets what waited for a controller that is gone.
 *
 * Every waiting answer and queued command is freed unsent, and the writer is told to forget each answer's group.
 *
 * @note Not thread-safe: the queue has no lock; call on the daemon's main thread only.
 */
void verbs_drop(void);

#endif
