#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/bounded_install_test.py [<root>]: a package manager's step in CI is bounded, never a silent hang to the job's
timeout-minutes (#76's bench and #72's harness each hung on a channel mirror until the job was cancelled).

- the scan: every apt-get, apt or dnf call in .github/workflows that fetches (install, update, upgrade, download,
  builddep, build-dep, makecache) runs through tools/bounded-install.sh; a planted bare call is seen.
- the wrapper: a command that hangs on a stub mirror (a server that accepts and never answers) turns red within its
  attempts' bound, naming the command and the mirror the sources name; a command that fails fast is red at once,
  with no retry; one that succeeds is green.
- the sabotage: the wrapper with its timeout taken out hangs on the same stub, so the bound is the wrapper's.
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAPPER = os.path.join(ROOT, "tools", "bounded-install.sh")
FETCH = re.compile(r"\b(apt-get|apt|dnf5?)\s+(?:-\S+\s+|--\S+\s+)*(install|update|upgrade|download|builddep|build-dep|makecache)\b")
failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def scan(root):
    """every fetching apt or dnf call of the workflows that is not run through bounded-install.sh, as 'path:line'"""
    found = []
    wf = os.path.join(root, ".github", "workflows")
    for name in sorted(os.listdir(wf)) if os.path.isdir(wf) else []:
        for n, line in enumerate(open(os.path.join(wf, name)), 1):
            code = line.split("#", 1)[0] if line.lstrip().startswith("#") else line
            if FETCH.search(code) and "bounded-install" not in code:
                found.append("%s:%d" % (name, n))
    return found


def hanging_mirror():
    """a server that accepts every connection and never answers: (url, stop)"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    held = []
    stop = threading.Event()

    def serve():
        s.settimeout(0.2)
        while not stop.is_set():
            try:
                held.append(s.accept()[0])
            except OSError:
                pass

    threading.Thread(target=serve, daemon=True).start()

    def close():
        stop.set()
        for c in held:
            c.close()
        s.close()
    return "http://127.0.0.1:%d/debian/" % s.getsockname()[1], close


def run(wrapper, argv, sources, limit):
    env = dict(os.environ, BOUNDED_INSTALL_TIMEOUT_S="2", BOUNDED_INSTALL_RETRIES="2", BOUNDED_INSTALL_SOURCES=sources)
    started = time.monotonic()
    try:
        p = subprocess.run(["sh", wrapper] + argv, capture_output=True, text=True, env=env, timeout=limit)
        return p.returncode, p.stdout + p.stderr, time.monotonic() - started
    except subprocess.TimeoutExpired:
        return None, "", time.monotonic() - started


def main():
    seen = scan(ROOT)
    check(not seen, "every fetching apt or dnf call of the workflows runs through tools/bounded-install.sh%s"
          % ("" if not seen else ": not " + ", ".join(seen)))
    plant = tempfile.mkdtemp(prefix="bounded-install.")
    try:
        os.makedirs(os.path.join(plant, ".github", "workflows"))
        open(os.path.join(plant, ".github", "workflows", "x.yml"), "w").write(
            "          apt-get update -qq\n          DEBIAN_FRONTEND=noninteractive apt-get install -y x\n"
            "          dnf builddep -y x.spec\n          tools/bounded-install.sh dnf install -y x\n"
            "          dnf repoquery --installed x\n          # apt-get install y\n")
        check(scan(plant) == ["x.yml:1", "x.yml:2", "x.yml:3"], "the scan sees three planted bare calls and passes the "
              "bounded one, a query and a comment: %s" % scan(plant))
    finally:
        shutil.rmtree(plant, ignore_errors=True)

    if not os.path.isfile(WRAPPER):
        check(False, "tools/bounded-install.sh exists")
        return 1
    url, close = hanging_mirror()
    work = tempfile.mkdtemp(prefix="bounded-install.")
    try:
        sources = os.path.join(work, "stub.sources")
        open(sources, "w").write("Types: deb\nURIs: %s\nSuites: ./\n" % url)
        hang = ["curl", "-s", url]
        rc, out, took = run(WRAPPER, hang, sources, 60)
        check(rc == 1 and took < 20, "a command that hangs on the stub mirror is red after its three attempts: rc %s in %.1f s"
              % (rc, took))
        check("curl -s %s" % url in out and "3 attempts" in out and "timed out" in out,
              "the red names the command, its attempts and the timeout: %r" % out[-300:])
        check(out.count(url) >= 2 and "::error::" in out, "the red names the mirror the sources name, as an error line")
        rc, out, took = run(WRAPPER, ["sh", "-c", "echo nothing provides x >&2; exit 100"], sources, 60)
        check(rc == 1 and took < 5 and "attempt 2" not in out, "a command that fails fast is red at once, not retried: rc %s, "
              "%.1f s" % (rc, took))
        rc, out, took = run(WRAPPER, ["true"], sources, 60)
        check(rc == 0, "a command that succeeds is green")
        # an apt attempt killed by its timeout can leave dpkg interrupted, which the next attempt refuses at once ("dpkg was
        # interrupted, you must manually run 'dpkg --configure -a'", #81's own run on a slow runner): before trying again
        # the wrapper finishes dpkg's work. Stub apt-get and dpkg: the first apt-get hangs, the second succeeds only if
        # dpkg --configure -a ran in between.
        stubs = os.path.join(work, "bin")
        os.makedirs(stubs)
        state = os.path.join(work, "state")
        open(os.path.join(stubs, "apt-get"), "w").write(
            "#!/bin/sh\nif [ ! -e %s.hung ]; then touch %s.hung; sleep 30; fi\n[ -e %s.configured ] || "
            "{ echo \"E: dpkg was interrupted\" >&2; exit 100; }\nexit 0\n" % (state, state, state))
        open(os.path.join(stubs, "dpkg"), "w").write(
            "#!/bin/sh\n[ \"$*\" = \"--configure -a\" ] && touch %s.configured\nexit 0\n" % state)
        for f in ("apt-get", "dpkg"):
            os.chmod(os.path.join(stubs, f), 0o755)
        env_path = os.environ["PATH"]
        os.environ["PATH"] = stubs + ":" + env_path
        try:
            rc, out, took = run(WRAPPER, ["apt-get", "install", "-y", "x"], sources, 60)
        finally:
            os.environ["PATH"] = env_path
        check(rc == 0 and os.path.exists(state + ".configured"), "an apt attempt killed by its timeout is followed by "
              "dpkg --configure -a before the next one, which then succeeds: rc %s, %r" % (rc, out[-200:]))
        sabotaged = os.path.join(work, "bounded-install.sh")
        text = open(WRAPPER).read()
        check("timeout -k" in text, "the wrapper bounds each attempt with timeout -k")
        open(sabotaged, "w").write(re.sub(r"timeout -k \S+ \S+ ", "", text))
        rc, out, took = run(sabotaged, hang, sources, 12)
        check(rc is None, "sabotage: with its timeout taken out the wrapper hangs on the stub mirror (still running at 12 s)")
    finally:
        close()
        shutil.rmtree(work, ignore_errors=True)
    print("bounded install: %s" % ("ok" if not failures else "%d failed" % len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
