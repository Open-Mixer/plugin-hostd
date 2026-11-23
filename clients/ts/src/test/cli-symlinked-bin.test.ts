// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
/**
 * The codec command run as npx runs it: through node_modules/.bin/plugin-hostd-codec, a symlink to dist/cli.js. It
 * must answer as it does by its own path, never exit 0 with nothing written.
 */
import { strict as assert } from 'node:assert';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, describe, it } from 'node:test';

const CLI = fileURLToPath(new URL('../cli.js', import.meta.url));
const SRC = fileURLToPath(new URL('../../src/cli.ts', import.meta.url));

describe('plugin-hostd-codec through a symlinked bin', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'plugin-hostd-codec-'));
  after(() => rmSync(scratch, { recursive: true, force: true }));
  const bin = join(scratch, 'node_modules', '.bin');
  mkdirSync(bin, { recursive: true });
  const link = join(bin, 'plugin-hostd-codec');
  symlinkSync(CLI, link);
  const run = (path: string) => spawnSync(process.execPath, [path], { input: '{"cases":[]}', encoding: 'utf8' });

  it('answers an empty case list as it does by its own path', () => {
    const direct = run(CLI);
    assert.equal(direct.status, 0);
    assert.equal(direct.stdout, '[]');
    const linked = run(link);
    assert.equal(linked.status, direct.status);
    assert.equal(linked.stdout, direct.stdout);
  });

  // the entry decides that it was run, not imported, with omx-contract's isMain (real paths on both sides)
  it('takes isMain from omx-contract instead of comparing argv[1] by hand', () => {
    const code = readFileSync(SRC, 'utf8').split('\n').filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l));
    assert.deepEqual(code.filter((l) => /process\.argv\[1\]/.test(l)), []);
    assert.ok(code.some((l) => /^import \{ isMain \} from '@openmixer\/omx-contract\/entry';$/.test(l)));
  });
});
