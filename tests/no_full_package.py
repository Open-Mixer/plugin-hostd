# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd builds no plugin-hostd-full (ruling 2026-11-09, #84): the metapackage that installs the whole plugin host
# stack is its own repository, Open-Mixer/plugin-hostd-full, the outermost layer, released last in each wave. Here: no
# `%package full` or `%files full` in the spec, no `Package: plugin-hostd-full` in debian/control, no release job that
# installs it, and no tool of its own (tools/full-install-check.sh, tests/full_ranges.py) left behind.
#
# Usage: no_full_package.py [root]. The check proves it sees each kind of leftover on a planted copy before it trusts
# its verdict on the tree. Exit 0 clean, 1 a leftover, 2 a check that cannot see.
import os, re, sys, tempfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))


def read(root, path):
    try:
        with open(os.path.join(root, path)) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def leftovers(root):
    p = []
    spec = read(root, "packaging/plugin-hostd.spec")
    for pat, what in ((r"^%package\s+(-n\s+plugin-hostd-)?full\b", "spec: %package full"),
                      (r"^%files\s+(-n\s+plugin-hostd-)?full\b", "spec: %files full"),
                      (r"^%description\s+(-n\s+plugin-hostd-)?full\b", "spec: %description full")):
        if re.search(pat, spec, re.M):
            p.append(what)
    if re.search(r"^Package:\s*plugin-hostd-full\s*$", read(root, "debian/control"), re.M):
        p.append("debian/control: Package: plugin-hostd-full")
    wf = read(root, ".github/workflows/release.yml")
    if re.search(r"^  full-(deb|rpm):", wf, re.M) or "full-install-check" in wf:
        p.append("release.yml: a job that installs plugin-hostd-full")
    for f in ("tools/full-install-check.sh", "tests/full_ranges.py"):
        if os.path.exists(os.path.join(root, f)):
            p.append(f"{f}: plugin-hostd-full's own tool, left here")
    if re.search(r"^check-full-ranges:", read(root, "Makefile"), re.M):
        p.append("Makefile: check-full-ranges")
    return p


def planted():
    """each kind of leftover planted in a copy of the files the check reads: every one must be seen"""
    cases = {
        "spec": ("packaging/plugin-hostd.spec", "\n%package full\nSummary: x\n"),
        "files": ("packaging/plugin-hostd.spec", "\n%files full\n"),
        "control": ("debian/control", "\nPackage: plugin-hostd-full\nArchitecture: all\n"),
        "job": (".github/workflows/release.yml", "\n  full-rpm:\n    runs-on: x\n"),
        "tool": ("tools/full-install-check.sh", "#!/bin/sh\n"),
        "ranges": ("tests/full_ranges.py", "\n"),
        "make": ("Makefile", "\ncheck-full-ranges:\n\ttrue\n"),
    }
    missed = []
    for kind, (path, text) in cases.items():
        with tempfile.TemporaryDirectory() as t:
            # a tree with none: the files the check reads, empty; then the one leftover planted
            for f in ("packaging/plugin-hostd.spec", "debian/control", ".github/workflows/release.yml", "Makefile"):
                os.makedirs(os.path.dirname(os.path.join(t, f)), exist_ok=True)
                open(os.path.join(t, f), "w").close()
            if leftovers(t):
                return ["an empty tree"]
            os.makedirs(os.path.join(t, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(t, path), "a") as f:
                f.write(text)
            if not leftovers(t):
                missed.append(kind)
    return missed


missed = planted()
if missed:
    print("no_full_package: the check does not see a planted " + ", ".join(missed))
    sys.exit(2)
p = leftovers(ROOT)
for line in p:
    print("FAIL " + line)
if p:
    print("plugin-hostd builds or releases plugin-hostd-full: it is Open-Mixer/plugin-hostd-full's (#84)")
    sys.exit(1)
print("ok   plugin-hostd builds no plugin-hostd-full: it is Open-Mixer/plugin-hostd-full's (#84)")
