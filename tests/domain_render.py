# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The render of plugin_hostd_vocabulary.h from this tree's domains, as the Makefile's check-rendered runs it, over any
# contract.d: omx-contract's installer stages the package plugin-hostd (no data file), and omx-contract renders it with each
# domain read by --with-domain (repeated), which rebuilds the domain's data files into that package. Used by the call-level tests of the domains
# plugin-hostd/grouping (tests/grouping_domain.py) and plugin-hostd/history (tests/history_domain.py).
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS = ["plugin-hostd/grouping", "plugin-hostd/history"]
OWNER_DOMAINS = ["machine", "qualification"]


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        sys.exit("%s is unset (run the test through its make target)" % name)
    return v


def render(contract_d, out):
    """Render the vocabulary of the domains under <contract_d> into <out>: (exit status, output)."""
    tmp = tempfile.mkdtemp(prefix="vocabulary-render-")
    try:
        pkg = os.path.join(tmp, "dir")
        # the package plugin-hostd as the Makefile's check-rendered stages it: a MANIFEST.json with no file, naming the owner's
        # top-level domains, which are installed beside it
        for d in OWNER_DOMAINS:
            subprocess.run(["sh", env("INSTALL_CONTRACT_DIR"), "--domain", os.path.join(ROOT, "contract.d", d), pkg,
                            "plugin-hostd"],
                           check=True, capture_output=True)
        subprocess.run(["sh", env("INSTALL_CONTRACT_DIR"), "--owner", "plugin-hostd", "0.0.0", "3", pkg] + OWNER_DOMAINS,
                       check=True, capture_output=True)
        path = pkg + ":" + subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True,
                                          text=True).stdout.strip()
        withs = [a for d in DOMAINS for a in ("--with-domain", os.path.join(contract_d, d))]
        r = subprocess.run(env("OMX_CONTRACT", "omx-contract").split() + ["render", "--target", "c", "--package",
                           "plugin-hostd", "--installed"] + withs + ["--out", out], capture_output=True, text=True,
                           env=dict(os.environ, OMX_CONTRACT_PATH=path))
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(tmp)


def scratch_include():
    """A scratch include directory holding a copy of include/plugin-hostd/, for a render to overwrite."""
    inc = tempfile.mkdtemp(prefix="vocabulary-include-")
    shutil.copytree(os.path.join(ROOT, "include", "plugin-hostd"), os.path.join(inc, "plugin-hostd"))
    return inc
