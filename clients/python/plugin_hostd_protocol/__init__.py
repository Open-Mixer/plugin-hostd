# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The Python client of plugin-hostd's protocol (docs/clients.md).

One codec over the files plugin-hostd-protocol installs: its protocol table (every command, feedback line, protocol
error and reply code), the vocabulary of omx-contract's contract directory (each reply code's English sentence) and
the catalogs (its sentence in another language). Nothing of the protocol is written here; a file that is not there is
an error naming it. No transport: a controller opens the socket and sends the lines.
"""
import json
import math
import os
import re
import subprocess

try:  # the paths pkg-config gave when the package was installed (make install-python): no -devel package at run time
    from . import _installed
except ImportError:
    _installed = None

__all__ = ["Protocol", "ProtocolError", "words", "quote", "encode_path", "decode_path", "uri_word", "pin_key",
           "format_number"]


class ProtocolError(ValueError):
    """A line the table does not declare, an argument no form takes, a reply that is no reply."""


# ---- the words of a line, as plugin-hostd-protocol's grammar (core.abnf: word, quoted, escaped-quote) writes them,
# and the percent-encoded path of a clap: uri, as its pin section does (PHD_PIN_PATH_EXCLUDED, PHD_PIN_PATH_ESCAPE)

# the daemon's tokenizer splits at C's isspace(): these six, and no other character
SPACE = " \t\n\v\f\r"
CLAP_PREFIX = "clap:"
ESCAPE = "%"
EXCLUDED = ",= \t\r\n"


def words(line):
    """The words of a line as the daemon reads them: split at whitespace; a word that starts with a quotation mark
    runs to the next one no backslash escapes, \\" in it is a quote, the marks are not part of it; a quoted word that
    never closes runs to the end of the line."""
    out, i, n = [], 0, len(line)
    while i < n:
        if line[i] in SPACE:
            i += 1
        elif line[i] == '"':
            i += 1
            word = []
            while i < n and line[i] != '"':
                if line[i] == "\\" and i + 1 < n and line[i + 1] == '"':
                    i += 1
                word.append(line[i])
                i += 1
            i += 1
            out.append("".join(word))
        else:
            j = i
            while j < n and line[j] not in SPACE:
                j += 1
            out.append(line[i:j])
            i = j
    return out


def quote(value):
    """A value as one quoted word: in quotation marks, \\" for a quote (the grammar's only escape)."""
    return '"' + value.replace('"', '\\"') + '"'


def _word(value):
    """A string as one word: bare when it can be, quoted when it is empty or holds whitespace or a quote."""
    if value and not any(c in SPACE or c == '"' for c in value):
        return value
    return quote(value)


def _escaped(c):
    return ord(c) < 0x20 or ord(c) == 0x7F or c in (ESCAPE, '"', "\\") or c in EXCLUDED


def encode_path(path):
    """A path as the word of a pin: every separator of pin_set's words, whitespace, the escape, a quote, a backslash and
    a control byte as %XX (uppercase hex) of its UTF-8 bytes, the rest as it is."""
    return "".join("".join("%%%02X" % b for b in c.encode()) if _escaped(c) else c for c in path)


def decode_path(word):
    """A percent-encoded path as it is; ProtocolError for a % not followed by two hex digits, as the daemon refuses."""
    raw, out, i = word.encode(), bytearray(), 0
    while i < len(raw):
        if raw[i] == ord(ESCAPE):
            digits = raw[i + 1:i + 3]
            if len(digits) != 2 or not all(chr(d) in "0123456789abcdefABCDEF" for d in digits):
                raise ProtocolError("'%%' not followed by two hex digits in %s" % word)
            out.append(int(digits, 16))
            i += 3
        else:
            out.append(raw[i])
            i += 1
    return out.decode(errors="surrogateescape")


def _split_uri(uri):
    if not uri.startswith(CLAP_PREFIX) or "#" not in uri:
        return None
    path, _, plugin_id = uri[len(CLAP_PREFIX):].rpartition("#")
    return path, plugin_id


def uri_word(uri):
    """A plugin uri as the daemon takes it: a clap: uri's path percent-encoded, so any file name is one bare word; any
    other uri as it is."""
    parts = _split_uri(uri)
    return uri if parts is None else "%s%s#%s" % (CLAP_PREFIX, encode_path(parts[0]), parts[1])


def pin_key(uri):
    """What a pin is keyed by: a clap: uri with its path decoded, so every spelling of one uri is one key."""
    parts = _split_uri(uri)
    if parts is None:
        return uri
    try:
        return "%s%s#%s" % (CLAP_PREFIX, decode_path(parts[0]), parts[1])
    except ProtocolError:
        return uri


