#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The format tables are the domains plugin-hostd/clap and plugin-hostd/lv2 (contract.d/plugin-hostd/<format>/<format>.json),
# the sorting pass row V19:
#   a. each domain is a header ($id, info.x-owner plugin-hostd) over its one item PLUGIN_HOSTD_<F>_MAP, a sheet whose x-value
#      is { format, rows }, the rows byte for byte (their sha256, canonical) those of data/formats/<f>.json at fac7531
#   b. data/formats is gone, and `make install_vocabulary_domains` into a scratch contract directory puts the documents at
#      <contractdir>/plugin-hostd/<f>/<f>.json and nothing under <contractdir>/3/plugin-hostd/formats
#   c. plugin-hostd-probe describe reads the domain document; the old data shape (a formatMap item at the top) and a
#      domain whose sheet lost its x-value are refused, exit 2, naming the missing sheet
# Environment: PROBE, MAKE (make test-format-domains).
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import format_tables

ROOT = format_tables.ROOT
PROBE = os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe"))
GOLDEN = {"clap": (373, "06fcf30bcacd643854b49570cf7f428e14a74a8dbe1403fbb4dfd7cec28e3f8f"),  # data/formats/clap.json at fac7531
          "lv2": (458, "f9a665cc8fc589d3182edf736ae2f1001c70d98538f763944db2a122044de7a5")}
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


for fmt, (count, want) in GOLDEN.items():
    doc = format_tables.load(fmt)
    item = format_tables.sheet(doc, fmt)
    rows = format_tables.rows(doc, fmt)
    check(doc.get("$id") == "https://openmixer.org/contract/plugin-hostd/" + fmt and doc["info"].get("x-owner") == "plugin-hostd",
          "%s: the document is the domain plugin-hostd/%s, owned by plugin-hostd" % (fmt, fmt))
    check(list(doc["components"]["schemas"]) == [format_tables.ITEMS[fmt]] and item.get("x-kind") == "sheet"
          and item["x-value"].get("format") == fmt, "%s: one item %s, a sheet of format %s" % (fmt, format_tables.ITEMS[fmt], fmt))
    check(len(rows) == count and digest(rows) == want, "%s: its %d rows are those of data/formats/%s.json at fac7531 (%d, %s)"
          % (fmt, count, fmt, len(rows), digest(rows)[:12]))
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

    fields = os.path.join(ROOT, "tests", "fixtures", "fields", "clap-controls.tsv")
    target = "clap:controls.clap#org.freemixer.plugin-qualify.fixture.controls"
    contract_dir = os.path.join(ROOT, "tests", "fixtures", "contract-dir")

    def describe(path):
        return subprocess.run([PROBE, "describe", "--table", path, "--contract-dir", contract_dir, "--fields-from", fields, target],
                              capture_output=True, text=True, timeout=60)

    good = describe(format_tables.path("clap"))
    check(good.returncode == 0 and '"controls"' in good.stdout, "describe over the domain document answers (%d: %s)" % (good.returncode, good.stderr.strip()[:200]))
    old = {"PLUGIN_HOSTD_CLAP_MAP": dict(kind="formatMap", format="clap", rows=format_tables.rows(format_tables.load("clap"), "clap"))}
    nov = format_tables.load("clap")
    del format_tables.sheet(nov, "clap")["x-value"]
    for what, doc in (("the old data shape (a formatMap item)", old), ("a sheet with no x-value", nov)):
        p = os.path.join(tmp, "t.json")
        with open(p, "w") as f:
            json.dump(doc, f)
        r = describe(p)
        check(r.returncode == 2 and "holds no sheet item" in r.stderr and not r.stdout, "%s is refused, exit 2 (%d: %s)" % (what, r.returncode, r.stderr.strip()[:160]))

print("format_domains: %d failure(s)" % fails if fails else "format_domains: held")
sys.exit(1 if fails else 0)
