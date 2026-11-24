#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/machine_domain.py: plugin-hostd owns the domain `machine` (contract.d/machine/machine.json) ; consumer-move recipe,
arms 1 to 8.

1. the document conforms: omx-contract validate and fmt --check, $schema, $id, info.x-owner/x-stability, every item MACHINE_-prefixed;
2. no machine_vocabulary.h exists or is included;
3. the words the probe and the schema generator write are the domain's: a scratch copy with every band word renamed, read
   through OMX_CONTRACT_PATH, gives the renamed words in the probe's machine.class and in the generated schema;
4. include/plugin-hostd/machine_codes.h holds exactly the items marked x-c-codes and is the render (--check), or there is none;
5. the CLIs (the probe, the generator) read OMX_CONTRACT_PATH, the library entry (machine_words_open with no directory,
   the daemon's) ignores it, and nothing of src/machine.c or src/domain_words.c reads the environment;
6. a machine domain that is absent, invalid or without the items or bands the probe cuts is refused by name at
   start-up: the probe exits 78 with the loader's code and the domain's name, the generator exits 1 the same way;
7. make install_machine_domain DESTDIR=<tmp> gives the tree the loader reads: omx_domain_open_at opens it and finds a
   word and a catalog text;
8. MACHINE_FAMILIES holds exactly the families the probe writes as machine.class.family (intel, amd, arm, unknown), the
   probe writes the domain's word (a scratch copy with every family renamed gives the renamed word), and a domain short of
   a family is refused by item at start-up; the generated probe-output schema's machine.class.family is an enum of the
   domain's MACHINE_FAMILIES words, rendered at build time (the renamed copy gives the renamed words), with an x-from
   naming the item (plugin-hostd#172).

9. the call-level read (machine_words_open, sorting pass V7): the family ids and the band counts of the call are the golden
   ones frozen from the hand copy (intel 0, amd 1, arm 2, unknown 3; counts 6, 5, 4), they are the codes of the domain's
   own header (include/plugin-hostd/machine_codes.h, one source: no hand-written enum or count in src/machine.h), and a
   domain whose family codes are swapped is refused by item at the call.

Environment: OMX_CONTRACT (the command, default omx-contract), INSTALL_CONTRACT_DIR (the installer, default found by
pkg-config), DOMAIN_CFLAGS and DOMAIN_LIBS (the loader, default pkg-config libomx-domain), CC. Exit 0 all green, 1 a
FAIL line. Arms 3, 5 and 6 also take PROBE (default ./plugin-hostd-probe), PROBE_CHILD (tests/probe-child), STRESS_CLAP
(tests/stress.clap) and GEN (tools/protocol-gen), built by make test-machine-domain.
"""
import atexit
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_views  # noqa: E402
import qualification_source  # noqa: E402
from tree_files import tracked as tree_tracked  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "contract.d", "machine", "machine.json")
HEADER = os.path.join(ROOT, "include", "plugin-hostd", "machine_codes.h")
OMX = shlex.split(os.environ.get("OMX_CONTRACT", "omx-contract"))
PROBE = os.path.abspath(os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe")))
DAEMON = os.path.abspath(os.environ.get("DAEMON", os.path.join(ROOT, "plugin-hostd")))
DAEMON_EMPTY = os.path.abspath(os.environ.get("DAEMON_EMPTY", os.path.join(ROOT, "tests", "plugin-hostd-test-empty")))
CHILD = os.path.abspath(os.environ.get("PROBE_CHILD", os.path.join(ROOT, "tests", "probe-child")))
CLAP = os.path.abspath(os.environ.get("STRESS_CLAP", os.path.join(ROOT, "tests", "stress.clap")))
GEN = os.path.abspath(os.environ.get("GEN", os.path.join(ROOT, "tools", "protocol-gen")))
WORDS_OPEN = "machine_words_open"
BANDS = ("MACHINE_CORE_BANDS", "MACHINE_CLOCK_BANDS")
FAMILIES = ["intel", "amd", "arm", "unknown"]
FAMILIES_REF = "https://openmixer.org/contract/machine#/components/schemas/MACHINE_FAMILIES"
# the probe domain is plugin-hostd-protocol's: where its contract package installs it, PROTOCOL_CONTRACT_DIR for a checkout's
PROBE_SOURCE = os.environ.get("PROTOCOL_CONTRACT_DIR") or subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"],
                                                                         capture_output=True, text=True).stdout.strip() or "/usr/share/omx-contract/contract.d"
failures = []
PROBE_ONLY = [None]  # a scratch contract directory holding this checkout's probe domain and no other, set by main()


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
        fail("arm 1: contract.d/machine/machine.json is not readable: %s" % e)
        return None


_ALONE = []


def machine_alone():
    """a scratch contract directory holding this checkout's machine domain alone (removed at exit)"""
    if not _ALONE:
        tmp = tempfile.mkdtemp(prefix="machine-alone-")
        atexit.register(shutil.rmtree, tmp, True)
        _ALONE.append(contract_views.domain_only(tmp, "machine"))
    return _ALONE[0]


def arm1(doc):
    if doc is None:
        return
    before = len(failures)
    # the machine domain staged alone: contract.d holds the qualification domain (which names other owners' domains) and
    # the vocabulary domains under plugin-hostd/ (read beside the package plugin-hostd), which a directory read alone refuses
    alone = machine_alone()
    r = run(OMX + ["validate", "--contract-dir", alone])
    if r.returncode != 0:
        fail("arm 1: omx-contract validate of contract.d/machine: %s" % (r.stderr.strip() or r.stdout.strip()))
    r = run(OMX + ["fmt", "--check", "--contract-dir", alone])
    if r.returncode != 0:
        fail("arm 1: omx-contract fmt --check of contract.d/machine: %s" % (r.stderr.strip() or r.stdout.strip()))
    if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("arm 1: $schema is %r, not the 2020-12 schema" % doc.get("$schema"))
    if doc.get("$id") != "https://openmixer.org/contract/machine":
        fail("arm 1: $id is %r, not https://openmixer.org/contract/machine" % doc.get("$id"))
    info = doc.get("info", {})
    if info.get("x-owner") != "plugin-hostd":
        fail("arm 1: info.x-owner is %r, not plugin-hostd" % info.get("x-owner"))
    if info.get("x-stability") != "experimental":
        fail("arm 1: info.x-stability is %r, not experimental" % info.get("x-stability"))
    for name in doc.get("components", {}).get("schemas", {}):
        if not name.startswith("MACHINE_"):
            fail("arm 1: item %s does not start with MACHINE_" % name)
    if len(failures) == before:
        ok("arm 1: the document conforms")


def arm2():
    before = len(failures)
    skip = {"tests/machine_domain.py"}
    names = tree_tracked(ROOT, untracked=True)
    for rel in names:
        if rel in skip or not os.path.isfile(os.path.join(ROOT, rel)):
            continue
        if "machine_vocabulary" in os.path.basename(rel):
            fail("arm 2: %s exists" % rel)
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if "machine_vocabulary" in text:
            fail("arm 2: %s names machine_vocabulary" % rel)
    if len(failures) == before:
        ok("arm 2: no machine_vocabulary file or include")


def arm4(doc):
    before = len(failures)
    marked = []
    if doc is not None:
        marked = [k for k, v in doc.get("components", {}).get("schemas", {}).items() if v.get("x-c-codes")]
    items = []
    if os.path.isfile(HEADER):
        items = re.findall(r"#define OMX_(MACHINE_[A-Z0-9_]+?)_COUNT ", open(HEADER).read())
    elif marked:
        fail("arm 4: %s are marked x-c-codes and include/plugin-hostd/machine_codes.h does not exist" % sorted(marked))
    if sorted(items) != sorted(marked):
        fail("arm 4: machine_codes.h holds %s, the x-c-codes items are %s" % (sorted(items), sorted(marked)))
    for name in marked:
        if not any(name in open(os.path.join(ROOT, f), errors="replace").read() for f in glob.glob(os.path.join(ROOT, "src", "*.c"))):
            fail("arm 4: %s is marked x-c-codes and no file of src/ names it" % name)
    r = run(OMX + ["render", "--target", "c", "--package", "machine", "--contract-dir", machine_alone(), "--out", "include/plugin-hostd", "--check"])
    if r.returncode != 0:
        fail("arm 4: omx-contract render --check: %s" % (r.stderr.strip() or r.stdout.strip()))
    if len(failures) == before:
        ok("arm 4: machine_codes.h holds the x-c-codes items only (%d) and is the render" % len(marked))


def arm7():
    before = len(failures)
    with tempfile.TemporaryDirectory() as tmp:
        make = ["make", "--no-print-directory", "install_machine_domain", "DESTDIR=" + tmp]
        if os.environ.get("INSTALL_CONTRACT_DIR"):
            make.append("INSTALL_CONTRACT_DIR=" + os.environ["INSTALL_CONTRACT_DIR"])
        r = run(make)
        if r.returncode != 0:
            fail("arm 7: make install_machine_domain: %s" % (r.stderr.strip() or r.stdout.strip()).splitlines()[-1:])
            return
        pc = run(["pkg-config", "--variable=contractdir", "omx-contract"]).stdout.strip() or "/usr/share/omx-contract/contract.d"
        installed = tmp + pc
        for rel in ("machine/machine.json", "machine/catalogs/ca.json"):
            if not os.path.isfile(os.path.join(installed, rel)):
                fail("arm 7: %s is not installed under %s" % (rel, pc))
        cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
        libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
        exe = os.path.join(tmp, "machine_domain_open")
        cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-o", exe, "tests/machine_domain_open.c"]
        b = run(cc + shlex.split(cflags) + shlex.split(libs))
        if b.returncode != 0:
            fail("arm 7: tests/machine_domain_open.c does not build (a loader is needed, libomx-domain): %s" % b.stderr.strip()[-200:])
            return
        o = run([exe, installed, "MACHINE_CORE_BANDS", "1-2", "MACHINE_CORE_BANDS.1-2", "ca"])
        if o.returncode != 0:
            fail("arm 7: the loader does not read the installed tree: %s" % o.stderr.strip())
        else:
            print("     " + o.stdout.strip())
            # the text is the installed catalog's, not the source sentence the loader falls back to without one
            with open(os.path.join(ROOT, "contract.d/machine/catalogs/ca.json"), encoding="utf-8") as f:
                want = json.load(f)["messages"]["MACHINE_CORE_BANDS.1-2"]["text"]
            if not o.stdout.strip().endswith(" text=" + want):
                fail("arm 7: the ca text read is not the installed catalog's (%r): %s" % (want, o.stdout.strip()))
    if len(failures) == before:
        ok("arm 7: the installed tree opens through omx_domain_open_at, a word and a catalog text are found")


def fixture(root, name, edit=None, text=None):
    """a scratch contract directory root/name holding the machine domain (with its catalogs), edit(document) applied, or
    text written in place of the document; its path"""
    out = os.path.join(root, name)
    shutil.copytree(os.path.join(ROOT, "contract.d", "machine"), os.path.join(out, "machine"))
    with open(DOC) as f:
        doc = json.load(f)
    if edit:
        edit(doc)
    with open(os.path.join(out, "machine", "machine.json"), "w") as f:
        if text is not None:
            f.write(text)
        else:
            json.dump(doc, f, indent=2)
    return out


def words(doc, item):
    return [w["const"] for w in sorted(doc["components"]["schemas"][item]["oneOf"], key=lambda w: w["x-code"])]


def renamed(doc):
    for item in BANDS:
        for w in doc["components"]["schemas"][item]["oneOf"]:
            w["const"] += "-x"


def with_qualification(contract_dir):
    """the test entry for the probe and the generator, which read the qualification domain and this checkout's
    probe domain as well: the machine directory under test first, a directory that holds the probe domain alone, the
    directory that holds the qualification domain"""
    # this checkout's qualification domain alone (contract.d holds the machine domain too, which an absent or renamed one
    # under test is not to find), then the installed domains the generator reads (plugin-db's, the pin domain)
    tmp = os.path.dirname(PROBE_ONLY[0])
    return ":".join([contract_dir, PROBE_ONLY[0], contract_views.domain_only(tmp, "qualification"),
                     contract_views.installed_without(tmp, ("machine", "probe", "qualification"))])


def run_probe(contract_dir, tmp):
    out = os.path.join(tmp, "probe.json")
    if os.path.exists(out):
        os.unlink(out)
    cmd = [PROBE, "run", "--child", CHILD, "--rates", "48000", "--quantum", "256", "--wall-s", "10", "--grace-ms", "200",
           "--out", out, CLAP, "org.plugin-hostd.test.stress"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=dict(os.environ, OMX_CONTRACT_PATH=with_qualification(contract_dir)))
    return p, (json.load(open(out)) if os.path.exists(out) else None)


def generate(contract_dir):
    return subprocess.run([GEN, "probe-schema", os.path.join(ROOT, "protocol", "probe-output.schema.in")], capture_output=True,
                          text=True, env=dict(os.environ, OMX_CONTRACT_PATH=with_qualification(contract_dir)))


def arm3(doc, tmp):
    before = len(failures)
    if doc is None:
        return
    core, clock = words(doc, "MACHINE_CORE_BANDS"), words(doc, "MACHINE_CLOCK_BANDS")
    p, out = run_probe(fixture(tmp, "as-is"), tmp)
    if p.returncode != 0 or out is None:
        fail("arm 3: positive control: the probe does not run over the domain as it is: rc %d %s" % (p.returncode, p.stderr[-200:]))
        return
    cls = out["machine"]["class"]
    if cls["coreBand"] not in core or cls["clockBand"] not in clock:
        fail("arm 3: positive control: the probe's bands %r %r are not the domain's" % (cls["coreBand"], cls["clockBand"]))
    p, out = run_probe(fixture(tmp, "renamed", renamed), tmp)
    if p.returncode != 0 or out is None:
        fail("arm 3: the probe does not run over the renamed domain: rc %d %s" % (p.returncode, p.stderr[-200:]))
    else:
        cls = out["machine"]["class"]
        if not (cls["coreBand"].endswith("-x") and cls["clockBand"].endswith("-x")):
            fail("arm 3: machine.class is %r %r, not the renamed domain's words" % (cls["coreBand"], cls["clockBand"]))
    g = generate(fixture(tmp, "renamed-gen", renamed))
    if g.returncode != 0:
        fail("arm 3: the generator does not run over the renamed domain: %s" % g.stderr[-200:])
    else:
        schema = json.loads(g.stdout)
        got = schema["properties"]["machine"]["properties"]["class"]["properties"]
        if got["coreBand"]["enum"] != [w + "-x" for w in core] or got["clockBand"]["enum"] != [w + "-x" for w in clock]:
            fail("arm 3: the generated schema's bands are not the renamed domain's: %s" % got["coreBand"]["enum"])
    if len(failures) == before:
        ok("arm 3: the probe and the generated schema write the domain's band words")


def arm5(tmp):
    before = len(failures)
    for rel in ("src/machine.c", "src/domain_words.c", "src/domain_words.h"):
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            fail("arm 5: %s does not exist" % rel)
        elif "getenv" in open(path).read():
            fail("arm 5: %s reads the environment: only a CLI's main passes OMX_CONTRACT_PATH" % rel)
    # the daemon reads no path and no variable for the contract (main.c reads other variables, so the name is checked)
    if "OMX_CONTRACT_PATH" in open(os.path.join(ROOT, "src", "main.c")).read():
        fail("arm 5: src/main.c names OMX_CONTRACT_PATH: the daemon reads the installed contract directory only")
    cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
    libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
    contract = os.environ.get("CONTRACT_CFLAGS") or run(["pkg-config", "--cflags", "omx-contract"]).stdout.strip()
    exe = os.path.join(tmp, WORDS_OPEN)
    cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-std=gnu99", "-D_GNU_SOURCE", "-Isrc", "-Iinclude", "-o", exe,
                                                    "tests/machine_words_open.c", "src/machine.c", "src/domain_words.c"]
    b = run(cc + shlex.split(contract) + shlex.split(cflags) + shlex.split(libs))
    if b.returncode != 0:
        fail("arm 5: tests/machine_words_open.c does not build: %s" % b.stderr.strip()[-300:])
        return
    scratch = fixture(tmp, "env-renamed", renamed)
    env = dict(os.environ, OMX_CONTRACT_PATH=scratch)
    entry = subprocess.run([exe], cwd=ROOT, capture_output=True, text=True, env=env)
    if "-x" in entry.stdout:
        fail("arm 5: the library entry read OMX_CONTRACT_PATH: %s" % entry.stdout.strip())
    # the test entry names a directory itself, and reads it
    listed = subprocess.run([exe, scratch], cwd=ROOT, capture_output=True, text=True)
    if listed.returncode != 0 or "-x" not in listed.stdout:
        fail("arm 5: the entry that names a directory does not read it: rc %d %s%s" % (listed.returncode, listed.stdout, listed.stderr))
    if len(failures) == before:
        ok("arm 5: the library entry ignores OMX_CONTRACT_PATH, the entry with a directory reads it")


def arm6(doc, tmp):
    before = len(failures)
    if doc is None:
        return

    def short(d):
        d["components"]["schemas"]["MACHINE_CORE_BANDS"]["oneOf"].pop()

    def lacking(d):
        del d["components"]["schemas"]["MACHINE_CLOCK_BANDS"]

    cases = (
        ("absent", os.path.join(tmp, "nowhere"), "contract.dir.absent"),
        ("invalid", fixture(tmp, "invalid", text="{ not json"), "contract."),
        ("without an item", fixture(tmp, "lacking", lacking), "MACHINE_CLOCK_BANDS"),
    )
    for what, dirs, mark in cases:
        p, out = run_probe(dirs, tmp)
        if not (p.returncode == 78 and out is None and "machine" in p.stderr and mark in p.stderr):
            fail("arm 6: a domain %s does not end the probe's start-up with 78, its code and the domain's name: rc %d %r" %
                 (what, p.returncode, p.stderr[-200:]))
        g = generate(dirs)
        if not (g.returncode != 0 and "machine" in g.stderr and mark in g.stderr):
            fail("arm 6: a domain %s is not refused by the generator, by name: rc %d %r" % (what, g.returncode, g.stderr[-200:]))
    # a band the probe cuts that the domain does not word: only the probe refuses it (the generator writes the words it finds)
    p, out = run_probe(fixture(tmp, "short", short), tmp)
    if not (p.returncode == 78 and out is None and "MACHINE_CORE_BANDS" in p.stderr and "machine" in p.stderr):
        fail("arm 6: a core band short of a word does not end the probe's start-up with 78 by item: rc %d %r" % (p.returncode, p.stderr[-200:]))
    # the daemon is a program too, and a production entry point: it reads no path and no variable for the contract. The test
    # builds hold the seam (OMX_CONTRACTDIR, compiled in): DAEMON over this checkout's domain, DAEMON_EMPTY over a directory
    # with none. OMX_CONTRACT_PATH is set in both to prove it is ignored.
    conf = os.path.join(tmp, "daemon.conf")
    with open(conf, "w") as f:
        f.write("pin_mode strict\nclap_path %s\nlv2_path %s\n" % (tmp, tmp))

    def daemon(exe, path):
        try:
            d = subprocess.run([exe, "-c", conf], capture_output=True, text=True, timeout=2,
                               env=dict(os.environ, OMX_CONTRACT_PATH=path))
            return d.returncode, d.stderr
        except subprocess.TimeoutExpired as e:
            return None, (e.stderr or b"").decode(errors="replace")

    rc, err = daemon(DAEMON_EMPTY, os.path.join(ROOT, "contract.d"))
    if not (rc == 78 and "machine" in err):
        fail("arm 6: the daemon over a directory with no domain does not end its start-up with 78 and the domain's name "
             "(OMX_CONTRACT_PATH over the checkout's domain is not to be read): rc %s %r" % (rc, err[-200:]))
    rc, err = daemon(DAEMON, os.path.join(tmp, "nowhere"))
    if rc is not None:
        fail("arm 6: the daemon over the domain does not start (OMX_CONTRACT_PATH over a directory with none is not to be read): "
             "rc %s %r" % (rc, err[-200:]))
    if len(failures) == before:
        ok("arm 6: an absent, invalid, short or item-less machine domain is refused by name at start-up")


def arm8(doc, tmp):
    before = len(failures)
    if doc is None:
        return
    item = doc["components"]["schemas"].get("MACHINE_FAMILIES")
    if item is None:
        fail("arm 8: the domain has no item MACHINE_FAMILIES")
        return
    if words(doc, "MACHINE_FAMILIES") != FAMILIES:
        fail("arm 8: MACHINE_FAMILIES holds %s, the probe writes %s" % (words(doc, "MACHINE_FAMILIES"), FAMILIES))

    def renamed_families(d):
        for w in d["components"]["schemas"]["MACHINE_FAMILIES"]["oneOf"]:
            w["const"] += "-x"

    def short(d):
        d["components"]["schemas"]["MACHINE_FAMILIES"]["oneOf"].pop()

    p, out = run_probe(fixture(tmp, "families-as-is"), tmp)
    if p.returncode != 0 or out is None:
        fail("arm 8: positive control: the probe does not run over the domain as it is: rc %d %s" % (p.returncode, p.stderr[-200:]))
        return
    if out["machine"]["class"]["family"] not in FAMILIES:
        fail("arm 8: positive control: the probe's family %r is not the domain's" % out["machine"]["class"]["family"])
    p, out = run_probe(fixture(tmp, "families-renamed", renamed_families), tmp)
    if p.returncode != 0 or out is None:
        fail("arm 8: the probe does not run over the domain with renamed families: rc %d %s" % (p.returncode, p.stderr[-200:]))
    elif not out["machine"]["class"]["family"].endswith("-x"):
        fail("arm 8: machine.class.family is %r, not the renamed domain's word" % out["machine"]["class"]["family"])
    for name, change, want in (("families-gen", None, FAMILIES),
                               ("families-renamed-gen", renamed_families, [w + "-x" for w in FAMILIES])):
        g = generate(fixture(tmp, name, change))
        if g.returncode != 0:
            fail("arm 8: the generator does not run over %s: %s" % (name, g.stderr[-200:]))
            continue
        family = json.loads(g.stdout)["properties"]["machine"]["properties"]["class"]["properties"]["family"]
        if family.get("enum") != want:
            fail("arm 8: the generated schema's family is %s, not the %s domain's words %s" % (family, name, want))
        if family.get("x-from") != [{"$ref": FAMILIES_REF}]:
            fail("arm 8: the generated schema's family names no item: x-from %r" % family.get("x-from"))
    p, out = run_probe(fixture(tmp, "families-short", short), tmp)
    if not (p.returncode == 78 and out is None and "MACHINE_FAMILIES" in p.stderr and "machine" in p.stderr):
        fail("arm 8: a family short of a word does not end the probe's start-up with 78 by item: rc %d %r" % (p.returncode, p.stderr[-200:]))
    if len(failures) == before:
        ok("arm 8: MACHINE_FAMILIES holds the probe's families and the probe writes the domain's word")


GOLDEN_FAMILIES = "intel:0,amd:1,arm:2,unknown:3"
GOLDEN_COUNTS = "6,5,4"


def words_open(dirs, tmp):
    """the call: tests/machine_words_open.c over machine_words_open(dirs); the process, or None when it does not build"""
    cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
    libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
    contract = os.environ.get("CONTRACT_CFLAGS") or run(["pkg-config", "--cflags", "omx-contract"]).stdout.strip()
    exe = os.path.join(tmp, WORDS_OPEN + "-9")
    if not os.path.exists(exe):
        cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-std=gnu99", "-D_GNU_SOURCE", "-Isrc", "-Iinclude",
                                                        "-o", exe, "tests/machine_words_open.c", "src/machine.c", "src/domain_words.c"]
        b = run(cc + shlex.split(contract) + shlex.split(cflags) + shlex.split(libs))
        if b.returncode != 0:
            fail("arm 9: tests/machine_words_open.c does not build: %s" % b.stderr.strip()[-300:])
            return None
    return subprocess.run([exe, dirs], cwd=ROOT, capture_output=True, text=True)


