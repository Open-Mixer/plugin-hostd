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
#include "qualification_words.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int qw_open(const char *dirs, omx_domain **out, char *why, size_t n)
{
    omx_domain_error err = { 0 };
    int rc;

    *out = NULL;
    if (dirs == NULL || *dirs == '\0')
        rc = omx_domain_open(QW_DOMAIN, QW_FLOOR, out, &err);
    else
    {
        const char *p = dirs;

        rc = OMX_CONTRACT_CODE_DIR_ABSENT;
        while (*p != '\0' && rc == OMX_CONTRACT_CODE_DIR_ABSENT)
        {
            const char *end = strchr(p, ':');
            size_t len = end ? (size_t)(end - p) : strlen(p);
            char dir[4096];

            if (len > 0 && len < sizeof(dir))
            {
                memcpy(dir, p, len);
                dir[len] = '\0';
                rc = omx_domain_open_at(dir, QW_DOMAIN, QW_FLOOR, out, &err);
            }
            p += len + (end != NULL);
        }
        if (rc == OMX_CONTRACT_CODE_DIR_ABSENT)
        {
            err.code = omx_domain_code(rc);
            snprintf(err.message, sizeof(err.message), "The domain " QW_DOMAIN " is in none of %s.", dirs);
        }
    }
    if (rc != 0)
        snprintf(why, n, "%s: %s", err.code ? err.code : "contract.file.invalid", err.message);
    return rc;
}

const char *qw_word(const omx_domain *d, const char *item, const char *key)
{
    int i, count = omx_domain_word_count(d, item);

    for (i = 0; i < count; i++)
    {
        omx_domain_word_info w;

        if (omx_domain_word_at(d, item, i, &w) == 0 && w.title != NULL && !strcmp(w.title, key))
            return w.word;
    }
    return NULL;
}

int qw_words(const omx_domain *d, const char *item, const char ***out, size_t *count)
{
    int i, n = omx_domain_word_count(d, item);
    const char **list;

    *out = NULL;
    *count = 0;
    if (n < 0)
        return OMX_CONTRACT_CODE_ITEM_UNKNOWN;
    list = calloc((size_t)n + 1, sizeof(*list));
    if (list == NULL)
        return OMX_CONTRACT_CODE_FILE_INVALID;
    for (i = 0; i < n; i++)
    {
        omx_domain_word_info w;
        int rc = omx_domain_word_at(d, item, i, &w);

        if (rc != 0)
        {
            free(list);
            return rc;
        }
        list[i] = w.word;
    }
    *out = list;
    *count = (size_t)n;
    return 0;
}
