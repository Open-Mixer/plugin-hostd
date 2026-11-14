#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Every arm of tests/probe_test.py is bounded by its own deadline: an arm that stalls (a wait on a child that never
# answers, a run starved on a loaded runner) fails NAMING the arm and the step it stalled in, and leaves no process
# behind; it never hangs until the job's timeout-minutes. The planted stall (PROBE_TEST_PLANT_STALL) must end as that
# red within the deadline; the sabotage, the deadline turned off (PROBE_ARM_DEADLINE_S=0), must hang again until the
# outer bound here kills it.
set -uo pipefail
cd "$(dirname "$0")/.."
out=$(mktemp); trap 'rm -f "$out"; pkill -f "^sleep 100000$" 2>/dev/null' EXIT
start=$(date +%s)
ONLY=planted_stall PROBE_TEST_PLANT_STALL=1 PROBE_ARM_DEADLINE_S=3 timeout -k 5 30 python3 tests/probe_test.py >"$out" 2>&1
rc=$?; took=$(( $(date +%s) - start ))
[ "$rc" = 1 ] || { echo "FAIL the planted stall did not end as a red within its deadline (rc $rc after ${took}s; 124 = it hung)"; cat "$out"; exit 1; }
grep -q '^FAIL planted_stall: the arm gave no answer within 3 s' "$out" || { echo "FAIL the red does not name the arm and its deadline:"; cat "$out"; exit 1; }
grep -q 'stalled in: probe_test.py:[0-9]* planted_stall' "$out" || { echo "FAIL the red does not name the step the arm stalled in:"; cat "$out"; exit 1; }
if pgrep -f "^sleep 100000$" >/dev/null; then echo "FAIL the stalled arm left its child behind"; exit 1; fi
echo "ok   a stalled probe arm fails within its deadline, naming the arm and the step, and leaves no process behind"
ONLY=planted_stall PROBE_TEST_PLANT_STALL=1 PROBE_ARM_DEADLINE_S=0 timeout -k 2 6 python3 tests/probe_test.py >"$out" 2>&1
rc=$?
[ "$rc" = 124 ] || [ "$rc" = 137 ] || { echo "FAIL the sabotage (no deadline) did not hang: rc $rc"; cat "$out"; exit 1; }
echo "ok   the sabotage: with the deadline off, the planted stall hangs again (rc $rc from the outer bound)"
