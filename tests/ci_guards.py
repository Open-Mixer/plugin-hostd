# SPDX-License-Identifier: GPL-3.0-or-later
# A step a runner may be unable to run fails where it cannot run it. The JACK scenarios need a private user and pid
# namespace with its own /proc: every `if unshare ...; then` in a workflow has an else branch, and that branch exits 1,
# so a runner that refuses the namespace fails the job instead of passing it with a warning (#107). A step with no
# else at all is an error of its own: the shell takes it as a quiet skip.
# Usage: ci_guards.py [root]. The scan proves it can see a planted warn-only branch before it trusts an empty result.
import os, re, shutil, sys, tempfile

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IF_UNSHARE = re.compile(r"^(\s*)if unshare .*; then\s*$")


def workflow_files(root):
    d = os.path.join(root, ".github", "workflows")
    return [os.path.join(d, f) for f in sorted(os.listdir(d))] if os.path.isdir(d) else []


def branches(lines):
    """every (line number, else lines) of an `if unshare` at the same indent; else lines is None without an else"""
    out = []
    for n, line in enumerate(lines):
        m = IF_UNSHARE.match(line)
        if not m:
            continue
        indent = m.group(1)
        body, in_else = None, False
        for later in lines[n + 1:]:
            if later == indent + "fi" or later.startswith(indent + "fi "):
                break
            if later == indent + "else":
                body, in_else = [], True
            elif in_else:
                body.append(later.strip())
        out.append((n + 1, body))
    return out


def scan(root):
    """every finding as 'path:line what'"""
    found = []
    for path in workflow_files(root):
        lines = open(path).read().split("\n")
        for n, body in branches(lines):
            where = "%s:%d" % (os.path.relpath(path, root), n)
            if body is None:
                found.append("%s an if unshare with no else: a runner that refuses the namespace skips the step quietly" % where)
            elif not any(b == "exit 1" or b.startswith("exit 1 ") for b in body):
                found.append("%s the else branch of an if unshare does not exit 1: a runner that refuses the namespace passes with a warning" % where)
    return found


# A pull request's older run is cancelled when a newer push supersedes it, and nothing else ever is: ci.yml and fuzz.yml
# carry a concurrency group whose cancel-in-progress is true on a pull request only, release.yml (a tag publishes from
# it) carries none. A workflow-level paths: filter on ci.yml or fuzz.yml would leave a required check that never reports,
# so the filters are the changes job's and the trigger has none.
CANCEL_LINE = "cancel-in-progress: ${{ github.event_name == 'pull_request' }}"
PATHS_FILTER = re.compile(r"^ {4}paths(-ignore)?:", re.M)


def cancel_scan(root):
    """every finding as 'path what'"""
    found = []
    d = os.path.join(root, ".github", "workflows")
    for name in ("ci.yml", "fuzz.yml"):
        path = os.path.join(d, name)
        if not os.path.exists(path):
            continue
        text = open(path).read()
        if not re.search(r"^concurrency:", text, re.M) or CANCEL_LINE not in text:
            found.append("%s has no concurrency group that cancels on a pull request only (%s)" % (name, CANCEL_LINE))
        if PATHS_FILTER.search(text):
            found.append("%s filters its trigger by paths: a required check that never reports blocks the pull request; use the changes job" % name)
    release = os.path.join(d, "release.yml")
    if os.path.exists(release) and re.search(r"^\s*(concurrency|cancel-in-progress):", open(release).read(), re.M):
        found.append("release.yml has a concurrency group: a run on a tag must never be cancelled")
    return found


# The contract directory as installed is validated in ci.yml (#165): a step of the job that builds and tests runs
# `make check-contract-dir`, which is red without the omx-contract command, never a skip.
GATE_RUN = re.compile(r"^\s+run:\s*make check-contract-dir\s*$", re.M)


def gate_scan(root):
    """every finding as 'path what'"""
    path = os.path.join(root, ".github", "workflows", "ci.yml")
    text = open(path).read() if os.path.exists(path) else ""
    if not GATE_RUN.search(text):
        return ["ci.yml has no step that runs make check-contract-dir: a table the installed schema refuses ships unseen"]
    return []


# Two tiers (owner ruling 2026-11-09: heavy workflows on tags, pull requests quick): a pull request runs the plain tier
# and one package arm (fc44 x86_64, trixie amd64); `make sabotage` (36 minutes of the last green run), the release dry
# run and bookworm run on push to main, tags and dispatch. Each is red where a pull request would run it.
OFF_PR = "github.event_name != 'pull_request'"


