#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The format tables are the domains plugin-hostd/clap and plugin-hostd/lv2 (contract.d/plugin-hostd/<format>/<format>.json),
# the sorting pass row V19 in omx-contract's mapping-table kind, and their unit and meaning pairs the owners' (M5, #215):
#   a. each domain is a header ($id, info.x-owner plugin-hostd) over its one item PLUGIN_HOSTD_<F>_MAP, x-kind map,
#      x-format the format, a oneOf of one row per source field, const = title = the field, x-code its place; its rows, in
#      the data form, are those of ca2bd900's sheet byte for byte (their sha256, canonical) but the M5 rows
#   b. the M5 rows (a unit lookup; an LV2 designation lookup, param:* and lv2:enabled) write the same word through
#      unit-id or designation-meaning and carry no values: the pair is the owner's published mapping
#   c. data/formats is gone, and `make install_vocabulary_domains` into a scratch contract directory puts the documents at
#      <contractdir>/plugin-hostd/<f>/<f>.json and nothing under <contractdir>/3/plugin-hostd/formats
#   d. plugin-hostd-probe describe reads the domain document; the old data shape (a formatMap item at the top), the
#      sheet form and a map with no rows are refused, exit 2, naming the missing map
#   e. the pairs follow the owner: describe over a contract directory whose plugin-db lv2 domain maps units:db to dBu,
#      whose omx-param-contract swaps the codes db and dbu, writes dBu where the installed owners give dB; an owner's
#      domain lacking the mapping item is refused naming the item; a M5 row that carries values is refused
# Environment: PROBE, MAKE, CONTRACTDIR (the installed contract directory, default pkg-config's) (make test-format-domains).
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import format_tables

ROOT = format_tables.ROOT
PROBE = os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe"))
# ca2bd900's rows less the M5 rows: count, M5 count, sha256 of the rest (canonical JSON)
GOLDEN = {"clap": (373, 1, "9eb880d5099b8e7deebc66c7d30efa051c12874913bdeb02ccc3df58dfc1462e"),
          "lv2": (458, 29, "09e2d5d6f4287448ef7e72fede628c1b7688d63e5a759144561135ba743e6a92")}
M5 = {"clap": {"omx_clap_param_contract_entry.unit": "unit-id"},
      "lv2": dict([(k, "designation-meaning") for k in ("lv2:enabled", "param:attack", "param:bypass", "param:cutoffFrequency",
                   "param:decay", "param:delay", "param:frequency", "param:gain", "param:hold", "param:ratio", "param:release",
                   "param:resonance", "param:threshold", "param:wetDryRatio")]
                  + [("units:" + u, "unit-id") for u in ("bpm", "cent", "coef", "db", "degree", "frame", "hz", "midiNote", "min",
                                                         "ms", "oct", "pc", "s", "semitone12TET", "unit")])}
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def installed_dir():
    if os.environ.get("CONTRACTDIR"):
        return os.environ["CONTRACTDIR"]
    r = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=contractdir", "omx-contract"],
                       capture_output=True, text=True)
    return r.stdout.strip()


for fmt, (count, nm5, want) in GOLDEN.items():
    doc = format_tables.load(fmt)
    item = format_tables.item(doc, fmt)
    ones = item.get("oneOf") or []
    check(doc.get("$id") == "https://openmixer.org/contract/plugin-hostd/" + fmt and doc["info"].get("x-owner") == "plugin-hostd",
          "%s: the document is the domain plugin-hostd/%s, owned by plugin-hostd" % (fmt, fmt))
    check(list(doc["components"]["schemas"]) == [format_tables.ITEMS[fmt]] and item.get("x-kind") == "map"
          and item.get("x-format") == fmt and "x-value" not in item,
          "%s: one item %s, x-kind map of format %s" % (fmt, format_tables.ITEMS[fmt], fmt))
    check(all(m.get("const") == m.get("title") and m.get("x-code") == i for i, m in enumerate(ones)),
          "%s: each row's const and title its field, x-code its place" % fmt)
    rows = {k: dict(r) for k, r in format_tables.rows(doc, fmt).items()}
    rest = {k: r for k, r in rows.items() if k not in M5[fmt]}
    check(len(rows) == count and len(rows) - len(rest) == nm5 and digest(rest) == want,
          "%s: its %d rows less the %d M5 rows are those of ca2bd900 (%d, %s)" % (fmt, count, nm5, len(rows), digest(rest)[:12]))
    bad = [k for k, tr in M5[fmt].items()
           if (rows.get(k, {}).get("word") or {}).get("transform") != tr or "values" in (rows.get(k, {}).get("word") or {})]
    check(not bad, "%s: the M5 rows read the owner's mapping (unit-id, designation-meaning) and carry no values (%s)"
          % (fmt, ", ".join(bad[:6]) or "all"))
check(not os.path.exists(os.path.join(ROOT, "data", "formats")), "data/formats is gone: one source per table")

