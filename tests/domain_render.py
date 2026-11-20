# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The render of plugin_hostd_vocabulary.h from this tree's domains, as the Makefile's check-rendered runs it, over any
# contract.d: tools/domain-data.mjs rebuilds the data files of the domains beside data/, omx-contract's installer stages
# them as the package plugin-hostd, and omx-contract renders that package. Used by the call-level tests of the domains
# plugin-hostd/grouping (tests/grouping_domain.py) and plugin-hostd/history (tests/history_domain.py).
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS = ["plugin-hostd/grouping", "plugin-hostd/history"]


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        sys.exit("%s is unset (run the test through its make target)" % name)
    return v


def render(contract_d, out):
    """Render the vocabulary of the domains under <contract_d> into <out>: (exit status, output)."""
    tmp = tempfile.mkdtemp(prefix="vocabulary-render-")
    try:
        stage = os.path.join(tmp, "stage", "data")
        shutil.copytree(os.path.join(ROOT, "data"), stage)
        r = subprocess.run(["node", os.path.join(ROOT, "tools", "domain-data.mjs"), env("OMX_CONTRACT_CLIDIR"), stage,
                            contract_d] + DOMAINS, capture_output=True, text=True)
        if r.returncode:
            return r.returncode, r.stderr
        pkg = os.path.join(tmp, "dir")
        subprocess.run(["sh", env("INSTALL_CONTRACT_DIR"), "plugin-hostd", "0.0.0", "3", stage, pkg, "data"],
                       check=True, capture_output=True)
        path = pkg + ":" + subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True,
                                          text=True).stdout.strip()
        r = subprocess.run(env("OMX_CONTRACT", "omx-contract").split() + ["render", "--target", "c", "--package",
                           "plugin-hostd", "--installed", "--out", out], capture_output=True, text=True,
                           env=dict(os.environ, OMX_CONTRACT_PATH=path))
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(tmp)


def scratch_include():
    """A scratch include directory holding a copy of include/plugin-hostd/, for a render to overwrite."""
    inc = tempfile.mkdtemp(prefix="vocabulary-include-")
    shutil.copytree(os.path.join(ROOT, "include", "plugin-hostd"), os.path.join(inc, "plugin-hostd"))
    return inc
