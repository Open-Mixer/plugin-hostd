#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# omx-clap-core is a dependency with a floor and no ceiling wherever it is declared: its packages omx-clap-core-contract
# (the build and plugin-hostd-contract; python3-plugin-hostd-protocol, which declared it too, is plugin-hostd-protocol's
# own), omx-clap-host-tests (the check stage) and omx-clap-host (recommended by plugin-hostd; plugin-hostd-full, which
# requires it, is Open-Mixer/plugin-hostd-full's own), each at FLOOR. Floors only: a ceiling or an exact pin is red, and so
# is a declaration that is gone. Usage: clap_core_floor.py [root]. The check proves it sees each fault before it trusts it.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = "0.33.0"
# package: (declarations in the spec, declarations in debian/control)
WANT = {"omx-clap-core-contract": (2, 2), "omx-clap-host-tests": (1, 1), "omx-clap-host": (1, 1)}


def problems(spec, control):
    bad = []
    for pkg, (n_spec, n_ctl) in WANT.items():
        q = re.escape(pkg)
        floors = re.findall(r"^(?:Build)?(?:Requires|Recommends):\s*\(?\s*%s\s*>=\s*(\S+?)\s*\)?\s*$" % q, spec, re.M)
        named = re.findall(r"^(?:Build)?(?:Requires|Recommends):.*\b%s\b(?!-)" % q, spec, re.M)
        if len(floors) != n_spec or len(named) != n_spec:
            bad.append("packaging/plugin-hostd.spec: %s: %d with a floor, %d name it; there must be %d" % (pkg, len(floors), len(named), n_spec))
        bad += ["packaging/plugin-hostd.spec: %s >= %s, it is %s" % (pkg, f, FLOOR) for f in floors if f != FLOOR]
        bad += ["packaging/plugin-hostd.spec: %s with a ceiling or a pin: %s" % (pkg, l.strip())
                for l in re.findall(r"^(?:Build)?(?:Requires|Recommends):.*\b%s\s*(?:<|=|with)" % q, spec, re.M)]
        # the build dependencies of the check stage carry <!nocheck> on each entry
        items = re.findall(r"\b%s\s*\(([^)]*)\)" % q, control)
        if len(items) != n_ctl:
            bad.append("debian/control: %s: %d entries with a version, there must be %d" % (pkg, len(items), n_ctl))
        bad += ["debian/control: %s (%s), it is (>= %s~)" % (pkg, i, FLOOR) for i in items if i != ">= %s~" % FLOOR]
    return bad


def fixture():
    spec, ctl = [], []
    for pkg, (n_spec, n_ctl) in WANT.items():
        spec += ["Requires: %s >= %s" % (pkg, FLOOR)] * n_spec
        ctl += ["%s (>= %s~)" % (pkg, FLOOR)] * n_ctl
    return "\n".join(spec) + "\n", ",\n ".join(ctl) + "\n"


def main():
    spec, ctl = fixture()
    arms = [
        ("the tree as written", spec, ctl, 0),
        ("a ceiling in the spec", spec.replace("omx-clap-host >= %s" % FLOOR, "omx-clap-host >= %s with omx-clap-host < 1" % FLOOR), ctl, 1),
        ("a low floor in the spec", spec.replace(FLOOR, "0.32.5", 1), ctl, 1),
        ("a ceiling in debian/control", spec, ctl.replace("omx-clap-host-tests (>= %s~)" % FLOOR, "omx-clap-host-tests (>= %s~), omx-clap-host-tests (<< 1~)" % FLOOR), 1),
        ("an exact pin in debian/control", spec, ctl.replace("omx-clap-host-tests (>= %s~)" % FLOOR, "omx-clap-host-tests (= %s)" % FLOOR), 1),
        ("a declaration gone", spec.replace("Requires: omx-clap-host >= %s\n" % FLOOR, ""), ctl, 1),
    ]
    for what, s, c, want in arms:
        got = problems(s, c)
        if bool(got) != bool(want):
            print("FAIL the omx-clap-core check on %s: want %s, got %s" % (what, "a finding" if want else "none", got))
            return 1
    print("ok   the omx-clap-core check sees a missing, a low, a ceiling and a pin in the spec and debian/control")

    def text(*path):
        with open(os.path.join(ROOT, *path)) as f:
            return f.read()
    bad = problems(text("packaging", "plugin-hostd.spec"), text("debian", "control"))
    for b in bad:
        print("FAIL %s" % b)
    if bad:
        return 1
    print("ok   omx-clap-core's packages are at their floor, %s, with no ceiling anywhere they are declared" % FLOOR)
    return 0


sys.exit(main())
