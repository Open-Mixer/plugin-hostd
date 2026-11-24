# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""A descriptions store of its own for a test (omx-panel docs/descriptions-store.md), written with the installed command.

The test builds of the daemon read the store the directory PLUGIN_HOSTD_TEST_DESCRIPTIONS_STORE names (src/main.c,
OMX_QUALIFICATION_TEST_STORE): base.sqlite, system.sqlite and user.sqlite in it, the installed contract directory for
the words. An entry is put with omx-panel-store, the store's own writer, into the layer of the effective uid; nothing
here writes the SQLite itself, so the test reads what the writer wrote. The base is an empty one, built by the command.
"""
import json, os, shutil, subprocess, tempfile

CMD = os.environ.get("OMX_PANEL_STORE", "omx-panel-store")
SEAM = "PLUGIN_HOSTD_TEST_DESCRIPTIONS_STORE"


def run(args, stdin=None, env=None):
    """the command; (status, stdout, stderr)"""
    # no inherited place: the Makefile's OMX_CONTRACT_PATH is a list for this tree's own programs, and the command takes
    # one directory there; with none it reads the installed contract directory, which holds the panel domain
    e = {k: v for k, v in os.environ.items() if not k.startswith("OMX_PANEL_STORE_") and k != "OMX_CONTRACT_PATH"}
    e.update(env or {})
    r = subprocess.run([CMD] + args, input=stdin, capture_output=True, text=True, env=e, timeout=30)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def have_command():
    """whether the store's command runs here"""
    try:
        return run(["rules"])[0] == 0
    except OSError:
        return False


class Store:
    """a directory holding the three layers; base is built empty unless base=False (no store installed)"""

    def __init__(self, base=True):
        self.dir = tempfile.mkdtemp(prefix="plugin-hostd-descriptions.")
        self.base = os.path.join(self.dir, "base.sqlite")
        self.system = os.path.join(self.dir, "system.sqlite")
        self.user = os.path.join(self.dir, "user.sqlite")
        if base:
            status, _, err = run(["build", "--out", self.base, "--built-from", "b" * 40], stdin="[]")
            if status != 0:
                raise RuntimeError("omx-panel-store build: %s" % err)
        self.rules = int(run(["rules"])[1])

    def places(self):
        """the command's places for this store: what a writer the test stands in for is given"""
        return {"OMX_PANEL_STORE_BASE": self.base, "OMX_PANEL_STORE_SYSTEM": self.system, "OMX_PANEL_STORE_USER": self.user}

    def daemon_env(self):
        """the test daemon's seam"""
        return {SEAM: self.dir}

    def source(self, fmt, path):
        """omx_panel_store_source of the plugin as installed: the LV2 bundle directory, the CLAP descriptor file"""
        status, out, err = run(["source", "--format", fmt, "--path", path])
        if status != 0:
            raise RuntimeError("omx-panel-store source: %s" % err)
        return out

    def put(self, sha256, fmt, uri, source, groups=None):
        """a derived entry of the key; groups a list of (symbol, name, [port symbols]) makes a grouped verdict"""
        entry = {"edited": 0, "made_by": "plugin-hostd test", "rules": self.rules, "source": source, "family": "eq",
                 "fingerprint": "f" * 64, "body": {"family": "eq", "sections": []}, "groups": {"repeated": []},
                 "refused": None, "controls": [], "verdict": None}
        if groups is not None:
            entry["verdict"] = {"outcome": "grouped", "reason": None, "groups": [
                {"symbol": s, "name": n, "display_priority": k + 1, "rule": "name", "declared": 0, "ports": p}
                for k, (s, n, p) in enumerate(groups)]}
        status, _, err = run(["put", "--sha256", sha256, "--format", fmt, "--uri", uri], stdin=json.dumps(entry),
                             env=self.places())
        if status != 0:
            raise RuntimeError("omx-panel-store put: %s" % err)

    def remove(self, sha256, fmt, uri):
        status, _, err = run(["remove", "--sha256", sha256, "--format", fmt, "--uri", uri], env=self.places())
        if status != 0:
            raise RuntimeError("omx-panel-store remove: %s" % err)

    def layer(self):
        """the layer a writer of this uid writes: system as root, user otherwise"""
        return "system" if os.geteuid() == 0 else "user"

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)
