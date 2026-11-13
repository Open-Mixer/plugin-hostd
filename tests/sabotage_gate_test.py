# SPDX-License-Identifier: GPL-3.0-or-later
# Plants a directory of shard-count artifacts as ci.yml's sabotage-gate job downloads them, and checks sabotage_gate
# passes a complete, consistent set and is red on each way the matrix can go wrong: one shard never reports, one
# reports twice (under the other's number), two disagree on the table size, or together they ran fewer arms than the
# table holds -- the last one is the planted sabotage: an arm quietly skipped inside one shard (#23).
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sabotage_gate

failed = 0


def check(ok, what):
    global failed
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failed += 1


def plant(root, rows):
    """rows: {artifact_name: (shard, mine, total)}"""
    shutil.rmtree(root, ignore_errors=True)
    for artifact, (shard, mine, total) in rows.items():
        d = os.path.join(root, artifact)
        os.makedirs(d)
        open(os.path.join(d, "sabotage-shard-count.txt"), "w").write("%d\n%d\n%d\n" % (shard, mine, total))


def red(rows):
    tmp = tempfile.mkdtemp(prefix="sabotage-gate-test.")
    try:
        plant(tmp, rows)
        return sabotage_gate.gate(sabotage_gate.read_counts("sabotage-shard-count.txt", tmp), 4) is not None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


good = {"sabotage-count-%d" % i: (i, 127, 508) for i in range(1, 5)}
check(not red(good), "four shards that together sum to the table pass")

missing = dict(good)
del missing["sabotage-count-4"]
check(red(missing), "a shard that never reported is red")

dup = dict(good)
dup["sabotage-count-4"] = (3, 127, 508)  # shard 4's artifact claims to be shard 3, same as another
check(red(dup), "two shards claiming the same number is red")

disagree = dict(good)
disagree["sabotage-count-2"] = (2, 127, 507)  # a container that saw a different table size
check(red(disagree), "shards that disagree on the table size are red")

skipped = dict(good)
skipped["sabotage-count-2"] = (2, 126, 508)  # the planted sabotage: this shard quietly dropped one arm
check(red(skipped), "shards that together ran fewer arms than the table holds are red")

print("sabotage FAILED (%d)" % failed if failed else "sabotage ok")
sys.exit(1 if failed else 0)
