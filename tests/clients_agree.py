#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""Both protocol clients answer every input the same (docs/clients.md, #29).

The cases are clients/fixtures/codec.json and, from plugin-hostd-protocol's host scenarios (its scenarios variable),
every command line decoded and encoded again and every reply the scenarios accept parsed. Each client is run once on
all of them through its own entry point (`python3 -m plugin_hostd_protocol`, `node clients/ts/dist/cli.js`), which
reads {"cases": [...]} and prints one answer per case, {"ok": value} or {"error": message}. Red for a case the two
answer differently (a refusal against a value, or two values), and for a fixture whose "expect" or "error" a client
does not meet. --self-test runs the comparison with one answer of the Python client changed and wants it red.

Usage: tests/clients_agree.py [--self-test]   (PYTHON, NODE: the interpreters; SCENARIOS: the scenarios file)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(ROOT, "clients", "fixtures", "codec.json")
# what the runner of the scenarios substitutes, stood in for by words the codec takes as they are
STAND_INS = {"$BAD_URI": "lv2:urn:example:missing", "$URI": "lv2:urn:example:gain", "$PARAM": "gain",
             "$DIR": "/tmp/plugin-hostd-presets", "$PORT_A": "system:capture_1", "$PORT_B": "system:playback_1",
             "$REMOVE_TWICE": "resp 0"}


def scenarios_file():
    path = os.environ.get("SCENARIOS")
    if path:
        return path
    out = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=scenarios", "plugin-hostd-protocol"],
                         capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        sys.exit("clients_agree: no scenarios: plugin-hostd-protocol-devel is not installed and SCENARIOS is not set")
    return out.stdout.strip()


def scenario_cases(path):
    """Every command of the scenarios decoded and encoded again, every reply they accept parsed."""
    cases = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue
            if line.startswith("@"):  # the scenario's own marker: skipped when that verb is not served
                line = line.split(None, 1)[1]
            for k, v in STAND_INS.items():
                line = line.replace(k, v)
            command, replies = (s.strip() for s in line.split("=>", 1))
            cases.append({"op": "reencode", "in": command, "from": "scenarios"})
            for reply in replies.split("|"):
                cases.append({"op": "parse", "in": reply.strip(), "from": "scenarios"})
    return cases


def run(argv, cases, env=None):
    proc = subprocess.run(argv, input=json.dumps({"cases": cases}), capture_output=True, text=True, cwd=ROOT,
                          env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        sys.exit("clients_agree: %s failed (%d): %s" % (" ".join(argv), proc.returncode, proc.stderr.strip()[:400]))
    answers = json.loads(proc.stdout)
    if len(answers) != len(cases):
        sys.exit("clients_agree: %s answered %d of %d cases" % (" ".join(argv), len(answers), len(cases)))
    return answers


def clean(value):
    """A value with its null fields dropped, so an absent field and a null one are the same answer."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def judge(cases, py, ts):
    """The lines that make the run red: a disagreement, or a fixture a client does not meet."""
    bad = []
    for case, a, b in zip(cases, py, ts):
        what = "%s %s" % (case["op"], json.dumps(case["in"], ensure_ascii=False))
        if ("error" in a) != ("error" in b) or clean(a.get("ok")) != clean(b.get("ok")):
            bad.append("DIFFER %s: python %s, typescript %s" % (what, json.dumps(a), json.dumps(b)))
            continue
        if case.get("error") and "error" not in a:
            bad.append("NOT REFUSED %s: both answer %s" % (what, json.dumps(a["ok"])))
        elif "expect" in case and ("error" in a or clean(a["ok"]) != clean(case["expect"])):
            bad.append("WRONG %s: both answer %s, the fixture %s" % (what, json.dumps(a), json.dumps(case["expect"])))
        elif not case.get("error") and "expect" not in case and case.get("from") != "scenarios" and "error" in a:
            bad.append("REFUSED %s: both refuse it (%s)" % (what, a["error"]))
    return bad


def main():
    with open(FIXTURES) as f:
        cases = json.load(f)["cases"] + scenario_cases(scenarios_file())
    python = [os.environ.get("PYTHON", sys.executable), "-m", "plugin_hostd_protocol"]
    node = [os.environ.get("NODE", "node"), os.path.join("clients", "ts", "dist", "cli.js")]
    py = run(python, cases, {"PYTHONPATH": os.path.join(ROOT, "clients", "python")})
    ts = run(node, cases)
    if "--self-test" in sys.argv[1:]:
        # a client that answers the first decoded command otherwise: the comparison must see it
        i = next(n for n, c in enumerate(cases) if c["op"] == "decode" and "ok" in py[n])
        py[i] = {"ok": {"verb": "changed", "args": []}}
        bad = judge(cases, py, ts)
        if any(line.startswith("DIFFER decode") for line in bad):
            print("SABOTAGE a client answering one input otherwise: red (%s)" % bad[0][:120])
            return 0
        print("FAIL clients_agree self-test: a changed answer stays green")
        return 1
    bad = judge(cases, py, ts)
    for line in bad:
        print(line)
    n_scen = sum(1 for c in cases if c.get("from") == "scenarios")
    print("clients_agree: %d cases (%d fixtures, %d from the scenarios), %d red" % (len(cases), len(cases) - n_scen, n_scen, len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
