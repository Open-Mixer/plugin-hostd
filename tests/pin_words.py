# SPDX-License-Identifier: GPL-3.0-or-later
# The words of a pin's verdict and pool key are plugin-hostd's: how the host uses a plugin (sorting pass, V12). They are the
# items PLUGIN_HOSTD_PIN_VERDICTS and PLUGIN_HOSTD_PIN_POOLS of data/pin.json, rendered into plugin_hostd_vocabulary.h with the
# other tables of this tree and installed in the package plugin-hostd of the contract directory. Held here, through the real
# calls (the installer of the package and omx-contract's render, the two the build makes):
#   a. golden: the package as installed carries the two items, and the render writes their words, docs, order, count,
#      initializer and X-macro as plugin-db's data/pin.json wrote them (tests/fixtures/pin-words-golden.json, frozen from
#      plugin-db 09ee2fa);
#   b. both sources: while the installed plugin-db package still holds PLUGIN_DB_PIN_VERDICTS and PLUGIN_DB_PIN_POOLS, its words
#      are the words of ours, item by item; once it holds none, that is said and nothing is compared;
#   c. sabotage: a scratch copy of the package with one word removed renders another header, which the check of the
#      committed header refuses, and one with a word renamed renders the renamed word: the render is the real reader.
# Usage (the Makefile's test-pin-words sets the environment): INSTALL_CONTRACT_DIR=<install-contract-dir.sh> VERSION=<x.y.z>
#   CONTRACT_SCHEMA_MAJOR=<n> CONTRACTDIR=<installed contract directory> OMX_CONTRACT=<command> pin_words.py
import json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = json.load(open(os.path.join(ROOT, "tests", "fixtures", "pin-words-golden.json")))
ITEMS = ("PLUGIN_HOSTD_PIN_VERDICTS", "PLUGIN_HOSTD_PIN_POOLS")
OLD = {"PLUGIN_HOSTD_PIN_VERDICTS": "PLUGIN_DB_PIN_VERDICTS", "PLUGIN_HOSTD_PIN_POOLS": "PLUGIN_DB_PIN_POOLS"}
INSTALL = os.environ["INSTALL_CONTRACT_DIR"]
VERSION = os.environ["VERSION"]
MAJOR = os.environ["CONTRACT_SCHEMA_MAJOR"]
CONTRACTDIR = os.environ["CONTRACTDIR"]
OMX_CONTRACT = os.environ.get("OMX_CONTRACT", "omx-contract")
HEADER = "plugin_hostd_vocabulary.h"
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def stage(tmp, name, edit=None):
    """install data/ as the package plugin-hostd of a contract directory, `edit` changing the tree first; returns the directory"""
    data = os.path.join(tmp, name + "-data")
    shutil.copytree(os.path.join(ROOT, "data"), data)
    if edit:
        edit(os.path.join(data, "pin.json"))
    out = os.path.join(tmp, name)
    subprocess.run(["sh", INSTALL, "plugin-hostd", VERSION, MAJOR, data, out, "data"], cwd=ROOT,
                   check=True, capture_output=True)
    return out


