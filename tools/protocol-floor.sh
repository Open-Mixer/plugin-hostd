#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The plugin-hostd-protocol floor of this tree, as packaging/deps.txt declares it. CI reads it here;
# tests/protocol_floor.py holds it to the first protocol release that declares what the sources use.
exec "$(dirname "$0")/dep-floor.sh" plugin-hostd-protocol-devel
