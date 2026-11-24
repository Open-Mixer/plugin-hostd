# SPDX-License-Identifier: GPL-3.0-or-later
# The files of a tree, for the tests that look for a name or a copy across the repository. git's list when git answers;
# when it answers nothing (a CI container refuses a checkout another user owns, or the tree is not a checkout), every
# file under the tree but .git. The walk can only add files (build outputs, generated trees), so a test that looks for
# something absent can fail wrongly on it but never pass wrongly; an empty list is never returned for a tree with files.
import os
import subprocess


def tracked(root, untracked=False):
    """the files of root, relative to it: git ls-files (with untracked=True also the untracked files git does not
    ignore), else a walk of root without .git (a directory in a checkout, a file in a worktree)"""
    cmd = ["git", "-C", root, "ls-files", "-z"] + (["-co", "--exclude-standard"] if untracked else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip("\0"):
        return [f for f in p.stdout.split("\0") if f]
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        out += [os.path.relpath(os.path.join(base, f), root) for f in files if f != ".git"]
    return out
