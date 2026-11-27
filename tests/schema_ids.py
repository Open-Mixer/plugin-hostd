# SPDX-License-Identifier: GPL-3.0-or-later
# Every committed *.schema.json names its $id under https://openmixer.org/schema/plugin-hostd/ (omx-contract#106): the
# canonical host openmixer.org, no www, no freemixer.org, no raw GitHub URL. Exit 0 when all hold; 1 naming each one
# that does not. It walks the tree rather than asking git, since CI checks out into a container where git refuses the
# tree as another user's (exit 128); it skips the dot directories, the installed contract tree the tests fill, and the
# deb build tree, which hold copies or other packages' files.
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "https://openmixer.org/schema/plugin-hostd/"

SKIP = {os.path.join(ROOT, "tests", "contract-tree"), os.path.join(ROOT, "debian")}
files = []
for top, dirs, names in os.walk(ROOT):
    dirs[:] = sorted(d for d in dirs if not d.startswith(".") and os.path.join(top, d) not in SKIP)
    files += sorted(os.path.relpath(os.path.join(top, n), ROOT) for n in names if n.endswith(".schema.json"))
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
