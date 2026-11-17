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
 * @brief The declarations of session.h.
 */

#ifndef SESSION_H
#define SESSION_H

#include <stddef.h>

/* The controller's session (plugin-hostd-protocol, doc/protocol.md, Sessions): what its last hello granted of the
 * extensions tags, errors and seq. A controller that never sends hello is answered as mod-host answers it. */

/**
 * @brief A new controller: nothing is granted, and the feedback sequence starts again.
 */
void session_reset(void);

/**
 * @brief hello \<version> [\<extension> ...]: records what the session is granted.
 * @param tok the words of the line, the verb first
 * @param ntok the number of words
 * @return the answer, malloc'd; NULL when there is no memory
 */
char *session_hello(char **tok, int ntok);

/**
 * @brief The length of the request tag a line starts with ("@" and tag characters, then a space or the end).
 * @param line the request line
 * @return the length, 0 when the line has none or the session was not granted tags
 */
size_t session_tag_len(const char *line);

/**
 * @brief The text of an answer, taken and freed, as the session sends it: a refusal alone followed by its error word
 * under errors, after the tag (its first tag_len bytes) and one space under tags.
 * @param text the answer, malloc'd; the call takes it
 * @param tag the request's tag, or NULL for none
 * @param tag_len the length of the tag
 * @return the line, malloc'd; NULL when text is NULL. With no memory for the tag the answer goes out without it.
 */
char *session_answer(char *text, const char *tag, size_t tag_len);

/**
 * @brief What a feedback line starts with: "#\<n> " under seq, else nothing.
 * @param buf where it is written, NUL-terminated
 * @param size the room in buf
 * @return its length
 */
size_t session_feedback_prefix(char *buf, size_t size);

#endif
