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



# A staged dispatch builds every cell of its arch-matrix: the shared build-rpm.yml and build-deb.yml build the quick set
# alone (fc45 x86_64 rpm, trixie arm64 deb) for a staged run that passes no matrix input, so run 46109907808 (staged,
# arm off) built no trixie amd64 deb. Every release.yml job that calls one of them passes `matrix:` 'full' for a staged
# run: the literal full, or an expression that gives 'full' when inputs.staged is true.
SHARED_BUILD = re.compile(r"^\s+uses:\s*\S*/build-(rpm|deb)\.yml@")
STAGED_FULL = re.compile(r"^\s+matrix:\s*(['\"]?full['\"]?|\$\{\{\s*inputs\.staged(\s*==\s*true)?\s*&&\s*'full'\s*(\|\|.*)?\}\})\s*(#.*)?$")


def staged_matrix_scan(root):
    """every finding as 'release.yml:line what'"""
    path = os.path.join(root, ".github", "workflows", "release.yml")
    if not os.path.exists(path):
        return []
    lines = open(path).read().split("\n")
    found = []
    for n, line in enumerate(lines):
        m = SHARED_BUILD.match(line)
        if not m:
            continue
        job = []
        for later in lines[n + 1:]:
            if later.strip() and len(later) - len(later.lstrip()) <= 2:
                break
            job.append(later)
        if not any(STAGED_FULL.match(j) for j in job if not j.lstrip().startswith("#")):
            found.append("release.yml:%d the build-%s.yml call passes no matrix 'full' for a staged run: a staged dispatch "
                         "builds the quick set alone" % (n + 1, m.group(1)))
    return found

# Two tiers (owner ruling 2026-11-09: heavy workflows on tags, pull requests quick): a pull request runs the plain tier
# and one package arm (fc45 x86_64, trixie arm64); `make sabotage` (36 minutes of the last green run), the release dry
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


# A job tests the daemon of its own run: plugin-hostd and plugin-hostd-contract are installed from the packages the run
# built (./rpms/..., ./debs/...), never by name from a repository. By name, dnf or apt takes the channel's daemon, and
# the job tests the served release instead of the change; with a floor the served one does not meet (omx-clap-host
# >= 0.32 against a served plugin-hostd that wants < 0.32), it cannot even install (#44's Zynthian chain).
INSTALL = re.compile(r"\b(dnf5?|apt-get|apt)\s+(?:-\S+\s+)*(install|download)\b")
OWN_PACKAGE = re.compile(r"(?<![\w./*\[-])'?plugin-hostd(?:-contract)?(?=['\s<>=]|$)")
# every workflow installs the daemon this run built: the smoke run of bench.yml too, which on a cell the channel has
# not yet served this version cannot resolve plugin-hostd by name (its plugin-hostd-contract is newer)
SERVED_HOSTS = set()


def own_build_scan(root):
    """every finding as 'path:line what'"""
    found = []
    for path in workflow_files(root):
        if os.path.basename(path) in SERVED_HOSTS:
            continue
        lines = open(path).read().split("\n")
        for n, line in enumerate(lines):
            if line.lstrip().startswith("#") or not INSTALL.search(line):
                continue
            command, k = line, n
            while command.rstrip().endswith("\\") and k + 1 < len(lines):
                k += 1
                command = command.rstrip()[:-1] + " " + lines[k].strip()
            if OWN_PACKAGE.search(command):
                found.append("%s:%d installs plugin-hostd by name: from a repository it is the channel's daemon, not this run's"
                             % (os.path.relpath(path, root), n + 1))
    return found


# Fedora 44 is dropped (owner ruling 2026-11-19): protocol 0.6.0 and later are published for fc45 only, so a workflow
# that names 44 as a Fedora release builds nothing the channel serves. Every form is refused: fedora:44, fc44, a matrix
# list (fedora: [45, 44], fedora: [44]) wherever 44 sits in it, and a block list (fedora: then - 44 beneath it).
# Comments count too. A missing .github/workflows is a finding, never a silent pass.
FEDORA_44_TEXT = re.compile(r"fedora:\s*44\b|\bfedora-44\b|\bfc44\b")
FEDORA_44_LIST = re.compile(r"fedora:\s*\[[^\]]*\b44\b[^\]]*\]")
FEDORA_KEY = re.compile(r"^(\s*)fedora:\s*$")
FEDORA_BLOCK_ITEM = re.compile(r"^\s*-\s*['\"]?44['\"]?\s*(#.*)?$")
FEDORA_MSG = "names Fedora 44 (fedora:44, fc44, or 44 in a fedora list): Fedora 44 is dropped, the cell is fedora:45 / fc45"


