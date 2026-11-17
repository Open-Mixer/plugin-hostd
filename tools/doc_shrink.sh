#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The documentation gates only shrink. tools/doxygen.baseline lists the doxygen warnings the C headers still carry, and
# `# noqa` comments carry ruff's findings on the Python clients; either may fall, neither may grow. This compares their
# counts in the working tree with the base branch's (DOC_GATE_BASE, origin/main by default; CI passes the pull
# request's base), read with git: a base this clone does not hold is red, by name, never skipped. A base without the
# gate (no baseline, no ruff.toml: the change that brings it) has nothing to compare.
# DOC_GATE_PY: the Python paths ruff checks (the Makefile's check-ruff).
set -eu
cd "$(dirname "$0")/.."
base=${DOC_GATE_BASE:-origin/main}
py=${DOC_GATE_PY:-clients/python tests/lib/plugin_hostd_client.py}
if ! git rev-parse --verify -q "$base^{commit}" >/dev/null; then
    echo "doc-shrink: the base $base is not in this clone; fetch it (actions/checkout with fetch-depth: 0)"
    exit 1
fi
fail=0
if git cat-file -e "$base:tools/doxygen.baseline" 2>/dev/null; then
    was=$(git show "$base:tools/doxygen.baseline" | wc -l)
    now=$(wc -l < tools/doxygen.baseline)
    if [ "$now" -gt "$was" ]; then
        echo "doc-shrink: tools/doxygen.baseline grew from $was to $now lines against $base: document the symbol instead"
        fail=1
    fi
    echo "doc-shrink: tools/doxygen.baseline $now lines, $was at $base"
else
    echo "doc-shrink: $base has no tools/doxygen.baseline (this change brings the gate): nothing to compare"
fi
if git cat-file -e "$base:ruff.toml" 2>/dev/null; then
    # shellcheck disable=SC2086 # the paths are words
    was=$(git grep -o '# noqa' "$base" -- $py | wc -l)
    # shellcheck disable=SC2086
    now=$(grep -rIo '# noqa' $py | wc -l)
    if [ "$now" -gt "$was" ]; then
        echo "doc-shrink: the # noqa comments grew from $was to $now against $base: fix the finding instead"
        fail=1
    fi
    echo "doc-shrink: $now # noqa comments, $was at $base"
else
    echo "doc-shrink: $base has no ruff.toml (this change brings the gate): nothing to compare"
fi
exit "$fail"