def render(contract_dir, out, extra=()):
    """omx-contract render of the package plugin-hostd as installed in contract_dir; (exit code, stderr)"""
    env = dict(os.environ, OMX_CONTRACT_PATH=contract_dir + ":" + CONTRACTDIR)
    p = subprocess.run([OMX_CONTRACT, "render", "--target", "c", "--package", "plugin-hostd", "--installed", "--out", out, *extra],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stderr


def words_of(header, item):
    """what the header says of one item: {"words": [(NAME, word, doc)], "count": n, "init": [word], "xmacro": [(code, word, NAME)]}"""
    prefix = "OMX_" + item + "_"
    words, count, init = [], None, None
    for line in header.splitlines():
        m = re.match(r'#define %s([A-Z0-9_]+) "([^"]*)" ///< (.*)$' % prefix, line)
        if m and m.group(1) not in ("COUNT", "INIT"):
            words.append((m.group(1), m.group(2), m.group(3)))
        m = re.match(r"#define %sCOUNT (\d+)u$" % prefix, line)
        if m:
            count = int(m.group(1))
        m = re.match(r"#define %sINIT \{ (.*) \}$" % prefix, line)
        if m:
            init = re.findall(r'"([^"]*)"', m.group(1))
    block = re.search(r"#define %s\(X\) \\\n((?:    .*\n?)+)" % re.escape("OMX_" + item), header)
    x = re.findall(r'X\((\d+)u, "([^"]*)", ([A-Z0-9_]+)\)', block.group(1)) if block else []
    return {"words": words, "count": count, "init": init, "xmacro": x}


def expected(item):
    """the same, from the golden words of plugin-db's file: the key is camelCase, the C name its upper snake case"""
    words = [(re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", k).upper(), w["word"], w["doc"]) for k, w in GOLDEN[item]["words"].items()]
    return {"words": words, "count": len(words), "init": [w[1] for w in words],
            "xmacro": [(str(i), w[1], w[0]) for i, w in enumerate(words)]}


def main():
    tmp = tempfile.mkdtemp(prefix="plugin-hostd-pin-words.")
    try:
        # a. golden
        good = stage(tmp, "as-installed")
        pkg = os.path.join(good, MAJOR, "plugin-hostd", "pin.json")
        check(os.path.exists(pkg), "the installed package plugin-hostd carries pin.json")
        doc = json.load(open(pkg)) if os.path.exists(pkg) else {}
        for item in ITEMS:
            check(item in doc, "the installed pin.json holds %s" % item)
            check(doc.get(item, {}).get("doc") == GOLDEN[item]["doc"], "%s: its doc is the one plugin-db's file wrote" % item)
            check({k: w for k, w in doc.get(item, {}).get("words", {}).items()} == GOLDEN[item]["words"],
                  "%s: its words, keys and docs are plugin-db's file's, in order" % item)
        out = os.path.join(tmp, "rendered")
        os.makedirs(out)
        rc, err = render(good, out)
        check(rc == 0, "the render of the package succeeds: %s" % err.strip()[:200])
        header = open(os.path.join(out, HEADER)).read() if os.path.exists(os.path.join(out, HEADER)) else ""
        for item in ITEMS:
            check(words_of(header, item) == expected(item),
                  "%s: the rendered names, words, docs, count, initializer and X-macro are golden" % item)
        committed = open(os.path.join(ROOT, "include", "plugin-hostd", HEADER)).read()
        check(committed == header, "the committed %s is the render of the package, byte for byte" % HEADER)

        # b. both sources, while both exist
        old_path = os.path.join(CONTRACTDIR, MAJOR, "plugin-db", "pin.json")
        old = json.load(open(old_path)) if os.path.exists(old_path) else {}
        held = [i for i in ITEMS if OLD[i] in old]
        if not os.path.exists(old_path):
            print("note plugin-db's package is not installed: nothing to compare the words with")
        elif not held:
            print("note the installed plugin-db package holds neither item any more: the old source is gone")
        for item in held:
            check(item in doc and old[OLD[item]]["words"] == doc[item]["words"] and old[OLD[item]]["doc"] == doc[item]["doc"],
                  "%s is %s of the installed plugin-db package, word for word" % (item, OLD[item]))

        # c. sabotage: a word removed, a word renamed
        def drop_refused(path):
            d = json.load(open(path))
            del d["PLUGIN_HOSTD_PIN_VERDICTS"]["words"]["refused"]
            json.dump(d, open(path, "w"), indent=2)

        def rename_cores(path):
            d = json.load(open(path))
            d["PLUGIN_HOSTD_PIN_POOLS"]["words"]["cores"]["word"] = "all-cores"
            json.dump(d, open(path, "w"), indent=2)
        for name, edit, item, what in (("no-refused", drop_refused, "PLUGIN_HOSTD_PIN_VERDICTS", "refused"),
                                       ("renamed", rename_cores, "PLUGIN_HOSTD_PIN_POOLS", "all-cores")):
            if not os.path.exists(os.path.join(ROOT, "data", "pin.json")):
                check(False, "%s: data/pin.json is absent: nothing to sabotage" % name)
                continue
            scratch = stage(tmp, name, edit)
            sout = os.path.join(tmp, "rendered-" + name)
            os.makedirs(sout)
            rc, _ = render(scratch, sout)
            sh = open(os.path.join(sout, HEADER)).read() if os.path.exists(os.path.join(sout, HEADER)) else ""
            check(rc == 0 and words_of(sh, item) != expected(item), "%s: the render of a package changed by one word differs from golden" % name)
            check(what in sh if name == "renamed" else "\"refused\"" not in " ".join(words_of(sh, item)["init"] or []),
                  "%s: the render follows the word" % name)
            rc, _ = render(scratch, os.path.join(ROOT, "include", "plugin-hostd"), ("--check",))
            check(rc != 0, "%s: the check of the committed header refuses it" % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%d failed" % failed)
    return 1 if failed else 0


sys.exit(main())
