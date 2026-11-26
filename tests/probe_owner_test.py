#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/probe_owner_test.py: the probe words (reasons, outcomes, steps, signals) are plugin-hostd-protocol's domain `probe`
(contract.d/probe there, shipped by plugin-hostd-protocol-contract), and this tree reads them from there (sorting pass V8):
(a) golden: probe_words_open and probe_signal_word, over the protocol package's domain, give the thirteen golden signal
    words and the word for any other (tests/probe_signal_word.c, built from this tree's sources);
(b) the old source is gone: this tree holds no contract.d/probe, no include/plugin-hostd/probe_codes.h, no install or check
    rule for them, and plugin-hostd-contract ships no probe domain; src/probe_words.h includes the header protocol installs
    (the compile finds <plugin-hostd/probe_codes.h> in the protocol include directory alone);
(c) sabotage: a temporary directory holding the domain with SIGSEGV changed, first on OMX_CONTRACT_PATH, gives the changed word at
    the call;
(d) packaging: the spec and debian/control name plugin-hostd-protocol (-devel, -contract), whose domain plugin-hostd-protocol
    carries the probe words (V16), by name and with no typed floor (the devel wave of 2026-11-24).

Environment: PROTOCOL_CONTRACT_DIR (the protocol package's contract directory; default pkg-config's contractdir of omx-contract),
PROTOCOL_HEADER (protocol.h of plugin-hostd-protocol), DOMAIN_CFLAGS, DOMAIN_LIBS, CC. Exit 0 all green, 1 a FAIL line."""
import json, os, re, shlex, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failed = 0
GOLDEN = "SIGSEGV SIGABRT SIGBUS SIGFPE SIGILL SIGKILL SIGTERM SIGXCPU SIGXFSZ SIGSYS SIGPIPE SIGINT SIGHUP".split()


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def source_dir():
    d = os.environ.get("PROTOCOL_CONTRACT_DIR") or run(["pkg-config", "--variable=contractdir", "omx-contract"]).stdout.strip()
    return d or "/usr/share/omx-contract/contract.d"


def main():
    header = os.environ.get("PROTOCOL_HEADER", "/usr/include/plugin-hostd-protocol/plugin-hostd/protocol.h")
    proto = os.path.dirname(os.path.dirname(header))
    cflags = os.environ.get("DOMAIN_CFLAGS") or run(["pkg-config", "--cflags", "libomx-domain"]).stdout.strip()
    libs = os.environ.get("DOMAIN_LIBS") or run(["pkg-config", "--libs", "libomx-domain"]).stdout.strip()
    src = source_dir()
    with tempfile.TemporaryDirectory() as tmp:
        exe = os.path.join(tmp, "probe_signal_word")
        cc = shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Werror", "-std=gnu99", "-D_GNU_SOURCE", "-Isrc", "-I" + proto,
              "-o", exe, "tests/probe_signal_word.c", "src/probe_words.c", "src/domain_words.c"]
        # (b) this tree's include directory is left out: the header is the one protocol installs
        b = run(cc + shlex.split(cflags) + shlex.split(libs))
        check(b.returncode == 0, "(b) src/probe_words.h compiles against the header protocol installs alone %s" % b.stderr.strip()[-200:])
        # (a)
        want = " ".join("%s=%s" % (n, n) for n in GOLDEN) + " other=SIGNAL slots=14"
        r = subprocess.run([exe, src], cwd=ROOT, capture_output=True, text=True) if b.returncode == 0 else None
        check(r is not None and r.stdout.strip() == want, "(a) the call over protocol's domain gives the golden words %s" % (r.stdout + r.stderr if r else ""))
        # (c)
        scratch = os.path.join(tmp, "x")
        shutil.copytree(os.path.join(src, "probe"), os.path.join(scratch, "probe"))
        p = os.path.join(scratch, "probe", "probe.json")
        d = json.load(open(p))
        for w in d["components"]["schemas"]["PROBE_SIGNALS"]["oneOf"]:
            if w["const"] == "SIGSEGV":
                w["const"] = "SIGSEGV-x"
        json.dump(d, open(p, "w"), indent=2)
        r = subprocess.run([exe, scratch + ":" + src], cwd=ROOT, capture_output=True, text=True) if b.returncode == 0 else None
        check(r is not None and "SIGSEGV=SIGSEGV-x " in r.stdout, "(c) a changed signal word is the call's result")
    # (b) the old source
    for rel in ("contract.d/probe", "include/plugin-hostd/probe_codes.h"):
        check(not os.path.exists(os.path.join(ROOT, rel)), "(b) %s is gone from this tree" % rel)
    mk = open(os.path.join(ROOT, "Makefile")).read()
    check("install_probe_domain" not in mk and "check-probe-codes" not in mk, "(b) the Makefile has no install or check rule for the probe domain")
    check("contract.d/probe" not in open(os.path.join(ROOT, "debian", "plugin-hostd-contract.install")).read()
          and "contract.d/probe/" not in open(os.path.join(ROOT, "debian", "plugin-hostd-contract.install")).read().replace("usr/share/omx-contract/contract.d/probe", "X"),
          "(b) plugin-hostd-contract ships no probe domain")
    # (d)
    spec = open(os.path.join(ROOT, "packaging", "plugin-hostd.spec")).read()
    control = open(os.path.join(ROOT, "debian", "control")).read()
    for name in ("plugin-hostd-protocol-contract", "plugin-hostd-protocol-devel"):
        check(re.search(r"^BuildRequires: %s$" % name, spec, re.M) is not None
              and re.search(r"^Requires: %s$" % name, spec, re.M) is not None, "(d) the spec requires and builds against %s, by name" % name)
    check(re.search(r"(^|[ ,])plugin-hostd-protocol-contract( <!nocheck>)?,", control, re.M) is not None
          and re.search(r"(^|[ ,])libplugin-hostd-protocol-dev,", control, re.M) is not None,
          "(d) debian/control names plugin-hostd-protocol-contract and -dev, by name")
    check(not re.search(r"plugin-hostd-protocol[a-z0-9-]* \(?>=", spec.split("%changelog")[0] + control), "(d) no floor of protocol is typed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
