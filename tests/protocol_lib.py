#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# The shell protocol client plugin-hostd-tests ships (tests/lib/protocol.sh) against a peer that answers in NUL-ended
# replies, split across writes, then its sabotage: a copy that frames by newline instead of NUL must fail the same
# checks, so the checks can tell a client that frames wrongly. The Python client, plugin_hostd_client, is the protocol
# owner's since plugin-hostd-protocol issue 45 (python3-plugin-hostd-client, tested there by tests/client_test.py): this
# tree holds NO copy of it (tests/lib), and the tests import the installed one, or PLUGIN_HOSTD_CLIENT_DIR's.
import os, re, socket, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")


def serve(srv, stop):
    """echo "resp <line>" as one reply, written in two pieces; "mute" is never answered; "bye" closes"""
    while not stop.is_set():
        try:
            c, _ = srv.accept()
        except OSError:
            return
        buf = b""
        while True:
            try:
                d = c.recv(4096)
            except OSError:
                break
            if not d:
                break
            buf += d
            while b"\0" in buf:
                line, buf = buf.split(b"\0", 1)
                if line == b"mute":
                    continue
                if line == b"bye":
                    c.close()
                    break
                reply = b"resp " + line + b"\0"
                c.sendall(reply[:3])
                time.sleep(0.02)
                c.sendall(reply[3:])
        c.close()


def shell(lib, port, script):
    """a bash that opens the peer on descriptor 3, sources `lib` and runs `script`; its stdout, stderr and status"""
    body = 'exec 3<>/dev/tcp/127.0.0.1/%d\n. %s\n%s' % (port, lib, script)
    p = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=30)
    return p.stdout, p.stderr, p.returncode


def check_shell(lib, port, failures):
    out, _, rc = shell(lib, port, 'PROTOCOL_TIMEOUT=2; send "add x 0"; protocol_send 3 2 "a b"')
    if out != "resp add x 0\nresp a b\n":
        failures.append("shell send: %r" % out)
    _, _, rc = shell(lib, port, 'protocol_expect 3 2 "ping" "resp ping"')
    if rc != 0:
        failures.append("shell expect of the right reply returned %d" % rc)
    _, err, rc = shell(lib, port, 'protocol_expect 3 2 "ping" "resp pong"')
    if rc == 0 or "resp ping" not in err:
        failures.append("shell expect of the wrong reply returned %d, said %r" % (rc, err))
    with tempfile.NamedTemporaryFile("w", suffix=".log") as log:
        _, _, rc = shell(lib, port, 'protocol_wait_ready %s 2' % log.name)
        if rc == 0:
            failures.append("a log without the marker was ready")
        log.write("starting\nplugin-hostd ready!\n")
        log.flush()
        _, _, rc = shell(lib, port, 'protocol_wait_ready %s 2' % log.name)
        if rc != 0:
            failures.append("a log with the marker was not ready")


def no_copy(failures):
    """the Python client lives in plugin-hostd-protocol: a copy here would drift from the one every consumer imports"""
    copy = os.path.join(LIB, "plugin_hostd_client.py")
    if os.path.exists(copy):
        failures.append("a copy of the protocol's Python client is still here: " + os.path.relpath(copy, HERE))
    try:
        d = os.environ.get("PLUGIN_HOSTD_CLIENT_DIR")
        if d:
            sys.path.insert(0, d)
        import plugin_hostd_client  # noqa: F401  python3-plugin-hostd-client
    except ImportError as e:
        failures.append("plugin_hostd_client does not import (install python3-plugin-hostd-client, or PLUGIN_HOSTD_CLIENT_DIR): %s" % e)


def run(libsh, port, failures):
    check_shell(libsh, port, failures)
    no_copy(failures)


def main():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port = srv.getsockname()[1]
    stop = threading.Event()
    for _ in range(8):
        threading.Thread(target=serve, args=(srv, stop), daemon=True).start()
    good = []
    run(os.path.join(LIB, "protocol.sh"), port, good)
    if good:
        print("FAIL the clients:", *good, sep="\n  ")
        return 1
    print("ok: the shell client frames by NUL, splits replies, times out and closes; the Python client is the protocol's, no copy here")
    # sabotage: frame by newline, and the same checks must fail
    with tempfile.TemporaryDirectory() as d:
        sh = open(os.path.join(LIB, "protocol.sh")).read().replace("'%s\\0'", "'%s\\n'").replace("-d ''", "-d $'\\n'")
        if sh == open(os.path.join(LIB, "protocol.sh")).read():
            print("FAIL the sabotage changed nothing")
            return 1
        open(os.path.join(d, "protocol.sh"), "w").write(sh)
        bad_sh = []
        check_shell(os.path.join(d, "protocol.sh"), port, bad_sh)
        if not bad_sh:
            print("FAIL a client that frames by newline passed: shell %r" % bad_sh)
            return 1
    print("ok: a client that frames by newline fails the same checks")
    stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
