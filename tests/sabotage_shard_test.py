# SPDX-License-Identifier: GPL-3.0-or-later
# SABOTAGE_SHARD=i/n keeps every n-th arm of tests/sabotage.py, by its position in the SABOTAGE table, so ci.yml's
# matrix of shards runs the whole table between them with nothing run twice (#23). This proves the partition itself,
# not a live run: every index lands in exactly one of the n shards, for every shard count ci.yml might use, and a bad
# SABOTAGE_SHARD is refused rather than silently read as "no sharding".
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sabotage

failed = 0


def check(ok, what):
    global failed
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failed += 1


def with_shard(value, fn):
    before = os.environ.get("SABOTAGE_SHARD")
    if value is None:
        os.environ.pop("SABOTAGE_SHARD", None)
    else:
        os.environ["SABOTAGE_SHARD"] = value
    try:
        return fn()
    finally:
        if before is None:
            os.environ.pop("SABOTAGE_SHARD", None)
        else:
            os.environ["SABOTAGE_SHARD"] = before


UNIVERSE = range(600)  # bigger than len(sabotage.SABOTAGE), so a stray off-by-one at the edges still shows up

for n in (1, 2, 3, 4, 5, 7):
    seen = {}
    for i in range(1, n + 1):
        kept = with_shard("%d/%d" % (i, n), lambda: [index for index in UNIVERSE if sabotage.in_shard(index)])
        for index in kept:
            seen[index] = seen.get(index, 0) + 1
    check(all(seen.get(index) == 1 for index in UNIVERSE), "every index lands in exactly one of %d shards" % n)

check(with_shard(None, lambda: all(sabotage.in_shard(index) for index in UNIVERSE)), "no SABOTAGE_SHARD keeps every index")

for bad in ("0/4", "5/4", "x/4", "2/0", "2", "2/4/8"):
    try:
        with_shard(bad, lambda: sabotage.in_shard(0))
        check(False, "SABOTAGE_SHARD=%s is refused" % bad)
    except SystemExit:
        check(True, "SABOTAGE_SHARD=%s is refused" % bad)

print("sabotage FAILED (%d)" % failed if failed else "sabotage ok")
sys.exit(1 if failed else 0)
