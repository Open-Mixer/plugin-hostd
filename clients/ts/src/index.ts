// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
/**
 * The TypeScript client of plugin-hostd's protocol (docs/clients.md).
 *
 * One codec over the files plugin-hostd-protocol installs: its protocol table (every command, feedback line, protocol
 * error and reply code), the vocabulary of omx-contract's contract directory (each reply code's English sentence) and
 * the catalogs (its sentence in another language). Nothing of the protocol is written here; a file that is not there
 * is an error naming it. No transport: a controller opens the socket and sends the lines. The Python client
 * (clients/python) is the same codec, held to this one by tests/clients_agree.py.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

/** A line the table does not declare, an argument no form takes, a reply that is no reply. */
export class ProtocolError extends Error {
  override name = 'ProtocolError';
}

/** An argument of a command: a word, or a number. */
export type Arg = string | number;

export interface Decoded {
  readonly tag?: string;
  readonly verb: string;
  readonly args: Arg[];
}

export type Reply =
  | { readonly kind: 'resp'; readonly tag?: string; readonly seq?: number; readonly code: number; readonly name?: string; readonly data: string[] }
  | { readonly kind: 'protocol_error'; readonly tag?: string; readonly seq?: number; readonly code: number; readonly name: string }
  | { readonly kind: 'feedback'; readonly tag?: string; readonly seq?: number; readonly line: string; readonly args: Arg[] };

// ---- the words of a line, as plugin-hostd-protocol's grammar (core.abnf: word, quoted, escaped-quote) writes them,
// and the percent-encoded path of a clap: uri, as its pin section does (PHD_PIN_PATH_EXCLUDED, PHD_PIN_PATH_ESCAPE)

/** The daemon's tokenizer splits at C's isspace(): these six, and no other character. */
const SPACE = ' \t\n\v\f\r';
const CLAP_PREFIX = 'clap:';
const ESCAPE = '%';
const EXCLUDED = ',= \t\r\n';

/**
 * The words of a line as the daemon reads them: split at whitespace; a word that starts with a quotation mark runs to
 * the next one no backslash escapes, \" in it is a quote, the marks are not part of it; a quoted word that never
 * closes runs to the end of the line.
 */
export function words(line: string): string[] {
  const out: string[] = [];
  let i = 0;
  const n = line.length;
  while (i < n) {
    if (SPACE.includes(line[i]!)) {
      i += 1;
    } else if (line[i] === '"') {
      i += 1;
      let word = '';
      while (i < n && line[i] !== '"') {
        if (line[i] === '\\' && i + 1 < n && line[i + 1] === '"') i += 1;
        word += line[i];
        i += 1;
      }
      i += 1;
      out.push(word);
    } else {
      let j = i;
      while (j < n && !SPACE.includes(line[j]!)) j += 1;
      out.push(line.slice(i, j));
      i = j;
    }
  }
  return out;
}

/** A value as one quoted word: in quotation marks, \" for a quote (the grammar's only escape). */
export function quote(value: string): string {
  return '"' + value.replaceAll('"', '\\"') + '"';
}

/** A string as one word: bare when it can be, quoted when it is empty or holds whitespace or a quote. */
function word(value: string): string {
  if (value && ![...value].some((c) => SPACE.includes(c) || c === '"')) return value;
  return quote(value);
}

function escaped(c: string): boolean {
  const code = c.codePointAt(0)!;
  return code < 0x20 || code === 0x7f || c === ESCAPE || c === '"' || c === '\\' || EXCLUDED.includes(c);
}

/**
 * A path as the word of a pin: every separator of pin_set's words, whitespace, the escape, a quote, a backslash and a
 * control byte as %XX (uppercase hex) of its UTF-8 bytes, the rest as it is.
 */
export function encodePath(path: string): string {
  const utf8 = new TextEncoder();
  let out = '';
  for (const c of path) {
    out += escaped(c) ? [...utf8.encode(c)].map((b) => '%' + b.toString(16).toUpperCase().padStart(2, '0')).join('') : c;
  }
  return out;
}

