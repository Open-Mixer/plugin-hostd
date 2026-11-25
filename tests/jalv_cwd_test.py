#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""A jalv these tools start leaves no state directory where the caller stands. jalv makes its state directory with a
relative mkdtemp("jalvXXXXXX") (jalv 1.8.0 src/jalv.c:872), in its working directory, and removes it only at a clean
exit; the tools end their jalvs with SIGTERM and then SIGKILL, so a run started from a home left one there per jalv.
Every jalv starts in tools/zynthian/jalv_scratch.py's directory instead, which goes when the tool ends, on a signal too.

Run against a jalv stand-in on PATH that makes the same relative directory and ignores SIGTERM, from a caller standing
in a private home, so the real one is never touched."""
import argparse, glob, importlib.util, os, re, signal, stat, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ZYN = os.path.join(ROOT, "tools", "zynthian")
FAKE_JALV = "#!/bin/sh\nmktemp -d jalvXXXXXX >/dev/null || exit 9\ntrap '' TERM\nwhile :; do sleep 1; done\n"
# where each tool starts its jalvs: an inline Popen, or the spawner its jalv argv goes through
SPAWN_SITES = [
    ("tools/zynthian/stress-pi5.py", r"subprocess\.Popen\(\[\"jalv\"[^\n]*\n[^\n]*\n[^\n]*"),
    ("tools/zynthian/instrument-proof.py", r"subprocess\.Popen\(\[\"jalv\"[^\n]*\n[^\n]*\n[^\n]*"),
    ("tools/zynthian/voices-cores.py", r"class proc_host:[\s\S]*?def pids"),
    ("bench/lib/bench.py", r"    def spawn\(self, argv, name[\s\S]*?return p\n"),
]
failed = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failed.append(msg)


def left(*dirs):
    return sorted(p for d in dirs for p in glob.glob(os.path.join(d, "**", "jalv??????"), recursive=True))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


with tempfile.TemporaryDirectory() as d:
    home, tmp, bindir, out = (os.path.join(d, n) for n in ("home", "tmp", "bin", "out"))
    for p in (home, tmp, bindir, out):
        os.makedirs(p)
    with open(os.path.join(bindir, "jalv"), "w") as f:
        f.write(FAKE_JALV)
    os.chmod(os.path.join(bindir, "jalv"), 0o755)
    env = dict(os.environ, HOME=home, TMPDIR=tmp, PATH=bindir + os.pathsep + os.environ["PATH"])

    # 1. voices-cores' proc_host (mixbus-bench and pools-bench start their jalvs through it): one jalv, stopped as the
    # tool stops it, from a caller standing in its home; then the caller exits
    caller = (
        "import argparse, importlib.util, os, sys, time\n"
        "spec = importlib.util.spec_from_file_location('vc', sys.argv[1]); vc = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(vc)\n"
        "srv = argparse.Namespace(env=dict(os.environ))\n"
        "h = vc.proc_host(argparse.Namespace(), srv, sys.argv[2])\n"
        "h.spawn(['jalv', '-n', 'inst_0', 'urn:x'])\n"
        "time.sleep(0.5)\n"
        "h.close()\n"
    )
    r = subprocess.run([sys.executable, "-I", "-c", caller, os.path.join(ZYN, "voices-cores.py"), out], cwd=home, env=env,
                       timeout=60)
    check(r.returncode == 0, "the proc_host caller ran (exit %d)" % r.returncode)
    check(left(home) == [], "a jalv proc_host stopped leaves no state directory in the caller's home: %s" % left(home))
    check(left(home, tmp) == [], "and none anywhere once the caller exited: %s" % left(home, tmp))

    # 2. the scratch directory goes with the caller when the caller is ended by SIGINT (Python's KeyboardInterrupt, whose
    # exit ends it by the signal), SIGTERM or SIGHUP, the signal then ending it as it would have; and at a plain exit
    for how in ("exit", "SIGINT", "SIGTERM", "SIGHUP"):
        caller = (
            "import importlib.util, os, signal, subprocess, sys, time\n"
            "spec = importlib.util.spec_from_file_location('js', sys.argv[1]); js = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(js)\n"
            "p = subprocess.Popen(['jalv', '-i', '-n', 'x', 'urn:x'], cwd=js.jalv_cwd(), start_new_session=True)\n"
            "time.sleep(0.5)\n"
            "os.killpg(p.pid, signal.SIGKILL); p.wait()\n"
            "if sys.argv[2] != 'exit':\n"
            "    os.kill(os.getpid(), getattr(signal, sys.argv[2])); time.sleep(5)\n"
        )
        # KeyboardInterrupt prints its traceback: not this test's output
        r = subprocess.run([sys.executable, "-I", "-c", caller, os.path.join(ZYN, "jalv_scratch.py"), how], cwd=home,
                           env=env, timeout=60, stderr=subprocess.DEVNULL if how == "SIGINT" else None)
        want = 0 if how == "exit" else -getattr(signal, how)
        check(r.returncode == want, "a caller ended by %s ends as it would have (%d, wants %d)" % (how, r.returncode, want))
        check(left(home, tmp) == [], "a killed jalv leaves nothing once its caller ended by %s: %s" % (how, left(home, tmp)))

    # 3. every jalv these tools start stands in the scratch directory
    for rel, pattern in SPAWN_SITES:
        sites = re.findall(pattern, open(os.path.join(ROOT, rel)).read())
        check(len(sites) == 1, "%s: its jalv spawn site is found" % rel)
        for site in sites:
            ok = "jalv_cwd()" in site and re.search(r"Popen\([\s\S]*\bcwd=", site) is not None
            check(ok, "%s: the jalv spawn stands in the scratch directory" % rel)

if failed:
    print("FAIL %d check(s)" % len(failed))
    sys.exit(1)
print("jalv cwd ok")
