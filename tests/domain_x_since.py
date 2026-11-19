# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# An item's x-since is the info.version of its domain document that first carried it (omx-contract's contract
# directory rule): never a version above the document's own, never a package's or omx-contract's release. The domains
# plugin-hostd owns are held to the versions that added each item:
#
#   machine 1.0.0: MACHINE_CLASS_FIELDS, MACHINE_PROFILE_FIELDS, MACHINE_CORE_BANDS, MACHINE_CLOCK_BANDS, MACHINE_ARCHES
#   machine 1.1.0: MACHINE_FAMILIES
#   probe   1.0.0: every item
#
# An item a domain gains later is added to SINCE with the version that adds it, or this check is red.
#
#   python3 tests/domain_x_since.py [<contract.d>]   red on an item whose x-since is not the one above (default: this tree's)
#   python3 tests/domain_x_since.py --self-test      an omx-contract release (2.18.0), a version above the document's,
#                                                    a missing x-since and an item not listed, each planted in a scratch
#                                                    copy, must be red
import copy
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SINCE = {
    "machine": {
        "MACHINE_CLASS_FIELDS": "1.0.0",
        "MACHINE_PROFILE_FIELDS": "1.0.0",
        "MACHINE_CORE_BANDS": "1.0.0",
        "MACHINE_CLOCK_BANDS": "1.0.0",
        "MACHINE_ARCHES": "1.0.0",
        "MACHINE_FAMILIES": "1.1.0",
    },
    "probe": {
        "PROBE_REASONS": "1.0.0",
        "PROBE_OUTCOMES": "1.0.0",
        "PROBE_STEPS": "1.0.0",
        "PROBE_SIGNALS": "1.0.0",
    },
}

SEMVER = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")


def ver(v):
    return tuple(int(x) for x in SEMVER.match(v).groups())


def check(contract_dir):
    fails = []
    for domain, want in SINCE.items():
        path = os.path.join(contract_dir, domain, domain + ".json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        own = doc["info"]["version"]
        items = doc["components"]["schemas"]
        for item, schema in items.items():
            since = schema.get("x-since")
            if since is None or not SEMVER.match(since):
                fails.append("%s: %s has no x-since version (%r)" % (domain, item, since))
                continue
            if ver(since) > ver(own):
                fails.append("%s: %s x-since %s is above the document's %s" % (domain, item, since, own))
            if item not in want:
                fails.append("%s: %s is not listed in tests/domain_x_since.py (add the version that adds it)" % (domain, item))
            elif since != want[item]:
                fails.append("%s: %s x-since is %s, the domain added it at %s" % (domain, item, since, want[item]))
        for item in want:
            if item not in items:
                fails.append("%s: %s is listed and not in the document" % (domain, item))
    return fails


def self_test():
    src = os.path.join(ROOT, "contract.d")
    with open(os.path.join(src, "machine", "machine.json"), encoding="utf-8") as f:
        machine = json.load(f)

    def plant(change):
        doc = copy.deepcopy(machine)
        change(doc)
        tmp = tempfile.mkdtemp(prefix="x-since-")
        try:
            dst = os.path.join(tmp, "contract.d")
            shutil.copytree(src, dst)
            with open(os.path.join(dst, "machine", "machine.json"), "w", encoding="utf-8") as f:
                json.dump(doc, f)
            return check(dst)
        finally:
            shutil.rmtree(tmp)

    s = lambda doc: doc["components"]["schemas"]
    plants = {
        "an omx-contract release": lambda d: s(d)["MACHINE_ARCHES"].__setitem__("x-since", "2.18.0"),
        "a version above the document's": lambda d: s(d)["MACHINE_FAMILIES"].__setitem__("x-since", "9.0.0"),
        "a new item given an older version": lambda d: s(d)["MACHINE_FAMILIES"].__setitem__("x-since", "1.0.0"),
        "a missing x-since": lambda d: s(d)["MACHINE_CORE_BANDS"].pop("x-since"),
        "an item not listed": lambda d: s(d).__setitem__("MACHINE_PLANTED", dict(s(d)["MACHINE_ARCHES"])),
    }
    bad = 0
    for name, change in plants.items():
        fails = plant(change)
        if fails:
            print("PASS self-test: %s is red (%s)" % (name, fails[0]))
        else:
            print("FAIL self-test: %s passes" % name)
            bad += 1
    return bad


def main():
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(1 if self_test() else 0)
    contract_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "contract.d")
    fails = check(contract_dir)
    for f in fails:
        print("FAIL " + f)
    if fails:
        sys.exit(1)
    print("PASS every item's x-since is the version of its domain that added it (%s)" % ", ".join(SINCE))


if __name__ == "__main__":
    main()
