#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# omx-clap-core is a dependency with a floor and a ceiling wherever it is declared: its packages omx-clap-core-contract
# (the build and plugin-hostd-contract; python3-plugin-hostd-protocol, which declared it too, is plugin-hostd-protocol's own),
# omx-clap-host-tests (the check stage) and omx-clap-host (recommended by plugin-hostd; plugin-hostd-full, which requires it, is Open-Mixer/plugin-hostd-full's own), each at its floor and below CEILING, the minor
# after the omx-clap-core release this tree is tested against (0.32: its omx-clap-host names each instance's node, #33). A floor with no ceiling, a ceiling other than CEILING and a declaration that is gone are red.
# Usage: clap_core_floor.py [root]. The check proves it sees each fault before it trusts the tree.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CEILING = "0.33"
# package: (floor, declarations in the spec, declarations in debian/control)
# the floor is omx-clap-core's release of the same pass (0.32.6, which releases before this tree's): outward requires
# the latest of each lower layer
FLOOR = "0.32.6"
WANT = {"omx-clap-core-contract": (FLOOR, 2, 2), "omx-clap-host-tests": (FLOOR, 1, 1), "omx-clap-host": (FLOOR, 1, 1)}


def problems(spec, control, workflows=None):
    bad = []
    for pkg, (floor, n_spec, n_ctl) in WANT.items():
        q = re.escape(pkg)
        rich = re.findall(r"^(?:Build)?(?:Requires|Recommends):\s*\(\s*%s\s*>=\s*(\S+)\s+with\s+%s\s*<\s*(\S+?)\s*\)\s*$" % (q, q), spec, re.M)
        named = re.findall(r"^(?:Build)?(?:Requires|Recommends):.*\b%s\b(?!-)" % q, spec, re.M)
        if len(rich) != n_spec or len(named) != n_spec:
            bad.append("packaging/plugin-hostd.spec: %s: %d with a floor and a ceiling, %d name it; there must be %d" % (pkg, len(rich), len(named), n_spec))
        bad += ["packaging/plugin-hostd.spec: %s >= %s and < %s, they are %s and %s" % (pkg, f, c, floor, CEILING)
                for f, c in rich if (f, c) != (floor, CEILING)]
        # the build dependencies of the check stage carry <!nocheck> on both entries
        pairs = re.findall(r"\b%s\s*\(>=\s*([^)\s~]+)~?\)(?: <!nocheck>)?,\s*%s\s*\(<<\s*([^)\s~]+)~?\)" % (q, q), control)
        named = len(re.findall(r"\b%s\s*\(>=" % q, control))
        if len(pairs) != n_ctl or named != n_ctl:
            bad.append("debian/control: %s: %d with a floor and a ceiling, %d have a floor; there must be %d" % (pkg, len(pairs), named, n_ctl))
        bad += ["debian/control: %s (>= %s~) (<< %s~), they are %s and %s" % (pkg, f, c, floor, CEILING)
                for f, c in pairs if (f, c) != (floor, CEILING)]
        # a workflow that installs a package with a typed bound: 'pkg >= x' is the floor, 'pkg < y' the ceiling
        for name, wtext in sorted((workflows or {}).items()):
            for n, wline in enumerate(wtext.splitlines(), 1):
                for op, v in re.findall(r"\b%s(?![\w-])\s*(>=|<)\s*([0-9][0-9.]*)" % q, wline):
                    want = floor if op == ">=" else CEILING
                    if v != want:
                        bad.append(".github/workflows/%s:%d: %s %s %s, it is %s" % (name, n, pkg, op, v, want))
    return bad


WORKFLOW_OK = {"ci.yml": "          bounded-install dnf install -y \\\n            'omx-clap-host >= %s' 'omx-clap-host < %s' \\\n" % (FLOOR, CEILING)}


def fixture():
    spec, ctl = [], []
    for pkg, (floor, n_spec, n_ctl) in WANT.items():
        spec += ["Requires: (%s >= %s with %s < %s)" % (pkg, floor, pkg, CEILING)] * n_spec
        ctl += ["%s (>= %s~), %s (<< %s~)" % (pkg, floor, pkg, CEILING)] * n_ctl
    return "\n".join(spec) + "\n", ",\n ".join(ctl) + "\n"


def main():
    spec, ctl = fixture()
    arms = [
        ("the tree as written", spec, ctl, 0),
        ("no ceiling in the spec", spec.replace(" with omx-clap-host < %s" % CEILING, "").replace("(omx-clap-host >= %s)" % WANT["omx-clap-host"][0], "omx-clap-host >= %s" % WANT["omx-clap-host"][0]), ctl, 1),
        ("a wide ceiling in the spec", spec.replace("< %s" % CEILING, "< 1", 1), ctl, 1),
        ("a floor of 0.1.0 in the spec", spec.replace(FLOOR, "0.1.0", 1), ctl, 1),
        ("no ceiling in debian/control", spec, ctl.replace(", omx-clap-host-tests (<< %s~)" % CEILING, ""), 1),
        ("a wide ceiling in debian/control", spec, ctl.replace("<< %s~" % CEILING, "<< 1~", 1), 1),
    ]
    for what, s, c, want in arms:
        got = problems(s, c, WORKFLOW_OK)
        if len(got) != want:
            print("FAIL the omx-clap-core check on %s: want %d findings, got %s" % (what, want, got))
            return 1
    # a floor or a ceiling typed in a workflow (ci.yml's dnf install of omx-clap-host) is one more declaration
    for what, wf, want in [
        ("a workflow at the floor", WORKFLOW_OK, 0),
        ("a low floor typed in a workflow", {"ci.yml": WORKFLOW_OK["ci.yml"].replace(">= %s" % FLOOR, ">= 0.32.5")}, 1),
        ("a wide ceiling typed in a workflow", {"ci.yml": WORKFLOW_OK["ci.yml"].replace("< %s" % CEILING, "< 1")}, 1),
    ]:
        got = problems(spec, ctl, wf)
        if len(got) != want:
            print("FAIL the omx-clap-core check on %s: want %d findings, got %s" % (what, want, got))
            return 1
    print("ok   the omx-clap-core check sees a missing, a wide and a low bound in the spec, debian/control and a workflow")

    def text(*path):
        with open(os.path.join(ROOT, *path)) as f:
            return f.read()
    wfdir = os.path.join(ROOT, ".github", "workflows")
    workflows = {f: text(".github", "workflows", f) for f in sorted(os.listdir(wfdir)) if f.endswith((".yml", ".yaml"))}
    bad = problems(text("packaging", "plugin-hostd.spec"), text("debian", "control"), workflows)
    for b in bad:
        print("FAIL %s" % b)
    if bad:
        return 1
    print("ok   omx-clap-core's packages are at their floors and below %s everywhere they are declared" % CEILING)
    return 0


sys.exit(main())
