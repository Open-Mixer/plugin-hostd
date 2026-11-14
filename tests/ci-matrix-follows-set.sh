#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# Ruling D25: a CI matrix follows the release set, never a hand list. bookworm is a full cell, built and served its
# floors only by the wave-end full release; while the organisation variable OMX_RELEASE_MATRIX is quick it cannot
# satisfy a floor released quick-only, so a hand-written bookworm cell turns every pull request red. A workflow line that
# names bookworm outside a comment must choose it through OMX_RELEASE_MATRIX on that same line.
# `ci-matrix-follows-set.sh [workflow...]`; with --self-test it also plants a hand cell and expects red.
set -eu
check() {
  bad=$(awk '/^[[:space:]]*#/ { next } /bookworm/ && !/OMX_RELEASE_MATRIX/ { print FILENAME ":" FNR ": " $0 }' "$@")
  if [ -n "$bad" ]; then
    printf '%s\n' "$bad" >&2
    echo "FAIL a hand-written bookworm cell: CI follows the release set (vars.OMX_RELEASE_MATRIX, ruling D25)" >&2
    return 1
  fi
}
self_test=
[ "${1:-}" = --self-test ] && { self_test=1; shift; }
[ $# -gt 0 ] || set -- .github/workflows/*.yml
check "$@"
echo "ok   no workflow names bookworm outside the OMX_RELEASE_MATRIX switch ($#)"
if [ -n "$self_test" ]; then
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  printf '    strategy:\n      matrix:\n        image: [%s]\n' "'fedora:44', 'debian:bookworm'" > "$tmp/planted.yml"
  if check "$tmp/planted.yml" 2>/dev/null; then echo "FAIL the self-test's hand bookworm cell passed" >&2; exit 1; fi
  echo "ok   a hand bookworm cell is red"
fi
