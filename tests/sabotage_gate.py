# SPDX-License-Identifier: GPL-3.0-or-later
# ci.yml's sabotage job shards tests/sabotage.py into a SABOTAGE_SHARD=i/4 matrix; each shard writes its own number,
# how many arms it selected, and how many the unsharded table holds in the same container, to a
# sabotage-count-<i>/sabotage-shard-count.txt artifact. The sabotage-gate job downloads every such artifact under one
# directory and runs this: red when a shard never reported, reported twice, disagrees with the others on the table
# size, or the shards together ran fewer arms than the table holds (#23).
import os
import sys


def read_counts(name, shards_dir):
    """every (shard, mine, total) found in shards_dir/*/<name>"""
    out = []
    for entry in sorted(os.listdir(shards_dir)):
        path = os.path.join(shards_dir, entry, name)
        if not os.path.isfile(path):
            continue
        words = open(path).read().split()
        if len(words) != 3 or not all(w.lstrip("-").isdigit() for w in words):
            raise SystemExit("%s: want three numbers (shard, mine, total), found %r" % (path, words))
        out.append(tuple(int(w) for w in words))
    return out


def gate(counts, n):
    """None when the n shards together ran every arm exactly once, else the line that says why not"""
    seen = {}
    for shard, mine, total in counts:
        if shard in seen:
            return "shard %d reported twice" % shard
        seen[shard] = (mine, total)
    if sorted(seen) != list(range(1, n + 1)):
        return "shards seen %s, wanted 1..%d" % (sorted(seen), n)
    totals = {total for _mine, total in seen.values()}
    if len(totals) != 1:
        return "the shards disagree on the table size: %s" % sorted(totals)
    total = totals.pop()
    ran = sum(mine for mine, _total in seen.values())
    if ran != total:
        return "the %d shards ran %d of %d arms" % (n, ran, total)
    return None


def main(argv):
    if len(argv) != 3:
        print("usage: sabotage_gate.py <counts-dir> <n>")
        return 2
    shards_dir, n = argv[1], int(argv[2])
    why = gate(read_counts("sabotage-shard-count.txt", shards_dir), n)
    if why:
        print("FAIL %s" % why)
        return 1
    print("ok   the %d shards ran every arm exactly once" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
