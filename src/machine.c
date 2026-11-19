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
#include <sys/utsname.h>
#include <unistd.h>

#include "domain_words.h"
#include "machine.h"

int machine_words_open(const char *dirs, machine_words *w, char *why, size_t n)
{
    static const struct
    {
        const char *item;
        size_t offset, count;
    } bands[] = {
        { "MACHINE_CORE_BANDS", offsetof(machine_words, core), MACHINE_CORE_BAND_COUNT },
        { "MACHINE_CLOCK_BANDS", offsetof(machine_words, clock), MACHINE_CLOCK_BAND_COUNT },
        { "MACHINE_FAMILIES", offsetof(machine_words, family), MACHINE_FAMILY_COUNT },
    };
    size_t b, i;
    int rc;

    memset(w, 0, sizeof(*w));
    if ((rc = domain_words_open(MACHINE_DOMAIN, MACHINE_FLOOR, dirs, &w->domain, why, n)) != 0)
        return rc;
    for (b = 0; b < sizeof(bands) / sizeof(*bands); b++)
    {
        const char **list, **slot = (const char **)((char *)w + bands[b].offset);
        size_t count;

        if ((rc = domain_words_list(w->domain, bands[b].item, &list, &count)) != 0)
        {
            snprintf(why, n, "%s: the domain " MACHINE_DOMAIN " has no item %s", omx_domain_code(rc), bands[b].item);
            machine_words_close(w);
            return rc;
        }
        if (count != bands[b].count)
        {
            snprintf(why, n, "%s: %s of the domain " MACHINE_DOMAIN " has %zu words, the probe cuts %zu",
                     omx_domain_code(OMX_CONTRACT_CODE_ITEM_UNKNOWN), bands[b].item, count, bands[b].count);
            free(list);
            machine_words_close(w);
            return OMX_CONTRACT_CODE_ITEM_UNKNOWN;
        }
        for (i = 0; i < count; i++)
            slot[i] = list[i];
        free(list);
    }
    return 0;
}

void machine_words_close(machine_words *w)
{
    if (w->domain != NULL)
        omx_domain_close(w->domain);
    memset(w, 0, sizeof(*w));
}

void machine_bands(const machine_words *w, long ncpu, long khz, const char **core_band, const char **clock_band)
{
    *core_band = w->core[ncpu <= 2 ? 0 : ncpu <= 4 ? 1 : ncpu <= 8 ? 2 : ncpu <= 16 ? 3 : ncpu <= 32 ? 4 : 5];
    *clock_band = w->clock[khz < 1500000 ? 0 : khz < 2500000 ? 1 : khz < 3500000 ? 2 : khz < 4500000 ? 3 : 4];
}

int machine_class(const machine_words *w, char *out, size_t size)
{
    struct utsname u;
    char text[64] = "";
    const char *core, *clock;
    long khz = 0;
    FILE *f;
    int n;

    if (uname(&u) != 0)
        snprintf(u.machine, sizeof(u.machine), "unknown");
    if ((f = fopen("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "r")))
    {
        if (fgets(text, sizeof(text), f))
            khz = atol(text);
        fclose(f);
    }
    machine_bands(w, sysconf(_SC_NPROCESSORS_ONLN), khz, &core, &clock);
    n = snprintf(out, size, "%s/%s/%s", u.machine, core, clock);
    return n > 0 && (size_t)n < size ? 0 : -1;
}
