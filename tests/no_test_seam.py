#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The production daemon carries no test seam for the qualification store.

Usage: no_test_seam.py <plugin-hostd binary>

The test builds of the daemon (src/main.c, OMX_QUALIFICATION_TEST_STORE) open the store file the variable
PLUGIN_HOSTD_TEST_QUALIFICATION_STORE names; the packaged daemon opens the store of its scope with pqdb_open and reads no
variable and no path. The binary the Makefile builds with no test define is the one that is packaged (the rpm and deb builds
run the same make), and an installed one can be checked as well: make check-no-test-seam BIN=/usr/bin/plugin-hostd.
The check proves it can see a string before it trusts an empty result: the binary must hold PLUGIN_HOSTD_CONF, which the
daemon reads, and its own scan finds the seam in a copy that has it planted.
"""
import sys

SEAM = b"PLUGIN_HOSTD_TEST_QUALIFICATION_STORE"
CONTROL = b"PLUGIN_HOSTD_CONF"


def check(data):
    """(ok, why) for the bytes of a daemon binary"""
    if CONTROL not in data:
        return False, "the scan cannot see the daemon's own strings (no %s): nothing is proved" % CONTROL.decode()
    if SEAM in data:
        return False, "the daemon carries the test seam %s: it was built with OMX_QUALIFICATION_TEST_STORE" % SEAM.decode()
    return True, ""


def main(argv):
    """Check the binary named on the command line."""
    if len(argv) != 2:
        sys.exit(__doc__)
    with open(argv[1], "rb") as f:
        data = f.read()
    planted_ok, _ = check(data + SEAM)
    if planted_ok:
        sys.exit("FAIL the scan does not see a planted seam")
    ok, why = check(data)
    if not ok:
        print("FAIL no_test_seam: %s" % why)
        sys.exit(1)
    print("ok   no_test_seam: %s holds no test seam for the qualification store" % argv[1])


if __name__ == "__main__":
    main(sys.argv)
