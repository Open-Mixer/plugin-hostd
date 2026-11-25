#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas
"""tests/qualification_pin_stage_test.py: the scratch contract directory of tests/qualification_pin_from.py carries an
owner package with the domains its manifest lists (plugin-db#84). An owner whose contract is only domains (plugin-db:
plugin-db, format, lv2, plugin-feature) installs <contractdir>/3/<package>/MANIFEST.json with "domains"; a staged copy
of the manifest without those domains is a package whose domains are missing, refused by every reader. A fake installed
directory holds such an owner; the staged copy must hold its manifest and each domain it lists, and nothing else.

Exit 0 green, 1 a FAIL line."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qualification_pin_from as q  # noqa: E402

failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    failed += not cond


with tempfile.TemporaryDirectory() as tmp:
    installed, d = os.path.join(tmp, "installed"), os.path.join(tmp, "staged")
    os.makedirs(os.path.join(installed, "3", "plugin-db"))
    with open(os.path.join(installed, "3", "plugin-db", "MANIFEST.json"), "w") as f:
        json.dump({"package": "plugin-db", "version": "0.5.2", "schemaMajor": 3, "files": {}, "domains": ["plugin-db", "format"]}, f)
    for domain in ("plugin-db", "format", "unrelated"):
        os.makedirs(os.path.join(installed, domain))
        with open(os.path.join(installed, domain, domain + ".json"), "w") as f:
            f.write("{}")
    os.makedirs(d)
    q.copy_package(installed, d, "plugin-db")
    check(os.path.isfile(os.path.join(d, "3", "plugin-db", "MANIFEST.json")), "the owner's manifest is staged")
    for domain in ("plugin-db", "format"):
        check(os.path.isfile(os.path.join(d, domain, domain + ".json")), "the domain %s its manifest lists is staged" % domain)
    check(not os.path.exists(os.path.join(d, "unrelated")), "a domain the manifest does not list is not staged")
    q.copy_package(installed, d, "absent")
    check(not os.path.exists(os.path.join(d, "3", "absent")), "a package not installed stages nothing")

sys.exit(1 if failed else 0)
