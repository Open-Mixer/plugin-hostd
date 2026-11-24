#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""Build a qualification store fixture from plugin-qualification-db's schema/qualification.sql.

Usage: qual_fixture.py <schema.sql> <out.sqlite> [options] [cell ...]

The schema is the library's installed DDL (pkg-config --variable=schema plugin-qualification-db), else PQDB_SCHEMA, else the
checkout's schema/qualification.sql (the Makefile takes it in that order); its fractional reason params and adapter params
tables are the correction of plugin-db-qualification 1d8b2e2f2, which a cell needs none of: they take no placeholder row.

  --user-version N   PRAGMA user_version (default 1; 0 is a file that is no store)
  --bad-word         a record whose mc_arch is in no item of the machine domain, with the word check of it recorded
  cell               sha256,uri,rate,quantum,median,p95,declared,measured,firstkb,perkb  ("-" is NULL)

A cell is one grid point of one plugin binary (its sha256 is a hex digit or digits repeated to 64 characters) on one host class; its record
is made once per sha256 and uri. Every column the schema needs and a cell does not name takes a plain placeholder.
"""
import os
import sqlite3
import subprocess
import sys

PLACEHOLDER = {"TEXT": "x", "INTEGER": 0, "REAL": 0.0}


def schema_path():
    """The DDL of the store: the installed one (pkg-config --variable=schema plugin-qualification-db), else PQDB_SCHEMA."""
    try:
        path = subprocess.run(["pkg-config", "--variable=schema", "plugin-qualification-db"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        path = ""
    return path if path and os.path.exists(path) else os.environ["PQDB_SCHEMA"]


def sha(letter):
    """The 64-hex sha256 a plugin binary of this letter (or hex digits) has: it repeated up to 64 characters."""
    return (letter * 64)[:64]


def fill(db, table, given):
    """Insert a row of table: the given columns, and a placeholder for every NOT NULL column without a default."""
    row = dict(given)
    for _cid, name, kind, notnull, default, _pk in db.execute(f"PRAGMA table_info({table})"):
        if name not in row and notnull and default is None:
            row[name] = PLACEHOLDER[kind]
    cols = ",".join(row)
    cur = db.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    return cur.lastrowid


def num(text):
    """A cell figure: "-" is NULL; a number stands for itself, a string is read."""
    text = str(text)
    return None if text == "-" else float(text) if "." in text else int(text)


def build(schema, out, cells, user_version=1, bad_word=False):
    """Write the store fixture out from the DDL of schema; cells are sequences of the ten cell fields (strings)."""
    db = sqlite3.connect(out)
    with open(schema, encoding="utf-8") as f:
        db.executescript(f.read())
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("INSERT INTO store_info (one, user_layer, record_schema, built_from) VALUES (1, 0, ?, ?)",
               ("plugin-qualify.qualification-record/1", "0" * 40))
    if bad_word:
        db.execute("INSERT INTO store_domain (domain, version) VALUES ('machine', '1.1.0')")
        db.execute("INSERT INTO word_check (tbl, col, domain, item) VALUES ('record', 'mc_arch', 'machine', 'MACHINE_ARCHES')")
    set_id = fill(db, "record_set", {"host_class": "x86-64", "name": "fixture", "tier": "reference"})
    plugins, records, ords = {}, {}, {}
    for letter, uri, rate, quantum, median, p95, declared, measured, first, per in cells:
        key = (letter, uri)
        if key not in plugins:
            plugins[key] = fill(db, "plugin", {"sha256": sha(letter), "format": "clap", "uri": uri})
            given = {"plugin_id": plugins[key], "set_id": set_id, "host_class": "x86-64", "offer": "default",
                     "name": uri + "@1", "probe_sha256": sha("0")}
            if bad_word:
                given["mc_arch"] = "not-an-arch"
            records[key] = fill(db, "record", given)
            ords[key] = 0
        rid = records[key]
        fill(db, "cell", {"record_id": rid, "ord": ords[key], "rate": int(rate), "quantum": int(quantum),
                          "outcome": "probe.ok", "cost_median": num(median), "cost_percentile_p": 95,
                          "cost_percentile_value": num(p95), "latency_declared_frames": num(declared),
                          "latency_measured_frames": num(measured), "mem_first_instance_kb": num(first),
                          "mem_per_instance_kb": num(per)})
        ords[key] += 1
        fill(db, "claim", {"record_id": rid, "plugin_id": plugins[key], "offer": "default", "host_class": "x86-64",
                           "rate": int(rate), "quantum": int(quantum)})
    db.commit()
    db.execute(f"PRAGMA user_version = {user_version}")
    db.commit()
    db.close()


def main(argv):
    """Build the fixture the arguments name."""
    schema, out, rest = argv[1], argv[2], argv[3:]
    version, bad_word, cells = 1, False, []
    while rest:
        arg = rest.pop(0)
        if arg == "--user-version":
            version = int(rest.pop(0))
        elif arg == "--bad-word":
            bad_word = True
        else:
            cells.append(arg.split(","))
    build(schema, out, cells, version, bad_word)


if __name__ == "__main__":
    main(sys.argv)
