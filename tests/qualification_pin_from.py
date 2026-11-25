#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""tests/qualification_pin_from.py: QUALIFICATION_PIN_VERDICTS names the verdict words of plugin-hostd-protocol's domain `pin`
(PIN_VERDICTS, its package plugin-hostd-protocol-contract 0.8.0), and holds no list of its own (sorting pass, V12).

a. every word of the item carries an `x-from` of one entry: the `$ref` of the domain pin's PIN_VERDICTS and the word's
   `title` as `x-term`, and its `const` is the word the domain pin gives that key (golden: in-process, isolated, refused);
b. omx-contract validate of this document beside the domain pin accepts it (the real reader of an `x-from`);
c. sabotage, in scratch directories: the domain pin without a word of PIN_VERDICTS, no domain pin at all, and an
   info.x-requires that no longer names pin are refused by validate, by name.

The document's `info.x-requires` lists names, no version (the devel wave 2026-11-24, no hand-kept floors): among them pin,
the domain its x-from names (the read refuses an x-from into a domain x-requires does not declare), and
plugin-hostd-protocol, the package that ships it. The scratch directories hold that package as x-requires names it: one table and its manifest at the version under test.

Environment: PIN_DOMAIN_DIR (a contract directory holding pin/pin.json: protocol's contract.d, or the installed contract
directory, the default), OMX_CONTRACT (the command). Exit 0 all green, 1 a FAIL line."""
import hashlib, json, os, shlex, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OMX = shlex.split(os.environ.get("OMX_CONTRACT", "omx-contract"))
REF = "https://openmixer.org/contract/pin#/components/schemas/PIN_VERDICTS"
GOLDEN = {"inProcess": "in-process", "isolated": "isolated", "refused": "refused"}
failed = 0


def check(cond, what):
    global failed
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failed += 1


def pin_dir():
    d = os.environ.get("PIN_DOMAIN_DIR")
    if d:
        return d
    p = subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True, text=True)
    return p.stdout.strip()


def stub(d, package, version, item):
    """a package that holds one small table and its manifest, at the version under test: a name is all the document asks
    of it (a manifest names at least one file), and the table is formatted as the installer writes it"""
    dst = os.path.join(d, "3", package)
    os.makedirs(dst)
    doc = {"$schema": "https://openmixer.org/schema/omx-contract/v3/omx-contract.schema.json",
           item: {"kind": "words", "since": version, "doc": "The word of a stand-in table.",
                  "words": {"stub": {"word": "stub", "doc": "A stand-in."}}}}
    body = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode()
    open(os.path.join(dst, "stub.json"), "wb").write(body)
    json.dump({"package": package, "version": version, "schemaMajor": 3, "tree": "data",
               "files": {"stub.json": hashlib.sha256(body).hexdigest()}}, open(os.path.join(dst, "MANIFEST.json"), "w"), indent=2)


def without(tmp, installed, hidden):
    """a view of the installed contract directory without the domains named in hidden (symlinks of every other entry)"""
    view = os.path.join(tmp, "installed-without-" + "-".join(hidden))
    if not os.path.isdir(view):
        os.makedirs(view)
        for e in os.listdir(installed):
            if e not in hidden:
                os.symlink(os.path.join(installed, e), os.path.join(view, e))
    return view


def stage(tmp, name, qualification, pin, protocol="0.8.0"):
    """a scratch contract directory: this document (a dict, or the text as it is), the domain pin when given, and the package
    plugin-hostd-protocol at the version under test; returns (directory, installed contract directory)"""
    d = os.path.join(tmp, name)
    os.makedirs(os.path.join(d, "qualification"))
    with open(os.path.join(d, "qualification", "qualification.json"), "w") as f:
        f.write(qualification if isinstance(qualification, str) else json.dumps(qualification, indent=2))
    if pin is not None:
        os.makedirs(os.path.join(d, "pin"))
        with open(os.path.join(d, "pin", "pin.json"), "w") as f:
            f.write(pin if isinstance(pin, str) else json.dumps(pin, indent=2))
    # the packages x-requires names, at the versions under test (plugin-hostd-protocol's is the one the arms move), and the
    # term domains the latency and voice words name (plugin-db's lv2, omx-clap's clap), copied from the installed directory
    installed = subprocess.run(["pkg-config", "--variable=contractdir", "omx-contract"], capture_output=True, text=True).stdout.strip()
    stub(d, "plugin-hostd-protocol", protocol, "PLUGIN_HOSTD_PROTOCOL_FLOOR_STUB")
    for package in ("plugin-db", "omx-clap"):  # the term domains' owners, as installed
        src = os.path.join(installed, "3", package)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(d, "3", package))
    for domain in ("lv2", "clap"):
        src = os.path.join(installed, domain)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(d, domain))
    return d, installed


def fmt_check(tmp, name, text, pin):
    """omx-contract fmt --check of the document staged with the domain pin it names: (exit code, output)"""
    d, _ = stage(tmp, name, text, pin)
    r = subprocess.run(OMX + ["fmt", "--check", "--contract-dir", d], capture_output=True, text=True)
    # only this document's formatting counts: the other owners' files staged beside it are theirs to format
    ours = [l for l in (r.stdout + r.stderr).splitlines() if "qualification" in l or "fmt --check:" not in l]
    bad = [l for l in ours if "not in the one formatting" in l or "contract." in l]
    return (1 if bad else 0), "\n".join(ours).strip()


def validate(tmp, name, qualification, pin, protocol="0.8.0"):
    """omx-contract validate over a scratch contract directory: this document, and the domain pin when given"""
    d, installed = stage(tmp, name, qualification, pin, protocol)
    if pin is None:  # no domain pin anywhere: the installed directory is read without its own
        installed = without(tmp, installed, ("pin",))
    # beside the installed contract directory, where the terms the other items name are; only the findings that name this
    # item, or the document's requires, count (the rest of the document is V5's own checks)
    env = dict(os.environ, OMX_CONTRACT_PATH=d + ":" + installed)
    r = subprocess.run(OMX + ["validate", "--installed"], capture_output=True, text=True, env=env)
    ours = [l for l in (r.stdout + r.stderr).splitlines() if "QUALIFICATION_PIN_VERDICTS" in l or "word-from-differs" in l or "requires plugin-hostd-protocol" in l or "requires pin" in l]
    return (1 if ours else 0), "; ".join(ours) or "no finding on QUALIFICATION_PIN_VERDICTS"


def main():
    qual = json.load(open(os.path.join(ROOT, "contract.d", "qualification", "qualification.json")))
    item = qual["components"]["schemas"]["QUALIFICATION_PIN_VERDICTS"]
    words = item["oneOf"]
    pin_path = os.path.join(pin_dir(), "pin", "pin.json")
    pin = json.load(open(pin_path)) if os.path.isfile(pin_path) else None
    check(pin is not None, "the domain pin is found (%s)" % pin_path)
    check({w["title"]: w["const"] for w in words} == GOLDEN, "the item's words are the golden three")
    check(all(w.get("x-from") == [{"$ref": REF, "x-term": w["title"]}] for w in words),
          "(a) every word names the domain pin's PIN_VERDICTS by x-from, its title the term")
    if pin is None:
        return 1
    # the item carries no meaning of its own: each word is the owner's word, its const, code, description and text verbatim
    owner = {w["title"]: w for w in pin["components"]["schemas"]["PIN_VERDICTS"]["oneOf"]}
    same = all(w["title"] in owner and all(w.get(k) == owner[w["title"]].get(k) for k in ("const", "x-code", "description", "x-text")) for w in words)
    check(same, "(a) every word is the owner's: const, x-code, description and x-text verbatim, no meaning of its own")
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = validate(tmp, "with-pin", qual, pin)
        check(rc == 0, "(b) validate accepts the document beside the domain pin: %s" % out[-200:])
        cut = json.loads(json.dumps(pin))
        cut["components"]["schemas"]["PIN_VERDICTS"]["oneOf"] = [w for w in cut["components"]["schemas"]["PIN_VERDICTS"]["oneOf"] if w["title"] != "refused"]
        rc, out = validate(tmp, "no-word", qual, cut)
        check(rc != 0, "(c) the domain pin without its refused word is refused: %s" % out[-160:])
        rc, out = validate(tmp, "no-pin", qual, None)
        check(rc != 0, "(c) no domain pin is refused: %s" % out[-160:])
        # a word that takes its meaning from a word is that word (format ruling (b), omx-contract#154): a const, a code, a
        # description or a text that differs, and a description that is absent, are each refused by `word-from-differs`
        def drop(ws):
            del ws[0]["description"]

        def swap(ws):  # the first two words trade places and codes: a valid order, each word's code differs from the target's
            ws[0], ws[1] = ws[1], ws[0]
            ws[0]["x-code"], ws[1]["x-code"] = 0, 1
        for what, edit in (("const", lambda ws: ws[0].update(const="in-proc")), ("x-code", swap),
                           ("description", lambda ws: ws[0].update(description="Another meaning.")),
                           ("x-text", lambda ws: ws[0].update({"x-text": "Another text."})), ("absent description", drop)):
            bad = json.loads(json.dumps(qual))
            edit(bad["components"]["schemas"]["QUALIFICATION_PIN_VERDICTS"]["oneOf"])
            rc, out = validate(tmp, "differs-" + what.replace(" ", "-"), bad, pin)
            check(rc != 0 and "word-from-differs" in out, "(c) a word whose %s differs from the target's is refused by word-from-differs: %s" % (what, out[-110:]))
        # the document stays in the one formatting (fmt --check, beside the domain pin it names), and a misformatted one is refused
        text = open(os.environ.get("QUALIFICATION_DOC", os.path.join(ROOT, "contract.d", "qualification", "qualification.json"))).read()
        rc, out = fmt_check(tmp, "fmt-real", text, open(pin_path).read())
        check(rc == 0, "(d) fmt --check accepts the document as it is: %s" % out[-160:])
        rc, out = fmt_check(tmp, "fmt-misformatted", json.dumps(json.loads(text), indent=4), open(pin_path).read())
        check(rc != 0, "(d) fmt --check refuses the document in another formatting: %s" % out[-120:])
        undeclared = json.loads(json.dumps(qual))
        undeclared["info"]["x-requires"] = [n for n in undeclared["info"]["x-requires"] if n != "pin"]
        rc, out = validate(tmp, "undeclared-pin", undeclared, pin)
        check(rc != 0 and "contract.ref.undeclared" in out and "info.x-requires does not declare" in out,
              "(c) an info.x-requires without pin, the domain the x-from names, is refused by contract.ref.undeclared: %s" % out[-160:])
    check(qual["info"].get("x-requires") == ["clap", "lv2", "omx-clap", "pin", "plugin-db", "plugin-hostd-protocol"],
          "(a) info.x-requires lists, sorted and with no version, the domain pin and plugin-hostd-protocol, and the term domains lv2 (plugin-db) and clap (omx-clap)")
    return 1 if failed else 0


sys.exit(main())
