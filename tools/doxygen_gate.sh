#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The C documentation gate is doxygen itself: tools/Doxyfile (INPUT = the headers) warns for every public symbol without
# a doc block and every parameter without @param. This runs it and compares the warning LINES, one per symbol, with
# tools/doxygen.baseline, a ratchet: a warning not in the baseline fails (a new undocumented symbol, or a new missing
# @param, even when another was fixed in the same change); a baseline line with no warning fails until it is removed.
# Usage: doxygen_gate.sh [--update]   (--update writes the baseline from the log only to lower it: a warning the
# baseline does not list refuses it, by name, and leaves the baseline as it is). DOXYGEN: the doxygen to run.
set -eu
cd "$(dirname "$0")/.."
LOG=$(mktemp)
trap 'rm -f "$LOG" "$LOG.now"' EXIT
DOXYGEN_LOG=$LOG "${DOXYGEN:-doxygen}" tools/Doxyfile >/dev/null
# a warning is `file:line: warning: text`; the line number moves with every edit, so the key is file + text
sed -n 's/^\(.*\):[0-9][0-9]*: warning: /\1: /p' "$LOG" | sed 's|^.*/src/|src/|' | LC_ALL=C sort -u > "$LOG.now"
new=$(LC_ALL=C comm -13 tools/doxygen.baseline "$LOG.now")
if [ "${1:-}" = "--update" ]; then
    if [ -n "$new" ]; then
        echo "doxygen-gate: --update only lowers the baseline; these warnings are not in it (document the symbol):"
        echo "$new"
        exit 1
    fi
    cp "$LOG.now" tools/doxygen.baseline
    echo "doxygen-gate: baseline now $(wc -l < tools/doxygen.baseline)"
    exit 0
fi
gone=$(LC_ALL=C comm -23 tools/doxygen.baseline "$LOG.now")
[ -z "$new" ] || { echo "doxygen-gate: new doxygen warnings (document the symbol, do not extend the baseline):"; echo "$new"; }
[ -z "$gone" ] || { echo "doxygen-gate: fixed, remove these lines from tools/doxygen.baseline:"; echo "$gone"; }
echo "doxygen-gate: $(wc -l < "$LOG.now") warning(s), baseline $(wc -l < tools/doxygen.baseline)"
[ -z "$new$gone" ]