# ---- numbers


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def format_number(value):
    """A finite number as a word: its shortest digits that read back to the same double, laid out as ECMAScript's
    Number.prototype.toString lays them out, so both clients write one spelling: an integral value with no fraction,
    0.000001 in full, 1e-7 and 1e+21 with an exponent and no leading zero."""
    if not _is_number(value):
        raise ProtocolError("%r is not a finite number" % (value,))
    x = float(value)
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    mantissa, _, exponent = repr(abs(x)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    if fraction == "0":
        fraction = ""
    digits = (whole + fraction).lstrip("0")
    point = len(whole) + (int(exponent) if exponent else 0) - (len(whole + fraction) - len((whole + fraction).lstrip("0")))
    digits = digits.rstrip("0") or "0"
    k, n = len(digits), point
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    return sign + digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e > 0 else "-") + str(abs(e))


_INT = re.compile(r"^-?[0-9]+$")
# a decimal numeral, as both clients read one (no digit separator, no other script's digits, no inf or nan)
_FLOAT = re.compile(r"^-?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")


# ---- the installed files


def _pkg_config(*args):
    try:
        out = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), *args], capture_output=True, text=True)
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def _read(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise ProtocolError("%s %s is not readable (%s)" % (what, path, e)) from e


def _texts(node, out):
    """Every reply code of a vocabulary file with its English sentence, wherever the file holds it."""
    if isinstance(node, dict):
        if isinstance(node.get("code"), str) and isinstance(node.get("text"), dict) and "en" in node["text"]:
            out.setdefault(node["code"], node["text"]["en"])
        for v in node.values():
            _texts(v, out)
    elif isinstance(node, list):
        for v in node:
            _texts(v, out)


class Protocol:
    """plugin-hostd's protocol as its installed files declare it.

    table: the protocol table (PLUGIN_HOSTD_PROTOCOL_TABLE, else where the installed package was told it is, else
    pkg-config's table variable of plugin-hostd-protocol);
    contract_dirs: omx-contract's contract directories (OMX_CONTRACT_PATH, else its contractdir variable), read for the
    sentences; datadir: where each package's catalogs/<lang>.json is (pkg-config's datadir of plugin-hostd-protocol)."""

    def __init__(self, table=None, contract_dirs=None, datadir=None):
        table = table or os.environ.get("PLUGIN_HOSTD_PROTOCOL_TABLE") or getattr(_installed, "TABLE", None) or \
            _pkg_config("--variable=table", "plugin-hostd-protocol")
        if not table:
            raise ProtocolError("no protocol table: plugin-hostd-protocol-devel is not installed and "
                                "PLUGIN_HOSTD_PROTOCOL_TABLE is not set")
        self.table_path = table
        t = _read(table, "the protocol table")
        self.commands = {c["verb"]: c for c in t["commands"]}
        self.feedback = {f["line"]: f for f in t["feedback"]}
        self.protocol_errors = {e["message"]: e for e in t["protocol_errors"]}
        self.names = {r["resp"]: r["code"] for r in t["reply_codes"]}
        self.codes = {v: k for k, v in self.names.items()}
        if contract_dirs is None:
            env = os.environ.get("OMX_CONTRACT_PATH")
            contract_dirs = [d for d in env.split(":") if d] if env else list(getattr(_installed, "CONTRACT_DIRS", ())) or \
                [d for d in [_pkg_config("--variable=contractdir", "omx-contract")] if d]
        self.datadir = datadir or getattr(_installed, "DATADIR", None) or \
            _pkg_config("--variable=datadir", "plugin-hostd-protocol") or \
            os.path.dirname(os.path.dirname(os.path.abspath(table)))
        self.sentences, self.owners = {}, {}
        for d in contract_dirs:
            root = os.path.join(d, "3")
            for package in sorted(os.listdir(root)) if os.path.isdir(root) else []:
                path = os.path.join(root, package, "verbs.json")
                if not os.path.isfile(path):
                    continue
                found = {}
                _texts(_read(path, "the vocabulary"), found)
                for code, text in found.items():
                    if code in self.codes and code not in self.sentences:
                        self.sentences[code] = text
                        self.owners[code] = package
        self._catalogs = {}

    # ---- commands

    def _arg(self, kind, value):
        if kind == "int":
            if not _is_number(value) or float(value) != int(value):
                raise ProtocolError("%r is not an integer" % (value,))
            return str(int(value))
        if kind == "float":
            return format_number(value)
        if isinstance(value, str):
            return _word(value)
        if _is_number(value):
            return format_number(value)
        raise ProtocolError("%r is not a word" % (value,))

    def encode(self, verb, args, tag=None):
        """The line of a command the table declares: the first form whose arguments fit, after @<tag> when a request
        tag is given (the tags extension: the answer carries the same tag)."""
        command = self.commands.get(verb)
        if command is None:
            raise ProtocolError("the protocol declares no command %s" % verb)
        why = "no form of %s takes %d arguments" % (verb, len(args))
        for form in command["forms"]:
            kinds = form["args"] or []
            if len(args) < len(kinds) or (len(args) > len(kinds) and not form.get("tail")):
                continue
            try:
                out = [self._arg(k, a) for k, a in zip(kinds, args)]
                out += [self._arg("word", a) for a in args[len(kinds):]]
            except ProtocolError as e:
                why = "%s: %s" % (verb, e)
                continue
            return " ".join(([] if tag is None else ["@" + tag]) + [verb] + out)
        raise ProtocolError(why)

    def decode(self, line):
        """A command line back into {"verb", "args"} and its request tag ("tag", when it starts with @<tag>): the first
        form its words fit, each argument as its type."""
        w = words(line)
        tag = None
        if w and w[0].startswith("@"):
            tag, w = w[0][1:], w[1:]
        if not w or w[0] not in self.commands:
            raise ProtocolError("the protocol declares no command %s" % (w[0] if w else "(empty)"))
        verb, rest = w[0], w[1:]
        for form in self.commands[verb]["forms"]:
            kinds = form["args"] or []
            if len(rest) < len(kinds) or (len(rest) > len(kinds) and not form.get("tail")):
                continue
            try:
                return {"tag": tag, "verb": verb,
                        "args": [self._value(k, v) for k, v in zip(kinds, rest)] + rest[len(kinds):]}
            except ProtocolError:
                continue
        raise ProtocolError("no form of %s reads %s" % (verb, line))

    def _value(self, kind, word):
        if kind == "int":
            if not _INT.match(word):
                raise ProtocolError("%s is not an integer" % word)
            return int(word)
        if kind == "float":
            if not _FLOAT.match(word):
                raise ProtocolError("%s is not a number" % word)
            v = float(word)
            if not math.isfinite(v):
                raise ProtocolError("%s is not a finite number" % word)
            return v
        return word

    def reencode(self, line):
        """A command line decoded and encoded again: the client's own spelling of it."""
        d = self.decode(line)
        return self.encode(d["verb"], d["args"], d["tag"])

    # ---- replies

    def parse(self, line):
        """What the host or the daemon answered: a tag (@<tag>) and a sequence number (#<n>) first when the line carries
        them, then resp <code> [data], a protocol error, or a feedback line by its declared arguments."""
        w = words(line)
        tag = seq = None
        if w and w[0].startswith("@") and len(w[0]) > 1:
            tag, w = w[0][1:], w[1:]
        if w and w[0].startswith("#") and _INT.match(w[0][1:]) and not w[0][1:].startswith("-"):
            seq, w = int(w[0][1:]), w[1:]
        if not w:
            raise ProtocolError("an empty reply")
        if w[0] == "resp":
            if len(w) < 2 or not _INT.match(w[1]):
                raise ProtocolError("resp with no code: %s" % line)
            code = int(w[1])
            return {"kind": "resp", "tag": tag, "seq": seq, "code": code, "name": self.names.get(code), "data": w[2:]}
        error = self.protocol_errors.get(" ".join(w))
        if error is not None:
            return {"kind": "protocol_error", "tag": tag, "seq": seq, "code": error["code"], "name": error["name"]}
        fb = self.feedback.get(w[0])
        if fb is not None:
            kinds, rest = fb["args"], w[1:]
            if kinds is not None:
                if len(rest) < len(kinds) or (len(rest) > len(kinds) and not fb.get("tail")):
                    raise ProtocolError("%s takes %d arguments: %s" % (w[0], len(kinds), line))
                args = [self._value(k, v) for k, v in zip(kinds, rest)] + rest[len(kinds):]
            else:
                args = rest
            return {"kind": "feedback", "tag": tag, "seq": seq, "line": w[0], "args": args}
        raise ProtocolError("no reply the protocol declares: %s" % line)

    # ---- codes

    def code(self, name):
        """The number of a reply code by its name (reply.<group>.<reason>); ProtocolError for one the table lacks."""
        if name not in self.codes:
            raise ProtocolError("the protocol declares no code %s" % name)
        return self.codes[name]

    def name(self, code):
        """The name of a reply code, or None for a number the table gives no name."""
        return self.names.get(code)

    def sentence(self, code, lang="en"):
        """What a reply code says to an operator, in English from the vocabulary or in `lang` from its owner's
        catalog; None when neither has it."""
        name = self.names.get(code)
        if name is None:
            return None
        if lang == "en":
            return self.sentences.get(name)
        owner = self.owners.get(name)
        if owner is None:
            return None
        key = (owner, lang)
        if key not in self._catalogs:
            path = os.path.join(self.datadir, owner, "catalogs", "%s.json" % lang)
            self._catalogs[key] = _read(path, "the catalog").get("messages", {}) if os.path.isfile(path) else {}
        return self._catalogs[key].get(name)
