#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-db is a dependency with a floor and a ceiling wherever it is declared: 0.4.0 (the release the channel serves,
# which the tree is built and tested against; a bound below it leaves apt no plugin-db-dev to install) and 0.5, the
# next minor. The spec's two lines, debian/control's two items and the pkg-config file of
# the development package are read here; a missing line, a floor below FLOOR and a missing or wide ceiling are red.
# Usage: plugin_db_floor.py [root]. The check proves it sees each fault before it trusts the tree.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR, CEILING = "0.4.0", "0.5"
SPEC = re.compile(r"^(?:Build)?Requires:\s*\(\s*(pkgconfig\(plugin-db\)|plugin-db-devel)\s*>=\s*(\S+)\s+with\s+\1\s*<\s*(\S+?)\s*\)\s*$", re.M)
SPEC_ANY = re.compile(r"^(?:Build)?Requires:.*plugin-db.*$", re.M)
CONTROL = re.compile(r"plugin-db-dev\s*\(>=\s*([^)\s~]+)~?\),\s*plugin-db-dev\s*\(<<\s*([^)\s~]+)~?\)")
CONTROL_ANY = re.compile(r"plugin-db-dev\s*\(")
PC = re.compile(r"^Requires:.*\bplugin-db >= (\S+?),\s*plugin-db < (\S+?)(?:,|\s*$)", re.M)


def problems(spec, control, pc):
    bad = []
    # (file, the floor-and-ceiling declarations found, the declarations of any shape, how many there must be)
    for name, found, named, want in (("packaging/plugin-hostd.spec", [(f, c) for _, f, c in SPEC.findall(spec)], len(SPEC_ANY.findall(spec)), 2),
                                     ("debian/control", CONTROL.findall(control), len(CONTROL_ANY.findall(control)) // 2, 2)):
        if len(found) != want or named != want:
            bad.append("%s: %d plugin-db declarations with a floor and a ceiling, %d name plugin-db; there must be %d" % (name, len(found), named, want))
        bad += ["%s: a floor of %s and a ceiling of %s, they are %s and %s" % (name, f, c, FLOOR, CEILING)
                for f, c in found if (f, c) != (FLOOR, CEILING)]
    m = PC.search(pc)
    if not m:
        bad.append("protocol/plugin-hostd.pc.in: no 'plugin-db >= floor, plugin-db < ceiling'")
    elif m.groups() != (FLOOR, CEILING):
        bad.append("protocol/plugin-hostd.pc.in: %s..%s, they are %s..%s" % (m.group(1), m.group(2), FLOOR, CEILING))
    return bad


SPEC_OK = ("BuildRequires: (pkgconfig(plugin-db) >= 0.4.0 with pkgconfig(plugin-db) < 0.5)\n"
           "Requires: (plugin-db-devel >= 0.4.0 with plugin-db-devel < 0.5)\n")
CTL_OK = ("Build-Depends: plugin-db-dev (>= 0.4.0~), plugin-db-dev (<< 0.5~),\n"
          "Depends: x, plugin-db-dev (>= 0.4.0~), plugin-db-dev (<< 0.5~), y\n")
PC_OK = "Requires: plugin-hostd-protocol >= 0.5.0, plugin-db >= 0.4.0, plugin-db < 0.5\n"


def main():
    # each arm breaks the bound it names, read from FLOOR and CEILING, so a moved bound moves the arms with it
    arms = [
        ("the tree as written", SPEC_OK, CTL_OK, PC_OK, 0),
        ("no ceiling in the spec", SPEC_OK.replace(" with plugin-db-devel < %s" % CEILING, "")
         .replace("(plugin-db-devel >= %s)" % FLOOR, "plugin-db-devel >= %s" % FLOOR), CTL_OK, PC_OK, 1),
        ("a wide ceiling in the spec", SPEC_OK.replace("< %s" % CEILING, "< 1", 1), CTL_OK, PC_OK, 1),
        ("a low floor in the spec", SPEC_OK.replace(FLOOR, "0.0.1", 1), CTL_OK, PC_OK, 1),
        ("no ceiling in debian/control", SPEC_OK, CTL_OK.replace(", plugin-db-dev (<< %s~)" % CEILING, "", 1), PC_OK, 1),
        ("a wide ceiling in debian/control", SPEC_OK, CTL_OK.replace("<< %s~" % CEILING, "<< 1~", 1), PC_OK, 1),
        ("no ceiling in the pkg-config file", SPEC_OK, CTL_OK, PC_OK.replace(", plugin-db < %s" % CEILING, ""), 1),
        ("a wide ceiling in the pkg-config file", SPEC_OK, CTL_OK, PC_OK.replace("< %s" % CEILING, "< 1"), 1),
    ]
    for what, spec, ctl, pc, want in arms:
        got = problems(spec, ctl, pc)
        if len(got) != want:
            print("FAIL the plugin-db check on %s: want %d findings, got %s" % (what, want, got))
            return 1
    print("ok   the plugin-db check sees a low floor and a missing or wide ceiling in the spec, debian/control and the pkg-config file")

    def text(*path):
        with open(os.path.join(ROOT, *path)) as f:
            return f.read()
    bad = problems(text("packaging", "plugin-hostd.spec"), text("debian", "control"), text("protocol", "plugin-hostd.pc.in"))
    for b in bad:
        print("FAIL %s" % b)
    if bad:
        return 1
    print("ok   plugin-db is >= %s and < %s everywhere it is declared" % (FLOOR, CEILING))
    return 0


sys.exit(main())
