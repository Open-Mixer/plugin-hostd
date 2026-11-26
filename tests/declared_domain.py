#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# The words of the protocol this tree reads (the daemon's verbs, the protocol's own verbs, the reply codes only plugin-hostd
# answers, the extensions hello grants) are the domain plugin-hostd-protocol, read from the contract directory
# through omx-contract's own rebuild (plugin-hostd-protocol#26; tests/declared.py), never from a verbs.json:
#   (a) the document is the domain's, <contractdir>/plugin-hostd-protocol/plugin-hostd-protocol.json, and no contract directory serves a
#       verbs.json of plugin-hostd-protocol's package;
#   (b) the four items come back in the number of words they had (39 reply codes, 30 daemon verbs, 6 protocol verbs, 3 extensions;
#       the 30th daemon verb is description_get, plugin-hostd-protocol#128, which src/verbs.c answers from the descriptions
#       store), and the `since` of a protocol verb is there;
#   (c) a changed copy of the domain, rendered as plugin-hostd-protocol renders it, changes the header the daemon is built
#       against: the verb table the daemon answers from is the domain's.
# Usage: declared_domain.py
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import declared  # noqa: E402

GOLDEN = {"PLUGIN_HOSTD_PROTOCOL_REPLY_CODES": ("codes", 39), "PLUGIN_HOSTD_PROTOCOL_DAEMON_VERBS": ("verbs", 30),
          "PLUGIN_HOSTD_PROTOCOL_LIBRARY_VERBS": ("verbs", 6), "PLUGIN_HOSTD_PROTOCOL_EXTENSIONS": ("words", 3)}
failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main():
    path = declared.domain_json()
    check(path.endswith(os.path.join("plugin-hostd-protocol", "plugin-hostd-protocol.json")) and os.path.isfile(path),
          "(a) the words of the protocol are the document %s" % path)
    old = [os.path.join(d, declared.PACKAGE, "verbs.json") for d in declared.contract_dirs()
           if os.path.exists(os.path.join(d, declared.PACKAGE, "verbs.json"))]
    check(not old, "(a) no contract directory serves a verbs.json of plugin-hostd-protocol: %s" % old)
    items = declared.verbs()
    got = {k: (v["kind"], len(v[v["kind"]])) for k, v in items.items() if k in GOLDEN}
    check(got == GOLDEN, "(b) the four items hold %s" % got)
    check(items["PLUGIN_HOSTD_PROTOCOL_LIBRARY_VERBS"]["verbs"]["hello"].get("since") == "0.1.0", "(b) hello's since is the domain's")
    work = tempfile.mkdtemp(prefix="declared-domain.")
    try:
        copy = os.path.join(work, "contract.d", "plugin-hostd-protocol", "plugin-hostd-protocol.json")
        os.makedirs(os.path.dirname(copy))
        with open(path) as f:
            text = f.read()
        check(text.count('"x-format": "chain_get %i"') == 1, "(c) the copy holds chain_get's format once")
        with open(copy, "w") as f:
            f.write(text.replace('"x-format": "chain_get %i"', '"x-format": "chain_get %i %i"'))
        out = os.path.join(work, "tree")
        os.makedirs(os.path.join(out, "include", "plugin-hostd"))
        declared.render_overlay(out, copy)
        with open(os.path.join(out, "include", "plugin-hostd", "plugin_hostd_protocol_host_verbs.h")) as f:
            check('"chain_get %i %i"' in f.read(), "(c) the changed copy renders into the header the daemon is built against")
    finally:
        shutil.rmtree(work)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
