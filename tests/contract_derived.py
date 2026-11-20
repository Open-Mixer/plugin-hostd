# SPDX-License-Identifier: GPL-3.0-or-later
# What plugin-hostd shares with omx-contract is read from omx-contract, never typed again here: the probe runner's
# default rates are ORACLE_FLOOR_RATES, the parameter scales of the protocol are PARAM_SCALES, the same words in
# the same order, and the probe output's shared enums are the words of the contract (the qualification domain, plugin-qualify's, read through the loader). Checked twice: against the installed contract (its data and its C header), and against a scratch
# copy of the header with the values changed, where the runner must follow and the generator must refuse to build.
# The JSON of the protocol is written by plugin-hostd-protocol's generator (its installed source, protocolgen), built here
# against the scratch copies; the probe schema by this tree's tools/protocol-gen.c.
# Usage: contract_derived.py (run from the tree; CC, PKG_CONFIG and PROBE from the environment, or their defaults).
import json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import declared as declared_protocol
import qualification_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the generator of the protocol's JSON, plugin-hostd-protocol's, and this tree's, which writes the probe schema
JSON_GEN = declared_protocol.variable("protocolgen")
OWN_GEN = os.path.join(ROOT, "tools", "protocol-gen.c")
CC = os.environ.get("CC", "cc")
PKG_CONFIG = os.environ.get("PKG_CONFIG", "pkg-config")
# cJSON's flags are the Makefile's (CJSON_CFLAGS, CJSON_LIBS); run by hand, pkg-config libcjson says the same
CJSON_CFLAGS = os.environ["CJSON_CFLAGS"] if "CJSON_CFLAGS" in os.environ else \
    subprocess.run([PKG_CONFIG, "--cflags", "libcjson"], capture_output=True, text=True, check=True).stdout
CJSON_LIBS = os.environ["CJSON_LIBS"] if "CJSON_LIBS" in os.environ else \
    subprocess.run([PKG_CONFIG, "--libs", "libcjson"], capture_output=True, text=True, check=True).stdout
# the machine domain's loader (libomx-domain): the Makefile's DOMAIN_CFLAGS and DOMAIN_LIBS, else pkg-config's
DOMAIN_CFLAGS = (os.environ["DOMAIN_CFLAGS"] if "DOMAIN_CFLAGS" in os.environ else
                 subprocess.run([PKG_CONFIG, "--cflags", "libomx-domain"], capture_output=True, text=True, check=True).stdout).split()
DOMAIN_LIBS = (os.environ["DOMAIN_LIBS"] if "DOMAIN_LIBS" in os.environ else
               subprocess.run([PKG_CONFIG, "--libs", "libomx-domain"], capture_output=True, text=True, check=True).stdout).split()
# the CLIs read the machine domain from OMX_CONTRACT_PATH: this checkout's own document
# (then the installed contract directory)
MACHINE_ENV = dict(os.environ, OMX_CONTRACT_PATH=":".join(
    [os.path.join(ROOT, "contract.d")] + [d for d in os.environ.get("OMX_CONTRACT_PATH", "").split(":") if d] +
    [subprocess.run([PKG_CONFIG, "--variable=contractdir", "omx-contract"], capture_output=True, text=True).stdout.strip()]))
PROBE = os.path.abspath(os.environ.get("PROBE", os.path.join(ROOT, "plugin-hostd-probe")))
failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL contract: " + what)


def pkg(*args):
    return subprocess.run([PKG_CONFIG] + list(args) + ["omx-contract"], capture_output=True, text=True, check=True).stdout.strip()


def contract_data(name):
    """an item of omx-contract's own data, as the installed package lays it out (contract.d/<major>/omx-contract)"""
    base = pkg("--variable=contractdir")
    for major in sorted(os.listdir(base), reverse=True):
        if not major.isdigit():
            continue  # a domain's directory (qualification/), not a schema major
        for f in sorted(os.listdir(os.path.join(base, major, "omx-contract"))):
            if f.endswith(".json") and f != "MANIFEST.json":
                with open(os.path.join(base, major, "omx-contract", f)) as fh:
                    data = json.load(fh)
                if name in data:
                    return data[name]
    raise SystemExit("omx-contract declares no %s" % name)


