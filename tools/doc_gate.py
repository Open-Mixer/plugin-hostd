#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The C documentation gate: every public function and struct/union/enum definition at file scope of the headers
named on the command line carries a comment immediately before it (blank lines and preprocessor lines between are
allowed). A ratchet: tools/doc-gate.baseline lists the items that are missing today, one `file:name` per line. An
item missing and not in the baseline fails (a new undocumented item); an item in the baseline that now has its
comment fails too (remove the line, so the list only shrinks). Headers carrying GENERATED in their first lines are
skipped. `--self-test` runs the checker over scratch headers and requires the undocumented one to be refused.

Usage: doc_gate.py [--baseline FILE] [--list] HEADER...   |   doc_gate.py --self-test
"""
import os
import re
import sys
import tempfile


def clean(text):
    """The header as (characters, line of each): comments become one \\x01 mark, strings their quotes, and
    preprocessor lines (continuations included) and the characters inside them are dropped."""
    out, lines = [], []
    i, n, line, bol = 0, len(text), 1, True
    while i < n:
        c = text[i]
        if c == "\n":
            out.append(c); lines.append(line); line += 1; i += 1; bol = True
            continue
        if bol and c == "#":
            while i < n and text[i] != "\n":
                if text[i] == "\\" and text[i + 1:i + 2] == "\n":
                    line += 1; i += 1
                i += 1
            continue
        if c not in " \t\r":
            bol = False
        if text.startswith("/*", i) or text.startswith("//", i):
            end = "*/" if text[i + 1] == "*" else "\n"
            j = text.find(end, i + 2)
            j = n if j < 0 else (j + 2 if end == "*/" else j)
            out.append("\x01"); lines.append(line)
            line += text.count("\n", i, j)
            i = j
            continue
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(c + c); lines.append(line); i = j + 1
            continue
        out.append(c); lines.append(line); i += 1
    return "".join(out), lines


def skip_body(txt, i):
    """The index just after the brace group that opens at txt[i]."""
    d = 0
    while i < len(txt):
        if txt[i] == "{":
            d += 1
        elif txt[i] == "}":
            d -= 1
            if d == 0:
                return i + 1
        i += 1
    return i


def scan(text):
    """The items of a header: a list of (line, name, kind, documented) for each file-scope function or type."""
    txt, lines = clean(text)
    items, i, n, start = [], 0, len(txt), 0
    transparent = 0
    while i < n:
        c = txt[i]
        if c not in ";{}":
            i += 1
            continue
        raw = txt[start:i]
        head = " ".join(raw.replace("\x01", " \x01 ").split())
        documented = head.startswith("\x01")
        s = re.sub(r"__attribute__\s*\(\(.*?\)\)", "", head.replace("\x01", "")).strip()
        line = lines[min(start + len(raw) - len(raw.lstrip()), n - 1)] if raw.strip() else lines[i]
        if c == "}":
            transparent = max(0, transparent - 1)
            i += 1; start = i
            continue
        if c == "{" and s == 'extern ""':
            transparent += 1
            i += 1; start = i
            continue
        m = re.match(r"^(typedef\s+)?(struct|union|enum)\s*([A-Za-z_]\w*)?$", s)
        if c == "{" and m:
            j = skip_body(txt, i)
            k = txt.find(";", j)
            k = n if k < 0 else k
            name = m.group(3)
            if not name and m.group(1):
                d = re.search(r"([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*$", txt[j:k])
                name = d.group(1) if d else None
            if name:
                items.append((line, name, m.group(2), documented))
            i = k + 1; start = i
            continue
        p = s.find("(")
        is_func = (p > 0 and not s.startswith("typedef") and "=" not in s[:p]
                   and s[p + 1:].lstrip()[:1] != "*")
        if is_func:
            fm = re.search(r"([A-Za-z_]\w*)\s*$", s[:p])
            if fm and fm.group(1) not in ("if", "while", "for", "switch", "sizeof"):
                items.append((line, fm.group(1), "function", documented))
        if c == "{":
            j = skip_body(txt, i)
            if is_func:
                i = j; start = i
            else:
                k = txt.find(";", j)
                i = (n if k < 0 else k) + 1; start = i
            continue
        i += 1; start = i
    return items


def missing_items(path):
    """The `file:name` keys of the undocumented items of one header, sorted."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "GENERATED" in "\n".join(text.splitlines()[:12]):
        return []
    return sorted({"%s:%s" % (path, nm) for _ln, nm, _kd, doc in scan(text) if not doc})


def read_baseline(path):
    """The baseline keys, one per line, `#` lines ignored."""
    if not path or not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}


def gate(headers, baseline):
    """Exit status and messages: new missing items, and baseline lines whose item is now documented."""
    missing = set()
    for h in headers:
        missing.update(missing_items(h))
    base = read_baseline(baseline)
    msgs = ["doc-gate: %s has no comment immediately before it (add one, do not extend the baseline)" % k
            for k in sorted(missing - base)]
    msgs += ["doc-gate: %s is documented now: remove its line from %s" % (k, baseline)
             for k in sorted(base - missing)]
    return (1 if msgs else 0), msgs, len(missing)


def self_test():
    """A scratch header with one documented and one undocumented function: the gate must refuse only the latter."""
    src = ('#ifndef T_H\n#define T_H\n#ifdef __cplusplus\nextern "C" {\n#endif\n\n'
           "/* documented */\nint good(int a);\n\nint bad(int a);\n\n"
           "/* a struct */\nstruct good_s {\n  int x;\n};\n\nstruct bad_s {\n  int y;\n};\n\n"
           "typedef struct {\n  int z;\n} Bad_t;\n\n"
           "/* inline */\nstatic inline int fine(int a) { return a; }\nstatic inline int plain(int a) { return a; }\n"
           "extern void (*hook)(void);\n#ifdef __cplusplus\n}\n#endif\n#endif\n")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.h")
        with open(p, "w") as f:
            f.write(src)
        got = {k.split(":", 1)[1] for k in missing_items(p)}
        want = {"bad", "bad_s", "Bad_t", "plain"}
        if got != want:
            print("doc-gate self-test: wanted %s, got %s" % (sorted(want), sorted(got)))
            return 1
        base = os.path.join(d, "b")
        with open(base, "w") as f:
            f.write("\n".join("%s:%s" % (p, k) for k in sorted(want)) + "\n")
        if gate([p], base)[0] != 0:
            print("doc-gate self-test: a baselined header was refused")
            return 1
        with open(base, "w") as f:
            f.write("%s:bad\n" % p)
        if gate([p], base)[0] != 1:
            print("doc-gate self-test: new undocumented items were not refused")
            return 1
    print("doc-gate self-test: ok")
    return 0


def main(argv):
    """Command line: see the module docstring."""
    if argv[1:] == ["--self-test"]:
        return self_test()
    baseline, listing, heads = None, False, []
    a = argv[1:]
    while a:
        x = a.pop(0)
        if x == "--baseline":
            baseline = a.pop(0)
        elif x == "--list":
            listing = True
        else:
            heads.append(x)
    if listing:
        for h in heads:
            for k in missing_items(h):
                print(k)
        return 0
    status, msgs, total = gate(heads, baseline)
    print("\n".join(msgs))
    print("doc-gate: %d undocumented item(s), baseline %d" % (total, len(read_baseline(baseline))))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
