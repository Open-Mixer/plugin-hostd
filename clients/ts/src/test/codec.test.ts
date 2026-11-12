// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
/**
 * The TypeScript client on clients/fixtures/codec.json (docs/clients.md), and what JSON cannot carry: a number that
 * is not finite, a boolean where a number goes.
 */
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { answer } from '../cli.js';
import { formatNumber, Protocol, ProtocolError } from '../index.js';

const FIXTURES = new URL('../../../fixtures/codec.json', import.meta.url);
const { cases } = JSON.parse(readFileSync(FIXTURES, 'utf8')) as { cases: { op: string; in: unknown; expect?: unknown; error?: boolean }[] };

function clean(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => [k, clean(v)]));
  }
  return value;
}

describe('the TypeScript client on the fixtures', () => {
  const protocol = new Protocol();

  it('meets every fixture', () => {
    assert.ok(cases.length > 40);
    for (const c of cases) {
      const what = `${c.op} ${JSON.stringify(c.in)}`;
      if (c.error) {
        assert.throws(() => answer(protocol, c.op, c.in), ProtocolError, what);
        continue;
      }
      const got = answer(protocol, c.op, c.in);
      if ('expect' in c) assert.deepEqual(clean(got), clean(c.expect), what);
    }
  });

  it('reads a sentence from the installed vocabulary and catalog', () => {
    assert.ok(protocol.sentence(protocol.code('reply.host.param-symbol-invalid'), 'en'));
    assert.ok(protocol.sentence(protocol.code('reply.plugin-hostd.preset-not-applied'), 'ca'));
    assert.equal(protocol.sentence(0, 'en'), null);
  });
});

describe('numbers', () => {
  it('refuses a number that is not finite, and a boolean', () => {
    const p = new Protocol();
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, true]) {
      assert.throws(() => p.encode('param_set_many', [3, 'gain', bad as unknown as number]), ProtocolError, String(bad));
    }
  });

  it('writes the shortest spelling that reads back to the same double', () => {
    for (const x of [0.1, 1 / 3, 2.5e-7, 123456789.125, 1e21, 5e-324, 1.7976931348623157e308, -0.000001, 1e-6, 100]) {
      assert.equal(Number(formatNumber(x)), x);
    }
  });

  it('lays it out as ECMAScript does, the layout the Python client writes', () => {
    const cases: [number, string][] = [[1, '1'], [1e20, '100000000000000000000'], [1e21, '1e+21'], [1e-6, '0.000001'],
      [1e-7, '1e-7'], [1.5e-7, '1.5e-7'], [123.456, '123.456'], [-2, '-2'], [0, '0'], [2.5e100, '2.5e+100']];
    for (const [x, want] of cases) assert.equal(formatNumber(x), want);
  });
});

describe('the installed files', () => {
  it('names a missing table', () => {
    assert.throws(() => new Protocol({ table: '/nonexistent/plugin-hostd-protocol.json' }), /\/nonexistent\/plugin-hostd-protocol\.json/);
  });
});
