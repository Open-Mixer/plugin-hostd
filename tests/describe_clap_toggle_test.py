# SPDX-License-Identifier: GPL-3.0-or-later
# plugin-hostd-probe describe over the recorded field dump of omx-plugins' omx-comp (tests/fixtures/fields/clap-comp.tsv;
# the 0.19.3 release's dump, taken with omx-clap-host 0.32.5, differs from it in versions, fingerprints and the ratio's
# unit only): a CLAP boolean is a toggle (docs/formats.md, "What the tables leave to describe").
#   - a parameter that is stepped, no enumeration, from 0 to 1 is a `toggle` (keyListen, duck: the plugin's own panel
#     draws them as switches, and omx-panel refuses a switch over a travel: Open-Mixer/zynthian-ui#47), its default the
#     parameter's default being non-zero, and no travel;
#   - a stepped parameter from 0 to 1 that CLAP flags no enumeration for is a toggle too (kind, keySource), whatever the
#     plugin's own declaration calls it: a choice reaches CLAP as CLAP_PARAM_IS_ENUM, or not at all;
#   - a stepped parameter over a wider range stays a stepped travel (detectorOversampling 0..2, detectLink 0..3,
#     thresholdDb over its dB range);
#   - the descriptor validates against omx-contract's schema.
# Sabotage: drop the range check of the rule in src/describe.c and detectorOversampling turns a toggle; drop the rule
# and keyListen stays a travel.
#   describe_clap_toggle_test.py   PROBE is the runner (default ./plugin-hostd-probe); the schema as describe_test.py
import json, os, sys
import jsonschema
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from describe_test import check, describe, schema_path  # noqa: E402
import describe_test  # noqa: E402
DUMP = os.path.join(ROOT, "tests", "fixtures", "fields", "clap-comp.tsv")
TARGET = "clap:omx-comp.clap#org.openmixer.comp"
TOGGLES = {14: "keyListen", 17: "duck", 7: "kind", 10: "keySource"}
STEPPED = {8: ("detectorOversampling", 0, 2), 16: ("detectLink", 0, 3)}


def main():
    r = describe(TARGET, dump=DUMP)
    check(r.returncode == 0, "describe over the omx-comp dump exits 0: %s" % r.stderr.strip())
    if r.returncode != 0:
        return 1
    got = json.loads(r.stdout)
    by_id = {c["id"]: c for c in got["controls"]}
    for pid, symbol in TOGGLES.items():
        c = by_id.get(pid, {})
        check(c.get("symbol") == symbol and c.get("kind") == "toggle",
              "%s (stepped, 0 to 1, no enumeration) is a toggle: %s" % (symbol, json.dumps({k: c.get(k) for k in ("symbol", "kind")})))
        check(c.get("default") is False, "%s defaults to false, its default 0: %r" % (symbol, c.get("default")))
        check("travel" not in c, "%s carries no travel" % symbol)
    for pid, (symbol, lo, hi) in STEPPED.items():
        c = by_id.get(pid, {})
        t = c.get("travel", {})
        check(c.get("kind") == "travel" and t.get("scale") == "stepped" and (t.get("min"), t.get("max")) == (lo, hi),
              "%s (stepped, %d to %d) stays a stepped travel: %s" % (symbol, lo, hi, json.dumps({"kind": c.get("kind"), "travel": t})))
    c = by_id.get(0, {})
    t = c.get("travel", {})
    check(c.get("kind") == "travel" and t.get("scale") == "stepped" and t.get("max", 0) - t.get("min", 0) > 1,
          "thresholdDb (stepped over its dB range) stays a travel: %s" % json.dumps(t))
    with open(schema_path()) as f:
        v = jsonschema.Draft202012Validator(json.load(f))
    errors = sorted(v.iter_errors(got), key=lambda e: list(e.path))
    check(not errors, "the descriptor validates against omx-contract's schema%s"
          % "".join("\n     %s: %s" % (list(e.path), e.message) for e in errors[:5]))
    failed = describe_test.failed
    print("describe_clap_toggle: %d failure(s)" % failed if failed else "describe_clap_toggle: held")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