def header(name="omx_contract_limits.h"):
    for flag in pkg("--cflags").split() + ["-I/usr/include"]:
        if flag.startswith("-I"):
            path = os.path.join(flag[2:], "omxcontract", name)
            if os.path.exists(path):
                return path
    raise SystemExit("omx-contract's C header %s is not installed" % name)


def child_rates(probe, tmp):
    """the --rates the runner hands its child when it is given none"""
    seen = os.path.join(tmp, "argv")
    child = os.path.join(tmp, "child.sh")
    with open(child, "w") as f:
        f.write('#!/bin/sh\nprintf "%%s\\n" "$@" > %s\n' % seen)
    os.chmod(child, 0o755)
    plugin = os.path.join(tmp, "x.clap")
    open(plugin, "w").close()
    subprocess.run([probe, "run", "--child", child, "--wall-s", "5", "--out", os.path.join(tmp, "doc.json"), plugin],
                   capture_output=True, text=True, timeout=60, env=MACHINE_ENV)
    args = open(seen).read().split("\n") if os.path.exists(seen) else []
    return args[args.index("--rates") + 1] if "--rates" in args else None


def help_rates(probe):
    p = subprocess.run([probe], capture_output=True, text=True, timeout=10)
    m = re.search(r"--rates R,R,\.\.\.\s+sample rates \(default ([0-9,]+)\)", p.stderr)
    return m.group(1) if m else None


# the probe runner's sources, as the Makefile's PROBE_SRC names them
PROBE_SRC = re.search(r"^PROBE_SRC = (.*)$", open(os.path.join(ROOT, "Makefile")).read(), re.M).group(1).split()


# <plugin-db/pin.h>: what every build that includes it asks of plugin-db.pc
PIN_CFLAGS = subprocess.run([PKG_CONFIG, "--cflags", "plugin-db"], capture_output=True, text=True, check=True).stdout.split()
PIN_LIBS = subprocess.run([PKG_CONFIG, "--libs", "plugin-db"], capture_output=True, text=True, check=True).stdout.split()
# the C loader of the contract's domains (libomx-domain): the probe and the schema generator read the qualification domain through it
DOMAIN_CFLAGS = subprocess.run([PKG_CONFIG, "--cflags", "libomx-domain"], capture_output=True, text=True, check=True).stdout.split()
DOMAIN_LIBS = subprocess.run([PKG_CONFIG, "--libs", "libomx-domain"], capture_output=True, text=True, check=True).stdout.split()


def build_probe(include_first, out):
    cmd = [CC, "-I" + include_first, "-I" + os.path.join(ROOT, "include"), "-I" + declared_protocol.include_dir()] + \
          pkg("--cflags").split() + PIN_CFLAGS + CJSON_CFLAGS.split() + DOMAIN_CFLAGS + ["-I" + os.path.join(ROOT, "src"), "-O2", "-std=gnu99", "-D_GNU_SOURCE",
                                     "-DPROBE_VERSION=\"0\"", "-o", out] + \
          [os.path.join(ROOT, f) for f in PROBE_SRC] + PIN_LIBS + ["-lm"] + DOMAIN_LIBS + CJSON_LIBS.split()
    return subprocess.run(cmd, capture_output=True, text=True)


def build_gen(include_first, out, source=JSON_GEN):
    # this tree's generator reads the machine domain through src/domain_words.c
    own = source == OWN_GEN
    cmd = [CC, "-I" + include_first, "-I" + os.path.join(ROOT, "include"), "-I" + declared_protocol.include_dir()] + \
          (["-I" + os.path.join(ROOT, "src")] if own else []) + pkg("--cflags").split() + PIN_CFLAGS + DOMAIN_CFLAGS + \
          ["-std=gnu99", "-o", out, source] + \
          ([os.path.join(ROOT, "src", f) for f in ("domain_words.c", "qualification_words.c")] if own else []) + PIN_LIBS + DOMAIN_LIBS
    return subprocess.run(cmd, capture_output=True, text=True)


