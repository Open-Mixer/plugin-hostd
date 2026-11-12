# SPDX-License-Identifier: GPL-3.0-or-later
# The CLAP and LV2 descriptors of one plugin shipped in both formats give the same meaning per control: omx-comp
# 0.19.1, the CLAP face's recorded dump (tests/fixtures/fields/clap-comp.tsv, its meanings from its declared panel's
# roles through the contract directory's role table) beside its LV2 face's (tests/fixtures/fields/lv2-comp.tsv, its
# meanings from lv2:designation). Controls pair by symbol: the CLAP control's contract symbol, the LV2 control's id.
#   An LV2 face can state only the meanings LV2's param: vocabulary has a term for, so a difference is allowed only
# where DIFFERENCES names it, with its reason; the list is held exactly: a difference it does not name is red, and so
# is a name it holds that no longer differs, so the list only shrinks (omx-plugins#12 empties it).
#   CONTRACT_DIR is the contract directory read for the role table (default: the fixture, tests/fixtures/contract-dir;
# where omx-plugins is installed, its own: OMX_CONTRACT_PATH or the system one, as plugin-qualify runs it).
#   describe_twin_test.py   PROBE is the runner (default ./plugin-hostd-probe)
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from describe_test import CONTRACT_DIR, describe  # noqa: E402

FIELDS = os.path.join(ROOT, "tests", "fixtures", "fields")
CLAP = ("clap:omx-comp.clap#org.openmixer.comp", os.path.join(FIELDS, "clap-comp.tsv"))
LV2 = ("lv2:urn:openmixer:comp", os.path.join(FIELDS, "lv2-comp.tsv"))
# symbol: (CLAP meaning, LV2 meaning, why they differ)
DIFFERENCES = {
    "kneeDb": ("knee", "unknown", "LV2's param: vocabulary has no knee: the LV2 face cannot state it (omx-plugins#12)"),
    "ratio": ("unknown", "ratio", "the CLAP panel declares no ratio role (omx-plugins#12)"),
    "makeupDb": ("makeup", "unknown", "LV2's param: vocabulary has no makeup: the LV2 face cannot state it (omx-plugins#12)"),
}
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def meanings(target, dump, key):
    r = describe(target, dump, contract_dir=os.environ.get("CONTRACT_DIR", CONTRACT_DIR))
    check(r.returncode == 0, "%s: describe exits 0 (%s)" % (target, r.stderr.strip()[:300]))
    if r.returncode:
        return {}
    return {c[key]: c.get("meaning", "unknown") for c in json.loads(r.stdout)["controls"]
            if not c.get("readonly") and isinstance(c.get(key), str)}


def main():
    clap, lv2 = meanings(*CLAP, "symbol"), meanings(*LV2, "id")
    both = sorted(set(clap) & set(lv2))
    check(len(both) >= 10, "the faces pair by symbol (%d controls: %s)" % (len(both), " ".join(both)))
    seen = {}
    for sym in both:
        if clap[sym] == lv2[sym]:
            check(sym not in DIFFERENCES, "%s: %s on both faces%s" % (sym, clap[sym],
                  "" if sym not in DIFFERENCES else ", and DIFFERENCES still lists it: drop it"))
            continue
        seen[sym] = (clap[sym], lv2[sym])
        listed = DIFFERENCES.get(sym)
        check(listed is not None and listed[:2] == seen[sym], "%s: CLAP %s, LV2 %s%s" % (
            sym, clap[sym], lv2[sym], " (listed: %s)" % listed[2] if listed and listed[:2] == seen[sym]
            else ", a difference DIFFERENCES does not name"))
    for sym in DIFFERENCES:
        check(sym in both, "%s, listed, is a control of both faces" % sym)
    print("describe_twin: %d failure(s)" % failed if failed else "describe_twin: held")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
