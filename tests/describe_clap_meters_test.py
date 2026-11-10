# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd-probe describe over the recorded field dump of omx-plugins' omx-comp (tests/fixtures/fields/clap-comp.tsv:
# the scan of omx-comp 0.19.1 with the records of its clap.meters/1 meters and its org.openmixer.param-contract/1
# entries): the CLAP descriptor carries what its LV2 twin carries.
#   - each meter is read-only controls, one per channel, with the LV2 twin's symbols: a one-channel meter is its name
#     (compGr, compKey), a meter of n channels is <name>_<i> (compIn_0, compIn_1, compOut_0, compOut_1); a gain
#     reduction's unit is dB, a level's dBFS (clap.meters/1's kinds);
#   - each parameter's unit is its contract's (threshold dB, attack and release ms), never unknown;
#   - the descriptor validates against omx-contract's schema.
# Sabotage: drop one meter or contract row of data/formats/clap.json and the describe is refused or a value goes.
#   describe_clap_meters_test.py   PROBE is the runner (default ./plugin-hostd-probe); the schema as describe_test.py
import json, os, subprocess, sys

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from describe_test import describe, schema_path  # noqa: E402

DUMP = os.path.join(ROOT, "tests", "fixtures", "fields", "clap-comp.tsv")
TARGET = "clap:omx-comp.clap#org.openmixer.comp"
METERS = {"compGr": "dB", "compIn_0": "dBFS", "compIn_1": "dBFS", "compOut_0": "dBFS", "compOut_1": "dBFS",
          "compKey": "dBFS"}
UNITS = {"Threshold": "dB", "Attack": "ms", "Release": "ms", "Knee": "dB", "Makeup": "dB"}
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def main():
    r = describe(TARGET, DUMP)
    check(r.returncode == 0, "omx-comp: describe exits 0 (%s)" % r.stderr.strip()[:400])
    if r.returncode:
        return 1
    got = json.loads(r.stdout)
    controls = got.get("controls", [])
    by_symbol = {c.get("symbol"): c for c in controls}
    by_name = {c.get("name"): c for c in controls}
    for sym, unit in METERS.items():
        c = by_symbol.get(sym)
        check(c is not None, "meter %s is a control" % sym)
        if c is None:
            continue
        check(c.get("readonly") is True, "meter %s is read-only" % sym)
        check((c.get("travel") or {}).get("unit") == unit,
              "meter %s has unit %s (got %r)" % (sym, unit, (c.get("travel") or {}).get("unit")))
    for name, unit in UNITS.items():
        c = by_name.get(name) or {}
        check((c.get("travel") or {}).get("unit") == unit,
              "parameter %s has its contract's unit %s (got %r)" % (name, unit, (c.get("travel") or {}).get("unit")))
    check(not any((c.get("travel") or {}).get("unit") == "unknown" for c in controls if not c.get("readonly")),
          "no parameter of a plugin with a contract has unit unknown")
    schema = json.load(open(schema_path()))
    v = jsonschema.validators.validator_for(schema)({"$defs": schema["$defs"], "$ref": "#/$defs/descriptor"})
    errors = sorted(v.iter_errors(got), key=lambda e: list(e.path))
    check(not errors, "the descriptor validates against omx-contract's schema%s"
          % "".join("\n     %s: %s" % (list(e.path), e.message) for e in errors[:5]))
    print("describe_clap_meters: %d failure(s)" % failed if failed else "describe_clap_meters: held")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
