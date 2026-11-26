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

#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "domain_words.h"
#include "probe_words.h"

int probe_words_open(const char *dirs, probe_words *w, char *why, size_t n)
{
    static const struct
    {
        const char *item;
        size_t offset, count;
    } lists[] = {
        { "PROBE_REASONS", offsetof(probe_words, reason), PROBE_REASON_COUNT },
        { "PROBE_OUTCOMES", offsetof(probe_words, outcome), PROBE_OUTCOME_COUNT },
        { "PROBE_STEPS", offsetof(probe_words, step), PROBE_STEP_COUNT },
        { "PROBE_SIGNALS", offsetof(probe_words, signal), OMX_PROBE_SIGNALS_COUNT },
    };
    size_t b, i;
    int rc;

    memset(w, 0, sizeof(*w));
    if ((rc = domain_words_open(PROBE_DOMAIN, dirs, &w->domain, why, n)) != 0)
        return rc;
    for (b = 0; b < sizeof(lists) / sizeof(*lists); b++)
    {
        const char **list, **slot = (const char **)((char *)w + lists[b].offset);
        size_t count;

        if ((rc = domain_words_list(w->domain, lists[b].item, &list, &count)) != 0)
        {
            snprintf(why, n, "%s: the domain " PROBE_DOMAIN " has no item %s", omx_domain_code(rc), lists[b].item);
            probe_words_close(w);
            return rc;
        }
        if (count != lists[b].count)
        {
            snprintf(why, n, "%s: %s of the domain " PROBE_DOMAIN " has %zu words, the probe writes %zu",
                     omx_domain_code(OMX_CONTRACT_CODE_ITEM_UNKNOWN), lists[b].item, count, lists[b].count);
            free(list);
            probe_words_close(w);
            return OMX_CONTRACT_CODE_ITEM_UNKNOWN;
        }
        for (i = 0; i < count; i++)
            slot[i] = list[i];
        free(list);
    }
    return 0;
}

void probe_words_close(probe_words *w)
{
    if (w->domain != NULL)
        omx_domain_close(w->domain);
    memset(w, 0, sizeof(*w));
}

const char *probe_signal_word(const probe_words *w, int sig)
{
    /* the signals the probe names a dead child's by: the operating system's number of each, and the domain's code of its word */
#define PROBE_SIGNAL_CASE(signo) \
    case signo: return w->signal[OMX_PROBE_SIGNALS_##signo];
    switch (sig)
    {
        PROBE_SIGNAL_CASE(SIGSEGV)
        PROBE_SIGNAL_CASE(SIGABRT)
        PROBE_SIGNAL_CASE(SIGBUS)
        PROBE_SIGNAL_CASE(SIGFPE)
        PROBE_SIGNAL_CASE(SIGILL)
        PROBE_SIGNAL_CASE(SIGKILL)
        PROBE_SIGNAL_CASE(SIGTERM)
        PROBE_SIGNAL_CASE(SIGXCPU)
        PROBE_SIGNAL_CASE(SIGXFSZ)
        PROBE_SIGNAL_CASE(SIGSYS)
        PROBE_SIGNAL_CASE(SIGPIPE)
        PROBE_SIGNAL_CASE(SIGINT)
        PROBE_SIGNAL_CASE(SIGHUP)
    default: return w->signal[OMX_PROBE_SIGNALS_SIGNAL];
    }
#undef PROBE_SIGNAL_CASE
}
