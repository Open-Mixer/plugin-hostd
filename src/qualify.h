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

#ifndef QUALIFY_H
#define QUALIFY_H

#include "writer.h"

/* The qualify spool (R-112): one request per plugin that has no verdict, written whole into the directory beside the pin
 * store and announced on the feedback socket. The daemon runs no probe, queue or judge and loads no plugin code; the
 * service that watches the spool does the check and writes the verdict. */

/* the spool's directory, "<the store's directory>/qualify" (PHD_QUALIFY_SPOOL_DIR); "" for a store with no path */
const char *qualify_dir(void);

/* the request of the uri, handed to the writer (a temporary file in the directory renamed over the name, the command
 * loop never waits on the disk) unless one is asked or there. `done` is told on the loop when it is on disk, with err
 * 0 or the errno. 1 when one was handed over, 0 when one was already asked, -1 when it could not be */
int qualify_request(const char *uri, writer_done_fn done, void *arg);

/* whether a request of the uri is asked and not yet answered, on disk or on its way there */
int qualify_asked(const char *uri);

/* the request of the uri is answered: the verdict landed, or the operator chose; removed. 1 when there was one */
int qualify_answered(const char *uri);

#endif
