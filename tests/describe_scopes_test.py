# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
# plugin-hostd-probe describe reads the scopes of a field dump from omx-clap-core's scan domain (contract.d/scan/scan.json
# there, item SCAN_FIELD_SCOPES), at start-up through the loader: the scope names of src/describe.c's parser are the
# domain's words, not a hand copy (sorting pass V9). The call is the runner's own, describe over a recorded dump:
#   (a) golden, frozen from the hand copy at 2235c68: the fourteen scopes (plugin, param, audio_in, audio_out, note_in,
#       note_out, port, panel, section, control, role, display, placement_default, meter) are scopes of a CLAP dump, but
#       port, which is LV2's, and every other word is no scope;
#   (b) the domain holds exactly those fourteen words;
#   (c) sabotage: a temporary contract directory whose domain has `param` renamed makes the renamed word the scope and
#       `param` none; one short of a word, or with none, refuses the start-up by name (exit 78).
#   (d) packaging: the scopes are omx-clap-core's, so the spec and debian/control name omx-clap-contract at the floor of
#       the release that carries the scan domain under its new name (0.34.0, the omx-clap rename) or a later one, 0.35.0 since the unit-id rows read its OMX_PARAM_CONTRACT_UNIT_IDS (#215 M5), a floor only (no Breaks, Replaces, Conflicts or Provides).
#   describe_scopes_test.py   PROBE is the runner (default ./plugin-hostd-probe); OMX_CONTRACT_PATH is the test entry the
#                             domain is read from: a ':' list, the first directory holding scan/ wins
import json, os, shutil, subprocess, sys, tempfile

import format_tables

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe"))
FIELDS = os.path.join(ROOT, "tests", "fixtures", "fields")
CONTRACT_DIR = os.path.join(ROOT, "tests", "fixtures", "contract-dir")
GOLDEN = ["plugin", "param", "audio_in", "audio_out", "note_in", "note_out", "port", "panel", "section", "control", "role",
          "display", "placement_default", "meter"]
NO_INDEX = {"plugin", "panel"}
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def scan_document():
    for d in os.environ.get("OMX_CONTRACT_PATH", "").split(":"):
        path = os.path.join(d, "scan", "scan.json")
        if d and os.path.isfile(path):
            return d, json.load(open(path))
    print("FAIL no directory of OMX_CONTRACT_PATH holds the scan domain")
    sys.exit(1)


def describe_line(fmt, scope, dirs, tmp):
    """describe over a dump of one line, `scope` a field no table has a row for: the refusal tells whether the scope is one"""
    dump = os.path.join(tmp, "dump.tsv")
    with open(dump, "w") as f:
        f.write("# omx-clap-scan --fields 1\n%s\tno_such_field\tx\n" % scope)
    target = {"clap": "clap:controls.clap#org.example.x", "lv2": "lv2:urn:example:x"}[fmt]
    env = dict(os.environ, OMX_CONTRACT_PATH=dirs)
    return subprocess.run([PROBE, "describe", "--table", format_tables.path(fmt), "--contract-dir", CONTRACT_DIR,
                           "--fields-from", dump, target], capture_output=True, text=True, timeout=60, env=env)


def is_scope(fmt, word, dirs, tmp):
    scope = word if word in NO_INDEX else word + ":0"
    r = describe_line(fmt, scope, dirs, tmp)
    return r.returncode == 2 and "is no %s scope" % fmt not in r.stderr and "no row" in r.stderr, r


def sabotaged(tmp, name, edit):
    where, doc = scan_document()
    out = os.path.join(tmp, name)
    shutil.copytree(os.path.join(where, "scan"), os.path.join(out, "scan"))
    edit(doc)
    with open(os.path.join(out, "scan", "scan.json"), "w") as f:
        json.dump(doc, f, indent=2)
    return out + ":" + os.environ["OMX_CONTRACT_PATH"]


def main():
    where, doc = scan_document()
    path = os.environ["OMX_CONTRACT_PATH"]
    with tempfile.TemporaryDirectory() as tmp:
        # (a) golden
        clap = [w for w in GOLDEN if w != "port"]
        bad = [w for w in clap if not is_scope("clap", w, path, tmp)[0]]
        check(not bad, "(a) the CLAP dump's scopes are the golden thirteen (not: %s)" % bad)
        ok_port, r = is_scope("clap", "port", path, tmp)
        check(not ok_port and "is no clap scope" in r.stderr, "(a) port is no scope of a CLAP dump")
        ok_port, r = is_scope("lv2", "port", path, tmp)
        check(ok_port, "(a) port is a scope of an LV2 dump (%d: %s)" % (r.returncode, r.stderr.strip()))
        ok_x, r = is_scope("clap", "param-x", path, tmp)
        check(not ok_x, "(a) a word that is no scope is none")
        # (b) the domain's words
        words = [w["const"] for w in sorted(doc["components"]["schemas"]["SCAN_FIELD_SCOPES"]["oneOf"], key=lambda w: w["x-code"])]
        check(sorted(words) == sorted(GOLDEN) and len(words) == 14, "(b) SCAN_FIELD_SCOPES holds the golden fourteen words (%s)" % words)

        # (c) sabotage
        def renamed(d):
            for w in d["components"]["schemas"]["SCAN_FIELD_SCOPES"]["oneOf"]:
                if w["const"] == "param":
                    w["const"] = "param-x"

        dirs = sabotaged(tmp, "renamed", renamed)
        got_x, r = is_scope("clap", "param-x", dirs, tmp)
        got_old, r2 = is_scope("clap", "param", dirs, tmp)
        check(got_x and not got_old, "(c) a domain with `param` renamed makes `param-x` the scope and `param` none (%d: %s)"
              % (r.returncode, (r.stderr + r2.stderr).strip()))

        def short(d):
            d["components"]["schemas"]["SCAN_FIELD_SCOPES"]["oneOf"].pop()

        r = describe_line("clap", "param:0", sabotaged(tmp, "short", short), tmp)
        check(r.returncode == 78 and "SCAN_FIELD_SCOPES" in r.stderr and "scan" in r.stderr,
              "(c) a domain short of a word ends the start-up with 78, naming the item (%d: %s)" % (r.returncode, r.stderr.strip()))
        r = describe_line("clap", "param:0", os.path.join(tmp, "nowhere"), tmp)
        check(r.returncode == 78 and "scan" in r.stderr, "(c) no scan domain ends the start-up with 78, naming it (%d: %s)"
              % (r.returncode, r.stderr.strip()))
        # (d) packaging
        spec = open(os.path.join(ROOT, "packaging", "plugin-hostd.spec")).read()
        control = open(os.path.join(ROOT, "debian", "control")).read()
        check("\nRequires: omx-clap-contract >= 0.35.0\n" in spec and "\nBuildRequires: omx-clap-contract >= 0.35.0\n" in spec,
              "(d) the spec requires and builds against omx-clap-contract >= 0.35.0")
        check("omx-clap-contract (>= 0.35.0~)" in control and control.count("omx-clap-contract") >= 2,
              "(d) debian/control depends on and builds against omx-clap-contract >= 0.35.0")
        check(not any(k + ":" in line and "omx-clap-contract" in line for line in (spec + control).splitlines()
                      for k in ("Breaks", "Replaces", "Conflicts", "Provides")), "(d) the relation is a floor only")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
