#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The grouping reasons plugin-hostd declares are the ones plugin-hostd-protocol's Python client reads.

data/grouping.json declares them (PLUGIN_HOSTD_GROUPING_REASONS); GroupingReason and RETRY_REASONS of the installed
python3-plugin-hostd-protocol (PLUGIN_HOSTD_CODEC_DIR: the directory holding plugin_hostd_protocol, when it is not
installed) must name every declared reason with the file's word, no other, and ask again for the reasons the file
declares retry. The codec lives in plugin-hostd-protocol and this tree keeps no copy of it, so the declaration is held to
the reader here, where the declaration is.

Usage: tests/grouping_reasons_test.py
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUPING = os.path.join(ROOT, "data", "grouping.json")
if os.environ.get("PLUGIN_HOSTD_CODEC_DIR"):
    sys.path.insert(0, os.environ["PLUGIN_HOSTD_CODEC_DIR"])
from plugin_hostd_protocol import RETRY_REASONS, GroupingReason  # noqa: E402


def declaration():
    with open(GROUPING) as f:
        return json.load(f)


class GroupingReasons(unittest.TestCase):
    @staticmethod
    def declared():
        return {w["word"] for w in declaration()["PLUGIN_HOSTD_GROUPING_REASONS"]["words"].values()}

    @staticmethod
    def constants():
        return {k: v for k, v in vars(GroupingReason).items() if not k.startswith("_")}

    def test_every_declared_reason_has_its_constant_with_the_files_value(self):
        by_value = {v: k for k, v in self.constants().items()}
        for word in sorted(self.declared()):
            with self.subTest(word=word):
                self.assertIn(word, by_value)
                self.assertEqual(by_value[word], word.upper().replace("-", "_"))

    def test_no_constant_names_a_reason_the_file_does_not_declare(self):
        self.assertEqual(sorted(set(self.constants().values()) - self.declared()), [])
        self.assertEqual(len(self.constants()), len(self.declared()))

    def test_every_reason_declares_its_retry_property(self):
        file = declaration()
        groups = {w["word"] for w in file["PLUGIN_HOSTD_GROUPING_REASON_GROUPS"]["words"].values()}
        self.assertEqual(groups, {"retry", "final"})
        self.assertEqual(file["PLUGIN_HOSTD_GROUPING_REASONS"]["groups"], "PLUGIN_HOSTD_GROUPING_REASON_GROUPS")
        for key, row in file["PLUGIN_HOSTD_GROUPING_REASONS"]["words"].items():
            with self.subTest(reason=key):
                self.assertIn(row.get("group"), groups)

    def test_the_reasons_to_ask_again_are_the_reasons_the_file_declares_retry(self):
        item = declaration()["PLUGIN_HOSTD_GROUPING_REASONS"]
        declared = tuple(w["word"] for w in item["words"].values() if w.get("group") == "retry")
        self.assertTrue(declared)
        self.assertEqual(RETRY_REASONS, declared)


if __name__ == "__main__":
    unittest.main()
