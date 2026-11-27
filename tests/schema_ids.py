# SPDX-License-Identifier: GPL-3.0-or-later
# Every committed *.schema.json names its $id under https://openmixer.org/schema/plugin-hostd/ (omx-contract#106): the
# canonical host openmixer.org, no www, no freemixer.org, no raw GitHub URL. Exit 0 when all hold; 1 naming each one
# that does not.
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "https://openmixer.org/schema/plugin-hostd/"

files = subprocess.run(["git", "-C", ROOT, "ls-files", "*.schema.json"], check=True, capture_output=True,
                       text=True).stdout.split()
if not files:
    print("schema_ids: no *.schema.json found", file=sys.stderr)
    sys.exit(1)
bad = []
for f in files:
    with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
        doc = json.load(fh)
    sid = doc.get("$id", "")
    if not sid.startswith(PREFIX):
        bad.append(f"{f}: $id {sid or '(none)'} is not under {PREFIX}")
for b in bad:
    print(b, file=sys.stderr)
if bad:
    sys.exit(1)
print(f"schema_ids: {len(files)} schemas name their $id under {PREFIX}")
