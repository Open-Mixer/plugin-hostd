#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# The words of a pin's verdict and pool are plugin-hostd-protocol's (its domain `pin`, generated into protocol.h as
# PHD_PIN_VERDICT_*, PHD_PIN_POOL_*, PHD_PIN_VERDICTS and PHD_PIN_POOLS, sorting pass V12). This tree reads them by those names
# (src/pins.c, src/supervisor.c, src/pin_words.c, fuzz/fuzz_command.c), so every protocol package it names, in the spec, in
# debian/control and in packaging/deps.txt, is floored at 0.8.0, the release that carries the domain, and no floor
# is a ceiling or an equality. The check sees each fault before it is trusted.
# Usage: pin_words_floor.py [root]
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRST = (0, 8, 0)
NAMES = ("plugin-hostd-protocol", "plugin-hostd-protocol-devel", "plugin-hostd-protocol-contract",
         "libplugin-hostd-protocol0", "libplugin-hostd-protocol-dev")
USES = re.compile(r"\bPHD_PIN_(?:VERDICT_[A-Z_]+|POOL_(?:CORES|OFF)|VERDICTS|POOLS)\b")


def version(s):
    return tuple(int(x) for x in s.split("."))


def floors(text):
    out = []
    for line in text.split("%changelog")[0].splitlines():
        if line.lstrip().startswith("#"):
            continue
        for m in re.finditer(r"(?<![\w-])(%s)(?:\s*>=\s*|\s*\(>=\s*)(\d+\.\d+\.\d+)" % "|".join(map(re.escape, NAMES)), line):
            out.append((m.group(1), m.group(2)))
    return out


def deps_floors(text):
    out = []
    for line in text.splitlines():
        w = line.split()
        if len(w) == 3 and not line.startswith("#") and w[0] in NAMES:
            out.append((w[0], w[2]))
    return out


def problems(uses, found):
    bad = []
    if uses and not found:
        bad.append("the sources use the pin words and no floor of a protocol package is declared")
    for name, v in found:
        if uses and version(v) < FIRST:
            bad.append("%s is floored at %s, below 0.8.0 where the pin words are generated from the domain pin" % (name, v))
    return bad


def read(path):
    with open(os.path.join(ROOT, path)) as f:
        return f.read()


def main():
    src = "".join(read("src/" + f) for f in sorted(os.listdir(os.path.join(ROOT, "src"))) if f.endswith((".c", ".h")))
    uses = bool(USES.search(src))
    arms = [("floor 0.8.0, used", True, [("plugin-hostd-protocol-devel", "0.8.0")], 0),
            ("floor 0.7.0, used", True, [("plugin-hostd-protocol-devel", "0.7.0")], 1),
            ("floor 0.7.0, not used", False, [("plugin-hostd-protocol-devel", "0.7.0")], 0),
            ("no floor, used", True, [], 1)]
    for what, u, f, want in arms:
        if len(problems(u, f)) != want:
            print("FAIL the check on %s: want %d findings, got %s" % (what, want, problems(u, f)))
            return 1
    print("ok   the check sees a protocol floor below 0.8.0 under the pin words")
    found = floors(read("packaging/plugin-hostd.spec")) + floors(read("debian/control")) + deps_floors(read("packaging/deps.txt"))
    names = {n for n, _ in found}
    if not {"plugin-hostd-protocol-devel", "plugin-hostd-protocol-contract"} <= names:
        print("FAIL the spec, control and deps.txt name no floor of -devel and -contract: %s" % sorted(names))
        return 1
    bad = problems(uses, found)
    for b in bad:
        print("FAIL " + b)
    if bad:
        return 1
    print("ok   this tree uses the pin words by protocol.h's names, and %d protocol floors are at 0.8.0 or above" % len(found))
    return 0


sys.exit(main())
