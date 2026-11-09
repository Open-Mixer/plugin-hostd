#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tools/zynthian/voices-cores.py says why it failed (#8): a private JACK server that does not start names its exit status
and its last log lines, a host that never listens names its exit status and host.log, and a row that fails for a reason
no handler listed (a missing key) still carries the kind of error. Run against fakes of jackd and jack_lsp on PATH."""
import argparse, importlib.util, io, os, stat, sys, tempfile, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("voices_cores", os.path.join(HERE, "..", "tools", "zynthian", "voices-cores.py"))
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)


def check(cond, msg):
    if not cond:
        print("FAIL " + msg)
        sys.exit(1)
    print("ok   " + msg)


def script(path, body):
    with open(path, "w") as f:
        f.write("#!/bin/sh\n" + body + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


with tempfile.TemporaryDirectory() as d:
    bindir = os.path.join(d, "bin")
    os.makedirs(bindir)
    script(os.path.join(bindir, "jackd"), "echo 'cannot open the dummy driver: boom' >&2; exit 3")
    script(os.path.join(bindir, "jack_lsp"), "exit 1")
    os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
    out = os.path.join(d, "out")
    os.makedirs(out)
    a = argparse.Namespace(rate=48000, frames=256, alsa="", server_wait=1)
    try:
        vc.server(a, out)
        check(False, "a private server that exits does not start")
    except SystemExit as e:
        msg = str(e)
        check("boom" in msg and "exit 3" in msg, "the failure names the exit status and the server's last line: %s" % msg)
    check(vc.tail_of(os.path.join(out, "absent.log")).startswith("(no absent.log"), "a missing log says so")
    open(os.path.join(out, "empty.log"), "w").close()
    check("empty" in vc.tail_of(os.path.join(out, "empty.log")), "an empty log says so")
print("voices-cores diagnostics ok")
