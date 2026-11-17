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
 * @brief The declarations of verbs.h.
 */

#ifndef VERBS_H
#define VERBS_H

#include <string.h>

#include <utils.h>

/**
 * @brief The length of the verb of a command format: mod-host.h declares each command as a format; its verb is the first
 * word of the format.
 * @param format the format
 * @return the length of its first word
 */
static inline int verb_len(const char *format)
{
    return (int)strcspn(format, " ");
}

/**
 * @brief Whether the first word of text, a token or a whole command line, is the verb of format.
 * @param text the token or the line
 * @param format the command format
 * @return non-zero when it is
 */
static inline int verb_is(const char *text, const char *format)
{
    size_t n = strcspn(format, " ");

    return strcspn(text, " \t") == n && !strncmp(text, format, n);
}

/**
 * @brief The socket's receive callback: one message in, one reply out.
 *
 * While an answer waits, the command is queued behind it, or refused in its place when too many wait.
 * @param msg the message; its sender and data are read
 */
void verbs_receive(msg_t *msg);

/** @brief Set by QUIT: the main loop stops. */
extern volatile int g_quitting;

/**
 * @brief The answers that wait, sent as far as they can go: a reply whose writes landed, then the commands queued behind it.
 */
void verbs_flush(void);

/**
 * @brief Whether an answer waits.
 * @return non-zero when one does
 */
int verbs_waiting(void);

/**
 * @brief The controller is gone: what waited for it is forgotten.
 */
void verbs_drop(void);

#endif
