# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# plugin-hostd-full, the metapackage that installs the whole plugin host stack, in the RPM spec (%package full) and
# debian/control (Package: plugin-hostd-full) alike:
# - it hard-depends on exactly HARD, plugin-hostd at its own version (= %{version}-%{release}, = ${source:Version}) and
#   every other name with a floor and a ceiling below the next minor (a version 1 or later: the next major), and
#   recommends exactly SOFT the same way: omx-panel is a weak dependency, so the headless install
#   (--no-install-recommends, install_weak_deps=False) leaves it out;
# - the RPM and the Debian ranges are the same numbers;
# - a dependency plugin-hostd itself declares (omx-clap-host, recommended by the daemon) has the same floor there.
# Usage: full_ranges.py [root]. The check proves it sees each kind of broken range on a planted copy before it trusts
# the tree.
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = "plugin-hostd"
HARD = {"omx-clap-host", "omx-plugins", "plugin-qualify", "plugin-qualification-records"}
SOFT = {"omx-panel"}


def vtuple(v):
    return tuple(int(x) for x in v.split("."))


def next_step(floor):
    """the ceiling a floor must have: the next minor below 1.0, the next major from 1.0"""
    t = vtuple(floor)
    return f"{t[0]}.{t[1] + 1}" if t[0] == 0 else f"{t[0] + 1}"


def deb_stanza(text):
    for para in re.split(r"\n\s*\n", text):
        lines = [l for l in para.splitlines() if not l.startswith("#")]
        if any(l == "Package: plugin-hostd-full" for l in lines):
            fields, cur = {}, None
            for l in lines:
                if l[:1] in (" ", "\t") and cur:
                    fields[cur] += " " + l.strip()
                elif ":" in l:
                    cur, v = l.split(":", 1)
                    fields[cur] = v.strip()
            return fields
    return None


def deb_ranges(field):
    """{name: [(op, version)]} of a Depends-like field; ${...} substitutions are kept as their own op"""
    out = {}
    for item in (x.strip() for x in field.split(",") if x.strip()):
        m = re.fullmatch(r"([a-z0-9.+-]+)(?:\s*\((>=|<<|=|<=|>>)\s*([^)\s]+)\))?", item)
        if not m:
            if not item.startswith("${"):
                out.setdefault(item, []).append(("?", item))
            continue
        name, op, ver = m.groups()
        out.setdefault(name, []).append((op, (ver or "").rstrip("~")) if op else ("none", ""))
    return out


def spec_full(text):
    """the Requires and Recommends lines of %package full, up to its %description"""
    m = re.search(r"^%package full\n(.*?)^%description full", text, re.M | re.S)
    if not m:
        return None
    req, rec = [], []
    for l in m.group(1).splitlines():
        if l.startswith("Requires:"):
            req.append(l.split(":", 1)[1].strip())
        elif l.startswith("Recommends:"):
            rec.append(l.split(":", 1)[1].strip())
    return req, rec


def rpm_ranges(lines):
    out = {}
    for l in lines:
        m = re.fullmatch(r"\((\S+) >= (\S+) with (\S+) < (\S+)\)", l)
        if m and m.group(1) == m.group(3):
            out.setdefault(m.group(1), []).extend([(">=", m.group(2)), ("<<", m.group(4))])
            continue
        m = re.fullmatch(r"(\S+)\s*(=|>=|<|<=)?\s*(\S+)?", l)
        if m:
            out.setdefault(m.group(1), []).append((m.group(2) or "none", m.group(3) or ""))
        else:
            out.setdefault(l, []).append(("?", l))
    return out


def judge(kind, ranges, want, self_exact):
    """problems of one field: the names are exactly want (plus SELF where self_exact names how it is pinned)"""
    p = []
    names = set(ranges) - ({SELF, "%{name}"} if self_exact else set())
    if names != want:
        p.append(f"{kind}: names {sorted(names)}, not {sorted(want)}")
    if self_exact:
        mine = ranges.get(SELF) or ranges.get("%{name}")
        if mine != [("=", self_exact)]:
            p.append(f"{kind}: {SELF} is {mine}, not exactly = {self_exact}")
    for name in sorted(names & want):
        ops = dict(ranges[name]) if len(ranges[name]) == 2 else {}
        floor, ceiling = ops.get(">="), ops.get("<<")
        if not floor or not ceiling or set(ops) != {">=", "<<"}:
            p.append(f"{kind}: {name} is {ranges[name]}, not a floor and a ceiling")
            continue
        if ceiling != next_step(floor):
            p.append(f"{kind}: {name} has the ceiling {ceiling} for the floor {floor}; the next step is {next_step(floor)}")
    return p


def floors(ranges):
    return {n: dict(r) for n, r in ranges.items() if len(r) == 2}


