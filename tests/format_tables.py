# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
#
# The format tables of this tree, as the tests read them: the domains plugin-hostd/clap and plugin-hostd/lv2
# (contract.d/plugin-hostd/<format>/<format>.json), each holding one sheet whose x-value is the map { format, rows }.
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS = os.path.join(ROOT, "contract.d", "plugin-hostd")
ITEMS = {"clap": "PLUGIN_HOSTD_CLAP_MAP", "lv2": "PLUGIN_HOSTD_LV2_MAP"}


def path(fmt):
    """The domain document of a format's table."""
    return os.path.join(DOMAINS, fmt, fmt + ".json")


def load(fmt):
    """The domain document of a format's table, parsed."""
    with open(path(fmt)) as f:
        return json.load(f)


def sheet(doc, fmt):
    """The item of the table: x-kind sheet, x-value the map."""
    return doc["components"]["schemas"][ITEMS[fmt]]


def rows(doc, fmt):
    """The rows of the table's map, { <source field>: <row> }."""
    return sheet(doc, fmt)["x-value"]["rows"]
