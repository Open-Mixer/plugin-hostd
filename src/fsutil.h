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

/** @file fsutil.h
 * @brief The declarations of fsutil.h.
 */

#ifndef FSUTIL_H
#define FSUTIL_H

#include <stddef.h>

/** @brief makes the parent directories of a path, each mode 0700 when missing
 *
 * @param[in,out] path the path; it is written through and restored.
 * @return 0, or -1 with errno set.
 */
int fs_mkdir_parents(char *path);

/** @brief fsyncs the directory that holds a path, so a rename into it survives a power cut
 *
 * @param path the path whose directory is synced.
 */
void fs_sync_dir(const char *path);

/** @brief writes bytes as the whole of a file, atomically
 *
 * A temporary file of its own beside it (mkstemp, mode 0600) is written, fsynced and renamed over it, then the
 * directory fsynced.
 *
 * @param path the file.
 * @param bytes what it holds.
 * @param len the length of bytes, in bytes.
 * @return 0, or the errno of the step that failed, with no temporary file left.
 */
int fs_write_atomic(const char *path, const char *bytes, size_t len);

/** @brief puts a written file in place: fsynced, renamed to its final path and the directory fsynced
 *
 * When final is there already it is kept and tmp removed.
 *
 * @param tmp the file written.
 * @param final the path it takes.
 * @return 0, or the errno of the step that failed.
 */
int fs_into_place(const char *tmp, const char *final);

#endif
