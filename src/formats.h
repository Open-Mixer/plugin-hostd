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

/** @file formats.h
 * @brief The table of plugin formats: one row per format, and the uri and route lookups over it.
 */

#ifndef FORMATS_H
#define FORMATS_H

#include <stddef.h>

#include "conf.h"
#include "names.h"

/** @brief The most rows the table holds. */
#define FORMATS_MAX 8

/**
 * @brief One row per plugin format.
 *
 * Everything the daemon does differently for a format is a field of its row: the protocol, the supervisor and the pins
 * read the row and never ask which format it is. A format joins with a row and its worker.
 */
typedef struct FORMAT_T {
    const char *name;               /**< the word of policy_set, worker_env and worker_list; not "*", "all" or "-" */
    const char *prefix;             /**< the uri says it is this format with this prefix; NULL for none */
    int strip_prefix;               /**< the worker is given the uri without the prefix */
    int fallback;                   /**< the format of a uri no prefix claims; one format only */
    int routed;                     /**< no uri reaches it by its prefix: another row's `route` hands uris to it */
    const char *worker_prefix;      /**< put before the uri the worker is given, NULL for nothing */
    /** the word of the worker's add that names the uri, written into out of room size; NULL for the uri as it is */
    void (*worker_word)(const char *uri, char *out, size_t size);
    /** the row a uri of this format is run by, as a name of the table, or NULL for this one; malloc'd nothing */
    const char *(*route)(const conf_t *conf, const char *uri);
    /** the worker runs the plugin through an adapter that may refuse it: its instantiation error is OMX_REPLY_PLUGIN_HOSTD_LV2_ADAPTER_REFUSED_RESP */
    int adapter;

    const char *(*worker)(const conf_t *conf);  /**< the program that serves it */
    const char *(*search)(const conf_t *conf);  /**< where its plugins are searched, NULL for nowhere */
    /** the declared plugin search path of the format (the settings' lv2_path or clap_path), the only directories a first-use
     * pin is learned in; NULL: first use learns no pin of the format */
    const char *(*declared)(const conf_t *conf);
    const char *world_env;                      /**< the worker's variable for the search path, NULL for none */
    /** a directory under `dir` that makes the worker's world the union of the n plugins' (one for an own worker, a chain's
     * members for a chain's), malloc'd; NULL when a plugin is not found: never a wider world than the plugins' */
    char *(*narrow_world)(const conf_t *conf, const char *dir, const char *const *uris, int n);

    /** the root and the relative files a host loads for the uri: what a pin holds. SUCCESS, or
     * OMX_REPLY_PLUGIN_HOSTD_PIN_BINARY_MISMATCH_RESP with the reason on stderr for what cannot be pinned */
    int (*pin_collect)(const char *uri, const char *search, char *root, size_t size, names_t *files);
    /** the one file the host loads the plugin's code from, as a path: what the name of its scanned descriptor hashes. 0,
     * or -1 when it cannot be told; NULL for a format whose plugins get no descriptor */
    int (*binary)(const char *uri, const char *search, char *path, size_t size);
    int layout_check;               /**< the worker takes pin_expect before the add and pin_layout after it */
    int pinned_own_only;            /**< a pinned plugin runs in a worker of its own: the pin holds in no shared world */

    int thread_pool;                /**< the worker is omx-clap-host, which takes --thread-pool: a plugin whose pin grants the pool
                                     * gets it, in a worker of its own */
    int native_instance_verbs;      /**< the worker answers PHD_INSTANCE_VERBS; 0: the daemon does */
    int native_chain;               /**< the worker takes OMX_VERB_CHAIN and runs a chain's members in order in one client */
    char *(*param_info)(int id, const char *symbol);    /**< the daemon's param_info, needed when it answers */
    /** the daemon's remote_pages when it answers; NULL for a format with no pages: 0 pages */
    char *(*remote_pages)(int id);
    /** the daemon's remote_page_get when it answers; NULL for a format with no pages: -902 for a page */
    char *(*remote_page_get)(int id, int page);
} format_t;

/**
 * @brief clap:\<path>#\<id> with its path decoded, one string that is not a word of a line.
 * @param uri the uri
 * @param[out] out the decoded uri
 * @param size the room in out
 * @return 0, or -1 when the uri is not one or its path is not percent-encoded
 */
int clap_plain_target(const char *uri, char *out, size_t size);

/**
 * @brief Adds a row to the table. The two built-in rows are in the table from the start.
 *
 * A row added later is copied; a row without a capability is refused, never half-registered.
 * @param format the row
 * @return its index, or -1 with the missing or wrong field named on stderr
 */
int formats_register(const format_t *format);

/**
 * @brief The number of rows.
 * @return the count
 */
int formats_count(void);
/**
 * @brief A row of the table.
 * @param index the row's index
 * @return the row, owned by the table; NULL for an index out of range
 */
const format_t *format_at(int index);

/**
 * @brief The format of a name of the table.
 * @param name the name
 * @return its index, or -1
 */
int format_by_name(const char *name);

