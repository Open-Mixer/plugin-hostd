#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-db is a dependency with a floor and no ceiling wherever it is declared: 0.4.5, the release of the same pass
# (0.4.1 brought plugin_db_constants.h, which src/pins.h includes so the fuzz harnesses need no OpenSSL). The spec's two
# lines, debian/control's two items and the pkg-config file of the development package are read here; a missing line,
# a floor other than FLOOR and any ceiling or exact pin are red.
# Usage: plugin_db_floor.py [root]. The check proves it sees each fault before it trusts the tree.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = "0.4.5"
SPEC = re.compile(r"^(?:Build)?Requires:.*\bplugin-db(?:-devel|\)|\s)[^\n]*$", re.M)
CONTROL = re.compile(r"plugin-db-dev\s*\(([^)]*)\)")
PC = re.compile(r"^Requires:.*\bplugin-db\s*(>=|<|=|<=)\s*(\S+?)\s*(?:,|$)", re.M)


def problems(spec, control, pc):
    bad = []
    lines = SPEC.findall(spec)
    if len(lines) != 2:
        bad.append("packaging/plugin-hostd.spec: %d plugin-db declarations, there must be 2" % len(lines))
    for l in lines:
        if not re.search(r"(>=|>)\s*%s\b" % re.escape(FLOOR), l) or re.search(r"(<|=)\s*\d", re.sub(r">=", "", l)):
            bad.append("packaging/plugin-hostd.spec: plugin-db is not >= %s with no ceiling: %s" % (FLOOR, l.strip()))
    items = CONTROL.findall(control)
    if len(items) != 2:
        bad.append("debian/control: %d plugin-db-dev entries, there must be 2" % len(items))
    bad += ["debian/control: plugin-db-dev (%s), it is (>= %s~) with no ceiling" % (i, FLOOR) for i in items if i != ">= %s~" % FLOOR]
    ops = PC.findall(pc)
    if ops != [(">=", FLOOR)]:
        bad.append("protocol/plugin-hostd.pc.in: plugin-db declared as %s, it is >= %s alone" % (ops, FLOOR))
    return bad


SPEC_OK = ("BuildRequires: pkgconfig(plugin-db) >= {f}\n"
           "Requires: plugin-db-devel >= {f}\n").format(f=FLOOR)
CTL_OK = ("Build-Depends: plugin-db-dev (>= {f}~),\n"
          "Depends: x, plugin-db-dev (>= {f}~), y\n").format(f=FLOOR)
PC_OK = "Requires: plugin-hostd-protocol >= 0.6.0, plugin-db >= {f}\n".format(f=FLOOR)


def main():
    arms = [
        ("the tree as written", SPEC_OK, CTL_OK, PC_OK, 0),
        ("a ceiling in the spec", SPEC_OK.replace("Requires: plugin-db-devel >= %s" % FLOOR, "Requires: plugin-db-devel >= %s with plugin-db-devel < 1" % FLOOR), CTL_OK, PC_OK, 1),
        ("a low floor in the spec", SPEC_OK.replace(FLOOR, "0.0.1", 1), CTL_OK, PC_OK, 1),
        ("a ceiling in debian/control", SPEC_OK, CTL_OK.replace("plugin-db-dev (>= %s~)," % FLOOR, "plugin-db-dev (>= %s~), plugin-db-dev (<< 1~)," % FLOOR, 1), PC_OK, 1),
        ("an exact pin in debian/control", SPEC_OK, CTL_OK.replace("(>= %s~)" % FLOOR, "(= %s)" % FLOOR, 1), PC_OK, 1),
        ("a ceiling in the pkg-config file", SPEC_OK, CTL_OK, PC_OK.replace(", plugin-db >= %s" % FLOOR, ", plugin-db >= %s, plugin-db < 1" % FLOOR), 1),
        ("no plugin-db in the pkg-config file", SPEC_OK, CTL_OK, PC_OK.replace(", plugin-db >= %s" % FLOOR, ""), 1),
    ]
    for what, spec, ctl, pc, want in arms:
        got = problems(spec, ctl, pc)
        if bool(got) != bool(want):
            print("FAIL the plugin-db check on %s: want %s, got %s" % (what, "a finding" if want else "none", got))
            return 1
    print("ok   the plugin-db check sees a low floor and a ceiling or pin in the spec, debian/control and the pkg-config file")

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
