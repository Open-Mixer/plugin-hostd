# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# Scratch contract directories for the tests that hand the probe and the generator a test entry (OMX_CONTRACT_PATH): this
# checkout's contract.d holds the machine and qualification domains together, and the loader reads the first directory
# that holds a domain, so an arm that removes or changes one domain needs the others from directories that do not also
# hold it. domain_only copies one domain of this checkout; installed_without is the installed contract directory (the
# probe domain and the pin domain of plugin-hostd-protocol, plugin-db's domain, the term domains) without the domains
# under test.
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_CONFIG = os.environ.get("PKG_CONFIG", "pkg-config")


def installed():
    return subprocess.run([PKG_CONFIG, "--variable=contractdir", "omx-contract"], capture_output=True, text=True).stdout.strip()


def domain_only(tmp, name, source=None):
    """a scratch contract directory holding the domain <name> of <source> (this checkout's contract.d) and no other"""
    out = os.path.join(tmp, name + "-only")
    if not os.path.isdir(out):
        shutil.copytree(os.path.join(source or os.path.join(ROOT, "contract.d"), name), os.path.join(out, name))
    return out


def installed_without(tmp, hidden):
    """a view of the installed contract directory (a symlink per entry) without the domains named in hidden"""
    view = os.path.join(tmp, "installed-without-" + "-".join(sorted(hidden)))
    if not os.path.isdir(view):
        os.makedirs(view)
        base = installed()
        for e in sorted(os.listdir(base)) if base and os.path.isdir(base) else []:
            if e not in hidden:
                os.symlink(os.path.join(base, e), os.path.join(view, e))
    return view
