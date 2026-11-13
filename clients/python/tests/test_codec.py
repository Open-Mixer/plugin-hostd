# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pau Aliagas <linuxnow@gmail.com>
"""The Python client on clients/fixtures/codec.json (docs/clients.md), and what JSON cannot carry: a number that is
not finite, a boolean where a number goes."""
import json
import math
import os
import unittest

from plugin_hostd_protocol import RETRY_REASONS, GroupingReason, Protocol, ProtocolError, format_number
from plugin_hostd_protocol.__main__ import answer

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "codec.json")
GROUPING = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "grouping.json")


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


class Replies(unittest.TestCase):
    """The replies with a shape of their own, on the lines docs/guide.md shows."""

    def setUp(self):
        self.protocol = Protocol()

    def data(self, line):
        reply = self.protocol.parse(line)
        self.assertEqual(reply["code"], 0)
        return reply["data"]

    def test_a_plan_is_read_from_the_reply_as_it_is_parsed(self):
        plan = self.protocol.read_plan(self.data("resp 0 1,2;3 0,0;-"))
        self.assertEqual(plan, {"segments": [[1, 2], [3]], "cores": [[0, 0], [None]]})

    def test_a_plan_read_back_names_the_reason_and_whether_to_ask_again(self):
        plan = self.protocol.read_plan_get(self.data("resp 0 1,2;3 3:plan-refused:-544 0,0;-"))
        self.assertEqual(plan["reasons"], [{"instance": 3, "reason": "plan-refused:-544", "word": "plan-refused",
                                            "code": -544, "name": "reply.plugin-hostd.preset-not-applied",
                                            "retry": True}])
        self.assertEqual(self.protocol.read_plan_get(self.data("resp 0 1 1:verdict-isolated -"))["reasons"][0]["retry"],
                         False)

    def test_an_estimate_names_every_figure(self):
        e = self.protocol.read_estimate(self.data("resp 0 192 24.00 - 2 1 1:-544 0 - - 3"))
        self.assertEqual((e["latency_frames"], e["cpu_percent"], e["ram_bytes"], e["workers"], e["unknown_count"]),
                         (192, 24.0, None, 2, 1))
        self.assertEqual(e["members"], [{"member": 1, "code": -544, "name": "reply.plugin-hostd.preset-not-applied"}])
        self.assertEqual((e["ram_used_bytes"], e["ram_added_bytes"], e["ram_budget_bytes"], e["ram_unknown_count"]),
                         (0, None, None, 3))

    def test_the_reasons_to_ask_again_are_words_the_daemon_declares(self):
        with open(GROUPING) as f:
            words = [w["word"] for w in json.load(f)["PLUGIN_HOSTD_GROUPING_REASONS"]["words"].values()]
        self.assertEqual(RETRY_REASONS, ("no-verdict", "plan-refused"))
        for word in RETRY_REASONS:
            self.assertIn(word, words)


class GroupingReasons(unittest.TestCase):
    """The reasons a plan gives are constants of the reader, written from data/grouping.json (#67)."""

    @staticmethod
    def declared():
        with open(GROUPING) as f:
            return {w["word"] for w in json.load(f)["PLUGIN_HOSTD_GROUPING_REASONS"]["words"].values()}

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

    def test_the_known_reasons_are_the_files(self):
        self.assertEqual(GroupingReason.GROUPING_OFF, "grouping-off")
        self.assertEqual(GroupingReason.PLAN_REFUSED, "plan-refused")


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
