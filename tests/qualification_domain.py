# SPDX-License-Identifier: GPL-3.0-or-later
# The qualification words are plugin-qualify's domain (contract.d/qualification/qualification.json there, its items
# QUALIFICATION_*): plugin-hostd ships no document of it and no render of it, and the probe reads it at start-up through
# the C loader (omx_domain_open, floor 1.1.0). Held here:
#   1. no qualification_vocabulary.h exists, is named by a source, a build rule, a package or a workflow;
#   2. this package ships no qualification document of its own;
#   3. the words the probe writes are the domain's: a scratch copy of the domain with three words renamed, the probe pointed
#      at it (--contract-dir, the probe's test entry), writes the renamed words;
#   4. a domain that is absent, below the floor, or without a word the probe writes ends the run with the loader's code and
#      the domain's name (or the word and the item), and no document.
#   PROBE=<runner> PROBE_CHILD=<tests/probe-child> STRESS_CLAP=<tests/stress.clap> qualification_domain.py
import json, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qualification_source as qs
from tree_files import tracked as tree_tracked

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.abspath(os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe")))
CHILD = os.path.abspath(os.environ.get("PROBE_CHILD", os.path.join(ROOT, "tests", "probe-child")))
CLAP = os.path.abspath(os.environ.get("STRESS_CLAP", os.path.join(ROOT, "tests", "stress.clap")))
ID = "org.plugin-hostd.test.stress"
FLOOR = "1.1.0"
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def run_probe(contract_dir, tmp):
    out = os.path.join(tmp, "probe.json")
    if os.path.exists(out):
        os.unlink(out)
    cmd = [PROBE, "run", "--child", CHILD, "--rates", "48000", "--quantum", "256", "--wall-s", "10", "--grace-ms", "200",
           "--out", out, CLAP, ID]
    # the test entry: OMX_CONTRACT_PATH, a ':' list whose first directory holding the domain wins; this checkout's
    # contract.d holds the machine domain the probe reads too
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, OMX_CONTRACT_PATH=os.path.join(ROOT, "contract.d") + ":" + contract_dir))
    return p, (json.load(open(out)) if os.path.exists(out) else None)


def main():
    files = tree_tracked(ROOT)
    # 1. no render of the domain
    check(not any(os.path.basename(f) == "qualification_vocabulary.h" for f in files),
          "no qualification_vocabulary.h is tracked")
    named = []
    for f in files:
        # a changelog records what was, and says so
        if f in ("tests/qualification_domain.py", "debian/changelog") or not os.path.isfile(os.path.join(ROOT, f)):
            continue
        try:
            text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        if f.endswith(".spec"):
            text = text.split("%changelog")[0]
        named += ["%s:%d" % (f, n) for n, line in enumerate(text.splitlines(), 1) if "qualification_vocabulary" in line]
    check(not named, "nothing names qualification_vocabulary: %s" % named[:6])
    # 2. no document of its own
    check(not os.path.exists(os.path.join(ROOT, "contract.d", "qualification")), "no contract.d/qualification here: the domain is plugin-qualify's")
    check(not any(f.startswith("contract.d/qualification") for f in files), "no qualification document is tracked")

    tmp = tempfile.mkdtemp(prefix="plugin-hostd-qualification.")
    try:
        # 3. the probe's words are the domain's
        words = {"QUALIFICATION_RESOURCE_THREAD_SCHEDULING": {"fifo": "fifo-x", "none": "none-x"},
                 "QUALIFICATION_MEASUREMENT_LATENCY_METHODS": {"impulse-onset": "impulse-x"}}

        def rename(doc):
            for item, pairs in words.items():
                for old, new in pairs.items():
                    qs.rename_word(item, old, new)(doc)
        scratch = qs.fixture(tmp, rename, "renamed")
        p, doc = run_probe(qs.fixture(tmp, None, "as-installed"), tmp)
        check(p.returncode == 0 and doc is not None, "positive control: the probe runs over the domain as installed: rc %d %s" % (p.returncode, p.stderr[-200:]))
        if doc:
            check(doc["run"]["realtime"]["class"] in ("fifo", "none") and doc["grid"][0]["latency"]["method"] == "impulse-onset",
                  "positive control: the installed domain's words are written: %s %s" % (doc["run"]["realtime"]["class"], doc["grid"][0]["latency"]["method"]))
        p, doc = run_probe(scratch, tmp)
        check(p.returncode == 0 and doc is not None, "the probe runs over the renamed domain: rc %d %s" % (p.returncode, p.stderr[-200:]))
        if doc:
            check(doc["run"]["realtime"]["class"] in ("fifo-x", "none-x"), "run.realtime.class is the domain's word: %s" % doc["run"]["realtime"]["class"])
            check(doc["grid"][0]["latency"]["method"] == "impulse-x", "latency.method is the domain's word: %s" % doc["grid"][0]["latency"]["method"])
            check(doc["offer"]["realtime"] in ("fifo-x", "none-x"), "offer.realtime is the domain's word: %s" % doc["offer"]["realtime"])
        # 4. an absent or too old domain is refused, by name
        p, doc = run_probe(os.path.join(tmp, "nowhere"), tmp)
        check(p.returncode == 78 and doc is None and "contract.dir.absent" in p.stderr and "qualification" in p.stderr,
              "an absent domain ends the run with the loader's code and the domain's name: rc %d %r" % (p.returncode, p.stderr[-200:]))

        # the first directory holding the domain wins, a directory without it is skipped, and when none holds it the refusal
        # names the domain and every directory tried
        a, b = os.path.join(tmp, "none-a"), os.path.join(tmp, "none-b")
        p, doc = run_probe(a + ":" + b, tmp)
        check(p.returncode == 78 and doc is None and "qualification" in p.stderr and a in p.stderr and b in p.stderr,
              "no directory holds the domain: exit 78 naming the domain and both directories: rc %d %r" % (p.returncode, p.stderr[-300:]))
        p, doc = run_probe(a + ":" + scratch, tmp)
        check(p.returncode == 0 and doc is not None and doc["run"]["realtime"]["class"] in ("fifo-x", "none-x"),
              "a directory without the domain is skipped, the next that holds it is read: rc %d" % p.returncode)

        def old(doc):
            doc["info"]["version"] = "1.0.0"
        def lacking(doc):
            item = doc["components"]["schemas"]["QUALIFICATION_MEASUREMENT_LATENCY_METHODS"]
            item["oneOf"] = [w for w in item["oneOf"] if w["title"] != "noteOnset"]
        p, doc = run_probe(qs.fixture(tmp, lacking, "lacking"), tmp)
        check(p.returncode == 78 and doc is None and "noteOnset" in p.stderr and "QUALIFICATION_MEASUREMENT_LATENCY_METHODS" in p.stderr,
              "a domain without a word the probe writes is refused by the word and the item: rc %d %r" % (p.returncode, p.stderr[-200:]))
        p, doc = run_probe(qs.fixture(tmp, old, "old"), tmp)
        check(p.returncode == 78 and doc is None and "contract.package.too-old" in p.stderr and FLOOR in p.stderr,
              "a domain below %s is refused with the loader's code and the floor: rc %d %r" % (FLOOR, p.returncode, p.stderr[-200:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("qualification domain: %s" % ("FAILED (%d)" % failed if failed else "ok"))
    return 1 if failed else 0


sys.exit(main())