def arm9(doc, tmp):
    before = len(failures)
    if doc is None:
        return
    # (a) golden, frozen from the hand copy of src/machine.h
    p = words_open(fixture(tmp, "nine-as-is"), tmp)
    if p is None:
        return
    if p.returncode != 0 or (" family=" + GOLDEN_FAMILIES) not in p.stdout or not p.stdout.strip().endswith(" counts=" + GOLDEN_COUNTS):
        fail("arm 9 (a): the call does not give the golden family ids %s and counts %s: rc %d %s" %
             (GOLDEN_FAMILIES, GOLDEN_COUNTS, p.returncode, (p.stdout + p.stderr).strip()))
    # (b) the call's ids and counts are the domain's own header, which is the domain
    codes = {}
    counts = {}
    if os.path.isfile(HEADER):
        text = open(HEADER).read()
        counts = {k: int(v) for k, v in re.findall(r"#define OMX_(MACHINE_[A-Z_]+)_COUNT (\d+)u?\b", text)}
        codes = {k: int(v) for k, v in re.findall(r"#define OMX_MACHINE_FAMILIES_([A-Z0-9_]+) (\d+)u?\b", text)}
    else:
        fail("arm 9 (b): include/plugin-hostd/machine_codes.h does not exist")
    want = {w["title"].upper(): w["x-code"] for w in doc["components"]["schemas"]["MACHINE_FAMILIES"]["oneOf"]}
    codes.pop("COUNT", None)
    if codes != want:
        fail("arm 9 (b): the header's family codes %s are not the domain's %s" % (codes, want))
    got = ",".join(str(counts.get(k, "-")) for k in ("MACHINE_CORE_BANDS", "MACHINE_CLOCK_BANDS", "MACHINE_FAMILIES"))
    if got != GOLDEN_COUNTS:
        fail("arm 9 (b): the header's counts %s are not the golden %s" % (got, GOLDEN_COUNTS))
    # no hand copy: the enum and the counts of src/machine.h are written from the header
    machine_h = open(os.path.join(ROOT, "src", "machine.h")).read()
    if "machine_codes.h" not in machine_h:
        fail("arm 9 (b): src/machine.h does not include the domain's machine_codes.h")
    if re.search(r"#define MACHINE_(CORE|CLOCK)_BAND_COUNT\s+\d", machine_h) or re.search(r"MACHINE_FAMILY_INTEL\s*[,}]", machine_h):
        fail("arm 9 (b): src/machine.h still holds a hand-written count or family enum")

    # (c) sabotage: a temporary domain whose first two family codes are swapped is refused by item at the call
    def swapped(d):
        one = d["components"]["schemas"]["MACHINE_FAMILIES"]["oneOf"]
        one[0]["x-code"], one[1]["x-code"] = one[1]["x-code"], one[0]["x-code"]

    p = words_open(fixture(tmp, "nine-swapped", swapped), tmp)
    if p is None:
        return
    if not (p.returncode == 1 and "MACHINE_FAMILIES" in p.stdout and p.stdout.startswith("refused")):
        fail("arm 9 (c): a domain with swapped family codes is not refused by item at the call: rc %d %s" %
             (p.returncode, (p.stdout + p.stderr).strip()))
    if len(failures) == before:
        ok("arm 9: the call's family ids and counts are the golden ones, the header's, and a swapped domain is refused")


def main():
    doc = load()
    arm1(doc)
    arm2()
    arm4(doc)
    arm7()
    tmp = tempfile.mkdtemp(prefix="plugin-hostd-machine.")
    PROBE_ONLY[0] = os.path.join(tmp, "probe-only")
    shutil.copytree(os.path.join(PROBE_SOURCE, "probe"), os.path.join(PROBE_ONLY[0], "probe"))
    try:
        arm3(doc, tmp)
        arm5(tmp)
        arm6(doc, tmp)
        arm8(doc, tmp)
        arm9(doc, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
