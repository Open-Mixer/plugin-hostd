#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/probe_domain.py: plugin-hostd owns the domain `probe` (contract.d/probe/probe.json): the words a probe run writes,
that the qualification store checks its record columns against. Arms 1 to 6.

1. the document conforms: omx-contract validate and fmt --check, $schema, $id, info.x-owner/x-stability, version 1.0.0, every
   item PROBE_-prefixed, every item's x-since the domain's first version (1.0.0), x-codes 0..n-1 in order;
2. the items hold exactly the words the probe can emit: PROBE_REASONS, PROBE_OUTCOMES and PROBE_STEPS the codes of the
   protocol's PHD_PROBE_REASONS, PHD_PROBE_OUTCOMES and PHD_PROBE_STEPS lists, PROBE_SIGNALS the signals src/probe_words.c
   names, plus the one word the probe writes for a signal it has no name for;
3. the probe writes the domain's words: over a scratch copy with every word renamed, a run (as it is, a --reason, and one
   that crashes) writes only renamed words at run.reason, run.outcome, steps[].step, steps[].outcome, steps[].signal and
   crash.signal, and the generated schema's enumerations are the renamed words;
4. a probe domain that is absent, invalid, too old (below 1.0.0) or without an item is refused by name at start-up: the probe
   exits 78 with the loader's code and the domain's name, the generator exits 1 the same way; an item short of a word is
   refused by item;
5. (moved: the package that ships the domain is plugin-hostd-protocol-contract; its own test installs it);
6. no word of the four items is a C literal of src/probe.c: the words are the domain's.

7. the call-level read (probe_signal_word, sorting pass V8): the word of each of the thirteen signals the probe names, the
   word for any other and the number of signal words one handle holds are the golden ones frozen from the hand copy of
   src/probe_words.h; the codes the call indexes by are the domain's own header (include/plugin-hostd/probe_codes.h, one
   source: no hand-written signal list in src/probe_words.h); and a temporary domain with a signal word renamed gives
   the renamed word at the call, with two signal codes swapped it is refused by item.

Environment: OMX_CONTRACT, INSTALL_CONTRACT_DIR, DOMAIN_CFLAGS, DOMAIN_LIBS, CC, PROTOCOL_HEADER (protocol.h of
plugin-hostd-protocol), PROBE, PROBE_CHILD, STRESS_CLAP, GEN. Exit 0 all green, 1 a FAIL line.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qualification_source  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the domain is plugin-hostd-protocol's, read where its contract package installs it (PROTOCOL_CONTRACT_DIR for a checkout's)
SOURCE = os.environ.get("PROTOCOL_CONTRACT_DIR") or subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"],
                                                                     capture_output=True, text=True).stdout.strip() or "/usr/share/omx-contract/contract.d"