with tempfile.TemporaryDirectory(prefix="format-domains-") as tmp:
    r = subprocess.run([os.environ.get("MAKE", "make"), "--no-print-directory", "-C", ROOT, "install_vocabulary_domains", "DESTDIR=" + tmp],
                       capture_output=True, text=True)
    cdir = None
    for root, dirs, files in os.walk(tmp):
        if root.endswith("/plugin-hostd/clap") and "clap.json" in files:
            cdir = os.path.dirname(os.path.dirname(root))
    check(r.returncode == 0 and cdir is not None and all(os.path.isfile(os.path.join(cdir, "plugin-hostd", f, f + ".json")) for f in GOLDEN),
          "install puts <contractdir>/plugin-hostd/<format>/<format>.json (%s)" % (r.stderr.strip()[-200:] or cdir))
    check(not any("/3/plugin-hostd/formats" in root for root, _, _ in os.walk(tmp)), "and nothing under 3/plugin-hostd/formats")

    FIELDS = os.path.join(ROOT, "tests", "fixtures", "fields")
    CASES = {"clap": ("clap-comp.tsv", "clap:omx-comp.clap#org.openmixer.comp"),
             "lv2": ("lv2-compressor.tsv", "lv2:urn:example:compressor")}
    fixture_dir = os.path.join(ROOT, "tests", "fixtures", "contract-dir")

    def describe(fmt, table=None, contract_dir=fixture_dir):
        dump, target = CASES[fmt]
        return subprocess.run([PROBE, "describe", "--table", table or format_tables.path(fmt), "--contract-dir", contract_dir,
                               "--fields-from", os.path.join(FIELDS, dump), target], capture_output=True, text=True, timeout=60)

    def units(r):
        try:
            return [c.get("travel", {}).get("unit") for c in json.loads(r.stdout)["controls"]]
        except (ValueError, KeyError):
            return []

    good = {f: describe(f) for f in GOLDEN}
    for f, g in good.items():
        check(g.returncode == 0 and "dB" in units(g), "%s: describe over the domain document answers, a unit dB among its controls (%d: %s)"
              % (f, g.returncode, g.stderr.strip()[:200]))
    old = {"PLUGIN_HOSTD_CLAP_MAP": dict(kind="formatMap", format="clap", rows={k: dict(r) for k, r in format_tables.rows(format_tables.load("clap"), "clap").items()})}
    sheet = format_tables.load("clap")
    it = format_tables.item(sheet, "clap")
    it["x-value"] = {"format": "clap", "rows": old["PLUGIN_HOSTD_CLAP_MAP"]["rows"]}
    it["x-kind"] = "sheet"
    del it["oneOf"]
    empty = format_tables.load("clap")
    format_tables.item(empty, "clap")["oneOf"] = []
    for what, doc in (("the old data shape (a formatMap item)", old), ("the sheet form", sheet), ("a map with no rows", empty)):
        p = os.path.join(tmp, "t.json")
        with open(p, "w") as f:
            json.dump(doc, f)
        r = describe("clap", p)
        check(r.returncode == 2 and "holds no map item" in r.stderr and not r.stdout, "%s is refused, exit 2 (%d: %s)" % (what, r.returncode, r.stderr.strip()[:160]))

    # e. the pairs are the owner's: a scratch contract directory, the fixture's role tables beside edited copies of the
    # installed owners' domains, which it holds first
    inst = installed_dir()
    owners = {"lv2": ("lv2", "plugin-db"), "clap": ("omx-param-contract", "omx-clap")}
    for fmt, (domain, owner) in owners.items():
        src = os.path.join(inst, domain, domain + ".json")
        if not os.path.isfile(src):
            check(False, "%s: %s's domain %s is installed under %s" % (fmt, owner, domain, inst))
            continue
        moved = json.load(open(src))
        schemas = moved["components"]["schemas"]
        if fmt == "lv2":
            for w in schemas["LV2_UNIT_IDS"]["oneOf"]:
                if w["const"] == "dB":
                    w["const"] = "dBu"
        else:
            # swapped with dbu, so the mapping stays one to one
            ids = schemas["OMX_PARAM_CONTRACT_UNIT_IDS"]["x-value"]
            ids["db"], ids["dbu"] = ids["dbu"], ids["db"]
        scratch = os.path.join(tmp, "owners-" + fmt)
        shutil.copytree(fixture_dir, scratch)
        os.makedirs(os.path.join(scratch, domain))
        with open(os.path.join(scratch, domain, domain + ".json"), "w") as f:
            json.dump(moved, f)
        r = describe(fmt, contract_dir=scratch)
        before, after = units(good[fmt]), units(r)
        moved_at = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        check(r.returncode == 0 and moved_at and all(before[i] == "dB" and after[i] == "dBu" for i in moved_at)
              and len(before) == len(after),
              "%s: an owner mapping db to dBu moves every dB control to dBu and nothing else (%d controls moved: %s)"
              % (fmt, len(moved_at), r.stderr.strip()[:160]))
        item = "LV2_UNIT_IDS" if fmt == "lv2" else "OMX_PARAM_CONTRACT_UNIT_IDS"
        del schemas[item]
        with open(os.path.join(scratch, domain, domain + ".json"), "w") as f:
            json.dump(moved, f)
        r = describe(fmt, contract_dir=scratch)
        check(r.returncode == 2 and item in r.stderr and not r.stdout,
              "%s: an owner's domain without %s is refused, naming it (%d: %s)" % (fmt, item, r.returncode, r.stderr.strip()[:160]))
    written = format_tables.load("lv2")
    format_tables.rows(written, "lv2")["units:db"]["word"]["values"] = {"units:db": "dB"}
    p = os.path.join(tmp, "values.json")
    with open(p, "w") as f:
        json.dump(written, f)
    r = describe("lv2", p)
    check(r.returncode == 2 and "units:db: unit-id reads the owner's published mapping" in r.stderr,
          "a unit-id row that writes its own values is refused (%d: %s)" % (r.returncode, r.stderr.strip()[:160]))

print("format_domains: %d failure(s)" % fails if fails else "format_domains: held")
sys.exit(1 if fails else 0)
