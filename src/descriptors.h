/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/* The scanned descriptors of the plugins a controller adds: descriptor_dir, the scan an add runs
 * in a child of its own, and descriptor_get; the panel the same scan files under the descriptor's name, and panel_get.
 * A descriptor describes a plugin; it gates no load, so no add waits for its scan or is refused by it. */

/** @file descriptors.h
 * @brief The declarations of descriptors.h.
 */

#ifndef PLUGIN_HOSTD_DESCRIPTORS_H
#define PLUGIN_HOSTD_DESCRIPTORS_H

#include <limits.h>

#include "conf.h"

/* descriptor_dir resolved (an empty setting is the default of protocol.h), made when missing
 * and tried for a write; SUCCESS, or OMX_REPLY_PLUGIN_HOSTD_DIR_NOT_WRITABLE_RESP with the key, the path and why on stderr. The resolved
 * paths are written back into conf, which is kept for the scans. */
int descriptors_init(conf_t *conf);

/* the add of uri was answered: unless its files already have a descriptor or a scan of them runs, start one */
void descriptors_add(const char *uri);

/* reap the scans that ended: a descriptor is named and moved into place, a failure is recorded */
void descriptors_tick(void);

/* descriptor_get <uri>: resp 0 "<path>", or the code of protocol.h; malloc'd */
char *descriptors_get(const char *uri);

/* panel_get <uri>: resp 0 "<path>" of the panel filed under the descriptor's name, or the code of protocol.h;
 * malloc'd */
char *descriptors_panel_get(const char *uri);

/**
 * @brief The key a plugin is held by in the descriptions store (omx-panel docs/descriptions-store.md, 3.1), and what its
 *        derivation reads.
 */
typedef struct DESCRIPTORS_KEY_T {
    char sha256[64 + 1];                    /**< the SHA-256 of the plugin's binary, 64 lowercase hex digits */
    char format[16];                        /**< the format word of the key: lv2 or clap */
    char id[PATH_MAX];                      /**< the uri of the key: the LV2 URI, the CLAP id */
    char target[PATH_MAX + 16];             /**< the plugin as the probe and the ask's programs take it */
    char descriptor[PATH_MAX];              /**< the descriptor its scan wrote, "" when none is in place */
    char bundle[PATH_MAX];                  /**< the LV2 bundle's directory, "" for a CLAP plugin */
    char source[PATH_MAX];                  /**< what its source is made from (3.6): the bundle, else the descriptor */
} descriptors_key_t;

/**
 * @brief The key of the plugin of uri as its files are now.
 *
 * @param uri the plugin as an add names it
 * @param[out] k the key
 * @return 0, or -1 for a plugin whose binary (or LV2 bundle) cannot be found
 */
int descriptors_key(const char *uri, descriptors_key_t *k);

/**
 * @brief Whether the scan of the plugin's files runs, or its file waits to be put in place.
 *
 * @param uri the plugin as an add names it
 * @return 1 while it does, else 0
 */
int descriptors_busy(const char *uri);

/* stop the scans still running and remove what they were writing */
void descriptors_finish(void);

#endif