/** A percent-encoded path as it is; ProtocolError for a % not followed by two hex digits, as the daemon refuses. */
export function decodePath(encoded: string): string {
  const raw = new TextEncoder().encode(encoded);
  const out: number[] = [];
  for (let i = 0; i < raw.length; ) {
    if (raw[i] === ESCAPE.charCodeAt(0)) {
      const digits = String.fromCharCode(...raw.slice(i + 1, i + 3));
      if (!/^[0-9a-fA-F]{2}$/.test(digits)) throw new ProtocolError(`'%' not followed by two hex digits in ${encoded}`);
      out.push(parseInt(digits, 16));
      i += 3;
    } else {
      out.push(raw[i]!);
      i += 1;
    }
  }
  return new TextDecoder().decode(new Uint8Array(out));
}

function splitUri(uri: string): [path: string, id: string] | undefined {
  if (!uri.startsWith(CLAP_PREFIX) || !uri.includes('#')) return undefined;
  const rest = uri.slice(CLAP_PREFIX.length);
  const at = rest.lastIndexOf('#');
  return [rest.slice(0, at), rest.slice(at + 1)];
}

/** A plugin uri as the daemon takes it: a clap: uri's path percent-encoded, so any file name is one bare word. */
export function uriWord(uri: string): string {
  const parts = splitUri(uri);
  return parts ? `${CLAP_PREFIX}${encodePath(parts[0])}#${parts[1]}` : uri;
}

/** What a pin is keyed by: a clap: uri with its path decoded, so every spelling of one uri is one key. */
export function pinKey(uri: string): string {
  const parts = splitUri(uri);
  if (!parts) return uri;
  try {
    return `${CLAP_PREFIX}${decodePath(parts[0])}#${parts[1]}`;
  } catch {
    return uri;
  }
}

// ---- numbers

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * A finite number as a word: its shortest digits that read back to the same double, laid out as
 * Number.prototype.toString lays them out (the layout the Python client writes too).
 */
export function formatNumber(value: number): string {
  if (!isNumber(value)) throw new ProtocolError(`${String(value)} is not a finite number`);
  return value === 0 ? '0' : String(value);
}

const INT = /^-?[0-9]+$/;
/** A decimal numeral, as both clients read one (no digit separator, no other script's digits, no inf or nan). */
const FLOAT = /^-?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/;

// ---- the installed files

function pkgConfig(...args: string[]): string | undefined {
  try {
    const out = execFileSync(process.env['PKG_CONFIG'] ?? 'pkg-config', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    return out || undefined;
  } catch {
    return undefined;
  }
}

function read(path: string, what: string): unknown {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    throw new ProtocolError(`${what} ${path} is not readable (${e instanceof Error ? e.message : String(e)})`);
  }
}

/** Every reply code of a vocabulary file with its English sentence, wherever the file holds it. */
function texts(node: unknown, out: Map<string, string>): void {
  if (Array.isArray(node)) {
    for (const v of node) texts(v, out);
  } else if (node && typeof node === 'object') {
    const o = node as Record<string, unknown>;
    const text = o['text'] as Record<string, unknown> | undefined;
    if (typeof o['code'] === 'string' && text && typeof text === 'object' && typeof text['en'] === 'string' && !out.has(o['code'])) {
      out.set(o['code'], text['en']);
    }
    for (const v of Object.values(o)) texts(v, out);
  }
}

interface Form {
  readonly args: readonly string[] | null;
  readonly tail?: boolean;
}

interface Table {
  readonly commands: readonly { readonly verb: string; readonly forms: readonly Form[] }[];
  readonly feedback: readonly { readonly line: string; readonly args: readonly string[] | null; readonly tail?: boolean }[];
  readonly protocol_errors: readonly { readonly name: string; readonly code: number; readonly message: string }[];
  readonly reply_codes: readonly { readonly resp: number; readonly code: string }[];
}

export interface ProtocolOptions {
  /** The protocol table: PLUGIN_HOSTD_PROTOCOL_TABLE, else pkg-config's table variable of plugin-hostd-protocol. */
  readonly table?: string;
  /** omx-contract's contract directories, read for the sentences: OMX_CONTRACT_PATH, else its contractdir variable. */
  readonly contractDirs?: readonly string[];
  /** Where each package's catalogs/<lang>.json is: pkg-config's datadir of plugin-hostd-protocol. */
  readonly datadir?: string;
}

