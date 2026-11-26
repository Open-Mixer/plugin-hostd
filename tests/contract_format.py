# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The omx-contract format a manifest or a domain document a test writes must state (its x-omx-contract): MAJOR.MINOR
of the x-omx-schema-version of the installed omx-contract.schema.json, and the address of that schema (the major only
in its path). Read from the installed omx-contract (the datadir of its pkg-config file), never typed in a test: the
contract directory has no schema-major level, so the documents are where the format is stated."""
import json
import os
import subprocess


def schema_path():
    datadir = subprocess.run([os.environ.get("PKG_CONFIG", "pkg-config"), "--variable=datadir", "omx-contract"],
                             capture_output=True, text=True).stdout.strip()
    return os.environ.get("OMX_CONTRACT_SCHEMA") or os.path.join(datadir, "omx-contract.schema.json")


def _schema():
    with open(schema_path(), encoding="utf-8") as f:
        return json.load(f)


def fmt():
    """the format as a document states it: "0.23" of the schema version 0.23.0"""
    return ".".join(_schema()["x-omx-schema-version"].split(".")[:2])


def schema_url():
    """the schema's own address, the $schema of a data file as installed"""
    return _schema()["$id"]