def fedora_scan(root):
    """every finding as 'path:line what'"""
    d = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(d):
        return ["%s has no .github/workflows directory: the Fedora scan has nothing to read" % root]
    found = []
    for path in workflow_files(root):
        lines = open(path).read().split("\n")
        where = os.path.relpath(path, root)
        for n, line in enumerate(lines):
            if FEDORA_44_TEXT.search(line) or FEDORA_44_LIST.search(line):
                found.append("%s:%d %s" % (where, n + 1, FEDORA_MSG))
                continue
            key = FEDORA_KEY.match(line)
            if key:
                k = n + 1
                while k < len(lines) and (not lines[k].strip() or len(lines[k]) - len(lines[k].lstrip()) > len(key.group(1))):
                    if FEDORA_BLOCK_ITEM.match(lines[k]):
                        found.append("%s:%d %s" % (where, k + 1, FEDORA_MSG))
                        break
                    k += 1
    return found


# Node is 26 everywhere (owner rule, #220). A workflow names its Node by major: a package install takes nodejs26 and its
# -bin/-npm siblings, never the distribution's unversioned nodejs or npm (Node 22 on Fedora 45) nor an older nodejsNN,
# and a setup-node step asks node-version 26 or later.
NODE_FLOOR = 26
INSTALL = re.compile(r"\b(dnf|apt-get|apt|yum|bounded-install)\b.*\binstall\b")
NODE_PACKAGE = re.compile(r"(?<![\w./-])(nodejs(\d*)|npm)(?![\w.])")
NODE_VERSION = re.compile(r"\bnode-version:\s*['\"]?(\d+)")
NODE_MSG = "Node is %d everywhere: " % NODE_FLOOR


def node_scan(root):
    """every finding as 'path:line what'"""
    found = []
    for path in workflow_files(root):
        lines = open(path).read().split("\n")
        where = os.path.relpath(path, root)
        installing = False
        for n, line in enumerate(lines):
            if line.lstrip().startswith("#"):
                continue
            m = NODE_VERSION.search(line)
            if m and int(m.group(1)) < NODE_FLOOR:
                found.append("%s:%d %snode-version %s" % (where, n + 1, NODE_MSG, m.group(1)))
            installing = installing or bool(INSTALL.search(line))
            if installing:
                for p in NODE_PACKAGE.finditer(line):
                    word, major = p.group(1), p.group(2)
                    if word == "npm" or not major:
                        found.append("%s:%d %sthe unversioned package %s is the distribution's Node, not nodejs%d"
                                     % (where, n + 1, NODE_MSG, word, NODE_FLOOR))
                    elif int(major) < NODE_FLOOR:
                        found.append("%s:%d %sthe package %s" % (where, n + 1, NODE_MSG, word))
            installing = installing and line.rstrip().endswith("\\")
    return found


# A push (a devel merge, a tag) releases the full matrix: every package in every cell (owner ruling 2026-11-26), so the
# arch-matrix a push takes in release.yml names both architectures of its format, amd64 and arm64 for a deb, x86_64 and
# aarch64 for an rpm. The push arm is the value after the last `||` of the expression (the fallback a push reaches), or
# the whole value when it is a literal. A push built for arm64 alone left the trixie amd64 cells nothing to install
# (the own-host page's apt took omx-plugins-clap:arm64 and failed on libc6:arm64).
FULL_MATRIX = (("amd64", "arm64"), ("x86_64", "aarch64"))
ARCH_MATRIX = re.compile(r"^\s*arch-matrix:\s*(.*)$")


def matrix_scan(root):
    """every finding as 'path:line what'"""
    path = os.path.join(root, ".github", "workflows", "release.yml")
    if not os.path.exists(path):
        return []
    found = []
    for n, line in enumerate(open(path).read().split("\n")):
        m = ARCH_MATRIX.match(line)
        if not m:
            continue
        push_arm = m.group(1).rsplit("||", 1)[-1]
        for full in FULL_MATRIX:
            named = [a for a in full if re.search(r"\b%s\b" % a, m.group(1))]
            missing = [a for a in full if not re.search(r"\b%s\b" % a, push_arm)]
            if named and missing:
                found.append("release.yml:%d a push builds without %s: a push releases the full matrix (owner 2026-11-26)"
                             % (n + 1, " ".join(missing)))
    return found


