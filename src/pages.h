/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/* The page size plugin-hostd cuts a group's controls into, the same for an LV2 instance's own groups
 * (src/lv2.c, docs/panel.md#drawing-a-panel-the-three-verbs-together) and a descriptor's (src/describe.c,
 * docs/formats.md#the-pages-describe-pages-writes): one page is PAGE_SLOTS controls of one group, in declared order. */
#ifndef PLUGIN_HOSTD_PAGES_H
#define PLUGIN_HOSTD_PAGES_H

#define PAGE_SLOTS 8

#endif
