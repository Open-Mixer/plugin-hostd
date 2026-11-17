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

/* LD_PRELOAD into the daemon: scandir lists a directory in an order the TEST sets, not the filesystem's, and only then
 * applies the caller's comparator, as glibc's does. So the bundle rule's test (tests/bundle_rule_test.sh) knows the
 * listing the daemon got: a daemon that sorts sees its own order, one that does not sees the listing. SCANDIR_MARK (a
 * file) gets each listed directory's path, so the test can tell the listing was this one; SCANDIR_DROP_ORDER=1 drops
 * the caller's comparator, the sabotage of a daemon that takes the listing as it comes. glibc's scandir reads the
 * directory through its own internal readdir, so a preloaded readdir would not reach it: scandir itself is replaced. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*order_fn)(const void *, const void *);

/* the listing order: byte order of the names (most filesystems list a small directory sorted) */
static int listing_order(const void *a, const void *b)
{
    return strcmp((*(const struct dirent *const *)a)->d_name, (*(const struct dirent *const *)b)->d_name);
}

static void mark(const char *dir)
{
    const char *path = getenv("SCANDIR_MARK");
    FILE *f;

    if (!path || !*path || !(f = fopen(path, "a")))
        return;
    fprintf(f, "%s\n", dir);
    fclose(f);
}

/* exported whatever -fvisibility the build uses: an interposer that is hidden interposes nothing */
__attribute__((visibility("default"))) int scandir(const char *dir, struct dirent ***out, int (*filter)(const struct dirent *),
            int (*compar)(const struct dirent **, const struct dirent **))
{
    DIR *d = opendir(dir);
    struct dirent *e, **list = NULL;
    size_t n = 0, cap = 0;
    const char *drop = getenv("SCANDIR_DROP_ORDER");

    if (!d)
        return -1;
    while ((e = readdir(d)))
    {
        struct dirent *copy;

        if (filter && !filter(e))
            continue;
        if (n == cap)
        {
            struct dirent **grown = realloc(list, (cap = cap ? 2 * cap : 16) * sizeof *list);

            if (!grown)
                goto fail;
            list = grown;
        }
        if (!(copy = malloc(sizeof *copy)))
            goto fail;
        memcpy(copy, e, sizeof *copy);
        list[n++] = copy;
    }
    closedir(d);
    mark(dir);
    if (n > 1)
        qsort(list, n, sizeof *list, listing_order);
    if (compar && n > 1 && !(drop && !strcmp(drop, "1")))
        qsort(list, n, sizeof *list, (order_fn)compar);
    *out = list;
    return (int)n;
fail:
    while (n)
        free(list[--n]);
    free(list);
    closedir(d);
    errno = ENOMEM;
    return -1;
}

/* the same, for a caller built with 64-bit file offsets: on LP64 the two are one layout */
__attribute__((visibility("default"))) int scandir64(const char *dir, struct dirent64 ***out, int (*filter)(const struct dirent64 *),
              int (*compar)(const struct dirent64 **, const struct dirent64 **))
{
    _Static_assert(sizeof(struct dirent) == sizeof(struct dirent64), "struct dirent is struct dirent64 here");
    return scandir(dir, (struct dirent ***)out, (int (*)(const struct dirent *))filter,
                   (int (*)(const struct dirent **, const struct dirent **))compar);
}
