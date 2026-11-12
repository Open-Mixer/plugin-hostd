# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The Python client on clients/fixtures/codec.json (docs/clients.md), and what JSON cannot carry: a number that is
not finite, a boolean where a number goes."""
import json
import math
import os
import unittest

from plugin_hostd_protocol import Protocol, ProtocolError, format_number
from plugin_hostd_protocol.__main__ import answer

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "codec.json")


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = Protocol()
        with open(FIXTURES) as f:
            cls.cases = json.load(f)["cases"]

    def test_every_fixture(self):
        self.assertGreater(len(self.cases), 40)
        for case in self.cases:
            with self.subTest(op=case["op"], arg=case["in"]):
                if case.get("error"):
                    with self.assertRaises(ProtocolError):
                        answer(self.protocol, case["op"], case["in"])
                    continue
                got = answer(self.protocol, case["op"], case["in"])
                if "expect" in case:
                    self.assertEqual(clean(got), clean(case["expect"]))

    def test_a_sentence_comes_from_the_installed_vocabulary_and_catalog(self):
        p = self.protocol
        self.assertTrue(p.sentence(p.code("reply.host.param-symbol-invalid"), "en"))
        self.assertTrue(p.sentence(p.code("reply.plugin-hostd.preset-not-applied"), "ca"))
        self.assertIsNone(p.sentence(0, "en"))


class Numbers(unittest.TestCase):
    def test_a_number_that_is_not_finite_or_a_boolean_is_refused(self):
        p = Protocol()
        for bad in (math.nan, math.inf, -math.inf, True):
            with self.subTest(value=bad), self.assertRaises(ProtocolError):
                p.encode("param_set", [3, "gain", bad])

    def test_the_shortest_spelling_reads_back_to_the_same_double(self):
        for x in (0.1, 1 / 3, 2.5e-7, 123456789.125, 1e21, 5e-324, 1.7976931348623157e308, -0.000001, 1e-6, 100.0):
            with self.subTest(x=x):
                self.assertEqual(float(format_number(x)), x)

    def test_the_layout_is_the_ecmascript_one(self):
        cases = {1.0: "1", 1e20: "100000000000000000000", 1e21: "1e+21", 1e-6: "0.000001", 1e-7: "1e-7",
                 1.5e-7: "1.5e-7", 123.456: "123.456", -2.0: "-2", 0.0: "0", 2.5e100: "2.5e+100"}
        for x, want in cases.items():
            with self.subTest(x=x):
                self.assertEqual(format_number(x), want)


class Files(unittest.TestCase):
    def test_a_missing_table_is_named(self):
        with self.assertRaises(ProtocolError) as e:
            Protocol(table="/nonexistent/plugin-hostd-protocol.json")
        self.assertIn("/nonexistent/plugin-hostd-protocol.json", str(e.exception))


if __name__ == "__main__":
    unittest.main()
