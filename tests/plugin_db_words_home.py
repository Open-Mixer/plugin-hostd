#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas
"""tests/plugin_db_words_home.py: plugin-hostd reads plugin-db's words from plugin-db's own headers, never from
plugin-hostd-protocol's copy of plugin_db_vocabulary.h (#250; plugin-db#34, ruling R5: the protocol stops rendering
plugin-db's package, so its copy goes).

(a) no C file of the tree includes the protocol's copy: <plugin-hostd/plugin_db_vocabulary.h>, or a bare
    "plugin_db_vocabulary.h", which protocol.h's directory would resolve to the copy;
(b) every C file that names an OMX_PLUGIN_DB_ word reaches a <plugin-db/...> header, plugin-db-devel's: itself, or through
    the tree's own headers it includes ("x.h", looked up beside it, then in src/);
(c) positive control: the tree names plugin-db words (src/proc.c's bundle rules, src/pins.h's digest length);
--self-test: sabotage in scratch copies, each red: the copy included, the plugin-db include dropped from src/pins.h, and
a plugin-db word used in a file that reaches no plugin-db header.

Exit 0 all green, 1 a FAIL line."""
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ("src", "tests", "fuzz", "tools")
WORD = re.compile(r"\bOMX_PLUGIN_DB_[A-Z0-9_]+")
INCLUDE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.M)
COPY = ("plugin-hostd/plugin_db_vocabulary.h", "plugin_db_vocabulary.h")


def c_files(root):
    for d in DIRS:
        for base, dirs, files in os.walk(os.path.join(root, d)):
            dirs[:] = [x for x in dirs if x not in (".git", "build")]
            for f in sorted(files):
                if f.endswith((".c", ".h")):
                    yield os.path.join(base, f)


def strip_comments(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def reaches_plugin_db(path, root, seen=None):
    """whether path includes a <plugin-db/...> header, itself or through a local "x.h" of the tree"""
    seen = set() if seen is None else seen
    if path in seen or not os.path.isfile(path):
        return False
    seen.add(path)
    for kind, name in INCLUDE.findall(strip_comments(open(path, encoding="utf-8").read())):
        if kind == "<" and name.startswith("plugin-db/"):
            return True
        if kind == '"':
            for cand in (os.path.join(os.path.dirname(path), name), os.path.join(root, "src", name)):
                if reaches_plugin_db(cand, root, seen):
                    return True
    return False


def problems(root):
    out, readers = [], 0
    for path in c_files(root):
        rel = os.path.relpath(path, root)
        text = strip_comments(open(path, encoding="utf-8").read())
        for kind, name in INCLUDE.findall(text):
            if name in COPY and not (kind == "<" and name.startswith("plugin-db/")):
                out.append(f"{rel}: includes {kind}{name}, plugin-hostd-protocol's copy of plugin-db's words")
        if WORD.search(text):
            readers += 1
            if not reaches_plugin_db(path, root):
                out.append(f"{rel}: names {WORD.search(text).group(0)} and reaches no <plugin-db/...> header")
    if not readers:
        out.append("no C file names a plugin-db word: the scan reads nothing (positive control)")
    return out


def report(root):
    bad = problems(root)
    for b in bad:
        print("FAIL " + b)
    return bad


def self_test():
    arms = (
        ("the protocol's copy included", "src/proc.c",
         lambda t: t.replace("#include <plugin-db/plugin_db_vocabulary.h>", "#include <plugin-hostd/plugin_db_vocabulary.h>", 1),
         "plugin-hostd-protocol's copy"),
        ("src/pins.h's plugin-db include dropped", "src/pins.h",
         lambda t: t.replace("#include <plugin-db/plugin_db_constants.h>", "", 1),
         "reaches no <plugin-db/...> header"),
        ("a plugin-db word in a file that reaches no plugin-db header", "tools/protocol-gen.c",
         lambda t: t + "\nstatic const unsigned planted = OMX_PLUGIN_DB_PIN_SHA256_HEX_LEN;\n",
         "tools/protocol-gen.c: names OMX_PLUGIN_DB_PIN_SHA256_HEX_LEN"),
    )
    failed = 0
    for what, rel, edit, want in arms:
        with tempfile.TemporaryDirectory() as tmp:
            t = os.path.join(tmp, "t")
            # the C sources alone: the scan reads nothing else
            for src in c_files(ROOT):
                dst = os.path.join(t, os.path.relpath(src, ROOT))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
            path = os.path.join(t, rel)
            before = open(path, encoding="utf-8").read()
            after = edit(before)
            if after == before:
                print(f"FAIL sabotage: {what}: the edit changes nothing in {rel}")
                failed += 1
                continue
            open(path, "w", encoding="utf-8").write(after)
            red = [p for p in problems(t) if want in p]
            print(("ok   " if red else "FAIL ") + f"sabotage: {what} is refused")
            failed += not red
    return failed


def main(argv):
    bad = report(ROOT)
    if not bad:
        print("ok   plugin-hostd reads plugin-db's words from plugin-db's own headers, never the protocol's copy")
    failed = len(bad)
    if "--self-test" in argv:
        failed += self_test()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
