# SPDX-License-Identifier: GPL-3.0-or-later
# A timing proof reads the load (ruling 2026-11-11). On a node whose 1-minute load average is above the cores this
# process may use, a timing proof that misses its bound WARNS, naming the load, and the gate reruns it on a quiet node;
# on a quiet node the miss stays a failure. Anything else a timing proof checks fails on any node. The load is faked with
# HOSTD_TEST_LOADAVG. The closing wave's fc44 box, at a load of about 67, failed two of daemon_test.py's timing proofs
# (a worker respawned in 11.61 s, an event waited for past its bound): those now read the load.
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness

# a suite of three, run by harness.run_tests in a child with a chosen load
SUITE = r'''
import os, sys
sys.path.insert(0, %(here)r)
from harness import check, check_timing, run_tests, wait_for
def a_bound_missed():
    check_timing(False, "the worker respawned in 11.61 s")
def a_wait_past_its_bound():
    wait_for(lambda: None, "event 'instance_quarantined 100 '", timeout=0.05, timing=True)
def a_wrong_answer():
    check(False, "resp -3, not resp 0")
names = os.environ["SUITE"].split(",")
sys.exit(run_tests([(n, globals()[n]) for n in names]))
'''


def run(load, names):
    env = dict(os.environ, SUITE=",".join(names))
    if load is None:
        env.pop("HOSTD_TEST_LOADAVG", None)
    else:
        env["HOSTD_TEST_LOADAVG"] = str(load)
    r = subprocess.run([sys.executable, "-c", SUITE % {"here": HERE}], env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


failed = 0


def expect(cond, what, out=""):
    global failed
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        failed += 1
        print("     " + out.replace("\n", "\n     "), flush=True)


cores = len(os.sched_getaffinity(0))
LOADED, QUIET = cores * 4 + 3.5, 0.0

expect(hasattr(harness, "node_load") and hasattr(harness, "check_timing"), "the harness reads the load and has timing checks")

rc, out = run(LOADED, ["a_bound_missed", "a_wait_past_its_bound"])
expect(rc == 0, "on a loaded node a missed bound and a wait past its bound do not fail the run", out)
expect(re.search(r"^WARN a_bound_missed: the worker respawned in 11\.61 s \(loaded node: 1-min load %.2f on %d cores\)" % (LOADED, cores), out, re.M),
       "the warning names the miss and the load", out)
expect(re.search(r"^TIMING-WARN a_bound_missed$", out, re.M) and re.search(r"^TIMING-WARN a_wait_past_its_bound$", out, re.M),
       "each warned proof is named for the gate to rerun on a quiet node", out)
expect("2 timing warnings on a loaded node" in out, "the summary counts the warnings", out)

rc, out = run(QUIET, ["a_bound_missed", "a_wait_past_its_bound"])
expect(rc == 1, "on a quiet node the same misses fail the run", out)
expect(re.search(r"^FAIL a_bound_missed: the worker respawned in 11\.61 s \(quiet node: 1-min load 0\.00 on %d cores\)" % cores, out, re.M),
       "the failure names the miss and the load", out)
expect(re.search(r"^FAIL a_wait_past_its_bound: timed out waiting for event", out, re.M), "a wait past its bound fails too", out)

rc, out = run(LOADED, ["a_wrong_answer"])
expect(rc == 1 and re.search(r"^FAIL a_wrong_answer: resp -3", out, re.M), "a wrong answer fails on a loaded node: only a timing proof reads the load", out)

rc, out = run(None, ["a_bound_missed"])
expect(re.search(r"\((loaded|quiet) node: 1-min load [0-9]+\.[0-9]{2} on %d cores\)" % cores, out),
       "with no fake the load is the node's own (/proc/loadavg)", out)

# the proofs the closing wave's fc44 box failed read the load
src = open(os.path.join(HERE, "daemon_test.py")).read()
def body(name):
    m = re.search(r"^def %s\(\):\n(.*?)(?=^@test|^def |\Z)" % name, src, re.M | re.S)
    return m.group(1) if m else ""
respawn = body("while_a_promised_write_waits_the_daemon_still_supervises_and_reports_at_once")
expect("check_timing(took < 1.0" in respawn and "timing=True" in respawn,
       "the respawn proof's bound and its waits are timing checks", respawn[:0])
abi = body("every_member_that_says_abi_clobber_is_isolated_however_many_say_it_at_once")
expect(abi.count("timing=True") >= 2, "the abi_clobber proof's bounded waits are timing waits")

print("timing-load test %s (%d failed)" % ("FAILED" if failed else "ok", failed))
sys.exit(1 if failed else 0)
