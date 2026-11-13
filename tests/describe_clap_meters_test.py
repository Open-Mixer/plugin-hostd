# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd-probe describe over the recorded field dump of omx-plugins' omx-comp (tests/fixtures/fields/clap-comp.tsv:
# the scan of omx-comp 0.19.1 with the records of its clap.meters/1 meters and its org.openmixer.param-contract/1
# entries): the descriptor carries the meters and the contract as omx-contract's docs/descriptors.md words them.
#   - each meter is one item of meters[]: its id, its symbol (the meter's name made an output symbol, omx-clap-core's
#     doc/reference.md rule), its kind, channels and display range, unit dB for a gain reduction and dBFS for a level;
#     no meter is a control, and no meter's channel symbol (<symbol>_<i> for more than one) answers to a control's;
#   - each parameter with a contract entry has the entry's symbol, its unit (a contract unit `none` is the plugin
#     stating none: unknown), its scale, and its step when the step is not 0;
#   - the contract's version and fingerprint and a meter's flags are carried in the extensions;
#   - a meter whose symbol a parameter answers to, two meters of one symbol, and a meter that answers to another's
#     channel symbol are refused, naming the symbol;
#   - the descriptor validates against omx-contract's schema.
# Sabotage: drop one meter or contract row of data/formats/clap.json and the describe is refused or a value goes.
#   describe_clap_meters_test.py   PROBE is the runner (default ./plugin-hostd-probe); the schema as describe_test.py
import json, os, sys, tempfile

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from describe_test import describe, schema_path  # noqa: E402

DUMP = os.path.join(ROOT, "tests", "fixtures", "fields", "clap-comp.tsv")
TARGET = "clap:omx-comp.clap#org.openmixer.comp"
METERS = [
    {"id": 0, "symbol": "compGr", "kind": "gain-reduction", "channels": 1, "unit": "dB", "min": -60, "max": 0},
    {"id": 1, "symbol": "compIn", "kind": "level", "channels": 2, "unit": "dBFS", "min": -60, "max": 6},
    {"id": 2, "symbol": "compOut", "kind": "level", "channels": 2, "unit": "dBFS", "min": -60, "max": 6},
    {"id": 3, "symbol": "compKey", "kind": "level", "channels": 1, "unit": "dBFS", "min": -60, "max": 0},
]
CONTRACT_UNIT = {"db": "dB", "ms": "ms", "hz": "Hz", "pc": "%", "none": "unknown"}
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def entries():
    """the contract entry of each param scope of the dump: {param id: {field: value}}"""
    ids, out = {}, {}
    for line in open(DUMP):
        p = line.rstrip("\n").split("\t")
        if len(p) != 3 or not p[0].startswith("param:"):
            continue
        if p[1] == "clap_param_info.id":
            ids[p[0]] = int(p[2])
        elif p[1].startswith("omx_clap_param_contract_entry."):
            out.setdefault(p[0], {})[p[1].split(".", 1)[1]] = p[2]
    return {ids[s]: e for s, e in out.items()}


def refused(old, new, symbol):
    """the dump with one meter's name changed: describe exits 2, writes nothing and names the symbol"""
    text = open(DUMP).read()
    assert ("clap_meter_info.name\t%s\n" % old) in text
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
        f.write(text.replace("clap_meter_info.name\t%s\n" % old, "clap_meter_info.name\t%s\n" % new))
    try:
        r = describe(TARGET, f.name)
    finally:
        os.unlink(f.name)
    check(r.returncode == 2 and not r.stdout and symbol in r.stderr,
          "a meter named %r is refused naming %s (exit %d: %s)" % (new, symbol, r.returncode, r.stderr.strip()[:300]))


def main():
    r = describe(TARGET, DUMP)
    check(r.returncode == 0, "omx-comp: describe exits 0 (%s)" % r.stderr.strip()[:400])
    if r.returncode:
        return 1
    got = json.loads(r.stdout)
    controls = got.get("controls", [])
    meters = got.get("meters", [])
    for want in METERS:
        m = next((m for m in meters if m.get("id") == want["id"]), None)
        check(m is not None, "meter %d (%s) is in meters[]" % (want["id"], want["symbol"]))
        if m is None:
            continue
        for k, v in want.items():
            check(m.get(k) == v, "meter %s: %s is %r (got %r)" % (want["symbol"], k, v, m.get(k)))
        check(m.get("scale") == "unknown", "meter %s: scale unknown, clap.meters/1 states none (got %r)"
              % (want["symbol"], m.get("scale")))
    check([m.get("id") for m in meters] == [m["id"] for m in METERS], "meters[] is the plugin's meters in its order")
    outputs = {m["symbol"] if m["channels"] == 1 else "%s_%d" % (m["symbol"], i)
               for m in METERS for i in range(m["channels"])}
    check(not any(c.get("symbol") in outputs or c.get("id") in outputs or c.get("readonly") for c in controls),
          "no meter is a control, and no control answers to a meter's symbol")
    by_id = {c.get("id"): c for c in controls}
    contract = entries()
    check(len(contract) == len(controls), "every parameter has a contract entry (%d of %d)" % (len(contract), len(controls)))
    for pid, e in sorted(contract.items()):
        c = by_id.get(pid) or {}
        travel = c.get("travel")
        check(c.get("symbol") == e["symbol"], "parameter %d: symbol %s (got %r)" % (pid, e["symbol"], c.get("symbol")))
        if travel is None:
            continue
        unit = CONTRACT_UNIT[e["unit"]]
        check(travel.get("unit") == unit, "%s: the contract's unit %s is %r (got %r)"
              % (e["symbol"], e["unit"], unit, travel.get("unit")))
        check(travel.get("scale") == e["scale"], "%s: the contract's scale %s (got %r)"
              % (e["symbol"], e["scale"], travel.get("scale")))
        step = float(e["step"])
        check(travel.get("step") == (step if step else None), "%s: step %s (got %r)"
              % (e["symbol"], e["step"] if step else "absent, 0 is continuous", travel.get("step")))
    ext = (got.get("extensions") or {}).get("clap") or {}
    check(ext.get("omx_clap_plugin_param_contract_ext.version") == "1"
          and len(ext.get("omx_clap_plugin_param_contract_ext.fingerprint", "")) == 64,
          "the contract's version and fingerprint are in the extensions")
    check(ext.get("meter:0/clap_meter_info.flags") == "CLAP_METER_IS_COHERENT", "a meter's flags are in the extensions")
    schema = json.load(open(schema_path()))
    v = jsonschema.validators.validator_for(schema)({"$defs": schema["$defs"], "$ref": "#/$defs/descriptor"})
    errors = sorted(v.iter_errors(got), key=lambda e: list(e.path))
    check(not errors, "the descriptor validates against omx-contract's schema%s"
          % "".join("\n     %s: %s" % (list(e.path), e.message) for e in errors[:5]))
    refused("compKey", "thresholdDb", "thresholdDb")  # a parameter answers to it
    refused("compKey", "compGr", "compGr")  # two meters, one symbol
    refused("compKey", "compIn 1", "compIn_1")  # derived, it answers to compIn's second channel
    print("describe_clap_meters: %d failure(s)" % failed if failed else "describe_clap_meters: held")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
