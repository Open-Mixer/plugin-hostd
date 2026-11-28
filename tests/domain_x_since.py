# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# An item's x-since is the info.version of its domain document that first carried it (omx-contract's contract
# directory rule): never a version above the document's own, never a package's or omx-contract's release. A domain's
# version is the version of its vocabulary, never the package's (owner, 2026-11-25): it started again at 0.1.0 and
# rises only when that domain's own words or items change. The domains plugin-hostd owns are held to the versions that
# added each item, every one of them 0.1.0 at the reset (SINCE below).
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
        "MACHINE_CLASS_FIELDS": "0.1.0",
        "MACHINE_PROFILE_FIELDS": "0.1.0",
        "MACHINE_CORE_BANDS": "0.1.0",
        "MACHINE_CLOCK_BANDS": "0.1.0",
        "MACHINE_ARCHES": "0.1.0",
        "MACHINE_FAMILIES": "0.1.0",
    },
    "qualification": {
        "QUALIFICATION_MEASUREMENT_DIMENSIONS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_UNMEASURED_KINDS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_UNMEASURED_REASONS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_LATENCY_METHODS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_COST_METHODS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_LATENCY_SCALING": "0.1.0",
        "QUALIFICATION_MEASUREMENT_LATENCY_SCALING_NOTES": "0.1.0",
        "QUALIFICATION_MEASUREMENT_LATENCY_EXCLUSIONS": "0.1.0",
        "QUALIFICATION_MEASUREMENT_VOICE_BASES": "0.1.0",
        "QUALIFICATION_MEASUREMENT_VERDICT_RATINGS": "0.1.0",
        "QUALIFICATION_RESOURCE_MEMORY_PHASES": "0.1.0",
        "QUALIFICATION_RESOURCE_UNMEASURED_REASONS": "0.1.0",
        "QUALIFICATION_RESOURCE_BUDGET_SCOPES": "0.1.0",
        "QUALIFICATION_RESOURCE_HOST_ISOLATIONS": "0.1.0",
        "QUALIFICATION_RESOURCE_HOST_LATENCY_HANDLING": "0.1.0",
        "QUALIFICATION_RESOURCE_THREAD_SCHEDULING": "0.1.0",
        "QUALIFICATION_HOST_CLASSES": "0.1.0",
        "QUALIFICATION_SET_TIERS": "0.1.0",
        "QUALIFICATION_HOST_PROFILES": "0.1.0",
        "QUALIFICATION_SYNC_SETTINGS": "0.1.0",
        "QUALIFICATION_OFFERS": "0.1.0",
        "QUALIFICATION_PACKAGE_FORMATS": "0.1.0",
        "QUALIFICATION_PACKAGE_DISTROS": "0.1.0",
        "QUALIFICATION_PACKAGE_ARCHES": "0.1.0",
        "QUALIFICATION_VERDICT_HOSTINGS": "0.1.0",
        "QUALIFICATION_VERDICT_ARMS": "0.1.0",
        "QUALIFICATION_REASON_PARAMS": "0.1.0",
        "QUALIFICATION_REASON_PARAM_WORDS": "0.1.0",
        "QUALIFICATION_RECORD_TIERS": "0.1.0",
        "QUALIFICATION_MEMORY_LIMIT_MECHANISMS": "0.1.0",
        "QUALIFICATION_NOTE_SWEEP_DIALECTS": "0.1.0",
        "QUALIFICATION_RUN_STEPS": "0.1.0",
        "QUALIFICATION_STEP_RESULTS": "0.1.0",
        "QUALIFICATION_GROUPABLE_CONDITIONAL_CODES": "0.1.2",
        "QUALIFICATION_NO_FIGURES_REASONS": "0.1.2",
        "QUALIFICATION_STEP_CODES": "0.1.0",
        "QUALIFICATION_REJUDGE_OWES": "0.1.0",
        "QUALIFICATION_REJUDGE_MEASUREMENTS": "0.1.0",
        "QUALIFICATION_ADAPTER_HOSTS": "0.1.0",
        "QUALIFICATION_PIN_VERDICTS": "0.1.0",
        "QUALIFICATION_HISTORY_MOVES": "0.1.0",
        "QUALIFICATION_HISTORY_REASONS": "0.1.0",
        "QUALIFICATION_HISTORY_BLOCKERS": "0.1.0",
        "QUALIFICATION_ADAPTER_CODE_KINDS": "0.1.0",
        "QUALIFICATION_MEMORY_BOUND_OUTCOMES": "0.1.0",
        "QUALIFICATION_UNIT_PROVENANCES": "0.1.0",
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
        "an item given a version the domain did not add it at": lambda d: s(d)["MACHINE_FAMILIES"].__setitem__("x-since", "0.0.9"),
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