def main():
    own = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        wf = os.path.join(own, ".github", "workflows")
        os.makedirs(wf)
        open(os.path.join(wf, "ci.yml"), "w").write(
            "          dnf install -y --setopt=retries=10 plugin-hostd 'omx-clap-host >= 0.32.0' \\\n"
            "            omx-plugins-clap\n"
            "          dnf install -y omx-clap-host-tests \\\n            'plugin-hostd-contract >= 0.20'\n"
            "          # dnf install plugin-hostd\n")
        seen = own_build_scan(own)
        open(os.path.join(wf, "ci.yml"), "w").write(
            "          dnf install -y ./rpms/plugin-hostd-[0-9]*.x86_64.rpm ./rpms/plugin-hostd-contract-[0-9]*.noarch.rpm \\\n"
            "            plugin-hostd-protocol-devel /usr/bin/plugin-hostd 'omx-clap-host >= 0.32.0'\n"
            "          apt-get install -y ./debs/plugin-hostd_*.deb\n")
        if [s.split(" ")[0] for s in seen] != [".github/workflows/ci.yml:1", ".github/workflows/ci.yml:3"] or own_build_scan(own):
            print("FAIL the own-build scan misses a planted install of plugin-hostd by name, or refuses the run's files: saw %s" % seen)
            return 1
    finally:
        shutil.rmtree(own, ignore_errors=True)
    print("ok   the own-build scan sees a planted plugin-hostd and plugin-hostd-contract by name, and passes the run's own files")
    gate = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
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
    staged_cases = [
        ("      staged: ${{ inputs.staged == true }}\n", 1),
        ("      staged: ${{ inputs.staged == true }}\n      # matrix: full\n", 1),
        ("      matrix: ${{ inputs.staged == true && 'quick' || '' }}\n", 1),
        ("      matrix: ${{ inputs.publish == true && 'full' || '' }}\n", 1),
        ("      matrix: ${{ inputs.staged == true && 'full' || '' }}\n", 0),
        ("      matrix: ${{ inputs.staged && 'full' }}\n", 0),
        ("      matrix: full\n", 0),
    ]
    for body, want in staged_cases:
        st = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
        try:
            wf = os.path.join(st, ".github", "workflows")
            os.makedirs(wf)
            open(os.path.join(wf, "release.yml"), "w").write(
                "jobs:\n  rpm:\n    uses: Open-Mixer/.github/.github/workflows/build-rpm.yml@openmixer-v1\n    with:\n" + body
                + "    secrets: inherit\n  later:\n    with:\n      matrix: full\n")
            seen = staged_matrix_scan(st)
            if len(seen) != want:
                print("FAIL the staged-matrix scan on a planted %r: want %d finding(s), saw %s" % (body, want, seen))
                return 1
        finally:
            shutil.rmtree(st, ignore_errors=True)
    print("ok   the staged-matrix scan sees a shared build call with no matrix, a commented one, quick and a non-staged full; "
          "passes full for a staged run and the literal")
    cases = [
        ("    image: fedora:44\n", 1),
        ("    # RPMs (fc44, x86_64)\n", 1),
        ("    fedora: [45, 44]\n", 1),
        ("    fedora: [44, 45]\n", 1),
        ("    fedora: [43, 44]\n", 1),
        ("    fedora: [44]\n", 1),
        ("    fedora:\n      - 45\n      - 44\n", 1),
        ("    fedora:\n      - 44\n      - 45\n", 1),
        ("    image: fedora:45\n", 0),
        ("    fedora: [45]\n", 0),
        ("    fedora:\n      - 45\n      - 43\n", 0),
    ]
    for body, want in cases:
        fed = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
        try:
            wf = os.path.join(fed, ".github", "workflows")
            os.makedirs(wf)
            open(os.path.join(wf, "ci.yml"), "w").write("jobs:\n  x:\n" + body)
            seen = fedora_scan(fed)
            if len(seen) != want:
                print("FAIL the fedora scan on a planted %r: want %d finding(s), saw %s" % (body, want, seen))
                return 1
        finally:
            shutil.rmtree(fed, ignore_errors=True)
    nodir = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
    try:
        if len(fedora_scan(nodir)) != 1:
            print("FAIL the fedora scan passes a tree with no .github/workflows directory")
            return 1
    finally:
        shutil.rmtree(nodir, ignore_errors=True)
    print("ok   the fedora scan sees fedora:44, fc44, 44 in a list at any position, a block list, and refuses a missing workflows directory; passes fc45-only trees")
    node_cases = [
        ("        run: dnf install -y gcc \\\n            python3 nodejs npm\n", 2),
        ("        run: bounded-install dnf install -y nodejs22 nodejs22-npm\n", 2),
        ("        run: apt-get install -y nodejs\n", 1),
        ("          node-version: 24\n", 1),
        ("          node-version: '22'\n", 1),
        ("        run: dnf install -y gcc nodejs26 nodejs26-bin nodejs26-npm\n", 0),
        ("          node-version: 26\n", 0),
        ("        run: npm ci && node tests/x.mjs\n", 0),
        ("        run: dnf install -y gcc\n      - run: npm ci\n", 0),
        ("        # dnf install nodejs\n", 0),
    ]
    for body, want in node_cases:
        nd = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
        try:
            wf = os.path.join(nd, ".github", "workflows")
            os.makedirs(wf)
            open(os.path.join(wf, "ci.yml"), "w").write("jobs:\n  x:\n    steps:\n" + body)
            seen = node_scan(nd)
            if len(seen) != want:
                print("FAIL the node scan on a planted %r: want %d finding(s), saw %s" % (body, want, seen))
                return 1
        finally:
            shutil.rmtree(nd, ignore_errors=True)
    print("ok   the node scan sees an unversioned nodejs or npm, an older nodejsNN and a node-version below %d; passes nodejs%d, "
          "an npm command and a comment" % (NODE_FLOOR, NODE_FLOOR))
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
    matrix_cases = [
        ("      arch-matrix: ${{ (github.event_name != 'push' && inputs.arm == false) && '[\"amd64\"]' || '[\"arm64\"]' }}\n", 1),
        ("      arch-matrix: '[\"arm64\"]'\n", 1),
        ("      arch-matrix: '[\"x86_64\"]'\n", 1),
        ("      arch-matrix: ${{ (github.event_name != 'push' && inputs.arm == false) && '[\"amd64\"]' || '[\"amd64\", \"arm64\"]' }}\n", 0),
        ("      arch-matrix: '[\"x86_64\", \"aarch64\"]'\n", 0),
        ("      # arch-matrix: '[\"arm64\"]'\n", 0),
    ]
    for body, want in matrix_cases:
        md = tempfile.mkdtemp(prefix="ci-guards.", dir=os.environ.get("TMPDIR") or ROOT)
        try:
            wf = os.path.join(md, ".github", "workflows")
            os.makedirs(wf)
            open(os.path.join(wf, "release.yml"), "w").write("jobs:\n  deb:\n    with:\n" + body)
            seen = matrix_scan(md)
            if len(seen) != want:
                print("FAIL the matrix scan on a planted %r: want %d finding(s), saw %s" % (body, want, seen))
                return 1
        finally:
            shutil.rmtree(md, ignore_errors=True)
    print("ok   the matrix scan sees a push arm, or a literal, with one architecture of its format; passes both and a comment")
    failed = 0
    for f in matrix_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   a push builds release.yml's full matrix: both architectures of each format (owner 2026-11-26)")
    for f in fedora_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   no workflow names fedora:44 or fc44: Fedora 44 is dropped")
    for f in node_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   every workflow takes Node %d: nodejs%d by name, no node-version below it" % (NODE_FLOOR, NODE_FLOOR))
    for f in own_build_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   every job installs plugin-hostd from its own run's packages, none by name from the channel")
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
    for f in staged_matrix_scan(ROOT):
        print("FAIL %s" % f)
        failed += 1
    if not failed:
        print("ok   every build-rpm.yml and build-deb.yml call in release.yml builds the full matrix for a staged run")
    n = sum(len(branches(open(p).read().split("\n"))) for p in workflow_files(ROOT))
    if not failed:
        print("ok   every if unshare in the workflows fails where the runner refuses the namespace (%d of them)" % n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
