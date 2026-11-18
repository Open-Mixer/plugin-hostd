#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/machine_domain.py: plugin-hostd owns the domain `machine` (contract.d/machine/machine.json) ; consumer-move recipe,
arms 1, 2, 4 and 7 (arms 3, 5 and 6 need the loader in plugin-hostd's own code and follow in part 2).

1. the document conforms: omx-contract validate and fmt --check, $schema, $id, info.x-owner/x-stability, every item MACHINE_-prefixed;
2. no machine_vocabulary.h exists or is included;
4. include/plugin-hostd/machine_codes.h holds exactly the items marked x-c-codes and is the render (--check), or there is none;
7. make install_machine_domain DESTDIR=<tmp> gives the tree the loader reads: omx_domain_open_at opens it and finds a
   word and a catalog text.

Environment: OMX_CONTRACT (the command, default omx-contract), INSTALL_CONTRACT_DIR (the installer, default found by
pkg-config), DOMAIN_CFLAGS and DOMAIN_LIBS (the loader, default pkg-config libomx-domain), CC. Exit 0 all green, 1 a
FAIL line.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "contract.d", "machine", "machine.json")
HEADER = os.path.join(ROOT, "include", "plugin-hostd", "machine_codes.h")
OMX = shlex.split(os.environ.get("OMX_CONTRACT", "omx-contract"))
failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL " + msg)


def ok(msg):
    print("ok   " + msg)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def load():
    try:
        with open(DOC) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        fail("arm 1: contract.d/machine/machine.json is not readable: %s" % e)
        return None


def arm1(doc):
    if doc is None:
        return
    before = len(failures)
    r = run(OMX + ["validate", "--contract-dir", "contract.d"])
    if r.returncode != 0:
        fail("arm 1: omx-contract validate --contract-dir contract.d: %s" % (r.stderr.strip() or r.stdout.strip()))
    r = run(OMX + ["fmt", "--check", "--contract-dir", "contract.d"])
    if r.returncode != 0:
        fail("arm 1: omx-contract fmt --check --contract-dir contract.d: %s" % (r.stderr.strip() or r.stdout.strip()))
    if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("arm 1: $schema is %r, not the 2020-12 schema" % doc.get("$schema"))
    if doc.get("$id") != "https://openmixer.org/contract/machine":
        fail("arm 1: $id is %r, not https://openmixer.org/contract/machine" % doc.get("$id"))
    info = doc.get("info", {})
    if info.get("x-owner") != "plugin-hostd":
        fail("arm 1: info.x-owner is %r, not plugin-hostd" % info.get("x-owner"))
    if info.get("x-stability") != "experimental":
        fail("arm 1: info.x-stability is %r, not experimental" % info.get("x-stability"))
    for name in doc.get("components", {}).get("schemas", {}):
        if not name.startswith("MACHINE_"):
            fail("arm 1: item %s does not start with MACHINE_" % name)
    if len(failures) == before:
        ok("arm 1: the document conforms")


def arm2():
    before = len(failures)
    skip = {"tests/machine_domain.py"}
    names = run(["git", "ls-files", "-co", "--exclude-standard"]).stdout.split()
    for rel in names:
        if rel in skip or not os.path.isfile(os.path.join(ROOT, rel)):
            continue
        if "machine_vocabulary" in os.path.basename(rel):
            fail("arm 2: %s exists" % rel)
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if "machine_vocabulary" in text:
            fail("arm 2: %s names machine_vocabulary" % rel)
    if len(failures) == before:
        ok("arm 2: no machine_vocabulary file or include")


def arm4(doc):
    before = len(failures)
    marked = []
    if doc is not None:
        marked = [k for k, v in doc.get("components", {}).get("schemas", {}).items() if v.get("x-c-codes")]
    items = []
    if os.path.isfile(HEADER):
        items = re.findall(r"#define OMX_(MACHINE_[A-Z0-9_]+?)_COUNT ", open(HEADER).read())
    elif marked:
        fail("arm 4: %s are marked x-c-codes and include/plugin-hostd/machine_codes.h does not exist" % sorted(marked))
    if sorted(items) != sorted(marked):
        fail("arm 4: machine_codes.h holds %s, the x-c-codes items are %s" % (sorted(items), sorted(marked)))
    for name in marked:
        if not any(name in open(os.path.join(ROOT, f), errors="replace").read() for f in glob.glob(os.path.join(ROOT, "src", "*.c"))):
            fail("arm 4: %s is marked x-c-codes and no file of src/ names it" % name)
    r = run(OMX + ["render", "--target", "c", "--package", "machine", "--contract-dir", "contract.d", "--out", "include/plugin-hostd", "--check"])
    if r.returncode != 0:
        fail("arm 4: omx-contract render --check: %s" % (r.stderr.strip() or r.stdout.strip()))
    if len(failures) == before:
        ok("arm 4: machine_codes.h holds the x-c-codes items only (%d) and is the render" % len(marked))


def arm7():
    before = len(failures)
    with tempfile.TemporaryDirectory() as tmp:
        make = ["make", "--no-print-directory", "install_machine_domain", "DESTDIR=" + tmp]
        if os.environ.get("INSTALL_CONTRACT_DIR"):
            make.append("INSTALL_CONTRACT_DIR=" + os.environ["INSTALL_CONTRACT_DIR"])
        r = run(make)
        if r.returncode != 0:
            fail("arm 7: make install_machine_domain: %s" % (r.stderr.strip() or r.stdout.strip()).splitlines()[-1:])
            return
        pc = run(["pkg-config", "--variable=contractdir", "omx-contract"]).stdout.strip() or "/usr/share/omx-contract/contract.d"
        installed = tmp + pc
        for rel in ("machine/machine.json", "machine/catalogs/ca.json"):
            if not os.path.isfile(os.path.join(installed, rel)):
                fail("arm 7: %s is not installed under %s" % (rel, pc))
        cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
        libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
        exe = os.path.join(tmp, "machine_domain_open")
        cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-o", exe, "tests/machine_domain_open.c"]
        b = run(cc + shlex.split(cflags) + shlex.split(libs))
        if b.returncode != 0:
            fail("arm 7: tests/machine_domain_open.c does not build (a loader is needed, libomx-domain): %s" % b.stderr.strip()[-200:])
            return
        o = run([exe, installed, "1.0.0", "MACHINE_CORE_BANDS", "1-2", "MACHINE_CORE_BANDS.1-2", "ca"])
        if o.returncode != 0:
            fail("arm 7: the loader does not read the installed tree: %s" % o.stderr.strip())
        else:
            print("     " + o.stdout.strip())
            # the text is the installed catalog's, not the source sentence the loader falls back to without one
            with open(os.path.join(ROOT, "contract.d/machine/catalogs/ca.json"), encoding="utf-8") as f:
                want = json.load(f)["messages"]["MACHINE_CORE_BANDS.1-2"]["text"]
            if not o.stdout.strip().endswith(" text=" + want):
                fail("arm 7: the ca text read is not the installed catalog's (%r): %s" % (want, o.stdout.strip()))
    if len(failures) == before:
        ok("arm 7: the installed tree opens through omx_domain_open_at, a word and a catalog text are found")


def main():
    doc = load()
    arm1(doc)
    arm2()
    arm4(doc)
    arm7()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
