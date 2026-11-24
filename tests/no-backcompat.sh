#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Development keeps no backward-compatibility machinery (owner rule, 2026-11-16): the paths below are gone and stay gone.
#   sh tests/no-backcompat.sh      each line is ok or FAIL; exit 1 on any FAIL
cd "$(dirname "$0")/.." || exit 2
bad=0
gone() { # gone <what> <fixed-string> <file>...
    what=$1; pat=$2; shift 2
    if grep -qF -- "$pat" "$@" 2>/dev/null; then echo "FAIL $what is still there ($pat)"; bad=1; else echo "ok   $what is gone"; fi
}
gone "the python client's table without arg_types" 't.get("arg_types")' clients/python/plugin_hostd_protocol/__init__.py
gone "the ts client's table without arg_types" 't.arg_types ?? ' clients/ts/src/index.ts
exit $bad
