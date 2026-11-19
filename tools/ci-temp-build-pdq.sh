#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# TEMPORARY: until libplugin-qualification-db is published in the OpenMixer channel, CI builds Open-Mixer/plugin-db-qualification at
# the pinned commit below and installs it under /usr/local, where pkg-config finds it. When its package is in the channel, the
# floor of packaging/deps.txt installs it by dnf builddep and this script and its steps in ci.yml are deleted.
# The installed .pc of that commit carries the prefix it was built with, so it is built and installed with PREFIX=/usr/local and
# `make check` is not run before the install. Fedora only (dnf), run as root.
set -eu
PDQ_URL=https://github.com/Open-Mixer/plugin-db-qualification.git
PDQ_SHA=1d8b2e2f20f2bd537d441ae1f8de35dd9a980a13

bounded-install dnf install -y --setopt=install_weak_deps=False git gcc make sqlite-devel libomx-domain-devel
dir=$(mktemp -d)
cd "$dir"
git init -q .
git fetch -q --depth 1 "$PDQ_URL" "$PDQ_SHA"
git checkout -q FETCH_HEAD
test "$(git rev-parse HEAD)" = "$PDQ_SHA"
make PREFIX=/usr/local
make PREFIX=/usr/local install
echo /usr/local/lib > /etc/ld.so.conf.d/plugin-qualification-db.conf
ldconfig
PKG_CONFIG_PATH=/usr/local/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
export PKG_CONFIG_PATH
echo "PKG_CONFIG_PATH=$PKG_CONFIG_PATH" >> "$GITHUB_ENV"
pkg-config --exists plugin-qualification-db
