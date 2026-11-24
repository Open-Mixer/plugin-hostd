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

/** @file conf.h
 * @brief The declarations of conf.h.
 */

#ifndef CONF_H
#define CONF_H

#include <limits.h>
#include <stdio.h>
#include <string.h>

#include <plugin-hostd/protocol.h>

/** @brief the size, in bytes with its NUL, of a string setting of size word */
#define CONF_SIZE_word 32
/** @brief the size, in bytes with its NUL, of a string setting of size path */
#define CONF_SIZE_path PATH_MAX
/** @brief the size, in bytes with its NUL, of a string setting of size pathlist, a list of paths */
#define CONF_SIZE_pathlist (PATH_MAX * 2)

/** @brief the string settings by their place in PHD_CONF_STRINGS; CONF_STRINGS_N counts them */
enum conf_string_key {
/** @brief one PHD_CONF_STRINGS row as its key, CONF_STRING_<key> */
#define X(key, size, def, env, meaning) CONF_STRING_##key,
    PHD_CONF_STRINGS(X)
#undef X
    CONF_STRINGS_N
};

/** @brief the settings: each of PHD_CONF_STRINGS as a string of its size, each of PHD_CONF_INTS as an int */
typedef struct CONF_T {
/** @brief one PHD_CONF_STRINGS row as its member, a string of CONF_SIZE_<size> bytes */
#define X(key, size, def, env, meaning) char key[CONF_SIZE_##size];
    PHD_CONF_STRINGS(X)
#undef X
/** @brief one PHD_CONF_INTS row as its member, an int in its unit */
#define X(key, def, unit, meaning) int key;
    PHD_CONF_INTS(X)
#undef X
    unsigned char from_file[CONF_STRINGS_N];  /**< 1 where the settings file set that string setting, by its key */
} conf_t;

/** @brief where a string setting's value came from
 *
 * @param conf the settings.
 * @param key the setting.
 * @return "file" when the settings file set it, else "env" when its variable (or, for clap_path, CLAP_PATH) is set
 *         and not empty, else "default".
 */
const char *conf_source(const conf_t *conf, enum conf_string_key key);

/** @brief sets every setting to its default, or to its variable's value when that is set and not empty
 *
 * clap_path is CLAP_PATH followed by the default when CLAP_PATH is set and not empty.
 *
 * @param[out] conf the settings.
 */
void conf_defaults(conf_t *conf);
/** @brief reads a settings file over the defaults: one "key value" per line, '#' starts a comment
 *
 * @pre conf_defaults set conf.
 * @param[in,out] conf the settings.
 * @param path the file.
 * @param required 1 when the path was asked for: a missing file is an error only then.
 * @return 0; -1 for a missing required file or a bad setting, with the reason on stderr.
 */
int conf_load(conf_t *conf, const char *path, int required);
/** @brief appends lv2_extra to lv2_path, so it is searched after it; once, after the file
 *
 * @param[in,out] conf the settings.
 * @return 0; -1 when the two together do not fit lv2_path, with the reason on stderr.
 */
int conf_merge_extra(conf_t *conf);

/** @brief whether the settings are consistent
 *
 * pin_mode is one of PHD_PIN_MODES, grouping one of PHD_GROUPING_MODES, ask_unknown one of PHD_ASK_UNKNOWN_MODES, lv2_worker one of
 * conf_lv2_workers, placement
 * one of PHD_CORE_PLACEMENTS, bind_address an IPv4 address, host_class holds no white space, and history_window_s,
 * history_save_s and history_regroup_s are not negative.
 *
 * @param conf the settings.
 * @return 0, or -1 with the reason on stderr.
 */
int conf_check(const conf_t *conf);
/** @brief whether pin_mode is first-use
 *
 * @param conf the settings.
 * @return 1 when it is, 0 otherwise.
 */
int conf_pins_first_use(const conf_t *conf);
/** @brief whether placement is spread
 *
 * @param conf the settings.
 * @return 1 when it is, 0 otherwise.
 */
int conf_spread(const conf_t *conf);
/** @brief whether grouping is on
 *
 * @param conf the settings.
 * @return 1 when it is, 0 otherwise.
 */
int conf_grouping_on(const conf_t *conf);

/** @brief the programs a user can name to run LV2 plugins (lv2_worker, lv2_worker_set): mod-host or omx-clap-host
 *
 * A plugin one of them refuses is reported with its code and never handed to the other: the user chooses the
 * program, the daemon does not. There is no third word that picks one for the user.
 */
static const char *const conf_lv2_workers[] = { PHD_LV2_WORKER_MOD_HOST, PHD_LV2_WORKER_CLAP_HOST };

/** @brief whether a word names one of conf_lv2_workers
 *
 * @param word the word, NUL-terminated.
 * @return 1 when it does, 0 otherwise.
 */
static inline int conf_lv2_worker_valid(const char *word)
{
    size_t n;

    for (n = 0; n < sizeof(conf_lv2_workers) / sizeof(*conf_lv2_workers); n++)
        if (!strcmp(word, conf_lv2_workers[n]))
            return 1;
    return 0;
}

/** @brief prints the words of conf_lv2_workers, each after a blank
 *
 * @param out the stream written.
 */
static inline void conf_lv2_workers_print(FILE *out)
{
    size_t n;

    for (n = 0; n < sizeof(conf_lv2_workers) / sizeof(*conf_lv2_workers); n++)
        fprintf(out, " %s", conf_lv2_workers[n]);
}

#endif
