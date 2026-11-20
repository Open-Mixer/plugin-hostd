#!/usr/bin/env node
// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
//
// tools/domain-data.mjs <clidir> <out data dir> <contract.d> <domain>...: the data files this tree's domains were made
// from, rebuilt by omx-contract's own reader (domainDataFiles of <clidir>/lib/domain.mjs, the rebuild `render
// --with-domain` runs) into <out data dir>, beside the files still in data/ there. omx-contract's render takes one
// --with-domain; this tree renders one vocabulary from several domains, so the Makefile stages them here and renders
// that data directory unchanged (docs/render.md of omx-contract: the files come out byte for byte the data form).
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

const [clidir, out, contractD, ...domains] = process.argv.slice(2);
if (!clidir || !out || !contractD || domains.length === 0) {
  console.error('usage: domain-data.mjs <omx-contract clidir> <out data dir> <contract.d> <domain>...');
  process.exit(2);
}
const { domainDataFiles, domainPath, readDomain } = await import(pathToFileURL(join(clidir, 'lib', 'domain.mjs')).href);
const { installedSchemaUrl } = await import(pathToFileURL(join(clidir, 'lib', 'contract-dir.mjs')).href);
const schemaMajor = JSON.parse(readFileSync(join(clidir, 'schema', 'omx-contract.schema.json'), 'utf8'))['x-omx-schema-version'].split('.')[0];
for (const name of domains) {
  const path = join(contractD, domainPath(name));
  const doc = JSON.parse(readFileSync(path, 'utf8'));
  readDomain(name, doc, installedSchemaUrl(schemaMajor), schemaMajor);
  for (const [file, text] of Object.entries(domainDataFiles(name, doc))) {
    const to = join(out, file);
    if (existsSync(to)) { console.error(`domain-data: ${to} is in data/ and rebuilt from the domain ${name}: one source per file`); process.exit(1); }
    mkdirSync(dirname(to), { recursive: true });
    // the data form names its schema relative to the data directory (data/grouping.json: ../schema/...); the rebuild
    // carries none, and omx-contract's installer writes the installed schema's address from it;
    const schema = `${'../'.repeat(file.split('/').length)}schema/omx-contract.schema.json`;
    // and a file with no declared package requires only the schema the domain reader rebuilds under (its own floor, the
    // one omx-contract's readDomain writes)
    const data = JSON.parse(text);
    writeFileSync(to, `${JSON.stringify({ $schema: schema, requires: data.requires ?? { 'omx-contract-schema': '>= 3.0.0' }, ...data }, null, 2)}\n`);
  }
}
