# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""python3 -m plugin_hostd_protocol: the client asked a batch of cases on stdin, {"cases": [{"op", "in"}...]}, each
answered on stdout as {"ok": value} or {"error": message}, in order (docs/clients.md; tests/clients_agree.py reads
it beside the TypeScript client's cli.js)."""
import json
import sys

from . import Protocol, ProtocolError, decode_path, encode_path, pin_key, quote, uri_word, words


def answer(protocol, op, arg):
    if op == "encode":
        return protocol.encode(*arg)
    if op == "decode":
        return protocol.decode(arg)
    if op == "reencode":
        return protocol.reencode(arg)
    if op == "parse":
        return protocol.parse(arg)
    if op == "read_plan":
        return protocol.read_plan(arg)
    if op == "read_plan_get":
        return protocol.read_plan_get(arg)
    if op == "read_estimate":
        return protocol.read_estimate(arg)
    if op == "read_reply":
        return protocol.read_reply(*arg)
    if op == "code":
        return protocol.code(arg)
    if op == "name":
        return protocol.name(arg)
    if op == "sentence":
        return protocol.sentence(arg[0], arg[1])
    plain = {"words": words, "quote": quote, "encode_path": encode_path, "decode_path": decode_path,
             "uri_word": uri_word, "pin_key": pin_key}
    if op in plain:
        return plain[op](arg)
    raise ProtocolError("no operation %s" % op)


def main():
    protocol = Protocol()
    out = []
    for case in json.load(sys.stdin)["cases"]:
        try:
            out.append({"ok": answer(protocol, case["op"], case["in"])})
        except ProtocolError as e:
            out.append({"error": str(e)})
    json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
