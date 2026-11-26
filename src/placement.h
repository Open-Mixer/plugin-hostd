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

/* Core placement (docs/placement.md): which cpus are the audio cores, every worker's mask, and which are kept for the
 * daemon. Pure functions: they read no file, no clock and no global, so the same mask gives the same cores. The
 * supervisor (src/supervisor.c) applies them. */

/** @file placement.h
 * @brief The declarations of placement.h.
 */

#ifndef PLACEMENT_H
#define PLACEMENT_H

#include <sched.h>
#include <stddef.h>

/** @brief reads a cpu list as the kernel writes one, "0-2,5"
 *
 * Numbers below CPU_SETSIZE and ranges low-high, joined by commas, nothing else.
 *
 * @param list the list, NUL-terminated.
 * @param[out] set the cpus it names.
 * @return 0, or -1 for anything that is not such a list.
 */
int placement_parse(const char *list, cpu_set_t *set);

/** @brief writes the list of a set, "0-2,5", "" for none
 *
 * @param set the cpus.
 * @param[out] buf where the text is written, NUL-terminated, truncated to size like snprintf.
 * @param size the size of buf, in bytes.
 * @return the length the text needs, in bytes, its NUL excluded.
 */
size_t placement_list_text(const cpu_set_t *set, char *buf, size_t size);

/** @brief reads the capacity of each cpu of a set
 *
 * cpu<n>/cpu_capacity when every cpu of allowed has one, else cpu<n>/cpufreq/cpuinfo_max_freq when every one has
 * that.
 *
 * @param dir the directory read, /sys/devices/system/cpu.
 * @param allowed the cpus read.
 * @param[out] capacity capacity[0] to capacity[CPU_SETSIZE - 1], each cpu's; 0 is unknown.
 * @return 1 when one was read, else 0 with every capacity 0.
 */
int placement_capacities(const char *dir, const cpu_set_t *allowed, long *capacity);

/** @brief splits a daemon's cpus into its audio cores and the reserved ones
 *
 * The audio cores are audio_cores when it is not empty, which must be a list inside allowed, else allowed less one
 * cpu, the one of least capacity, the lowest of a tie; reserved is the rest of allowed.
 *
 * @param allowed the daemon's cpus.
 * @param audio_cores the audio cores set in the configuration, a cpu list; NULL or "" for none.
 * @param capacity each cpu's capacity, as placement_capacities reads it; NULL or all equal for none known.
 * @param[out] audio the audio cores.
 * @param[out] reserved the cpus kept for the daemon.
 * @return 0, or -1 for an audio_cores that is no list or names a cpu outside allowed.
 */
int placement_cores(const cpu_set_t *allowed, const char *audio_cores, const long *capacity, cpu_set_t *audio,
                    cpu_set_t *reserved);

#endif
