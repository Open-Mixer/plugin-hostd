/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * This file is part of plugin-hostd.
 *
 * Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
 */

/** @file descriptions_open.h
 * @brief How the descriptions store is opened (src/descriptions.c): the one declaration that names the store library's
 *        types, apart from descriptions.h, which src/verbs.c includes.
 */

#ifndef PLUGIN_HOSTD_DESCRIPTIONS_OPEN_H
#define PLUGIN_HOSTD_DESCRIPTIONS_OPEN_H

#include <omx-panel/omx_panel_store.h>

/**
 * @brief How the store is opened: omx_panel_store_open of the scope of the effective uid when NULL (the packaged
 *        daemon); the test builds name a store of their own (src/main.c, OMX_QUALIFICATION_TEST_STORE).
 *
 * @param opener the opener, or NULL
 */
void descriptions_use_opener(int (*opener)(omx_panel_store **out, omx_panel_store_error *err));

#endif
