# SPDX-License-Identifier: GPL-3.0-or-later
# The property ledger is keyed per instance AND symbol (property_set is replace-keyed, omx-clap-core#15): two sets of
# one symbol on one instance keep only the later; two symbols on one instance keep both; one symbol on two instances
# keeps both. Read back as the lines a respawned worker is sent. tests/property_ledger_sabotage.py builds the daemon
# with the key losing the symbol, losing the instance, appending every set and keeping none: each must fail this test.
import os, signal, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Daemon, check, run_tests

EXE = os.path.abspath(os.environ.get("PLUGIN_HOSTD", "./plugin-hostd"))
FAKE = os.path.abspath(os.environ.get("FAKE_HOST", "tests/fake-host"))
TESTS = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


def sent_to(log, pid):
    """the commands one fake worker was sent"""
    if not os.path.exists(log):
        return []
    with open(log, encoding="utf-8") as f:
        return [l.split(" ", 1)[1].rstrip("\n") for l in f if l.startswith("%d " % pid)]


def respawn(d, instances):
    """kill every worker that holds one of instances, once each; the new workers' pids once all are restored"""
    killed = set()
    mark = d.mark()
    for n in instances:
        _, w = d.holder(n)
        if w["pid"] not in killed:
            os.kill(w["pid"], signal.SIGKILL)
            killed.add(w["pid"])
    for n in instances:
        d.wait_event("instance_restored %d " % n, since=mark)
    return {n: d.holder(n)[1]["pid"] for n in instances}


@test
def the_ledger_keeps_the_latest_set_per_instance_and_symbol():
    log = tempfile.mktemp(prefix="plugin-hostd-property-ledger.")
    d = Daemon(EXE, FAKE, env={"FAKE_LOG": log})
    sets = {
        "zero_file_first": 'property_set 0 file "/var/lib/zero-first.wav"',
        "zero_label": 'property_set 0 label "zero"',
        "zero_file": 'property_set 0 file "/var/lib/zero-latest.wav"',
        "one_file": 'property_set 1 file "/var/lib/one.wav"',
        "one_label": 'property_set 1 label "one"',
    }
    try:
        d.expect("add clap:fake#a 0", "resp 0")
        d.expect("add clap:fake#a 1", "resp 1")
        # interleaved across the instances, so a key without the instance would let instance 1 overwrite instance 0
        for k in ("zero_file_first", "zero_label", "one_file", "zero_file", "one_label"):
            d.expect(sets[k], "resp 0")
        pids = respawn(d, [0, 1])
        for n, want in ((0, [sets["zero_file"], sets["zero_label"]]), (1, [sets["one_file"], sets["one_label"]])):
            got = [c for c in sent_to(log, pids[n]) if c.startswith("property_set %d " % n)]
            check(got == want, "instance %d is sent each symbol once, its latest value, in the order first set: %s, "
                  "wanted %s" % (n, got, want))
    finally:
        d.close()
        if os.path.exists(log):
            os.unlink(log)


sys.exit(run_tests(TESTS))
