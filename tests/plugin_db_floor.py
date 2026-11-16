#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-db is a dependency with a floor and no ceiling wherever it is declared: 0.4.5, the release of the same pass
# (0.4.1 brought plugin_db_constants.h, which src/pins.h includes so the fuzz harnesses need no OpenSSL). The spec's
# two lines, debian/control's two items and the pkg-config file of
# the development package are read here; a missing line, a floor other than FLOOR and any ceiling are red.
# Usage: plugin_db_floor.py [root]. The check proves it sees each fault before it trusts the tree.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = "0.4.5"
SPEC = re.compile(r"^(?:Build)?Requires:\s*(pkgconfig\(plugin-db\)|plugin-db-devel)\s*>=\s*(\S+)\s*$", re.M)
SPEC_CEIL = re.compile(r"^(?:Build)?Requires:.*plugin-db[^\n]*(?:<|\bwith\b)", re.M)
SPEC_ANY = re.compile(r"^(?:Build)?Requires:.*plugin-db.*$", re.M)
CONTROL = re.compile(r"plugin-db-dev\s*\(>=\s*([^)\s~]+)~?\)")
CONTROL_CEIL = re.compile(r"plugin-db-dev\s*\((?:<<|<=|<|=)")
CONTROL_ANY = re.compile(r"plugin-db-dev\s*\(")
PC = re.compile(r"^Requires:.*\bplugin-db >= (\S+?)(?:,|\s*$)", re.M)
PC_CEIL = re.compile(r"^Requires:.*\bplugin-db\s*<", re.M)


def problems(spec, control, pc):
    bad = []
    # (file, the floor declarations found, the declarations of any shape, how many there must be)
    for name, found, named, want in (("packaging/plugin-hostd.spec", [f for _, f in SPEC.findall(spec)], len(SPEC_ANY.findall(spec)), 2),
                                     ("debian/control", CONTROL.findall(control), len(CONTROL_ANY.findall(control)), 2)):
        if len(found) != want or named != want:
            bad.append("%s: %d plugin-db declarations with a floor, %d name plugin-db; there must be %d" % (name, len(found), named, want))
        bad += ["%s: a floor of %s, it is %s" % (name, f, FLOOR) for f in found if f != FLOOR]
    bad += ["packaging/plugin-hostd.spec: a ceiling on plugin-db, floors only: %s" % m.group(0).strip() for m in SPEC_CEIL.finditer(spec)]
    bad += ["debian/control: a ceiling on plugin-db, floors only: %s" % m.group(0) for m in CONTROL_CEIL.finditer(control)]
    m = PC.search(pc)
    if not m:
        bad.append("protocol/plugin-hostd.pc.in: no 'plugin-db >= floor'")
    elif m.group(1) != FLOOR:
        bad.append("protocol/plugin-hostd.pc.in: a floor of %s, it is %s" % (m.group(1), FLOOR))
    if PC_CEIL.search(pc):
        bad.append("protocol/plugin-hostd.pc.in: a ceiling on plugin-db, floors only")
    return bad


# the tree as written, from FLOOR
SPEC_OK = ("BuildRequires: pkgconfig(plugin-db) >= {f}\n"
           "Requires: plugin-db-devel >= {f}\n").format(f=FLOOR)
CTL_OK = ("Build-Depends: plugin-db-dev (>= {f}~),\n"
          "Depends: x, plugin-db-dev (>= {f}~), y\n").format(f=FLOOR)
PC_OK = "Requires: plugin-hostd-protocol >= 0.5.0, plugin-db >= {f}\n".format(f=FLOOR)


def main():
    # each arm breaks the bound it names, read from FLOOR, so a moved floor moves the arms with it
    arms = [
        ("the tree as written", SPEC_OK, CTL_OK, PC_OK, 0),
        ("a ceiling in the spec", SPEC_OK.replace("Requires: plugin-db-devel >= %s" % FLOOR, "Requires: (plugin-db-devel >= %s with plugin-db-devel < 1)" % FLOOR), CTL_OK, PC_OK, 2),
        ("a low floor in the spec", SPEC_OK.replace(FLOOR, "0.0.1", 1), CTL_OK, PC_OK, 1),
        ("a ceiling in debian/control", SPEC_OK, CTL_OK.replace("Build-Depends: plugin-db-dev (>= %s~)," % FLOOR, "Build-Depends: plugin-db-dev (>= %s~), plugin-db-dev (<< 1~)," % FLOOR), PC_OK, 2),
        ("a ceiling in the pkg-config file", SPEC_OK, CTL_OK, PC_OK.rstrip("\n") + ", plugin-db < 1\n", 1),
    ]
    for what, spec, ctl, pc, want in arms:
        got = problems(spec, ctl, pc)
        if len(got) != want:
            print("FAIL the plugin-db check on %s: want %d findings, got %s" % (what, want, got))
            return 1
    print("ok   the plugin-db check sees a low floor and any ceiling in the spec, debian/control and the pkg-config file")

    def text(*path):
        with open(os.path.join(ROOT, *path)) as f:
            return f.read()
    bad = problems(text("packaging", "plugin-hostd.spec"), text("debian", "control"), text("protocol", "plugin-hostd.pc.in"))
    for b in bad:
        print("FAIL %s" % b)
    if bad:
        return 1
    print("ok   plugin-db is >= %s, with no ceiling, everywhere it is declared" % FLOOR)
    return 0


sys.exit(main())
