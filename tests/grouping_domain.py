#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The grouping words are the domain plugin-hostd/grouping (contract.d/plugin-hostd/grouping/grouping.json), the call-level
# test of the sorting pass row V17:
#   a. golden: planner_reason_word, the planner's real read (compiled against the committed vocabulary header), gives the
#      16 reasons frozen from data/grouping.json at 2235c68, in that order, and the domain holds them with their groups
#   b. the committed include/plugin-hostd/plugin_hostd_vocabulary.h is the render of the domain, byte for byte (the
#      rebuild of tools/domain-data.mjs, then omx-contract render --check), and data/grouping.json is gone
#   c. sabotage: a scratch domain with no-pin renamed no-pin-x renders a header whose planner_reason_word says no-pin-x,
#      and with PLUGIN_HOSTD_GROUPING_REASONS removed from a scratch domain the planner does not build
#   d. plugin-hostd-protocol's Python client (GroupingReason, RETRY_REASONS, written there from this domain) holds the same
#      words and the same retry group
# Environment: OMX_CONTRACT, OMX_CONTRACT_CLIDIR, INSTALL_CONTRACT_DIR, CC, CFLAGS (the Makefile's test-grouping-domain).
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAIN = os.path.join(ROOT, "contract.d", "plugin-hostd", "grouping", "grouping.json")
HEADER = os.path.join(ROOT, "include", "plugin-hostd", "plugin_hostd_vocabulary.h")
GOLDEN = [  # data/grouping.json at 2235c68: (word, group)
    ("refused", "final"), ("no-pin", "final"), ("no-verdict", "retry"), ("verdict-isolated", "final"),
    ("format-world", "final"), ("history-crashed", "final"), ("history-xruns", "final"), ("cost-over", "final"),
    ("format-mixed", "final"), ("group-full", "final"), ("group-cost", "final"), ("cost-assumed", "final"),
    ("no-neighbour", "final"), ("grouping-off", "final"), ("history-unavailable", "final"), ("plan-refused", "retry"),
]
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        sys.exit("grouping_domain.py: %s is unset (run it as make test-grouping-domain)" % name)
    return v


def render(contract_d, out):
    """The Makefile's render of the vocabulary, over another contract.d: rebuild, install as the package, render."""
    tmp = tempfile.mkdtemp(prefix="grouping-render-")
    try:
        stage = os.path.join(tmp, "stage", "data")
        shutil.copytree(os.path.join(ROOT, "data"), stage)
        r = subprocess.run(["node", os.path.join(ROOT, "tools", "domain-data.mjs"), env("OMX_CONTRACT_CLIDIR"), stage,
                            contract_d, "plugin-hostd/grouping"], capture_output=True, text=True)
        if r.returncode:
            return r.returncode, r.stderr
        pkg = os.path.join(tmp, "dir")
        subprocess.run(["sh", env("INSTALL_CONTRACT_DIR"), "plugin-hostd", "0.0.0", "3", stage, pkg, "data"],
                       check=True, capture_output=True)
        path = pkg + ":" + subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True,
                                          text=True).stdout.strip()
        r = subprocess.run(env("OMX_CONTRACT", "omx-contract").split() + ["render", "--target", "c", "--package",
                           "plugin-hostd", "--installed", "--out", out], capture_output=True, text=True,
                           env=dict(os.environ, OMX_CONTRACT_PATH=path))
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(tmp)


def planner_words(include):
    """planner_reason_word for every reason, compiled against the header under <include>/plugin-hostd/."""
    tmp = tempfile.mkdtemp(prefix="grouping-planner-")
    try:
        c = os.path.join(tmp, "words.c")
        with open(c, "w") as f:
            f.write('#include <stdio.h>\n#include "planner.h"\nint main(void) { for (int r = 0; r < PLANNER_REASON_COUNT; r++)'
                    ' printf("%s\\n", planner_reason_word(r)); return 0; }\n')
        exe = os.path.join(tmp, "words")
        cmd = [env("CC", "cc")] + ["-I" + include] + env("CFLAGS", "").split() + ["-I" + os.path.join(ROOT, "src"), "-o", exe, c,
               os.path.join(ROOT, "src", "planner.c")] + subprocess.run(["pkg-config", "--libs", "plugin-db"],
                                                                         capture_output=True, text=True).stdout.split()
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr
        return subprocess.run([exe], capture_output=True, text=True, check=True).stdout.split(), ""
    finally:
        shutil.rmtree(tmp)


