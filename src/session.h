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

/** @file session.h
 * @brief The controller's session: what its last hello granted of the extensions tags, errors and seq.
 *
 * As plugin-hostd-protocol's doc/protocol.md, Sessions. A controller that never sends hello is answered as mod-host
 * answers it. What is granted and the feedback sequence number are read and written atomically, so the relay's thread
 * may number the feedback lines while the main thread answers.
 */

#ifndef SESSION_H
#define SESSION_H

#include <stddef.h>

/** @brief Starts the session of a new controller: nothing is granted, and the feedback sequence starts again. */
void session_reset(void);

/**
 * @brief Answers hello \<version\> [\<extension\> ...] and records what the session is granted.
 *
 * Each word after the version that names an extension of the protocol grants it, and an extension not named is no
 * longer granted; the feedback sequence starts again. A refused hello changes nothing.
 *
 * @param tok the words of the line, the verb first
 * @param ntok the number of words
 * @return "resp 0 \<protocol version\>" and the extensions granted, or "resp -902" (invalid-operation) for a version
 *         that is not a number of 1 or above; malloc'd; NULL when there is no memory, nothing changed
 * @pre tok is not NULL and ntok is at least 2.
 */
char *session_hello(char **tok, int ntok);

/**
 * @brief The length of the request tag a line starts with ("@" and tag characters, then a space or the end).
 *
 * @param line the request line
 * @return the length, 0 when the line has none or the session was not granted tags
 * @pre line is not NULL.
 */
size_t session_tag_len(const char *line);

/**
 * @brief The text of an answer as the session sends it.
 *
 * Under errors, a refusal that is "resp \<code\>" alone is followed by the error word the protocol declares for the
 * code. Under tags, the answer goes after the tag (its first tag_len bytes) and one space. With no memory for the word
 * or the tag the answer goes out without it.
 *
 * @param text the answer, malloc'd, or NULL; the call takes it
 * @param tag the request's tag, or NULL for none
 * @param tag_len the length of the tag
 * @return the line, malloc'd, the caller frees it; NULL when text is NULL
 */
char *session_answer(char *text, const char *tag, size_t tag_len);

/**
 * @brief Writes what a feedback line starts with: "#\<n\> " under seq, else nothing.
 *
 * Each call under seq takes the next number, from 1 after a hello or a reset.
 *
 * @param[out] buf where it is written, NUL-terminated
 * @param size the room in buf
 * @return its length, as snprintf counts it: 0 when seq is not granted
 * @pre buf is not NULL and size is at least 1.
 */
size_t session_feedback_prefix(char *buf, size_t size);

#endif
