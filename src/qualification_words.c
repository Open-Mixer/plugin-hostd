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

#include "domain_words.h"

#include <string.h>

int qw_open(const char *dirs, omx_domain **out, char *why, size_t n)
{
    return domain_words_open(QW_DOMAIN, dirs, out, why, n);
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