def gen_json(gen):
    p = subprocess.run([gen, "json"], capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def gen_methods(gen, contract_path):
    """the latency methods of the probe schema the generator writes from this tree's template, the qualification domain
    read from contract_path (OMX_CONTRACT_PATH, the generator's test entry); the installed contract directory follows, for
    the domains the template takes from their owners (plugin-db's address formats)"""
    p = subprocess.run([gen, "probe-schema", os.path.join(ROOT, "protocol", "probe-output.schema.in")], capture_output=True,
                       text=True, timeout=30, env=dict(os.environ, OMX_CONTRACT_PATH=":".join(
                           [os.path.join(ROOT, "contract.d"), contract_path] + qualification_source.search_path())))
    if p.returncode != 0:
        return None
    return json.loads(p.stdout)["$defs"]["point"]["properties"]["latency"]["properties"]["method"]["enum"]


def main():
    floor = ",".join(str(r) for r in contract_data("ORACLE_FLOOR_RATES")["values"])
    scales = contract_data("PARAM_SCALES")["ids"]
    with open(declared_protocol.variable("protocoljson")) as f:
        declared = [s["name"] for s in json.load(f)["param_scales"]]
    check(declared == scales, "the protocol's parameter scales %s are omx-contract's PARAM_SCALES %s" % (declared, scales))

    tmp = tempfile.mkdtemp(prefix="plugin-hostd-contract.")
    try:
        check(child_rates(PROBE, tmp) == floor, "the runner's child gets omx-contract's ORACLE_FLOOR_RATES %s by default, "
              "not %s" % (floor, child_rates(PROBE, tmp)))
        check(help_rates(PROBE) == floor, "the runner's usage names the same default: %s" % help_rates(PROBE))

        # a scratch contract whose floor is other rates: the runner built against it follows, with no edit of its own
        scratch = os.path.join(tmp, "include")
        os.makedirs(os.path.join(scratch, "omxcontract"))
        text = open(header()).read()
        moved = re.sub(r"(#define OMX_ORACLE_FLOOR_RATES_INIT )\{[^}]*\}", r"\1{ 32000, 88200 }", text)
        check(moved != text, "positive control: the scratch header's floor was changed")
        with open(os.path.join(scratch, "omxcontract", "omx_contract_limits.h"), "w") as f:
            f.write(moved.replace("#define OMX_ORACLE_FLOOR_RATES_COUNT 4u", "#define OMX_ORACLE_FLOOR_RATES_COUNT 2u"))
        built = build_probe(scratch, os.path.join(tmp, "probe"))
        check(built.returncode == 0, "the runner builds against the scratch contract: %s" % built.stderr[-400:])
        if built.returncode == 0:
            check(child_rates(os.path.join(tmp, "probe"), tmp) == "32000,88200",
                  "a moved floor moves the runner's default: %s" % child_rates(os.path.join(tmp, "probe"), tmp))

        # the generator builds against the contract as it is and writes its scales; it refuses a word of the
        # protocol's own that is not the contract's, and a contract whose scales are in another order
        built = build_gen(os.path.dirname(os.path.dirname(header())), os.path.join(tmp, "gen"))
        check(built.returncode == 0, "positive control: the generator builds against the contract: %s" % built.stderr[-400:])
        if built.returncode == 0:
            rc, out, err = gen_json(os.path.join(tmp, "gen"))
            check(rc == 0 and [x["name"] for x in json.loads(out)["param_scales"]] == scales,
                  "positive control: the generator writes the contract's scales: rc %d %s" % (rc, err[-200:]))
        # protocol.h is plugin-hostd-protocol's: a changed copy of its headers, read before the installed ones
        own = os.path.dirname(declared_protocol.overlay(os.path.join(tmp, "own")))
        proto = os.path.join(own, "plugin-hostd", "protocol.h")
        ptext = open(proto).read()
        renamed = ptext.replace('X(LOG, "log", ', 'X(LOG, "logarithmic", ')
        check(renamed != ptext, "positive control: the scratch protocol.h's word was changed")
        with open(proto, "w") as f:
            f.write(renamed)
        # both generators: plugin-hostd-protocol's of the JSON, and this tree's of its pages
        for source, mode in ((JSON_GEN, "json"), (OWN_GEN, "regions")):
            exe = os.path.join(tmp, "gen-renamed-" + mode)
            built = build_gen(own, exe, source)
            if built.returncode == 0:
                p = subprocess.run([exe, mode], capture_output=True, text=True, timeout=30)
                check(p.returncode != 0 and "PARAM_SCALES" in p.stderr and p.stdout == "",
                      "%s writes nothing for a scale word that is not the contract's: rc %d %r"
                      % (source, p.returncode, p.stderr[-200:]))
            else:
                check(0, "%s builds with a renamed word, to refuse it when it runs: %s" % (source, built.stderr[-300:]))
        swapped = text.replace("OMX_PARAM_SCALES_LOG = 1", "OMX_PARAM_SCALES_LOG = 2").replace(
            "OMX_PARAM_SCALES_STEPPED = 2", "OMX_PARAM_SCALES_STEPPED = 1")
        check(swapped != text, "positive control: the scratch header's scales were swapped")
        with open(os.path.join(scratch, "omxcontract", "omx_contract_limits.h"), "w") as f:
            f.write(swapped)
        for source in (JSON_GEN, OWN_GEN):
            built = build_gen(scratch, os.path.join(tmp, "gen-swapped"), source)
            check(built.returncode != 0 and "PARAM_SCALES" in built.stderr,
                  "%s refuses scales the contract orders otherwise: rc %d %s" % (source, built.returncode, built.stderr[-300:]))

        # a scratch qualification domain (plugin-qualify's document, read through the loader) whose latency methods have a
        # word more: the probe schema the generator writes has it too; a domain without the item is refused by name
        built = build_gen(os.path.dirname(os.path.dirname(header())), os.path.join(tmp, "gen-domain"), OWN_GEN)
        check(built.returncode == 0, "the schema generator builds against the loader: %s" % built.stderr[-400:])
        if built.returncode == 0:
            item = "QUALIFICATION_MEASUREMENT_LATENCY_METHODS"
            have = qualification_source.words(item)
            check(gen_methods(os.path.join(tmp, "gen-domain"), qualification_source.fixture(tmp, None, "as-installed")) == have,
                  "the probe schema's latency methods are the installed domain's %s" % have)

            def grow(doc):
                words = doc["components"]["schemas"][item]["oneOf"]
                # the loader holds a word's x-code to its index: the new word takes the next one
                words.append({"const": "x-onset", "title": "xOnset", "x-code": len(words), "x-text": "x"})
            grown = qualification_source.fixture(tmp, grow, "grown")
            methods = gen_methods(os.path.join(tmp, "gen-domain"), grown)
            check(methods is not None and methods[-1:] == ["x-onset"],
                  "a word the domain adds to the latency methods is in the probe schema: %s" % methods)

            def drop(doc):
                del doc["components"]["schemas"][item]
            bare = qualification_source.fixture(tmp, drop, "bare")
            p = subprocess.run([os.path.join(tmp, "gen-domain"), "probe-schema", os.path.join(ROOT, "protocol", "probe-output.schema.in")],
                               capture_output=True, text=True, timeout=30, env=dict(os.environ, OMX_CONTRACT_PATH=":".join([os.path.join(ROOT, "contract.d"), bare] + qualification_source.search_path())))  # the probe and plugin-db domains are the installed ones
            check(p.returncode != 0 and p.stdout == "" and item in p.stderr,
                  "the generator refuses a domain that lacks %s, by name: rc %d %r" % (item, p.returncode, p.stderr[-200:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("contract: %s" % ("FAILED (%d)" % failures if failures else "ok"))
    return 1 if failures else 0


sys.exit(main())
