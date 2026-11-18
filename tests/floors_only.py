#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# Floors only: every dependency listed in packaging/deps.txt is declared at its floor and nowhere above it. The RPM spec
# (Requires, BuildRequires, Recommends) and debian/control (Depends, Build-Depends, Recommends) carry no `<`, `<=`, `=`,
# `<<` or `<<=` on any listed package, so a planted ceiling on one of our packages is red. The shared engine
# (Open-Mixer/.github deps-render, render.sh --check) holds the numbers; this holds the rule the engine does not state.
# Usage: floors_only.py [root]. The check proves it sees a planted ceiling in a scratch copy before it trusts the tree.
import os, re, shutil, sys, tempfile

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPS = os.path.join("packaging", "deps.txt")


def rows(root):
    """(rpm name, deb name) of every dependency deps.txt lists"""
    out = []
    with open(os.path.join(root, DEPS)) as f:
        for line in f:
            if line.strip() == "" or line.lstrip().startswith("#"):
                continue
            cols = line.split()
            out.append((cols[0], cols[1]))
    return out


def ceilings(spec, ctl, rpm, deb):
    """every ceiling on rpm in the spec and on deb in debian/control, as 'where: text'"""
    found = []
    # the rpm name, not followed by a name character, then an operator that caps it (`<`, `<=`, `=`); `>=` and `>` are floors
    rx_spec = re.compile(r"(?<![\w.+-])%s(?![\w.+-])(?:%%\{\?_isa\})?\s*(?:<=|<|=)(?!=)\s*\S+" % re.escape(rpm))
    for line in spec.splitlines():
        if re.match(r"^\s*(Build)?(Requires|Recommends|Conflicts|Obsoletes)\s*:", line) and rx_spec.search(line):
            found.append("packaging/plugin-hostd.spec: %s" % line.strip())
    # the deb name and a parenthesised operator that caps it: `(<< x)`, `(<= x)`, `(< x)`, `(= x)`
    rx_ctl = re.compile(r"(?<![\w.+-])%s\s*\(\s*(?:<<|<=|<|=)\s*[^)]+\)" % re.escape(deb))
    for m in rx_ctl.finditer(ctl):
        found.append("debian/control: %s" % m.group(0))
    return found


def problems(root):
    spec = open(os.path.join(root, "packaging", "plugin-hostd.spec")).read()
    ctl = open(os.path.join(root, "debian", "control")).read()
    bad = []
    for rpm, deb in rows(root):
        bad += ["%s carries a ceiling on %s (floors only): %s" % (where, rpm, text)
                for where, text in [t.split(": ", 1) for t in ceilings(spec, ctl, rpm, deb)]]
    return bad


def scratch(spec, ctl, deps):
    """a scratch tree holding the given spec, debian/control and deps.txt, and its findings"""
    tmp = tempfile.mkdtemp(prefix="floors-only.", dir=os.environ.get("TMPDIR") or None)
    try:
        os.makedirs(os.path.join(tmp, "packaging"))
        os.makedirs(os.path.join(tmp, "debian"))
        open(os.path.join(tmp, "packaging", "plugin-hostd.spec"), "w").write(spec)
        open(os.path.join(tmp, "debian", "control"), "w").write(ctl)
        open(os.path.join(tmp, DEPS), "w").write(deps)
        return problems(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    real_spec = open(os.path.join(ROOT, "packaging", "plugin-hostd.spec")).read()
    real_ctl = open(os.path.join(ROOT, "debian", "control")).read()
    deps = open(os.path.join(ROOT, DEPS)).read()
    dep_rows = rows(ROOT)
    if not dep_rows:
        print("FAIL %s lists no dependency" % DEPS)
        return 1
    # the scratch tree first: the floor as written is clean, and a ceiling planted on EACH listed package is red
    clean = scratch("Requires: plugin-hostd-protocol >= 0.5.9\n", "Depends: libplugin-hostd-protocol0 (>= 0.5.9~)\n", deps)
    if clean:
        print("FAIL the floors-only check flags a bare floor: %s" % clean)
        return 1
    for rpm, deb in dep_rows:
        for what, spec_add, ctl_add in (
                ("in the spec", "Requires: %s < 1\n" % rpm, ""),
                ("in the spec, the rich form", "Requires: (%s >= 0.1 with %s < 1)\n" % (rpm, rpm), ""),
                ("in the spec, an exact pin", "BuildRequires: %s = 0.1\n" % rpm, ""),
                ("in debian/control", "", "Depends: %s (<< 1~)\n" % deb),
                ("in debian/control, an exact pin", "", "Depends: %s (= 0.1)\n" % deb)):
            got = scratch(real_spec + spec_add, real_ctl + ctl_add, deps)
            if not got:
                print("FAIL the floors-only check misses a ceiling on %s %s" % (rpm, what))
                return 1
    print("ok   the floors-only check sees a planted ceiling or pin on every listed package, in the spec and in debian/control")
    failed = problems(ROOT)
    for b in failed:
        print("FAIL %s" % b)
    if failed:
        return 1
    print("ok   every package in packaging/deps.txt is declared at its floor and no ceiling (%d listed)" % len(dep_rows))
    return 0


sys.exit(main())
