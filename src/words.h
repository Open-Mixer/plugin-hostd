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

/** @file words.h
 * @brief The declarations of words.h.
 */

#ifndef WORDS_H
#define WORDS_H

#include <stddef.h>

/* The words of a line, as the protocol reads them (plugin-hostd-protocol, grammar: word = quoted / bare-word): split at
 * spaces and tabs, a word in double quotes may hold spaces and has \" for a quote, and the quotes are not part of the
 * value. The reading is the protocol library's (strarr_split); this only makes tabs and line ends spaces first. */

/** @brief cuts a line into its words, in place
 *
 * Leading and trailing blanks are no words.
 *
 * @param[in,out] line the line, NUL-terminated; it is changed, and the words point into it.
 * @param[out] tok the words, tok[0] to tok[n - 1].
 * @param max the most words read, the room of tok.
 * @return how many words were read; -1 when there is no memory.
 */
int words_read(char *line, char **tok, int max);

/** @brief whether a word has to be quoted to be read back as one
 *
 * @param word the word, NUL-terminated.
 * @return 1 when it is empty, or holds a blank or a quote; 0 otherwise.
 */
int words_need_quotes(const char *word);

/** @brief a word as it is written in a line: itself, or in quotes with \\" for a quote when it needs them
 *
 * @param word the word, NUL-terminated.
 * @param[out] buf where it is written, NUL-terminated, cut when buf is too small.
 * @param size the size of buf, in bytes.
 * @return the length it needs, in bytes, its NUL excluded.
 */
size_t words_write(const char *word, char *buf, size_t size);

#endif
