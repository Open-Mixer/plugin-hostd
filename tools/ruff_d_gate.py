#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The Python documentation gate: ruff's D1 rules (a public module, class, function, method or package without a
docstring) over the paths named, as a ratchet. tools/ruff-d.baseline holds `<file> <count>` for each file that has
missing docstrings today (ruff.toml carries the same files as per-file ignores, so a plain `ruff check` is green).
A per-file ignore alone would let a new function into a baselined file, so this counts: a file with more missing
docstrings than its baseline, or a file not in the baseline with any, fails; a file with fewer fails too, until its
baseline line is lowered (the list only shrinks). `--self-test` plants an undocumented function and requires a refusal.

Usage: ruff_d_gate.py [--baseline FILE] PATH...   |   ruff_d_gate.py --self-test
"""
import collections
import json
import os
import subprocess
import sys
import tempfile


def counts(paths):
    """Missing-docstring counts per file, from ruff with its own config ignored (the baseline's ignores must not hide)."""
    p = subprocess.run(["ruff", "check", "--isolated", "--select", "D1", "--output-format", "json", "--no-cache",
                        *paths], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        sys.exit("ruff-d-gate: ruff failed: " + p.stderr.strip())
    out = collections.Counter()
    for d in json.loads(p.stdout or "[]"):
        out[os.path.relpath(d["filename"])] += 1
    return out


def read_baseline(path):
    """`file count` lines to a dict; `#` lines ignored."""
    out = {}
    if path and os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            if ln.strip() and not ln.startswith("#"):
                f, c = ln.split()
                out[f] = int(c)
    return out


def gate(paths, baseline):
    """Exit status and messages."""
    now, base, msgs = counts(paths), read_baseline(baseline), []
    for f in sorted(set(now) | set(base)):
        if now[f] > base.get(f, 0):
            msgs.append("ruff-d-gate: %s has %d public item(s) without a docstring, the baseline allows %d: "
                        "document the new one (ruff check --isolated --select D1 %s)" % (f, now[f], base.get(f, 0), f))
        elif now[f] < base.get(f, 0):
            msgs.append("ruff-d-gate: %s has %d now, the baseline says %d: lower its line in %s"
                        % (f, now[f], base[f], baseline))
    return (1 if msgs else 0), msgs, sum(now.values())


def self_test():
    """A scratch module with an undocumented public function: refused with an empty baseline, accepted when baselined."""
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        open("m.py", "w").write('"""m."""\n\n\ndef good():\n    """g."""\n\n\ndef bad():\n    pass\n')
        if gate(["m.py"], "none")[0] != 1:
            print("ruff-d-gate self-test: an undocumented function was not refused")
            return 1
        open("b", "w").write("m.py 1\n")
        if gate(["m.py"], "b")[0] != 0:
            print("ruff-d-gate self-test: a baselined file was refused")
            return 1
    print("ruff-d-gate self-test: ok")
    return 0


def main(argv):
    """Command line: see the module docstring."""
    if argv[1:] == ["--self-test"]:
        return self_test()
    a, baseline, paths = argv[1:], None, []
    while a:
        x = a.pop(0)
        if x == "--baseline":
            baseline = a.pop(0)
        else:
            paths.append(x)
    status, msgs, total = gate(paths, baseline)
    print("\n".join(msgs))
    print("ruff-d-gate: %d missing docstring(s), baseline %d" % (total, sum(read_baseline(baseline).values())))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
