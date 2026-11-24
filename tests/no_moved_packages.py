# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd builds neither package that has moved out of it:
# - plugin-hostd-full, the metapackage of the whole plugin host stack, is Open-Mixer/plugin-hostd-full's (#84), the
#   outermost layer, released last in each pass;
# - python3-plugin-hostd-protocol, the Python codec, is plugin-hostd-protocol's package (no epoch: owner ruling 2026-11-18).
# Here: no %package, %description or %files of either in the spec, no `Package:` stanza of either in debian/control,
# no debian/python3-plugin-hostd-protocol.install, no install-python step in debian/rules or the spec, no release job
# that installs plugin-hostd-full and no tool of its own left behind; and a dependency on python3-plugin-hostd-protocol,
# if any, is a floor only, with no epoch (rulings 2026-11-16 floors only, 2026-11-18 no epochs).
#
# Usage: no_moved_packages.py [root]. The check proves it sees each kind of leftover on a planted copy before it trusts
# its verdict on the tree. Exit 0 clean, 1 a leftover, 2 a check that cannot see.
import os, re, sys, tempfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
CODEC = "python3-plugin-hostd-protocol"
READ = ("packaging/plugin-hostd.spec", "debian/control", "debian/rules", ".github/workflows/release.yml", "Makefile")


def read(root, path):
    try:
        with open(os.path.join(root, path)) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def dependency_lines(spec, control):
    """the lines that declare a dependency: the spec's tags before %changelog, debian/control's relation fields"""
    for line in spec.split("\n%changelog", 1)[0].splitlines():
        if re.match(r"^(Build)?(Requires|Recommends|Suggests|Supplements|Enhances|Conflicts|Obsoletes)(\(\w+\))?:", line):
            yield "spec", line
    field = None
    for line in control.splitlines():
        if line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z-]+):", line)
        if m:
            field = m.group(1)
        elif not line[:1].isspace():
            field = None
        if field in ("Depends", "Pre-Depends", "Build-Depends", "Build-Depends-Indep", "Recommends", "Suggests",
                     "Breaks", "Conflicts", "Replaces", "Enhances"):
            yield "debian/control", line


def leftovers(root):
    p = []
    spec = read(root, "packaging/plugin-hostd.spec")
    for sec in ("package", "description", "files"):
        if re.search(r"^%%%s\s+(-n\s+plugin-hostd-)?full\b" % sec, spec, re.M):
            p.append(f"spec: %{sec} full")
        if re.search(r"^%%%s\s+-n\s+%s\b" % (sec, re.escape(CODEC)), spec, re.M):
            p.append(f"spec: %{sec} -n {CODEC}")
    if re.search(r"^[^#\n]*\binstall-python\b", spec, re.M):
        p.append("spec: an install-python step")
    control = read(root, "debian/control")
    for pkg in ("plugin-hostd-full", CODEC):
        if re.search(r"^Package:\s*%s\s*$" % re.escape(pkg), control, re.M):
            p.append(f"debian/control: Package: {pkg}")
    if os.path.exists(os.path.join(root, "debian", CODEC + ".install")):
        p.append(f"debian/{CODEC}.install")
    if re.search(r"^[^#\n]*\binstall-python\b", read(root, "debian/rules"), re.M):
        p.append("debian/rules: an install-python step")
    # a dependency on the codec is a floor only (>=), with no epoch and no ceiling
    for path, line in dependency_lines(spec, control):
        for m in re.finditer(r"%s\s*(\(?\s*(>=|<<|<|=|>)\s*([^\s,)]+))?" % re.escape(CODEC), line):
            if m.group(1) is None or m.group(2) != ">=" or ":" in m.group(3):
                p.append(f"{path}: {CODEC} is not a floor without an epoch: {line.strip()}")
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
        "spec full": ("packaging/plugin-hostd.spec", "\n%package full\nSummary: x\n"),
        "files full": ("packaging/plugin-hostd.spec", "\n%files full\n"),
        "spec codec": ("packaging/plugin-hostd.spec", "\n%package -n python3-plugin-hostd-protocol\nSummary: x\n"),
        "files codec": ("packaging/plugin-hostd.spec", "\n%files -n python3-plugin-hostd-protocol\n"),
        "spec install": ("packaging/plugin-hostd.spec", "\n%make_build install-python DESTDIR=%{buildroot}\n"),
        "control full": ("debian/control", "\nPackage: plugin-hostd-full\nArchitecture: all\n"),
        "control codec": ("debian/control", "\nPackage: python3-plugin-hostd-protocol\nArchitecture: all\n"),
        "install file": ("debian/python3-plugin-hostd-protocol.install", "usr/lib/python3\n"),
        "rules": ("debian/rules", "\n\t$(MAKE) install-python DESTDIR=x\n"),
        "epoch": ("packaging/plugin-hostd.spec", "\nBuildRequires: python3-plugin-hostd-protocol >= 1:0.5.10\n"),
        "ceiling": ("debian/control", "\nBuild-Depends: python3-plugin-hostd-protocol (<< 0.9~),\n"),
        "bare": ("debian/control", "\nBuild-Depends: python3-plugin-hostd-protocol,\n"),
        "job": (".github/workflows/release.yml", "\n  full-rpm:\n    runs-on: x\n"),
        "tool": ("tools/full-install-check.sh", "#!/bin/sh\n"),
        "ranges": ("tests/full_ranges.py", "\n"),
        "make": ("Makefile", "\ncheck-full-ranges:\n\ttrue\n"),
    }
    missed = []
    for kind, (path, text) in cases.items():
        with tempfile.TemporaryDirectory() as t:
            for f in READ:
                os.makedirs(os.path.dirname(os.path.join(t, f)), exist_ok=True)
                open(os.path.join(t, f), "w").close()
            if leftovers(t):
                return ["an empty tree"]
            # the floor deps.txt renders is no leftover
            with open(os.path.join(t, "packaging/plugin-hostd.spec"), "a") as f:
                f.write("BuildRequires: python3-plugin-hostd-protocol >= 0.8.0\n")
            with open(os.path.join(t, "debian/control"), "a") as f:
                f.write("Build-Depends: python3-plugin-hostd-protocol (>= 0.8.0~) <!nocheck>,\n")
            if leftovers(t):
                return ["the floor as a leftover"]
            os.makedirs(os.path.join(t, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(t, path), "a") as f:
                f.write(text)
            if not leftovers(t):
                missed.append(kind)
    return missed


missed = planted()
if missed:
    print("no_moved_packages: the check does not see a planted " + ", ".join(missed))
    sys.exit(2)
p = leftovers(ROOT)
for line in p:
    print("FAIL " + line)
if p:
    print("plugin-hostd builds a package that moved out: plugin-hostd-full is Open-Mixer/plugin-hostd-full's (#84), "
          "python3-plugin-hostd-protocol is plugin-hostd-protocol's")
    sys.exit(1)
print("ok   plugin-hostd builds no plugin-hostd-full and no python3-plugin-hostd-protocol: both moved out")
