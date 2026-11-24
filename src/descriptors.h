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

#include "conf.h"

/** @brief resolves descriptor_dir, makes it when missing and tries a write in it
 *
 * An empty setting is the default of protocol.h. The resolved paths are written back into conf, which is kept for
 * the scans.
 *
 * @param[in,out] conf the configuration; it must outlive the scans.
 * @return SUCCESS, or OMX_REPLY_PLUGIN_HOSTD_DIR_NOT_WRITABLE_RESP with the key, the path and why on stderr.
 */
int descriptors_init(conf_t *conf);

/** @brief starts the scan of a plugin whose add was answered, unless its files have a descriptor or a scan of them runs
 *
 * @param uri the plugin.
 */
void descriptors_add(const char *uri);

/** @brief reaps the scans that ended: a descriptor is named and moved into place, a failure is recorded */
void descriptors_tick(void);

/** @brief the answer of descriptor_get
 *
 * @param uri the plugin.
 * @return resp 0 "<path>", or the code of protocol.h; malloc'd, the caller frees it.
 */
char *descriptors_get(const char *uri);

/** @brief the answer of panel_get
 *
 * @param uri the plugin.
 * @return resp 0 "<path>" of the panel filed under the descriptor's name, or the code of protocol.h; malloc'd, the
 *         caller frees it.
 */
char *descriptors_panel_get(const char *uri);

/** @brief stops the scans still running and removes what they were writing */
void descriptors_finish(void);

#endif
