#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The grouping reasons as constants of the clients' readers (#67). data/grouping.json declares them
# (PLUGIN_HOSTD_GROUPING_REASONS); GroupingReason in clients/python/plugin_hostd_protocol/__init__.py and in
# clients/ts/src/index.ts is written between its markers from that file, never by hand.
#
#   tools/grouping-reasons.py write       writes both regions
#   tools/grouping-reasons.py check       fails when a region is missing or is not what the file gives
#   tools/grouping-reasons.py self-test   plants a new reason, a stray constant and a hand edit; each must fail the check
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
JSON = "data/grouping.json"
PY = "clients/python/plugin_hostd_protocol/__init__.py"
TS = "clients/ts/src/index.ts"
NAME = "grouping-reasons"


def fail(msg):
    sys.exit(f"grouping-reasons: {msg}")


def reasons(root):
    try:
        with open(os.path.join(root, JSON), encoding="utf-8") as f:
            words = json.load(f)["PLUGIN_HOSTD_GROUPING_REASONS"]["words"]
    except (OSError, ValueError, KeyError) as e:
        fail(f"{JSON}: {e}")
    out = []
    for key, row in words.items():
        word = row["word"]
        if not re.fullmatch(r"[a-z]+(-[a-z]+)*", word) or not re.fullmatch(r"[a-z][A-Za-z]*", key):
            fail(f"{JSON}: {key}: {word!r} is no reason word")
        out.append((key, word))
    if not out:
        fail(f"{JSON}: no reason")
    return out


def banner(comment):
    return f"{comment} BEGIN GENERATED {NAME} (tools/grouping-reasons.py, from {JSON}): do not edit"


def python_region(rs):
    o = [banner("#"), "class GroupingReason:",
         '    """The reasons a plan gives (PLUGIN_HOSTD_GROUPING_REASONS): a controller compares against these and writes no',
         '    reason word of its own. plan_get answers them as instance:reason; a plan-refused is followed by a colon and the',
         '    number of the refusal."""', ""]
    o += [f'    {w.upper().replace("-", "_")} = "{w}"' for _, w in rs]
    o.append(f"# END GENERATED {NAME}")
    return "\n".join(o) + "\n"


def ts_region(rs):
    o = [banner("//"),
         "/** The reasons a plan gives (PLUGIN_HOSTD_GROUPING_REASONS), by the key the file gives each: a controller compares",
         " * against these and writes no reason word of its own. A plan-refused is followed by a colon and the refusal's number. */",
         "export const GroupingReason = {"]
    o += [f"  {k}: '{w}'," for k, w in rs]
    o += ["} as const;", "/** One of the reasons a plan gives. */",
          "export type GroupingReasonWord = (typeof GroupingReason)[keyof typeof GroupingReason];",
          f"// END GENERATED {NAME}"]
    return "\n".join(o) + "\n"


def splice(text, region, comment, path):
    pat = re.compile(rf"^{re.escape(comment)} BEGIN GENERATED {NAME}.*?^{re.escape(comment)} END GENERATED {NAME}\n",
                     re.S | re.M)
    if len(pat.findall(text)) != 1:
        fail(f"{path}: not exactly one {NAME} region")
    return pat.sub(lambda _: region, text)


def render(root):
    rs = reasons(root)
    return {PY: (python_region(rs), "#"), TS: (ts_region(rs), "//")}


def run(root, write):
    bad = []
    for path, (region, comment) in render(root).items():
        full = os.path.join(root, path)
        with open(full, encoding="utf-8") as f:
            text = f.read()
        new = splice(text, region, comment, path)
        if new != text:
            if write:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new)
            else:
                bad.append(path)
    return bad


def check(root):
    bad = run(root, False)
    if bad:
        fail(f"{', '.join(bad)} is not what {JSON} gives: make render-grouping-reasons")
    return True


def self_test():
    # each plant must turn the check red: a reason the file gains, a constant it does not declare, a hand edit
    plants = {
        "a reason added to the file": (JSON, lambda t: t.replace(
            '"groupingOff": {', '"groupingNew": {\n        "word": "grouping-new",\n        "doc": "x"\n      },\n      "groupingOff": {', 1)),
        "a stray constant in the Python client": (PY, lambda t: t.replace('    GROUPING_OFF = "grouping-off"\n',
                                                                         '    GROUPING_OFF = "grouping-off"\n    STRAY = "stray"\n', 1)),
        "a stray constant in the TypeScript client": (TS, lambda t: t.replace("  groupingOff: 'grouping-off',\n",
                                                                              "  groupingOff: 'grouping-off',\n  stray: 'stray',\n", 1)),
        "a hand edit of a value": (TS, lambda t: t.replace("'grouping-off'", "'grouping-of'", 1)),
    }
    for what, (path, edit) in plants.items():
        tmp = tempfile.mkdtemp()
        try:
            for p in (JSON, PY, TS):
                os.makedirs(os.path.dirname(os.path.join(tmp, p)), exist_ok=True)
                shutil.copy(os.path.join(ROOT, p), os.path.join(tmp, p))
            with open(os.path.join(tmp, path), encoding="utf-8") as f:
                before = f.read()
            after = edit(before)
            if after == before:
                fail(f"self-test: the plant {what!r} changed nothing")
            with open(os.path.join(tmp, path), "w", encoding="utf-8") as f:
                f.write(after)
            try:
                check(tmp)
            except SystemExit:
                print(f"ok   {what} turns the check red")
                continue
            fail(f"self-test: {what} left the check green")
        finally:
            shutil.rmtree(tmp)


def main(argv):
    if len(argv) != 2 or argv[1] not in ("write", "check", "self-test"):
        fail("usage: grouping-reasons.py write|check|self-test")
    if argv[1] == "self-test":
        self_test()
    elif argv[1] == "write":
        run(ROOT, True)
    elif check(ROOT):
        print(f"ok   the {NAME} constants are what {JSON} gives")


main(sys.argv)