/** plugin-hostd's protocol as its installed files declare it. */
export class Protocol {
  readonly tablePath: string;
  private readonly commands: Map<string, { readonly forms: readonly Form[] }>;
  private readonly feedback: Map<string, Table['feedback'][number]>;
  private readonly protocolErrors: Map<string, Table['protocol_errors'][number]>;
  private readonly names: Map<number, string>;
  private readonly codes: Map<string, number>;
  private readonly sentences = new Map<string, string>();
  private readonly owners = new Map<string, string>();
  private readonly catalogs = new Map<string, Record<string, string>>();
  private readonly datadir: string;

  constructor(options: ProtocolOptions = {}) {
    const table = options.table ?? process.env['PLUGIN_HOSTD_PROTOCOL_TABLE'] ?? pkgConfig('--variable=table', 'plugin-hostd-protocol');
    if (!table) {
      throw new ProtocolError('no protocol table: plugin-hostd-protocol-devel is not installed and PLUGIN_HOSTD_PROTOCOL_TABLE is not set');
    }
    this.tablePath = table;
    const t = read(table, 'the protocol table') as Table;
    this.commands = new Map(t.commands.map((c) => [c.verb, c]));
    this.feedback = new Map(t.feedback.map((f) => [f.line, f]));
    this.protocolErrors = new Map(t.protocol_errors.map((e) => [e.message, e]));
    this.names = new Map(t.reply_codes.map((r) => [r.resp, r.code]));
    this.codes = new Map(t.reply_codes.map((r) => [r.code, r.resp]));
    const env = process.env['OMX_CONTRACT_PATH'];
    const contractDirs = options.contractDirs ??
      (env ? env.split(':').filter(Boolean) : [pkgConfig('--variable=contractdir', 'omx-contract')].filter((d): d is string => !!d));
    this.datadir = options.datadir ?? pkgConfig('--variable=datadir', 'plugin-hostd-protocol') ?? dirname(dirname(resolve(table)));
    for (const d of contractDirs) {
      const root = join(d, '3');
      const packages = existsSync(root) ? readdirSync(root).sort() : [];
      for (const pkg of packages) {
        const path = join(root, pkg, 'verbs.json');
        if (!existsSync(path)) continue;
        const found = new Map<string, string>();
        texts(read(path, 'the vocabulary'), found);
        for (const [code, text] of found) {
          if (this.codes.has(code) && !this.sentences.has(code)) {
            this.sentences.set(code, text);
            this.owners.set(code, pkg);
          }
        }
      }
    }
  }

  // ---- commands

  private arg(kind: string, value: unknown): string {
    if (kind === 'int') {
      if (!isNumber(value) || !Number.isInteger(value)) throw new ProtocolError(`${JSON.stringify(value)} is not an integer`);
      return String(value);
    }
    if (kind === 'float') return formatNumber(value as number);
    if (typeof value === 'string') return word(value);
    if (isNumber(value)) return formatNumber(value);
    throw new ProtocolError(`${JSON.stringify(value)} is not a word`);
  }

  /** The line of a command the table declares: the first form whose arguments fit, after @<tag> when one is given. */
  encode(verb: string, args: readonly Arg[], tag?: string | null): string {
    const command = this.commands.get(verb);
    if (!command) throw new ProtocolError(`the protocol declares no command ${verb}`);
    let why = `no form of ${verb} takes ${args.length} arguments`;
    for (const form of command.forms) {
      const kinds = form.args ?? [];
      if (args.length < kinds.length || (args.length > kinds.length && !form.tail)) continue;
      try {
        const out = kinds.map((k, i) => this.arg(k, args[i]));
        for (const a of args.slice(kinds.length)) out.push(this.arg('word', a));
        return [...(tag === undefined || tag === null ? [] : ['@' + tag]), verb, ...out].join(' ');
      } catch (e) {
        if (!(e instanceof ProtocolError)) throw e;
        why = `${verb}: ${e.message}`;
      }
    }
    throw new ProtocolError(why);
  }

  /** A command line back into its verb, its arguments (each as its type) and its request tag. */
  decode(line: string): Decoded {
    let w = words(line);
    let tag: string | undefined;
    if (w.length && w[0]!.startsWith('@')) {
      tag = w[0]!.slice(1);
      w = w.slice(1);
    }
    const verb = w[0];
    const command = verb === undefined ? undefined : this.commands.get(verb);
    if (!command || verb === undefined) throw new ProtocolError(`the protocol declares no command ${verb ?? '(empty)'}`);
    const rest = w.slice(1);
    for (const form of command.forms) {
      const kinds = form.args ?? [];
      if (rest.length < kinds.length || (rest.length > kinds.length && !form.tail)) continue;
      try {
        const args: Arg[] = [...kinds.map((k, i) => this.value(k, rest[i]!)), ...rest.slice(kinds.length)];
        return tag === undefined ? { verb, args } : { tag, verb, args };
      } catch (e) {
        if (!(e instanceof ProtocolError)) throw e;
      }
    }
    throw new ProtocolError(`no form of ${verb} reads ${line}`);
  }