def tier_scan(root):
    """every finding as 'path what'"""
    path = os.path.join(root, ".github", "workflows", "ci.yml")
    if not os.path.exists(path):
        return []
    lines = open(path).read().split("\n")
    found = []
    for n, line in enumerate(lines):
        if re.search(r"\bmake sabotage\b", line) and not line.lstrip().startswith("#"):
            # the step that holds it: back to its `- name:` or `- run:` line, its `if:` between there and here
            start = n
            while start > 0 and not re.match(r"^\s*- (name|run|uses):", lines[start]):
                start -= 1
            if not any(OFF_PR in l for l in lines[start:n]):
                found.append("ci.yml:%d make sabotage runs on a pull request: it belongs to push, tags and dispatch" % (n + 1))
    text = "\n".join(lines)
    m = re.search(r"^  release-dry-run:\n((?:    .*\n|\n)*)", text + "\n", re.M)
    if m and not re.search(r"^    if: .*" + re.escape(OFF_PR), m.group(1), re.M):
        found.append("ci.yml: release-dry-run runs on a pull request: it belongs to push, tags and dispatch")
    for n, line in enumerate(lines):
        if re.match(r"^\s*suite: \[", line):
            found.append("ci.yml:%d a suite matrix that a pull request runs whole: trixie alone on a pull request" % (n + 1))
    return found


def main():
    gate = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        wf = os.path.join(gate, ".github", "workflows")
        os.makedirs(wf)
        open(os.path.join(wf, "ci.yml"), "w").write("      - run: make test\n      # run: make check-contract-dir\n")
        missed = gate_scan(gate)
        open(os.path.join(wf, "ci.yml"), "w").write("      - name: x\n        run: make check-contract-dir\n")
        if len(missed) != 1 or gate_scan(gate):
            print("FAIL the gate scan misses a planted ci.yml without make check-contract-dir, or refuses one with it")
            return 1
    finally:
        shutil.rmtree(gate, ignore_errors=True)
    print("ok   the gate scan sees a planted ci.yml without make check-contract-dir and passes one with it")
    tmp = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        scratch = os.path.join(tmp, "t")
        os.makedirs(os.path.join(scratch, ".github", "workflows"))
        plant = ("      run: |\n          if unshare --user --map-root-user true; then\n            make test-jack\n          else\n"
                 "            echo \"::warning::skipped\"\n          fi\n"
                 "          if unshare --user true; then\n            make test-jack2\n          fi\n"
                 "          if unshare --user true; then\n            make x\n          else\n            echo no\n            exit 1\n          fi\n")
        open(os.path.join(scratch, ".github", "workflows", "ci.yml"), "w").write(plant)
        seen = scan(scratch)
        if len(seen) != 2 or "warning" not in seen[0] or "no else" not in seen[1]:
            print("FAIL the scan misses a planted branch: saw %s" % seen)
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ok   the scan sees a planted warn-only else and a planted missing else, and passes one that exits 1")
    bad = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        wf = os.path.join(bad, ".github", "workflows")
        os.makedirs(wf)
        open(os.path.join(wf, "ci.yml"), "w").write("on:\n  pull_request:\n    paths: [src/]\nconcurrency:\n  cancel-in-progress: true\n")
        open(os.path.join(wf, "fuzz.yml"), "w").write("on:\n  pull_request:\n")
        open(os.path.join(wf, "release.yml"), "w").write("concurrency:\n  group: x\n")
        seen = cancel_scan(bad)
        if len(seen) != 4:
            print("FAIL the cancel scan misses a planted fault: saw %s" % seen)
            return 1
    finally:
        shutil.rmtree(bad, ignore_errors=True)
    print("ok   the cancel scan sees a planted paths filter, a missing group, a cancelling group and a release group")
    tiers = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        wf = os.path.join(tiers, ".github", "workflows")
        os.makedirs(wf)
        open(os.path.join(wf, "ci.yml"), "w").write(
            "jobs:\n  test:\n    steps:\n      - name: s\n        run: make sabotage\n"
            "  deb:\n    strategy:\n      matrix:\n        suite: [bookworm, trixie]\n"
            "  release-dry-run:\n    if: needs.changes.outputs.packages == 'true'\n    uses: ./x.yml\n")
        seen = tier_scan(tiers)
        open(os.path.join(wf, "ci.yml"), "w").write(
            "jobs:\n  test:\n    steps:\n      - name: s\n        if: %s\n        run: make sabotage\n"
            "  deb:\n    strategy:\n      matrix:\n        suite: ${{ fromJSON(github.event_name == 'pull_request' && '[\"trixie\"]' || '[\"bookworm\", \"trixie\"]') }}\n"
            "  release-dry-run:\n    if: needs.changes.outputs.packages == 'true' && %s\n    uses: ./x.yml\n" % (OFF_PR, OFF_PR))
        if len(seen) != 3 or tier_scan(tiers):
            print("FAIL the tier scan misses a planted heavy step on a pull request, or refuses a split one: saw %s" % seen)
            return 1
    finally:
        shutil.rmtree(tiers, ignore_errors=True)
    print("ok   the tier scan sees a planted sabotage, a whole suite matrix and a dry run on a pull request, and passes them split")
    failed = 0
    for f in tier_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   a pull request runs the plain tier and one package arm; sabotage, bookworm and the dry run on push, tags, dispatch")
    for f in cancel_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   ci.yml and fuzz.yml cancel a superseded pull request run only, release.yml never, no workflow paths filter")
    for f in gate_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   ci.yml validates the staged contract directory (make check-contract-dir)")
    for f in scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    n = sum(len(branches(open(p).read().split("\n"))) for p in workflow_files(ROOT))
    if not failed:
        print("ok   every if unshare in the workflows fails where the runner refuses the namespace (%d of them)" % n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
