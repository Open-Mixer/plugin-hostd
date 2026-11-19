# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# plugin-hostd-contract carries the qualification domain: contract.d/qualification/qualification.json at 1.4.0, x-owner
# plugin-hostd, installed beside machine and probe by the package lists. Held here:
#   1. the document is 1.4.0, owned by plugin-hostd, and no item's x-since is above the document's own version
#      (omx-contract's rule domain-x-since);
#   2. the five items 1.4.0 added are there, x-since 1.4.0, with exactly their words:
#        QUALIFICATION_ADAPTER_HOSTS     omx-clap-host, mod-host, jalv
#        QUALIFICATION_PIN_VERDICTS      in-process, isolated, refused
#        QUALIFICATION_HISTORY_MOVES     demote, promote, none
#        QUALIFICATION_HISTORY_REASONS   history.crashed, history.xruns-grouped, history.crashed-alone, history.steady,
#                                        history.no-record, history.no-change, history.not-liftable
#        QUALIFICATION_HISTORY_BLOCKERS  unknown, refused, no-deciding-reason
#   3. the three package lists (spec %files, debian/plugin-hostd-contract.install, ci.yml's expected file list) name the
#      document, and the Makefile installs it by the domain mode of omx-contract's installer.
# The document's validity against the installed omx-contract is `make check-contract-dir` and `make check-machine-codes`.
#
#   python3 tests/qualification_owned.py [<contract.d>]   red on any of the above
#   python3 tests/qualification_owned.py --self-test      each item dropped in a scratch copy, a word dropped, an x-since
#                                                         above the version, a wrong owner and a wrong version, each must be red
import copy
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = os.path.join("qualification", "qualification.json")
NEW = {
    "QUALIFICATION_ADAPTER_HOSTS": ["omx-clap-host", "mod-host", "jalv"],
    "QUALIFICATION_PIN_VERDICTS": ["in-process", "isolated", "refused"],
    "QUALIFICATION_HISTORY_MOVES": ["demote", "promote", "none"],
    "QUALIFICATION_HISTORY_REASONS": ["history.crashed", "history.xruns-grouped", "history.crashed-alone", "history.steady",
                                      "history.no-record", "history.no-change", "history.not-liftable"],
    "QUALIFICATION_HISTORY_BLOCKERS": ["unknown", "refused", "no-deciding-reason"],
}


def ver(v):
    return tuple(int(x) for x in v.split("."))


def check_doc(doc):
    fails = []
    info = doc.get("info", {})
    if info.get("version") != "1.4.0":
        fails.append("info.version is %r, not 1.4.0" % info.get("version"))
    if info.get("x-owner") != "plugin-hostd":
        fails.append("info.x-owner is %r, not plugin-hostd" % info.get("x-owner"))
    items = doc.get("components", {}).get("schemas", {})
    for name, schema in items.items():
        since = schema.get("x-since")
        if not since or ver(since) > ver(info.get("version", "0.0.0")):
            fails.append("%s: x-since %r is above the document's %r" % (name, since, info.get("version")))
    for name, words in NEW.items():
        item = items.get(name)
        if item is None:
            fails.append("%s is not in the document" % name)
            continue
        if item.get("x-since") != "1.4.0":
            fails.append("%s: x-since is %r, not 1.4.0" % (name, item.get("x-since")))
        got = [w.get("const") for w in item.get("oneOf", [])]
        if got != words:
            fails.append("%s: words %r, not %r" % (name, got, words))
    return fails


def check_packages():
    fails = []
    def has(path, needle):
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            return needle in f.read()
    for path, needle in (("packaging/plugin-hostd.spec", "%{omx_contract_domain_dir}/qualification/"),
                         ("debian/plugin-hostd-contract.install", "usr/share/omx-contract/contract.d/qualification"),
                         (".github/workflows/ci.yml", "/usr/share/omx-contract/contract.d/qualification/qualification.json"),
                         ("Makefile", "--domain contract.d/qualification ")):
        if not has(path, needle):
            fails.append("%s does not name %s" % (path, needle))
    return fails


def load(contract_dir):
    with open(os.path.join(contract_dir, REL), encoding="utf-8") as f:
        return json.load(f)


def main():
    args = sys.argv[1:]
    if args == ["--self-test"]:
        doc = load(os.path.join(ROOT, "contract.d"))
        bad = 0
        if check_doc(doc):
            print("FAIL the shipped document is not green before the sabotage: %s" % check_doc(doc))
            return 1
        cases = []
        for name in NEW:
            d = copy.deepcopy(doc); del d["components"]["schemas"][name]; cases.append("drop item %s" % name), cases.append(d)
            d = copy.deepcopy(doc); d["components"]["schemas"][name]["oneOf"].pop(); cases.append("drop a word of %s" % name), cases.append(d)
        d = copy.deepcopy(doc); d["components"]["schemas"]["QUALIFICATION_PIN_VERDICTS"]["x-since"] = "1.5.0"; cases += ["x-since above the version", d]
        d = copy.deepcopy(doc); d["info"]["x-owner"] = "plugin-qualify"; cases += ["owner plugin-qualify", d]
        d = copy.deepcopy(doc); d["info"]["version"] = "1.3.0"; cases += ["version 1.3.0", d]
        for label, d in zip(cases[0::2], cases[1::2]):
            red = check_doc(d)
            print(("PASS" if red else "FAIL") + " self-test: %s is red" % label)
            bad += 0 if red else 1
        return 1 if bad else 0
    fails = check_packages()
    try:
        fails += check_doc(load(args[0] if args else os.path.join(ROOT, "contract.d")))
    except FileNotFoundError as e:
        fails.append("the document is absent: %s" % e.filename)
    for f in fails:
        print("FAIL " + f)
    if not fails:
        print("PASS plugin-hostd-contract carries the qualification domain 1.4.0, x-owner plugin-hostd, with the five 1.4.0 items")
    return 1 if fails else 0


sys.exit(main())
