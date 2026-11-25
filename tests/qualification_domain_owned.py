#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/qualification_domain_owned.py: plugin-hostd owns the domain `qualification` (contract.d/qualification/qualification.json),
the vocabulary sorting pass, row V5. The domain was plugin-qualify's up to 1.4.0 at plugin-qualify 2d6aefc; its words are
frozen in tests/fixtures/qualification-golden.json (item -> [title, word] pairs, in the document's order), less
QUALIFICATION_MACHINE_CLASSES, which nothing reads (ownership map rows 5 and 20) and is dropped from the domain and its catalogs.

a. golden: the document of this checkout, and the tree `make install_qualification_domain DESTDIR=<tmp>` installs, hold
   exactly the golden items with the golden words; info.x-owner and every catalog's owner are plugin-hostd;
b. both sources agree while both exist: when QUALIFICATION_OLD_DOMAIN names a contract directory holding plugin-qualify's
   qualification domain, the two documents are equal but for the owner (skipped, and said so, when it is not set);
c. sabotage: the installed tree with one word removed from its document is refused by the golden comparison, and so is
   an installed tree with an item removed (the test is run against a scratch copy, the source is never edited).

d. packaging: the spec and debian/control name no plugin-qualify package ending -contract (the package is pruned from the channel; no Breaks,
   Replaces, Conflicts or Provides stand in for it) and plugin-hostd-contract ships the domain, in the spec's %files and in
   debian/plugin-hostd-contract.install.

Environment: PKG_ROOT (the tree whose packaging arm d reads, default this one), INSTALL_CONTRACT_DIR (the installer, as the Makefile finds it), QUALIFICATION_OLD_DOMAIN (arm b). Exit 0 all green,
1 a FAIL line.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "qualification-golden.json")
DOC = os.path.join("qualification", "qualification.json")
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def words(doc):
    return {k: [[e["title"], e["const"]] for e in v["oneOf"]] for k, v in doc["components"]["schemas"].items()}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def catalog_owners(domain_dir):
    cat = os.path.join(domain_dir, "qualification", "catalogs")
    return sorted({load(os.path.join(cat, f)).get("owner") for f in os.listdir(cat)}) if os.path.isdir(cat) else []


def install(tmp):
    cmd = ["make", "--no-print-directory", "-C", ROOT, "install_qualification_domain", "DESTDIR=" + tmp]
    if os.environ.get("INSTALL_CONTRACT_DIR"):
        cmd.append("INSTALL_CONTRACT_DIR=" + os.environ["INSTALL_CONTRACT_DIR"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr.strip() or r.stdout.strip()).splitlines()[-1:]
    pc = subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True, text=True).stdout.strip() \
        or "/usr/share/omx-contract/contract.d"
    return tmp + pc, None


# the pruned package's name, built from its parts: this guard asserts it is absent, so the literal never stands in the tree
OLD_PACKAGE = "plugin-qualify" + "-contract"


def packaging(root):
    def read(rel):
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read()
    spec = read("packaging/plugin-hostd.spec").split("%changelog")[0]
    control = read("debian/control")
    named = [rel for rel, text in (("packaging/plugin-hostd.spec", spec), ("debian/control", control))
             if OLD_PACKAGE in text]
    check(not named, "d. nothing but the changelogs names %s: %s" % (OLD_PACKAGE, named))
    relations = [line for line in (spec + control).splitlines()
                 if line.split(":")[0].strip() in ("Breaks", "Replaces", "Conflicts", "Provides", "Obsoletes") and "qualif" in line]
    check(not relations, "d. no Breaks, Replaces, Conflicts, Provides or Obsoletes for the old package: %s" % relations)
    check("%{omx_contract_dir}/qualification/" in spec.split("%files contract")[-1],
          "d. the spec's %files contract holds the qualification domain")
    check("usr/share/omx-contract/contract.d/qualification" in read("debian/plugin-hostd-contract.install").split(),
          "d. debian/plugin-hostd-contract.install holds the qualification domain")


def main():
    packaging(os.environ.get("PKG_ROOT", ROOT))
    golden = load(GOLDEN)
    src = os.path.join(ROOT, "contract.d")
    doc_path = os.path.join(src, DOC)
    check(os.path.isfile(doc_path), "contract.d/qualification/qualification.json is in this tree")
    if not os.path.isfile(doc_path):
        print("qualification domain owned: FAILED (%d)" % failed)
        return 1
    doc = load(doc_path)
    check(words(doc) == golden, "a. the document's items and words are the golden ones (%d items)" % len(golden))
    check(doc["info"].get("x-owner") == "plugin-hostd", "a. info.x-owner is plugin-hostd: %r" % doc["info"].get("x-owner"))
    check("QUALIFICATION_MACHINE_CLASSES" not in doc["components"]["schemas"], "a. QUALIFICATION_MACHINE_CLASSES is not an item of the domain")
    texts = [k for f in os.listdir(os.path.join(src, "qualification", "catalogs")) for k in load(os.path.join(src, "qualification", "catalogs", f))["messages"]
             if k.startswith("QUALIFICATION_MACHINE_CLASSES.")]
    check(not texts, "a. no catalog holds a text of it: %s" % texts[:2])
    check(catalog_owners(src) == ["plugin-hostd"], "a. every catalog's owner is plugin-hostd: %s" % catalog_owners(src))

    old = os.environ.get("QUALIFICATION_OLD_DOMAIN")
    if old and os.path.isfile(os.path.join(old, DOC)):
        o = load(os.path.join(old, DOC))
        o["info"]["x-owner"] = doc["info"]["x-owner"]
        check(o == doc, "b. the document is plugin-qualify's, but for the owner")
    else:
        print("skip b. QUALIFICATION_OLD_DOMAIN names no directory holding plugin-qualify's domain")

    with tempfile.TemporaryDirectory(prefix="plugin-hostd-qualification-owned.") as tmp:
        tree, why = install(tmp)
        check(tree is not None, "make install_qualification_domain installs the domain: %s" % (why or ""))
        if tree:
            installed = os.path.join(tree, DOC)
            check(os.path.isfile(installed) and words(load(installed)) == golden, "a. the installed document holds the golden words")
            check(os.path.isfile(installed) and open(installed, "rb").read() == open(doc_path, "rb").read(),
                  "the installed document is the source, byte for byte")
            check(os.path.isfile(os.path.join(tree, "qualification", "catalogs", "ca.json")), "the catalogs are installed with it")
            # c. one word removed from a scratch copy of the installed tree: the golden comparison refuses it
            scratch = os.path.join(tmp, "scratch")
            shutil.copytree(tree, scratch)
            bad = load(os.path.join(scratch, DOC))
            item = bad["components"]["schemas"]["QUALIFICATION_MEASUREMENT_VERDICT_RATINGS"]
            item["oneOf"] = [e for e in item["oneOf"] if e["title"] != "conditional"]
            check(words(bad) != golden, "c. a tree with one word removed is refused by the golden comparison")
            bad2 = copy.deepcopy(load(os.path.join(scratch, DOC)))
            del bad2["components"]["schemas"]["QUALIFICATION_PIN_VERDICTS"]
            check(words(bad2) != golden, "c. a tree with one item removed is refused by the golden comparison")
    print("qualification domain owned: %s" % ("FAILED (%d)" % failed if failed else "ok"))
    return 1 if failed else 0


sys.exit(main())
