# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The working directory every jalv these tools start stands in.

jalv 1.8 makes its plugin state directory with a relative mkdtemp("jalvXXXXXX") (jalv 1.8.0 src/jalv.c:872), so in
its working directory, and removes it only at a clean exit. (jalv 1.6, and Zynthian's asyncli fork of it, uses an
absolute /tmp/jalv-XXXXXX instead, which no working directory moves.) The tools end their jalvs with
SIGTERM and then SIGKILL, so a jalv started where the caller stands left one jalvXXXXXX there per run: a user's home
when the tool was started from it. This directory is made on first use and removed when the tool exits; on SIGINT,
SIGTERM or SIGHUP left at their default it is removed first and the signal then ends the tool as it would have. A
handler a tool installed itself is kept (Python's SIGINT raises KeyboardInterrupt), and the exit it leads to runs the
removal.

Loaded by path beside the tool that uses it, so a copy of a tool on a device carries this file with it."""
import atexit
import os
import shutil
import signal
import tempfile

_dir = None


def _remove():
    if _dir is not None:
        shutil.rmtree(_dir, ignore_errors=True)


def _on_signal(sig, _frame):
    _remove()
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)


def jalv_cwd():
    """the tool's scratch directory for its jalvs, made on first use"""
    global _dir
    if _dir is None:
        _dir = tempfile.mkdtemp(prefix="jalv-cwd-")
        atexit.register(_remove)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                if signal.getsignal(sig) == signal.SIG_DFL:
                    signal.signal(sig, _on_signal)
            except ValueError:
                pass  # not the main thread: the exit still removes it
    return _dir
