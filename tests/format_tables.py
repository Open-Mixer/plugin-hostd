# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The format tables of this tree, as the tests read them: the domains plugin-hostd/clap and plugin-hostd/lv2
# (contract.d/plugin-hostd/<format>/<format>.json), each holding one item of omx-contract's mapping-table kind, x-kind map
# (omx-contract#191): x-format the format, and a oneOf of one row per source field. rows() gives them in the data form
# docs/formats.md names them by ({ <source field>: { term, from, word, extension, dropped, doc } }), and an edit of that
# view (a row set or popped, a key of a row set or popped, a word's keys changed) is an edit of the map item.
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS = os.path.join(ROOT, "contract.d", "plugin-hostd")
ITEMS = {"clap": "PLUGIN_HOSTD_CLAP_MAP", "lv2": "PLUGIN_HOSTD_LV2_MAP"}
# a row's data-form key, and the map row's key it is (omx-contract's rebuild writes them in this order)
KEYS = (("term", "x-term"), ("from", "x-from"), ("word", "x-word"), ("extension", "x-extension"),
        ("dropped", "x-dropped"), ("doc", "description"))
X = dict(KEYS)


def path(fmt):
    """The domain document of a format's table."""
    return os.path.join(DOMAINS, fmt, fmt + ".json")


def load(fmt):
    """The domain document of a format's table, parsed."""
    with open(path(fmt)) as f:
        return json.load(f)


def item(doc, fmt):
    """The item of the table: x-kind map, x-format the format, oneOf its rows."""
    return doc["components"]["schemas"][ITEMS[fmt]]


def map_row(field, row, code):
    """A data-form row as the map row of source field `field` at place `code`."""
    out = {"const": field, "title": field, "x-code": code}
    if "doc" in row:
        out["description"] = row["doc"]
    for k, x in KEYS:
        if k != "doc" and k in row:
            out[x] = row[k]
    return out


class Row(dict):
    """One row in the data form; its keys write through to the map row (a word is the map row's own x-word object)."""

    def __init__(self, m):
        super().__init__((k, m[x]) for k, x in KEYS if x in m)
        self._m = m

    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        self._m[X[k]] = v

    def __delitem__(self, k):
        super().__delitem__(k)
        del self._m[X[k]]

    def pop(self, k, *default):
        if k in self:
            self._m.pop(X[k], None)
        return super().pop(k, *default)

    def update(self, *a, **kw):
        for k, v in dict(*a, **kw).items():
            self[k] = v


class Rows(dict):
    """The rows of a map item in the data form, { <source field>: Row }; setting or popping a row edits the oneOf."""

    def __init__(self, it):
        self._it = it
        super().__init__((m["const"], Row(m)) for m in it["oneOf"])

    def __setitem__(self, k, row):
        ones = self._it["oneOf"]
        at = next((i for i, m in enumerate(ones) if m["const"] == k), None)
        m = map_row(k, row, len(ones) if at is None else at)
        if at is None:
            ones.append(m)
        else:
            ones[at] = m
        super().__setitem__(k, Row(m))

    def pop(self, k, *default):
        if k in self:
            self._it["oneOf"] = [m for m in self._it["oneOf"] if m["const"] != k]
            for i, m in enumerate(self._it["oneOf"]):
                m["x-code"] = i
        return super().pop(k, *default)

    def __delitem__(self, k):
        self.pop(k)


def rows(doc, fmt):
    """The rows of the table, { <source field>: <row> } in the data form, editing the document through."""
    return Rows(item(doc, fmt))
