/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/** @file descriptions.h
 * @brief The descriptions store as plugin-hostd reads it, and the ask for a plugin it does not hold.
 *
 * omx-panel docs/descriptions-store.md, section 7. At an add the daemon reads the store entry of the plugin's key (its
 * binary's SHA-256, its format and uri, through libomx-panel-store) with the plugin's source as installed: a grouped
 * verdict's groups replace the declared pg:group for the LV2 pages, and anything else keeps the declared ones. The
 * daemon infers no group. A plugin no layer holds is asked for, once per key while the daemon runs: after the add's
 * scan, plugin-qualify-sync --plugin, omx-panel describe --plugin ... --store and the LV2 generators with that plugin's
 * --only run one after the other as children of the daemon, at nice 19, SCHED_IDLE and the idle I/O class, confined.
 * When the ask ends the entry is read again and description_changed tells the clients. description_get answers the key.
 * Never in a real-time path: every call reads files and takes locks; the daemon reads at an add and copies what it keeps.
 */

#ifndef PLUGIN_HOSTD_DESCRIPTIONS_H
#define PLUGIN_HOSTD_DESCRIPTIONS_H

#include <stddef.h>

#include <omx-panel/omx_panel_store.h>

/** @brief A port group of a store entry, copied: its symbol, its name and the symbols of its ports. */
typedef struct DESC_GROUP_T {
    char *symbol;       /**< the group's symbol */
    char *name;         /**< its name, a page's title */
    char **ports;       /**< the symbols of its ports */
    size_t nports;      /**< how many */
} desc_group_t;

/** @brief The groups of a grouped verdict, by display priority. */
typedef struct DESC_GROUPS_T {
    desc_group_t *group;    /**< the groups */
    size_t n;               /**< how many */
} desc_groups_t;

/** @brief add's ask word (plugin-hostd-protocol's PHD_ADD_ASK and PHD_ADD_NO_ASK). */
enum {
    DESC_ASK_DEFAULT = -1,  /**< none given: asked when plugin-qualify-sync is installed */
    DESC_ASK_NO = 0,        /**< no-ask */
    DESC_ASK_YES = 1        /**< ask */
};

/**
 * @brief How the store is opened: omx_panel_store_open of the scope of the effective uid when NULL (the packaged
 *        daemon); the test builds name a store of their own (src/main.c, OMX_QUALIFICATION_TEST_STORE).
 *
 * @param opener the opener, or NULL
 */
void descriptions_use_opener(int (*opener)(omx_panel_store **out, omx_panel_store_error *err));

/**
 * @brief The add of uri was answered: reads its store entry, and asks for a plugin no layer holds.
 *
 * @param uri the plugin as the add named it
 * @param ask DESC_ASK_DEFAULT, DESC_ASK_NO or DESC_ASK_YES: the add's last word
 * @note Call after descriptors_add, so the ask waits for the scan it started.
 */
void descriptions_add(const char *uri, int ask);

/**
 * @brief The groups the store holds for the plugin, read at its add or at the end of its ask.
 *
 * @param uri the plugin as the add named it, or as its instance keeps it (sup_instance_uri)
 * @return the groups, valid until the next add or tick; NULL when its entry has no grouped verdict, or no layer holds it
 */
const desc_groups_t *descriptions_groups(const char *uri);

/**
 * @brief description_get \<uri\>: "resp 0 \<sha256\> \<format\> \<uri\> \<layer\>", -529 when no layer holds it, -530
 *        while its ask runs.
 *
 * @param uri the plugin as a client names it
 * @return the reply, malloc'd
 */
char *descriptions_get(const char *uri);

/** @brief Reaps the ask's children that ended, starts its next program or ends it. */
void descriptions_tick(void);

/** @brief Stops the children of the asks still running. */
void descriptions_finish(void);

#endif