def problems(root):
    p = []
    spec = open(os.path.join(root, "packaging", "plugin-hostd.spec")).read()
    control = open(os.path.join(root, "debian", "control")).read()
    full = spec_full(spec)
    stanza = deb_stanza(control)
    if full is None:
        return ["packaging/plugin-hostd.spec has no %package full with a %description full"]
    if stanza is None:
        return ["debian/control has no plugin-hostd-full stanza"]
    if "BuildArch: noarch" not in re.search(r"^%package full\n(.*?)^%description full", spec, re.M | re.S).group(1):
        p.append("spec: %package full is not noarch")
    if "%files full" not in spec:
        p.append("spec: no %files full, so no plugin-hostd-full is built")
    rreq, rrec = rpm_ranges(full[0]), rpm_ranges(full[1])
    dreq, drec = deb_ranges(stanza.get("Depends", "")), deb_ranges(stanza.get("Recommends", ""))
    p += judge("spec Requires", rreq, HARD, "%{version}-%{release}")
    p += judge("spec Recommends", rrec, SOFT, None)
    p += judge("debian Depends", dreq, HARD, "${source:Version}")
    p += judge("debian Recommends", drec, SOFT, None)
    for kind, r, d in (("Requires/Depends", rreq, dreq), ("Recommends", rrec, drec)):
        fr, fd = floors(r), floors(d)
        for name in sorted(set(fr) & set(fd)):
            if fr[name] != fd[name]:
                p.append(f"{kind}: {name} is {fr[name]} in the spec and {fd[name]} in debian/control")
    # the daemon's own declaration of its worker: one floor for both
    m = re.search(r"^Recommends: \(omx-clap-host >= (\S+) with omx-clap-host < (\S+)\)", spec, re.M)
    if m and floors(rreq).get("omx-clap-host") != {">=": m.group(1), "<<": m.group(2)}:
        p.append(f"spec: plugin-hostd recommends omx-clap-host {m.group(1)} below {m.group(2)}, plugin-hostd-full "
                 f"requires {floors(rreq).get('omx-clap-host')}")
    return p


def planted(root, edits):
    """problems of a copy of the two files with edits applied: [(file, old, new)]"""
    import shutil, tempfile
    t = tempfile.mkdtemp()
    try:
        for d, f in (("packaging", "plugin-hostd.spec"), ("debian", "control")):
            os.makedirs(os.path.join(t, d))
            shutil.copy(os.path.join(root, d, f), os.path.join(t, d, f))
        for f, old, new in edits:
            path = os.path.join(t, f)
            text = open(path).read()
            if old not in text:
                return [f"plant: {old!r} is not in {f}"]
            open(path, "w").write(text.replace(old, new, 1))
        return problems(t)
    finally:
        shutil.rmtree(t)


SABOTAGE = [
    ("a floor with no ceiling (deb)", [("debian/control", ", omx-plugins (<< 0.20~)", "")], "not a floor and a ceiling"),
    ("a floor with no ceiling (rpm)", [("packaging/plugin-hostd.spec", "(plugin-qualify >= 0.20.0 with plugin-qualify < 0.21)", "plugin-qualify >= 0.20.0")], "not a floor and a ceiling"),
    ("a ceiling past the next minor", [("debian/control", "plugin-qualify (<< 0.21~)", "plugin-qualify (<< 0.22~)")], "the next step is 0.21"),
    ("the records left out", [("packaging/plugin-hostd.spec", "Requires: (plugin-qualification-records >= 0.20.0 with plugin-qualification-records < 0.21)\n", "")], "names"),
    ("the panel a hard dependency", [("debian/control", "Recommends: omx-panel (>= 0.12.0~), omx-panel (<< 0.13~)\n", ""),
                                     ("debian/control", "         ${misc:Depends}\nRecommends", "         omx-panel (>= 0.12.0~), omx-panel (<< 0.13~),\n         ${misc:Depends}\nRecommends")], "names"),
    ("the daemon not at its own version", [("debian/control", "plugin-hostd (= ${source:Version}),\n         omx-clap-host", "plugin-hostd (>= 0.20.0~),\n         omx-clap-host")], "not exactly"),
    ("the formats disagree", [("packaging/plugin-hostd.spec", "(omx-panel >= 0.12.0 with omx-panel < 0.13)", "(omx-panel >= 0.12.1 with omx-panel < 0.13)")], "in the spec and"),
]


def main():
    bad = 0
    for what, edits, expect in SABOTAGE:
        got = planted(ROOT, edits)
        if not any(expect in g for g in got):
            print(f"FAIL sabotage not seen: {what} (got {got})")
            bad = 1
        else:
            print(f"ok   sabotage seen: {what}")
    p = problems(ROOT)
    for line in p:
        print("FAIL " + line)
    if not p:
        print("ok   plugin-hostd-full: plugin-hostd at its version, "
              + ", ".join(sorted(HARD)) + " each a floor and a ceiling; omx-panel recommended the same way")
    return 1 if p or bad else 0


if __name__ == "__main__":
    sys.exit(main())