with open(DOMAIN, encoding="utf-8") as f:
    doc = json.load(f)
items = doc["components"]["schemas"]
reasons = items["PLUGIN_HOSTD_GROUPING_REASONS"]["oneOf"]

# a
words, err = planner_words(os.path.join(ROOT, "include"))
check(words == [w for w, _ in GOLDEN], "a. planner_reason_word gives the 16 golden reasons in order: %s %s" % (words, err))
check([(e["const"], e["x-group"]) for e in reasons] == GOLDEN, "a. the domain holds the 16 reasons and their groups")
check([e["const"] for e in items["PLUGIN_HOSTD_GROUPING_REASON_GROUPS"]["oneOf"]] == ["retry", "final"],
      "a. the domain holds the two groups, retry and final")

# b
out = tempfile.mkdtemp(prefix="grouping-out-")
rc, msg = render(os.path.join(ROOT, "contract.d"), out)
with open(HEADER, "rb") as f:
    committed = f.read()
got = open(os.path.join(out, "plugin_hostd_vocabulary.h"), "rb").read() if rc == 0 else b""
check(rc == 0 and got == committed, "b. the committed vocabulary header is the domain's render, byte for byte %s" % ("" if rc == 0 else msg))
check(not os.path.exists(os.path.join(ROOT, "data", "grouping.json")), "b. data/grouping.json, the old source, is gone")
shutil.rmtree(out)

# c
scratch = tempfile.mkdtemp(prefix="grouping-sabotage-")
try:
    cd = os.path.join(scratch, "contract.d")
    shutil.copytree(os.path.join(ROOT, "contract.d"), cd)
    sab = json.loads(json.dumps(doc))
    for e in sab["components"]["schemas"]["PLUGIN_HOSTD_GROUPING_REASONS"]["oneOf"]:
        if e["const"] == "no-pin":
            e["const"] = "no-pin-x"
    with open(os.path.join(cd, "plugin-hostd", "grouping", "grouping.json"), "w") as f:
        json.dump(sab, f, indent=2)
    inc = os.path.join(scratch, "include")
    os.makedirs(os.path.join(inc, "plugin-hostd"))
    shutil.copytree(os.path.join(ROOT, "include", "plugin-hostd"), os.path.join(inc, "plugin-hostd"), dirs_exist_ok=True)
    rc, msg = render(cd, os.path.join(inc, "plugin-hostd"))
    words, err = planner_words(inc) if rc == 0 else (None, msg)
    check(words is not None and words[1] == "no-pin-x", "c. a renamed word in a scratch domain is planner_reason_word's: %s %s" % (words and words[1], err))
    del sab["components"]["schemas"]["PLUGIN_HOSTD_GROUPING_REASONS"]
    with open(os.path.join(cd, "plugin-hostd", "grouping", "grouping.json"), "w") as f:
        json.dump(sab, f, indent=2)
    rc, msg = render(cd, os.path.join(inc, "plugin-hostd"))
    words, err = planner_words(inc) if rc == 0 else (None, msg)
    check(words is None, "c. without PLUGIN_HOSTD_GROUPING_REASONS in a scratch domain the planner does not build: %s" % (words or "refused"))
finally:
    shutil.rmtree(scratch)

# d
try:
    import plugin_hostd_protocol as client
    gr = {k: v for k, v in vars(client.GroupingReason).items() if not k.startswith("_")}
    check(list(gr.values()) == [w for w, _ in GOLDEN], "d. plugin-hostd-protocol's GroupingReason holds the domain's 16 words in order")
    check(tuple(client.RETRY_REASONS) == tuple(w for w, g in GOLDEN if g == "retry"), "d. its RETRY_REASONS are the domain's retry group")
except ImportError as e:
    check(False, "d. plugin-hostd-protocol's Python client is not importable (python3-plugin-hostd-protocol 0.8.0): %s" % e)

print("grouping domain: %s" % ("ok" if not fails else "FAILED (%d)" % fails))
sys.exit(1 if fails else 0)
