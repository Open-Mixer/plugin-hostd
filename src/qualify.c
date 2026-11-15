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

#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <plugin-hostd/protocol.h>

#include "fsutil.h"
#include "writer.h"
#include "pins.h"
#include "qualify.h"

const char *qualify_dir(void)
{
    static char dir[PATH_MAX];
    char base[PATH_MAX];

    if (!pins_store_dir_of(base, sizeof(base)) || snprintf(dir, sizeof(dir), "%s/" PHD_QUALIFY_SPOOL_DIR, base) >= (int)sizeof(dir))
        return "";
    return dir;
}

/* the name of a request: the uri's characters that are safe, and the FNV-1a of the whole uri so two uris never share one */
static int request_path(const char *uri, char *path, size_t size)
{
    const char *dir = qualify_dir();
    char safe[64];
    uint64_t h = 1469598103934665603ULL;
    size_t n, k = 0;

    if (!*dir)
        return -1;
    for (n = 0; uri[n]; n++)
    {
        h = (h ^ (unsigned char)uri[n]) * 1099511628211ULL;
        if (k + 1 < sizeof(safe) && ((uri[n] >= 'a' && uri[n] <= 'z') || (uri[n] >= 'A' && uri[n] <= 'Z') ||
                                     (uri[n] >= '0' && uri[n] <= '9') || uri[n] == '.' || uri[n] == '-'))
            safe[k++] = uri[n];
    }
    safe[k] = '\0';
    return snprintf(path, size, "%s/%s-%016llx" PHD_QUALIFY_REQUEST_SUFFIX, dir, safe, (unsigned long long)h) >= (int)size ? -1 : 0;
}

/* the uris asked this run: a request is written by the writer thread, so the file may not be there yet when the
 * plugin is added again, and it is asked once however often */
static char **g_asked;
static int g_nasked;

int qualify_asked(const char *uri)
{
    int n;

    for (n = 0; n < g_nasked; n++)
        if (!strcmp(g_asked[n], uri))
            return 1;
    return 0;
}

int qualify_request(const char *uri, writer_done_fn done, void *arg)
{
    char path[PATH_MAX], dir[PATH_MAX], *body, **grown;
    size_t cap = 4096, len;
    const char *file, *digest;
    int n;

    if (request_path(uri, path, sizeof(path)) != 0)
        return -1;
    if (qualify_asked(uri) || access(path, F_OK) == 0)
        return 0;
    snprintf(dir, sizeof(dir), "%s/", qualify_dir());
    /* the directory is made here, with no sync: the command loop never waits on the disk, the file is the writer's */
    if (fs_mkdir_parents(dir) != 0)
        return -1;
    for (n = 0; pins_file_at(uri, n, &file, &digest) == 0; n++)
        cap += strlen(file) + strlen(digest) + 16;
    body = malloc(cap);
    grown = realloc(g_asked, (g_nasked + 1) * sizeof(char *));
    if (!body || !grown || !(grown[g_nasked] = strdup(uri)))
    {
        free(body);
        if (grown)
            g_asked = grown;
        return -1;
    }
    g_asked = grown;
    g_nasked++;
    len = (size_t)snprintf(body, cap, PHD_QUALIFY_REQUEST_URI " %s\n", uri);
    for (n = 0; len < cap && pins_file_at(uri, n, &file, &digest) == 0; n++)
        len += (size_t)snprintf(body + len, cap - len, PHD_QUALIFY_REQUEST_FILE " %s %s\n", file, digest);
    /* writer_put owns body from here; its done is told on the loop once the request is on disk */
    return writer_put(path, body, len, 0, done, arg, "the qualify request %s: %s; the plugin stays bypassed with no check asked for") == 0 ? 1 : -1;
}

int qualify_answered(const char *uri)
{
    char path[PATH_MAX];
    int n;

    /* asked again if it is added again and has no verdict then */
    for (n = 0; n < g_nasked; n++)
        if (!strcmp(g_asked[n], uri))
        {
            free(g_asked[n]);
            g_asked[n] = g_asked[--g_nasked];
            break;
        }
    return request_path(uri, path, sizeof(path)) == 0 && unlink(path) == 0;
}
