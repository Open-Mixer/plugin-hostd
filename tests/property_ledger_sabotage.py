# SPDX-License-Identifier: GPL-3.0-or-later
# The sabotage arms of tests/property_ledger_test.py: each builds the daemon with the property ledger keyed wrongly and
# the test must fail. Without this the test could pass by reading nothing.
import os, shlex, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import declared

exe, fake, cc, cflags, objs, libs = sys.argv[1:7]

# the key without the instance: a set drops the same symbol's line from every other instance first, so one line per
# symbol is kept across the daemon
DROP_ELSEWHERE = """    char *kept = strdup(line), **grown;

    for (int o = 0; o < MAX_INSTANCE; o++)
        for (int k = 0; g_inst[o] && g_inst[o] != i && k < g_inst[o]->nkeyed; k++)
        {
            char *had = key_of(g_inst[o]->keyed[k]);

            if (had && !strcmp(had, key))
            {
                free(g_inst[o]->keyed[k]);
                for (int m = k; m + 1 < g_inst[o]->nkeyed; m++)
                    g_inst[o]->keyed[m] = g_inst[o]->keyed[m + 1];
                g_inst[o]->nkeyed--;
                k--;
            }
            free(had);
        }
"""

ARMS = [
    ("the key leaves out the symbol (plain replace: the latest per instance)",
     [("src/supervisor.c", "const int same = had && !strcmp(had, key);", "const int same = 1;")]),
    ("the key leaves out the instance (the latest per symbol across the daemon)",
     [("src/supervisor.c", "    char *kept = strdup(line), **grown;\n", DROP_ELSEWHERE)]),
    ("every set is appended (append: no key)",
     [("src/supervisor.c", "const int same = had && !strcmp(had, key);", "const int same = 0;")]),
    ("no set is kept (the ledger before replace-keyed)",
     [("src/supervisor.c", "if (ledger == PHD_LEDGER_REPLACE_KEYED && count > 2 &&", "if (0 && count > 2 &&")]),
]

failures = 0
for name, edits in ARMS:
    tmp = tempfile.mkdtemp(prefix="plugin-hostd-property-ledger-sabotage.")
    changed = set()
    declared.overlay(tmp)
    for path, old, new in edits:
        target = os.path.join(tmp, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        src = open(target if os.path.exists(target) else path).read()
        assert src.count(old) == 1, "%s does not hold exactly one: %s" % (path, old)
        open(target, "w").write(src.replace(old, new))
        changed.add(path)
    out = os.path.join(tmp, "plugin-hostd")
    own = []
    for c in sorted(changed):
        obj = os.path.join(tmp, os.path.basename(c)[:-2] + ".o")
        subprocess.run([cc, "-I" + os.path.join(tmp, "include"), *shlex.split(cflags), "-Isrc", "-c", "-o", obj,
                        os.path.join(tmp, c)], check=True)
        own.append(obj)
    kept = [o for o in shlex.split(objs) if o[:-2] + ".c" not in changed]
    subprocess.run([cc, *own, *kept, *shlex.split(libs), "-pthread", "-lm", "-o", out], check=True)
    r = subprocess.run([sys.executable, "tests/property_ledger_test.py"],
                       env=dict(os.environ, PLUGIN_HOSTD=out, FAKE_HOST=fake), capture_output=True, text=True)
    if r.returncode == 0:
        print("FAIL %s: tests/property_ledger_test.py passed" % name)
        failures += 1
    else:
        why = [l for l in r.stdout.splitlines() if l.startswith("FAIL ")] or r.stdout.strip().splitlines()[-1:]
        print("ok   %s: tests/property_ledger_test.py fails: %s" % (name, why[0]))
sys.exit(1 if failures else 0)