  private value(kind: string, w: string): Arg {
    if (kind === 'int') {
      if (!INT.test(w)) throw new ProtocolError(`${w} is not an integer`);
      return Number(w);
    }
    if (kind === 'float') {
      if (!FLOAT.test(w)) throw new ProtocolError(`${w} is not a number`);
      const v = Number(w);
      if (!Number.isFinite(v)) throw new ProtocolError(`${w} is not a finite number`);
      return v;
    }
    return w;
  }

  /** A command line decoded and encoded again: the client's own spelling of it. */
  reencode(line: string): string {
    const d = this.decode(line);
    return this.encode(d.verb, d.args, d.tag);
  }

  // ---- replies

  /**
   * What the host or the daemon answered: a tag (@<tag>) and a sequence number (#<n>) first when the line carries
   * them, then resp <code> [data], a protocol error, or a feedback line by its declared arguments.
   */
  parse(line: string): Reply {
    let w = words(line);
    let tag: string | undefined;
    let seq: number | undefined;
    if (w.length && w[0]!.startsWith('@') && w[0]!.length > 1) {
      tag = w[0]!.slice(1);
      w = w.slice(1);
    }
    if (w.length && w[0]!.startsWith('#') && /^[0-9]+$/.test(w[0]!.slice(1))) {
      seq = Number(w[0]!.slice(1));
      w = w.slice(1);
    }
    const head = { ...(tag === undefined ? {} : { tag }), ...(seq === undefined ? {} : { seq }) };
    if (!w.length) throw new ProtocolError('an empty reply');
    if (w[0] === 'resp') {
      if (w.length < 2 || !INT.test(w[1]!)) throw new ProtocolError(`resp with no code: ${line}`);
      const code = Number(w[1]);
      const name = this.names.get(code);
      return { kind: 'resp', ...head, code, ...(name === undefined ? {} : { name }), data: w.slice(2) };
    }
    const error = this.protocolErrors.get(w.join(' '));
    if (error) return { kind: 'protocol_error', ...head, code: error.code, name: error.name };
    const fb = this.feedback.get(w[0]!);
    if (fb) {
      const rest = w.slice(1);
      let args: Arg[] = rest;
      if (fb.args !== null) {
        if (rest.length < fb.args.length || (rest.length > fb.args.length && !fb.tail)) {
          throw new ProtocolError(`${w[0]} takes ${fb.args.length} arguments: ${line}`);
        }
        args = [...fb.args.map((k, i) => this.value(k, rest[i]!)), ...rest.slice(fb.args.length)];
      }
      return { kind: 'feedback', ...head, line: w[0]!, args };
    }
    throw new ProtocolError(`no reply the protocol declares: ${line}`);
  }

  // ---- codes

  /** The number of a reply code by its name (reply.<group>.<reason>); ProtocolError for one the table lacks. */
  code(name: string): number {
    const code = this.codes.get(name);
    if (code === undefined) throw new ProtocolError(`the protocol declares no code ${name}`);
    return code;
  }

  /** The name of a reply code, or null for a number the table gives no name. */
  name(code: number): string | null {
    return this.names.get(code) ?? null;
  }

  /** What a reply code says to an operator, in English from the vocabulary or in `lang` from its owner's catalog. */
  sentence(code: number, lang = 'en'): string | null {
    const name = this.names.get(code);
    if (name === undefined) return null;
    if (lang === 'en') return this.sentences.get(name) ?? null;
    const owner = this.owners.get(name);
    if (owner === undefined) return null;
    const key = `${owner}/${lang}`;
    if (!this.catalogs.has(key)) {
      const path = join(this.datadir, owner, 'catalogs', `${lang}.json`);
      const doc = existsSync(path) ? (read(path, 'the catalog') as { messages?: Record<string, string> }) : {};
      this.catalogs.set(key, doc.messages ?? {});
    }
    return this.catalogs.get(key)![name] ?? null;
  }
}
