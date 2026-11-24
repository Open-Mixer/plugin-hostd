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

/** @file qualify.h
 * @brief The qualify spool (R-112): one request per plugin that has no verdict, written whole beside the pin store.
 *
 * A request is written into the directory beside the pin store and announced on the feedback socket. The daemon runs
 * no probe, queue or judge and loads no plugin code; the service that watches the spool does the check and writes the
 * verdict.
 */

#ifndef QUALIFY_H
#define QUALIFY_H

#include "writer.h"

/**
 * @brief The spool's directory, "\<the store's directory\>/qualify" (PHD_QUALIFY_SPOOL_DIR).
 *
 * @return the directory, or "" for a store with no path
 * @note Not thread-safe: call on the daemon's main thread.
 */
const char *qualify_dir(void);

/**
 * @brief Hands the request of a uri to the writer, unless one is asked or there.
 *
 * The writer writes a temporary file in the directory and renames it over the name, so the command loop never waits
 * on the disk.
 *
 * @param uri the plugin's uri
 * @param done told on the loop when the request is on disk, with err 0 or the errno
 * @param arg passed to done
 * @return 1 when one was handed over, 0 when one was already asked, -1 when it could not be
 * @note Not thread-safe: call on the daemon's main thread.
 */
int qualify_request(const char *uri, writer_done_fn done, void *arg);

/**
 * @brief Whether a request of the uri is asked and not yet answered, on disk or on its way there.
 *
 * @param uri the plugin's uri
 * @return 1 when it is asked, else 0
 * @note Not thread-safe: call on the daemon's main thread.
 */
int qualify_asked(const char *uri);

/**
 * @brief The request of the uri is answered (the verdict landed, or the operator chose): it is removed.
 *
 * @param uri the plugin's uri
 * @return 1 when there was one, else 0
 * @note Not thread-safe: call on the daemon's main thread.
 */
int qualify_answered(const char *uri);

#endif
