#!/usr/bin/env node
// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
/**
 * node dist/cli.js: the client asked a batch of cases on stdin, {"cases": [{"op", "in"}...]}, each answered on stdout
 * as {"ok": value} or {"error": message}, in order (docs/clients.md; tests/clients_agree.py reads it beside the Python
 * client's python3 -m plugin_hostd_protocol).
 */
import { readFileSync } from 'node:fs';
import { decodePath, encodePath, pinKey, Protocol, ProtocolError, quote, uriWord, words, type Arg } from './index.js';

export function answer(protocol: Protocol, op: string, arg: unknown): unknown {
  const a = arg as unknown[];
  switch (op) {
    case 'encode':
      return protocol.encode(a[0] as string, a[1] as Arg[], a[2] as string | undefined);
    case 'decode':
      return protocol.decode(arg as string);
    case 'reencode':
      return protocol.reencode(arg as string);
    case 'parse':
      return protocol.parse(arg as string);
    case 'code':
      return protocol.code(arg as string);
    case 'name':
      return protocol.name(arg as number);
    case 'sentence':
      return protocol.sentence(a[0] as number, a[1] as string);
    case 'words':
      return words(arg as string);
    case 'quote':
      return quote(arg as string);
    case 'encode_path':
      return encodePath(arg as string);
    case 'decode_path':
      return decodePath(arg as string);
    case 'uri_word':
      return uriWord(arg as string);
    case 'pin_key':
      return pinKey(arg as string);
    default:
      throw new ProtocolError(`no operation ${op}`);
  }
}

function main(): void {
  const protocol = new Protocol();
  const { cases } = JSON.parse(readFileSync(0, 'utf8')) as { cases: { op: string; in: unknown }[] };
  const out = cases.map((c) => {
    try {
      return { ok: answer(protocol, c.op, c.in) };
    } catch (e) {
      if (!(e instanceof ProtocolError)) throw e;
      return { error: e.message };
    }
  });
  process.stdout.write(JSON.stringify(out));
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) main();