/**
 * @brief The format a uri belongs to, and the uri as the worker is given it.
 * @param uri the uri
 * @param[out] worker_uri the uri without the prefix when the format strips it, else the uri itself; may be NULL
 * @return the format's index, or -1 when no prefix claims it and no row is the fallback
 */
int format_of_uri(const char *uri, const char **worker_uri);

/**
 * @brief The row that runs the plugin: the format's own, or the one its `route` names.
 * @param conf the configuration
 * @param format the format's index
 * @param uri the uri
 * @return the row's index; -1 when a route names no row
 */
int format_route(const conf_t *conf, int format, const char *uri);

/**
 * @brief The pin root and files of a CLAP: the directory of the .clap and the file.
 * @param uri clap:\<path>#\<id>
 * @param search not used
 * @param[out] root the directory
 * @param size the room in root
 * @param files the names of the files the pin holds, added to
 * @return SUCCESS, a pin refusal, or a memory refusal
 */
int clap_pin_collect(const char *uri, const char *search, char *root, size_t size, names_t *files);

/**
 * @brief The .clap file of clap:\<path>#\<id>.
 * @param uri the uri
 * @param search not used
 * @param[out] path the file, decoded
 * @param size the room in path
 * @return 0, or -1 when the uri is not an absolute clap: path or the path does not decode
 */
int clap_binary(const char *uri, const char *search, char *path, size_t size);

/**
 * @brief The LV2 format's binary: the one file the plugin's bundle names as its code.
 * @param uri the plugin's uri
 * @param search the LV2 search path
 * @param[out] path the file
 * @param size the room in path
 * @return 0, or -1 when the bundle, its manifest or exactly one binary is not found
 */
int lv2_binary(const char *uri, const char *search, char *path, size_t size);
/**
 * @brief The LV2 format's pin root and files: the bundle's directory, its manifest and the files the manifest names.
 * @param uri the plugin's uri
 * @param search the LV2 search path
 * @param[out] root the bundle's directory
 * @param size the room in root
 * @param files the names of the files the pin holds, added to
 * @return SUCCESS, a pin refusal, or a memory refusal
 */
int lv2_pin_collect(const char *uri, const char *search, char *root, size_t size, names_t *files);
/**
 * @brief An own LV2 worker sees a world of one bundle, a chain's worker the union of its members'.
 *
 * A directory holding a link to each bundle that holds one of the URIs, once, and to each bundle of LV2_PATH that names
 * one of them with no binary (its presets: the bundle's own, the user's, a distribution's), so every preset of the
 * plugin lists and loads.
 * @param conf the configuration
 * @param dir the directory to make the world in
 * @param uris the plugins' uris
 * @param n the number of uris
 * @return the directory, malloc'd; NULL when a URI's bundle is not found
 */
char *lv2_narrow_world(const conf_t *conf, const char *dir, const char *const *uris, int n);
/**
 * @brief param_info of an LV2 instance, from the control ports of its bundle.
 *
 * The unit and scale its port states, the range and default, and the port's symbol, which is stable across hosts. -103
 * for what is no control port, and for the host's bypass; -511 for a port whose unit the daemon has no word for or
 * whose range it does not state. A bundle that cannot be read leaves the answer to mod-host's param_get: -103 for what
 * is no parameter, -511 for a parameter.
 * @param id the instance
 * @param symbol the port's symbol
 * @return the reply line, malloc'd
 */
char *lv2_param_info(int id, const char *symbol);
/**
 * @brief remote_pages of an LV2 instance: the pages its bundle's groups make.
 * @param id the instance
 * @return "resp \<count>", malloc'd; 0 pages for a bundle that cannot be read
 */
char *lv2_remote_pages(int id);
/**
 * @brief remote_page_get of an LV2 instance.
 * @param id the instance
 * @param page the page's number
 * @return the page's reply line, malloc'd; invalid-operation for a bundle that cannot be read or a page that is not one
 */
char *lv2_remote_page_get(int id, int page);

/**
 * @brief Which LV2 row runs a uri: the lv2_worker_set override of the uri, else the lv2_worker setting.
 *
 * A plugin the row's worker refuses stays refused: it is never moved to the other row.
 * @param conf the configuration
 * @param uri the plugin's uri
 * @return the name of the row, or NULL for the lv2 row itself
 */
const char *lv2_route(const conf_t *conf, const char *uri);
/**
 * @brief lv2_worker_set: the worker of one uri, or PHD_WORD_NONE to take the override back.
 * @param uri the plugin's uri
 * @param worker the worker's word, or PHD_WORD_NONE
 * @return 0; -1 for a word that is no worker, or when there is no memory to record it
 */
int lv2_worker_pick(const char *uri, const char *worker);
/**
 * @brief The hosting.* code an adapter's refusal carries after the error code on its reply line, "-" for none.
 * @param reply the adapter's reply line, "resp \<code> \<hosting code>"
 * @param[out] buf the code, or PHD_WORD_NONE
 * @param size the room in buf
 */
void lv2_refusal_reason(const char *reply, char *buf, size_t size);

#endif
