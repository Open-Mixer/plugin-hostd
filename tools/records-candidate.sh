#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
#   tools/records-candidate.sh deb|rpm [<package>]
#
# The version of <package> (plugin-qualification-records) the channel offers FOR THIS MACHINE'S ARCHITECTURE, or
# nothing. A flat apt repository lists every architecture's build in one Packages file, so `apt-cache policy <name>`
# answers with another architecture's candidate (name:arm64) when this one has none: a Recommends published for
# another architecture only is not "in the channel" here, and apt rightly does not install it (plugin-hostd 0.20.1's
# full install check on amd64 failed on exactly that).
set -euo pipefail
kind=$1 pkg=${2:-plugin-qualification-records}
case $kind in
    deb)
        have=$(apt-cache policy "$pkg:$(dpkg --print-architecture)" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')
        [ "$have" = "(none)" ] && have= ;;
    rpm)
        have=$(dnf -q repoquery --latest-limit 1 --arch "$(uname -m)" "$pkg" 2>/dev/null | head -1) ;;
    *) echo "deb or rpm, not $kind" >&2; exit 2 ;;
esac
echo "${have:-}"
