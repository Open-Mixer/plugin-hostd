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

/** @file names.h
 * @brief The declarations of names.h.
 */

#ifndef NAMES_H
#define NAMES_H

#include <stdlib.h>
#include <string.h>

/** @brief a list of names: the files a format loads for a plugin; all zero is the empty list */
typedef struct NAMES_T {
    /** the names, each allocated, n of them */
    char **name;
    /** how many names the list holds */
    int n;
} names_t;

/** @brief adds a copy of a name to a list
 *
 * @param[in,out] names the list.
 * @param name the name, NUL-terminated; the list keeps a copy.
 * @return 0, or -1 with the list as it was when memory runs out.
 */
static inline int names_add(names_t *names, const char *name)
{
    char **grown = realloc(names->name, (names->n + 1) * sizeof(char *));
    char *copy;

    if (!grown)
        return -1;
    names->name = grown;
    copy = strdup(name);
    if (!copy)
        return -1;
    names->name[names->n++] = copy;
    return 0;
}

/** @brief whether a list holds a name
 *
 * @param names the list.
 * @param name the name, NUL-terminated.
 * @return 1 when the list holds it, 0 otherwise.
 */
static inline int names_has(const names_t *names, const char *name)
{
    int n;

    for (n = 0; n < names->n; n++)
        if (!strcmp(names->name[n], name))
            return 1;
    return 0;
}

/** @brief frees a list's names and leaves it empty
 *
 * @param[in,out] names the list, all zero after.
 */
static inline void names_free(names_t *names)
{
    while (names->n)
        free(names->name[--names->n]);
    free(names->name);
    names->name = NULL;
}

#endif
