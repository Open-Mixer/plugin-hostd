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
# The warnings are only trusted when doxygen provably read every header, so before the compare it refuses, by name:
#   a doxygen of another version than tools/doxygen.version pins (other versions give other rows);
#   a header of the Doxyfile's INPUT (each entry a file, or the FILE_PATTERNS files of a directory, below it too when
#     RECURSIVE = YES; git-tracked files only) with no @file or \file in a /** doc comment: doxygen reports a file's
#     undocumented members only when the file has @file, so a header without one hides its rows;
#   a warning log doxygen did not write, and a header it wrote no HTML page for (it did not read it). An empty log is
#     then a fully documented tree.
set -eu
cd "$(dirname "$0")/.."
DOXYGEN=${DOXYGEN:-doxygen}
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
# the log is doxygen's to create: a path that does not exist yet
LOG=$T/warnings.log
OUT=$T/out
mkdir "$OUT"

want=$(cat tools/doxygen.version)
have=$("$DOXYGEN" --version | head -n 1)
if [ "$have" != "$want" ]; then
    echo "doxygen-gate: doxygen is $have, tools/doxygen.version pins $want: other versions give other warnings, run the gate with doxygen $want"
    exit 1
fi

# setting <key>: the value of a Doxyfile key, its continuation lines joined (+= appends)
setting() {
    awk -v key="$1" '
        { while (sub(/\\$/, "")) { if ((getline more) <= 0) break; $0 = $0 " " more } }
        $1 == key && ($2 == "=" || $2 == "+=") { if ($2 == "=") v = ""; $1 = $2 = ""; v = v " " $0 }
        END { gsub(/^ +| +$/, "", v); print v }' tools/Doxyfile
}
patterns=$(setting FILE_PATTERNS)
recursive=$(setting RECURSIVE)
set -f # the patterns are matched by case, never expanded here
for entry in $(setting INPUT); do
    if [ -d "$entry" ]; then
        git ls-files -- "$entry" | while IFS= read -r f; do
            rest=${f#"${entry%/}"/}
            case "$rest" in */*) [ "$recursive" = YES ] || continue ;; esac
            for p in ${patterns:-*.h}; do
                # shellcheck disable=SC2254 # a pattern, matched as one
                case "${f##*/}" in $p) echo "$f"; break ;; esac
            done
        done
    else
        git ls-files -- "$entry"
    fi
done | LC_ALL=C sort -u > "$T/headers"
set +f
if [ ! -s "$T/headers" ]; then
    echo "doxygen-gate: the INPUT of tools/Doxyfile names no git-tracked header: nothing would be checked"
    exit 1
fi
nofile=$(while IFS= read -r h; do
    awk '/\/\*\*/ { doc = 1 } doc && /[@\\]file([^A-Za-z_]|$)/ { found = 1 } /\*\// { doc = 0 } END { exit !found }' "$h" ||
        echo "doxygen-gate: $h has no @file in a /** doc comment: doxygen reports none of its undocumented members without one"
done < "$T/headers")
[ -z "$nofile" ] || { echo "$nofile"; exit 1; }

DOXYGEN_LOG=$LOG DOXYGEN_OUT=$OUT "$DOXYGEN" tools/Doxyfile >/dev/null
if [ ! -f "$LOG" ]; then
    echo "doxygen-gate: doxygen wrote no warning log ($LOG, WARN_LOGFILE of tools/Doxyfile): its warnings are unknown"
    exit 1
fi
# doxygen read a header when it wrote its file page. It names the page after the file name, or, when two headers share
# the name, after their paths below the directory they have in common, with _ written __, . written _8 and / written _2
# (doxygen 1.9.8: probe_lock.h is probe__lock_8h.html, plugin-hostd/protocol.h beside protocol.h is
# plugin-hostd_2protocol_8h.html)
nopage=$(awk '
    { path[NR] = $0; n = split($0, part, "/"); base[NR] = b = part[n]; count[b]++
      dir = substr($0, 1, length($0) - length(b))
      if (!(b in common)) common[b] = dir
      while (common[b] != "" && index(dir, common[b]) != 1) sub(/[^\/]*\/$/, "", common[b]) }
    END { for (i = 1; i <= NR; i++) {
              name = count[base[i]] > 1 ? substr(path[i], length(common[base[i]]) + 1) : base[i]
              gsub(/_/, "__", name); gsub(/\./, "_8", name); gsub(/\//, "_2", name)
              print path[i] " " name ".html" } }' "$T/headers" |
    while read -r h page; do
        [ -f "$OUT/html/$page" ] ||
            echo "doxygen-gate: doxygen wrote no page for $h (html/$page): it did not read the header"
    done)
[ -z "$nopage" ] || { echo "$nopage"; exit 1; }
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
