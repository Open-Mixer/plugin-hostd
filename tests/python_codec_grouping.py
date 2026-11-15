#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The Python codec is plugin-hostd-protocol's (python3-plugin-hostd-protocol, imported installed: no copy of it is in this
# tree), and the grouping reasons are plugin-hostd's (data/grouping.json, PLUGIN_HOSTD_GROUPING_REASONS). The codec's
# GroupingReason holds one constant for each declared reason, with the file's value, and no other; its RETRY_REASONS are
# the reasons whose group the file declares retry, in the file's order. tools/grouping-reasons.py holds the TypeScript
# client to the same file by writing it. The codec's package must be the protocol's, at or above the floor of the spec.
#
#   tests/python_codec_grouping.py             red when the installed codec does not hold what the file declares
#   tests/python_codec_grouping.py --self-test each fault planted in a stand-in codec must be red
import json
import os
import re
import subprocess
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = re.compile(r"python3-plugin-hostd-protocol\s*>=\s*1:(\d+(?:\.\d+)*)")


def problems(declared, codec):
    """what the codec holds that the declared reasons (the parsed data/grouping.json) do not say"""
    words = [(k, w["word"], w.get("group")) for k, w in declared["PLUGIN_HOSTD_GROUPING_REASONS"]["words"].items()]
    constants = {k: v for k, v in vars(codec.GroupingReason).items() if not k.startswith("_")}
    bad = []
    for _, word, _g in words:
        name = word.upper().replace("-", "_")
        if constants.get(name) != word:
            bad.append("no constant %s = %r in GroupingReason" % (name, word))
    for name, value in constants.items():
        if value not in {w for _, w, _g in words}:
            bad.append("GroupingReason.%s = %r names no declared reason" % (name, value))
    retry = tuple(w for _, w, g in words if g == "retry")
    if tuple(codec.RETRY_REASONS) != retry:
        bad.append("RETRY_REASONS is %r, the file declares %r retry" % (tuple(codec.RETRY_REASONS), retry))
    return bad


def floor():
    with open(os.path.join(ROOT, "packaging", "plugin-hostd.spec"), encoding="utf-8") as f:
        m = FLOOR.search(f.read())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def installed_version():
    """the version of the installed package python3-plugin-hostd-protocol, with its epoch, from the package manager"""
    for cmd, parse in ((["rpm", "-q", "--qf", "%{EPOCH}:%{VERSION}", "python3-plugin-hostd-protocol"], lambda o: o),
                       (["dpkg-query", "-W", "-f", "${Version}", "python3-plugin-hostd-protocol"], lambda o: o)):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
        except OSError:
            continue
        if p.returncode == 0 and p.stdout.strip():
            return parse(p.stdout.strip())
    return None


def version_problems(want, have):
    if want is None:
        return ["packaging/plugin-hostd.spec names no python3-plugin-hostd-protocol >= 1:<version> floor"]
    if have is None:
        return ["python3-plugin-hostd-protocol is not installed (plugin-hostd-protocol >= %s serves it)" % ".".join(map(str, want))]
    m = re.match(r"(?:(\d+|\(none\)):)?(\d+(?:\.\d+)*)", have)
    epoch = 0 if not m.group(1) or m.group(1) == "(none)" else int(m.group(1))
    got = tuple(int(x) for x in m.group(2).split("."))
    if epoch < 1 or got < want:
        return ["python3-plugin-hostd-protocol %s is installed, the codec of plugin-hostd-protocol %s with epoch 1 is the floor "
                "(an older one is the package plugin-hostd built before it moved)" % (have, ".".join(map(str, want)))]
    return []


def stand_in(extra=None, retry=None, drop=None):
    cls = {"REFUSED": "refused", "NO_VERDICT": "no-verdict", "PLAN_REFUSED": "plan-refused"}
    cls.pop(drop, None)
    cls.update(extra or {})
    return types.SimpleNamespace(GroupingReason=type("GroupingReason", (), cls),
                                 RETRY_REASONS=("no-verdict", "plan-refused") if retry is None else retry)


def self_test():
    declared = {"PLUGIN_HOSTD_GROUPING_REASONS": {"words": {
        "refused": {"word": "refused", "group": "final"}, "noVerdict": {"word": "no-verdict", "group": "retry"},
        "planRefused": {"word": "plan-refused", "group": "retry"}}}}
    assert not problems(declared, stand_in()), "the stand-in codec is not clean"
    faults = {
        "a declared reason with no constant": stand_in(drop="REFUSED"),
        "a stray constant": stand_in(extra={"STRAY": "stray"}),
        "a constant with another value": stand_in(extra={"REFUSED": "refusd"}),
        "a RETRY_REASONS with a reason the file does not call retry": stand_in(retry=("refused", "no-verdict", "plan-refused")),
        "a RETRY_REASONS short of one": stand_in(retry=("no-verdict",)),
    }
    for what, codec in faults.items():
        if not problems(declared, codec):
            sys.exit("python_codec_grouping: self-test: %s left the check green" % what)
        print("ok   %s turns the check red" % what)
    for what, want, have in (("no installed package", (0, 5, 10), None), ("the package plugin-hostd built (no epoch)", (0, 5, 10), "(none):0.20.6"),
                             ("an older codec", (0, 5, 10), "1:0.5.9")):
        if not version_problems(want, have):
            sys.exit("python_codec_grouping: self-test: %s left the version check green" % what)
        print("ok   %s turns the version check red" % what)
    if version_problems((0, 5, 10), "1:0.5.10"):
        sys.exit("python_codec_grouping: self-test: the floor itself is red")


def main():
    if "--self-test" in sys.argv:
        return self_test()
    bad = version_problems(floor(), installed_version())
    try:
        import plugin_hostd_protocol as codec
    except ImportError as e:
        sys.exit("python_codec_grouping: the codec is not installed: %s" % e)
    with open(os.path.join(ROOT, "data", "grouping.json"), encoding="utf-8") as f:
        try:
            bad += problems(json.load(f), codec)
        except AttributeError as e:  # a codec that predates GroupingReason is the old package: the version problem says so
            bad.append("the installed codec has no %s" % e.name if hasattr(e, "name") else "the installed codec lacks %s" % e)
    if bad:
        sys.exit("python_codec_grouping: " + "\npython_codec_grouping: ".join(bad))
    print("ok   the installed codec (%s) holds the reasons data/grouping.json declares" % codec.__file__)


main()
