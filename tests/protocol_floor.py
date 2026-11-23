#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# The plugin-hostd-protocol floor is high enough: packaging/deps.txt declares it once (tools/protocol-floor.sh reads it;
# deps-render holds every file that writes it to that), and the sources use an OMX_VERB_* of the
# protocol's verb group that carries its own `since`, which is a release of plugin-hostd-protocol, so the floor is at
# or above the largest `since` of what they use. PLUGIN_HOSTD_VERBS' own `since` counts plugin-hostd's releases, from
# before the protocol was a package of its own, and the verbs it held then carry none: they are all in the first one
# (0.2.0). A verb added to it since carries its own, a release of plugin-hostd-protocol (node_label, 0.5.6), and counts
# as the protocol group's do.
# Usage: protocol_floor.py [root]. The check proves it sees each fault before it trusts the tree.
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import declared

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUP = "PLUGIN_HOSTD_PROTOCOL_VERBS"


def version(s):
    return tuple(int(x) for x in s.split("."))


def macro(verb):
    return "OMX_VERB_" + verb.upper()


def group_since(verbs):
    """{macro of a verb of the group: the protocol release that first declares it}"""
    out = {macro(v["verb"]): v["since"] for v in verbs[GROUP]["verbs"].values()}
    out.update({macro(v["verb"]): v["since"] for v in verbs["PLUGIN_HOSTD_VERBS"]["verbs"].values() if v.get("since")})
    return out


def problems(floor, sources, since):
    bad = []
    for sym, first in sorted(since.items()):
        users = [name for name, text in sources.items() if re.search(r"\b%s\b" % sym, text)]
        if users and version(floor) < version(first):
            bad.append("%s uses %s, first declared by plugin-hostd-protocol %s: the floor %s is below it"
                       % (users[0], sym, first, floor))
    return bad


def text_of(path):
    with open(path) as f:
        return f.read()


def tree_files(sub, suffixes):
    d = os.path.join(ROOT, sub)
    return {os.path.join(sub, f): text_of(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(suffixes)}


SRC_OK = {"src/verbs.c": "strcmp(verb, OMX_VERB_HELLO)\n"}
SINCE = {"OMX_VERB_HELLO": "0.3.0", "OMX_VERB_PARAM_SET_MANY": "0.3.0"}


def main():
    # the check sees each fault before it is trusted: (what, floor, sources, findings)
    arms = [
        ("the tree as written", "0.3.0", SRC_OK, 0),
        ("a verb past the floor, used", "0.2.0", {"src/supervisor.c": "OMX_VERB_PARAM_SET_MANY\n"}, 1),
        ("a verb past the floor, not used", "0.2.0", {"src/verbs.c": "OMX_VERB_PARAM_SET_MANYFOLD\n"}, 0),
    ]
    for what, floor, src, want in arms:
        got = problems(floor, src, SINCE)
        if len(got) != want:
            print("FAIL the floor check on %s: want %d findings, got %s" % (what, want, got))
            return 1
    print("ok   the floor check sees a verb used past the protocol floor")

    p = subprocess.run([os.path.join(ROOT, "tools", "protocol-floor.sh")], capture_output=True, text=True)
    if p.returncode != 0:
        print("FAIL " + p.stderr.strip())
        return 1
    floor = p.stdout.strip()
    since = group_since(declared.verbs())
    sources = tree_files("src", (".c", ".h"))
    bad = problems(floor, sources, since)
    for b in bad:
        print("FAIL %s" % b)
    if bad:
        return 1
    used = sorted(s for s in since if any(re.search(r"\b%s\b" % s, t) for t in sources.values()))
    print("ok   the protocol floor is %s, at or above what the sources use of %s (%s)" % (floor, GROUP, ", ".join(used)))
    return 0


sys.exit(main())