DOC = os.path.join(SOURCE, "probe", "probe.json")
OMX = shlex.split(os.environ.get("OMX_CONTRACT", "omx-contract"))
PROBE = os.path.abspath(os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe")))
CHILD = os.path.abspath(os.environ.get("PROBE_CHILD", os.path.join(ROOT, "tests", "probe-child")))
CLAP = os.path.abspath(os.environ.get("STRESS_CLAP", os.path.join(ROOT, "tests", "stress.clap")))
GEN = os.path.abspath(os.environ.get("GEN", os.path.join(ROOT, "tools", "protocol-gen")))
HEADER = os.environ.get("PROTOCOL_HEADER", "/usr/include/plugin-hostd-protocol/plugin-hostd/protocol.h")
ITEMS = ("PROBE_REASONS", "PROBE_OUTCOMES", "PROBE_STEPS", "PROBE_SIGNALS")
LISTS = {"PROBE_REASONS": "PHD_PROBE_REASONS", "PROBE_OUTCOMES": "PHD_PROBE_OUTCOMES", "PROBE_STEPS": "PHD_PROBE_STEPS"}
UNKNOWN_SIGNAL = "SIGNAL"
failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL " + msg)


def ok(msg):
    print("ok   " + msg)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def load():
    try:
        with open(DOC) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        fail("arm 1: %s is not readable: %s" % (DOC, e))
        return None


def words(doc, item):
    return [w["const"] for w in sorted(doc["components"]["schemas"][item]["oneOf"], key=lambda w: w["x-code"])]


def arm1(doc):
    if doc is None:
        return
    before = len(failures)
    if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("arm 1: $schema is %r" % doc.get("$schema"))
    if doc.get("$id") != "https://openmixer.org/contract/probe":
        fail("arm 1: $id is %r, not https://openmixer.org/contract/probe" % doc.get("$id"))
    info = doc.get("info", {})
    if info.get("x-owner") != "plugin-hostd-protocol":
        fail("arm 1: info.x-owner is %r" % info.get("x-owner"))
    if info.get("x-stability") != "experimental":
        fail("arm 1: info.x-stability is %r" % info.get("x-stability"))
    if info.get("version") != "1.0.0":
        fail("arm 1: info.version is %r, the first version is 1.0.0" % info.get("version"))
    schemas = doc.get("components", {}).get("schemas", {})
    if sorted(schemas) != sorted(ITEMS):
        fail("arm 1: the items are %s, not %s" % (sorted(schemas), sorted(ITEMS)))
    for name, item in schemas.items():
        if not name.startswith("PROBE_"):
            fail("arm 1: item %s does not start with PROBE_" % name)
        if item.get("x-since") != "1.0.0":
            fail("arm 1: item %s x-since is %r, the domain's first version 1.0.0" % (name, item.get("x-since")))
        codes = [w.get("x-code") for w in item.get("oneOf", [])]
        if codes != list(range(len(codes))):
            fail("arm 1: item %s x-codes are %s, not 0..n-1 in order" % (name, codes))
    if len(failures) == before:
        ok("arm 1: the document conforms")


def header_words(list_name):
    text = open(HEADER).read()
    m = re.search(r"#define %s\(X\)((?:[^\n]*\\\n)*[^\n]*)" % list_name, text)
    if m is None:
        fail("arm 2: %s is not in %s" % (list_name, HEADER))
        return []
    return re.findall(r'X\(\w+,\s*"([^"]+)"', m.group(1))


def probe_signals():
    text = open(os.path.join(ROOT, "src", "probe_words.c")).read()
    sig = re.findall(r"PROBE_SIGNAL_CASE\((SIG[A-Z0-9]+)\)", text)
    if not sig:
        fail("arm 2: probe_signal_word names no signal in src/probe_words.c")
        return []
    return sig + [UNKNOWN_SIGNAL]


def arm2(doc):
    if doc is None:
        return
    before = len(failures)
    for item, lst in LISTS.items():
        want = header_words(lst)
        if not want or words(doc, item) != want:
            fail("arm 2: %s holds %s, the probe's %s is %s" % (item, words(doc, item), lst, want))
    sig = probe_signals()
    if not sig or words(doc, "PROBE_SIGNALS") != sig:
        fail("arm 2: PROBE_SIGNALS holds %s, the probe names %s" % (words(doc, "PROBE_SIGNALS"), sig))
    # the signals the probe names are the cases of its one name table, nothing else names a signal
    src = open(os.path.join(ROOT, "src", "probe.c")).read()
    for name in re.findall(r'"(SIG[A-Z0-9]+)"', src):
        fail("arm 2: src/probe.c holds the signal name %s as a literal" % name)
    if len(failures) == before:
        ok("arm 2: the items hold exactly the words the probe can emit (%s)" %
           ", ".join("%s %d" % (i, len(words(doc, i))) for i in ITEMS))


def fixture(root, name, edit=None, text=None):
    out = os.path.join(root, name)
    shutil.copytree(os.path.join(SOURCE, "probe"), os.path.join(out, "probe"))
    with open(DOC) as f:
        doc = json.load(f)
    if edit:
        edit(doc)
    with open(os.path.join(out, "probe", "probe.json"), "w") as f:
        if text is not None:
            f.write(text)
        else:
            json.dump(doc, f, indent=2)
    return out


def renamed(doc):
    for item in ITEMS:
        for w in doc["components"]["schemas"][item]["oneOf"]:
            w["const"] += "-x"


def search(probe_dir, tmp):
    """the test entry of the probe and the generator: the probe domain under test first, then this checkout's other
    domains, then the qualification domain; a probe-only directory is excluded when the domain is the thing
    that is absent"""
    only = os.path.join(tmp, "others")
    if not os.path.isdir(only):
        os.makedirs(only)
        shutil.copytree(os.path.join(ROOT, "contract.d", "machine"), os.path.join(only, "machine"))
    # the qualification domain alone: the installed contract directory holds the probe domain too, which an absent one is not to find
    qual = os.path.join(tmp, "qualification-only")
    if not os.path.isdir(qual):
        qualification_source.fixture(tmp, None, "qualification-only")
        # the generator reads plugin-db's domain as well
        if os.path.isdir(os.path.join(qualification_source.source_dir(), "plugin-db")):
            shutil.copytree(os.path.join(qualification_source.source_dir(), "plugin-db"), os.path.join(qual, "plugin-db"))
    return probe_dir + ":" + only + ":" + qual


def run_probe(probe_dir, tmp, fault=None, extra=()):
    out = os.path.join(tmp, "probe.json")
    if os.path.exists(out):
        os.unlink(out)
    env = dict(os.environ, OMX_CONTRACT_PATH=search(probe_dir, tmp))
    env.pop("STRESS_FAULT", None)
    if fault:
        env["STRESS_FAULT"] = fault
    cmd = [PROBE, "run", "--child", CHILD, "--rates", "48000", "--quantum", "256", "--wall-s", "10", "--grace-ms", "200",
           "--out", out, *extra, CLAP, "org.plugin-hostd.test.stress"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    return p, (json.load(open(out)) if os.path.exists(out) else None)


def generate(probe_dir, tmp):
    return subprocess.run([GEN, "probe-schema", os.path.join(ROOT, "protocol", "probe-output.schema.in")], capture_output=True,
                          text=True, env=dict(os.environ, OMX_CONTRACT_PATH=search(probe_dir, tmp)))


def emitted(d):
    """the strings a document holds at the probe's word paths"""
    out = []
    run_ = d.get("run", {})
    out += [("run.reason", run_.get("reason")), ("run.outcome", run_.get("outcome"))]
    for s in d.get("steps", []):
        out += [("steps.step", s.get("step")), ("steps.outcome", s.get("outcome"))]
        if "signal" in s:
            out.append(("steps.signal", s["signal"]))
    if "crash" in d and "signal" in d["crash"]:
        out.append(("crash.signal", d["crash"]["signal"]))
    return out


def enums(node, found):
    if isinstance(node, dict):
        if isinstance(node.get("enum"), list):
            found.append(node["enum"])
        for v in node.values():
            enums(v, found)
    elif isinstance(node, list):
        for v in node:
            enums(v, found)
    return found


def arm3(doc, tmp):
    if doc is None:
        return
    before = len(failures)
    items = {i: set(words(doc, i)) for i in ITEMS}
    known = set().union(*items.values())
    plain = fixture(tmp, "as-is")
    p, out = run_probe(plain, tmp)
    if p.returncode != 0 or out is None:
        fail("arm 3: positive control: the probe does not run over the domain as it is: rc %d %s" % (p.returncode, p.stderr[-200:]))
        return
    bad = [(k, v) for k, v in emitted(out) if v is not None and v not in known]
    if bad:
        fail("arm 3: positive control: the probe wrote words the domain does not hold: %s" % bad)
    rn = fixture(tmp, "renamed", renamed)
    for what, fault, extra, must in (
            ("a run", None, (), {"run.reason", "run.outcome", "steps.step", "steps.outcome"}),
            ("a run with --reason", None, ("--reason", "add-x"), {"run.reason"}),
            ("a crashed run", "crash", (), {"run.outcome", "steps.signal", "crash.signal"})):
        p, out = run_probe(rn, tmp, fault, extra)
        if out is None:
            fail("arm 3: %s over the renamed domain gave no document: rc %d %s" % (what, p.returncode, p.stderr[-200:]))
            continue
        got = emitted(out)
        paths = {k for k, v in got if v is not None}
        for k in sorted(must - paths):
            fail("arm 3: %s over the renamed domain wrote nothing at %s" % (what, k))
        for k, v in got:
            if v is not None and not v.endswith("-x"):
                fail("arm 3: %s over the renamed domain wrote %r at %s, not the domain's word" % (what, v, k))
        if what == "a run with --reason" and out["run"]["reason"] != "add-x":
            fail("arm 3: --reason add-x over the renamed domain wrote %r" % out["run"]["reason"])
        if what == "a crashed run" and out.get("crash", {}).get("signal") != "SIGABRT-x":
            fail("arm 3: the crash block holds %r, not the renamed SIGABRT" % out.get("crash", {}).get("signal"))
    g = generate(rn, tmp)
    if g.returncode != 0:
        fail("arm 3: the generator does not run over the renamed domain: %s" % g.stderr[-200:])
    else:
        found = [set(e) for e in enums(json.loads(g.stdout), [])]
        for item in ITEMS:
            want = {w + "-x" for w in items[item]}
            if want not in found:
                fail("arm 3: no enumeration of the generated schema is the renamed %s" % item)
    if len(failures) == before:
        ok("arm 3: the probe and the generated schema write the domain's words (reason, outcome, step, signal)")


def arm4(doc, tmp):
    if doc is None:
        return

    def old(d):
        d["info"]["version"] = "0.9.0"

    def lacking(name):
        def edit(d):
            del d["components"]["schemas"][name]
        return edit

    def short(name):
        def edit(d):
            d["components"]["schemas"][name]["oneOf"].pop()
        return edit

    before = len(failures)
    cases = [("absent", os.path.join(tmp, "nowhere"), "contract.dir.absent"),
             ("invalid", fixture(tmp, "invalid", text="{ not json"), "contract."),
             ("too old", fixture(tmp, "old", old), "contract.package.too-old")]
    cases += [("without %s" % i, fixture(tmp, "lacking-" + i, lacking(i)), i) for i in ITEMS]
    for what, dirs, mark in cases:
        p, out = run_probe(dirs, tmp)
        if not (p.returncode == 78 and out is None and "probe" in p.stderr and mark in p.stderr):
            fail("arm 4: a domain %s does not end the probe's start-up with 78, its code and the domain's name: rc %d %r" %
                 (what, p.returncode, p.stderr[-200:]))
        g = generate(dirs, tmp)
        if not (g.returncode != 0 and "probe" in g.stderr and mark in g.stderr):
            fail("arm 4: a domain %s is not refused by the generator, by name: rc %d %r" % (what, g.returncode, g.stderr[-200:]))
    for i in ITEMS:
        p, out = run_probe(fixture(tmp, "short-" + i, short(i)), tmp)
        if not (p.returncode == 78 and out is None and i in p.stderr and "probe" in p.stderr):
            fail("arm 4: %s short of a word does not end the probe's start-up with 78 by item: rc %d %r" % (i, p.returncode, p.stderr[-200:]))
    if "1.0.0" not in run_probe(cases[2][1], tmp)[0].stderr:
        fail("arm 4: the too-old refusal does not name the floor 1.0.0")
    if len(failures) == before:
        ok("arm 4: an absent, invalid, too old, item-less or short probe domain is refused by name at start-up (78)")


def arm6(doc):
    if doc is None:
        return
    before = len(failures)
    src = open(os.path.join(ROOT, "src", "probe.c")).read()
    for item in ("PROBE_REASONS", "PROBE_OUTCOMES"):
        for w in words(doc, item):
            if '"%s"' % w in src:
                fail("arm 6: src/probe.c holds the %s word %r as a literal" % (item, w))
    for w in words(doc, "PROBE_STEPS"):
        for call in ("add_step", "child_end", "add_lv2_figure_step"):
            if '%s("%s"' % (call, w) in src:
                fail("arm 6: src/probe.c names the PROBE_STEPS word %r in a call of %s: the word is the domain's" % (w, call))
    if len(failures) == before:
        ok("arm 6: no word of the probe domain is a literal of src/probe.c")


GOLDEN_SIGNALS = ("SIGSEGV SIGABRT SIGBUS SIGFPE SIGILL SIGKILL SIGTERM SIGXCPU SIGXFSZ SIGSYS SIGPIPE SIGINT SIGHUP").split()
HEADER_CODES = os.path.join(os.path.dirname(HEADER), "probe_codes.h")


def signal_word_call(dirs, tmp):
    """the call: tests/probe_signal_word.c over probe_words_open(dirs) and probe_signal_word(); the process, or None when it does
    not build"""
    cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
    libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
    proto = os.path.dirname(os.path.dirname(HEADER))
    exe = os.path.join(tmp, "probe_signal_word")
    if not os.path.exists(exe):
        cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-std=gnu99", "-D_GNU_SOURCE", "-Isrc", "-Iinclude",
                                                        "-I" + proto, "-o", exe, "tests/probe_signal_word.c", "src/probe_words.c",
                                                        "src/domain_words.c"]
        b = run(cc + shlex.split(cflags) + shlex.split(libs))
        if b.returncode != 0:
            fail("arm 7: tests/probe_signal_word.c does not build: %s" % b.stderr.strip()[-300:])
            return None
    return subprocess.run([exe, dirs], cwd=ROOT, capture_output=True, text=True)


def arm7(doc, tmp):
    before = len(failures)
    if doc is None:
        return
    want = " ".join("%s=%s" % (n, n) for n in GOLDEN_SIGNALS) + " other=%s slots=14" % UNKNOWN_SIGNAL
    # (a) golden, frozen from the hand copy of src/probe_words.h
    p = signal_word_call(fixture(tmp, "seven-as-is"), tmp)
    if p is None:
        return
    if p.returncode != 0 or p.stdout.strip() != want:
        fail("arm 7 (a): the call does not give the golden words: rc %d %s (want %s)" % (p.returncode, (p.stdout + p.stderr).strip(), want))
    # (b) the codes the call indexes by are the domain's own header, and src/probe_words.h holds no list of its own
    header = {}
    if os.path.isfile(HEADER_CODES):
        text = open(HEADER_CODES).read()
        header = {k: int(v) for k, v in re.findall(r"#define OMX_PROBE_SIGNALS_([A-Z0-9_]+) (\d+)u?\b", text)}
        if header.pop("COUNT", None) != len(GOLDEN_SIGNALS) + 1:
            fail("arm 7 (b): the header's OMX_PROBE_SIGNALS_COUNT is not %d" % (len(GOLDEN_SIGNALS) + 1))
    else:
        fail("arm 7 (b): probe_codes.h does not exist beside protocol.h")
    codes = {w["const"]: w["x-code"] for w in doc["components"]["schemas"]["PROBE_SIGNALS"]["oneOf"]}
    if header != codes:
        fail("arm 7 (b): the header's signal codes %s are not the domain's %s" % (header, codes))
    words_h = open(os.path.join(ROOT, "src", "probe_words.h")).read()
    if "probe_codes.h" not in words_h:
        fail("arm 7 (b): src/probe_words.h does not include the domain's probe_codes.h")
    if re.search(r"#define PROBE_SIGNALS\(X\)", words_h) or re.search(r"PROBE_SIGNAL_SEGV", words_h):
        fail("arm 7 (b): src/probe_words.h still holds the hand-written signal list")

    # (c) sabotage: a renamed word is the call's result, swapped codes are refused by item
    def rename_one(d):
        for w in d["components"]["schemas"]["PROBE_SIGNALS"]["oneOf"]:
            if w["const"] == "SIGSEGV":
                w["const"] = "SIGSEGV-x"

    def swapped(d):
        one = d["components"]["schemas"]["PROBE_SIGNALS"]["oneOf"]
        one[0]["x-code"], one[1]["x-code"] = one[1]["x-code"], one[0]["x-code"]

    p = signal_word_call(fixture(tmp, "seven-renamed", rename_one), tmp)
    if p is None:
        return
    if p.returncode != 0 or "SIGSEGV=SIGSEGV-x " not in p.stdout:
        fail("arm 7 (c): a renamed signal word is not the call's result: rc %d %s" % (p.returncode, (p.stdout + p.stderr).strip()))
    p = signal_word_call(fixture(tmp, "seven-swapped", swapped), tmp)
    if p is None:
        return
    if not (p.returncode == 1 and p.stdout.startswith("refused") and "PROBE_SIGNALS" in p.stdout):
        fail("arm 7 (c): a domain with swapped signal codes is not refused by item at the call: rc %d %s" %
             (p.returncode, (p.stdout + p.stderr).strip()))
    if len(failures) == before:
        ok("arm 7: the call's signal words are the golden ones, the codes are the header's, a renamed word is the result and swapped codes are refused")


def main():
    doc = load()
    arm1(doc)
    arm2(doc)
    arm6(doc)
    tmp = tempfile.mkdtemp(prefix="plugin-hostd-probe-domain.")
    try:
        arm3(doc, tmp)
        arm4(doc, tmp)
        arm7(doc, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
