#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The floor packaging/deps.txt declares for the dependency whose RPM name is <name>: what the pkg-config file, the
# Makefile and the workflows read, so none of them types a number. (The spec and debian/control are written from the same
# file by deps-render in Open-Mixer/.github.)
#
# Usage: dep-floor.sh <rpm name>
deps=$(dirname "$0")/../packaging/deps.txt
floor=$(awk -v n="$1" '$1 == n { print $3 }' "$deps")
[ -n "$floor" ] || { echo "dep-floor.sh: $deps lists no $1" >&2; exit 1; }
printf '%s\n' "$floor"
