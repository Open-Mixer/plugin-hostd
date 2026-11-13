"""Unit tests of the matrix report (bench/lib/matrix.py, #48): run with `python3 -I bench/tests/test_matrix.py`. The
documents are small fixtures in data/matrix/, in the shape bench.py writes: one per (rate, frames, periods), the dummy
driver's and the alsa driver's at two and three periods, a set that ran no cell and a set directory with no document."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data", "matrix")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


matrix = load("matrix", os.path.join(BENCH, "lib", "matrix.py"))


def fixtures(*names):
    return [os.path.join(DATA, n) for n in names]


def everything():
    return [os.path.join(DATA, n) for n in sorted(os.listdir(DATA))]


class Sets(unittest.TestCase):
    def test_a_document_is_one_set_its_period_in_ms(self):
        (s,) = matrix.load_sets(fixtures("desk-r48000-f128.json"))
        self.assertEqual((s["rate"], s["frames"], s["periods"]), (48000, 128, "dummy"))
        self.assertEqual(s["ms"], 2.67)
        self.assertTrue(s["reachable"])

    def test_the_alsa_driver_is_keyed_by_its_periods_two_when_not_written(self):
        sets = matrix.load_sets(fixtures("pi-r48000-f128-n3.json", "pi-r48000-f256-n2.json"))
        self.assertEqual(sorted(s["periods"] for s in sets), ["n2", "n3"])

    def test_per_host_clean_over_ok_and_the_xruns_summed(self):
        (s,) = matrix.load_sets(fixtures("desk-r48000-f256.json"))
        self.assertEqual(s["hosts"]["H1"], {"ok": 2, "clean": 2, "xruns": 0})
        self.assertEqual(s["hosts"]["H2"], {"ok": 2, "clean": 1, "xruns": 3})
        self.assertEqual(s["hosts"]["H4"], {"ok": 2, "clean": 1, "xruns": 1})
        self.assertEqual(s["xruns"], 4)
        self.assertFalse(s["clean"])

    def test_a_row_that_did_not_run_is_not_counted_as_ok(self):
        (s,) = matrix.load_sets(fixtures("desk-r48000-f1024.json"))
        self.assertEqual(s["hosts"]["H1"]["ok"], 2)  # the unsupported pianoteq row of H1 is not ok
        self.assertTrue(s["clean"])

    def test_a_set_that_ran_no_cell_is_not_reachable(self):
        (s,) = matrix.load_sets(fixtures("pi-r96000-f64-n3.json"))
        self.assertFalse(s["reachable"])
        self.assertFalse(s["clean"])

    def test_a_set_directory_without_a_document_is_not_reachable(self):
        (s,) = matrix.load_sets(fixtures("r96000-f128-n2"))
        self.assertEqual((s["rate"], s["frames"], s["periods"], s["reachable"]), (96000, 128, "n2", False))

    def test_a_directory_holding_documents_is_read_through(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "r48000-f512-n3")
            os.mkdir(sub)
            with open(os.path.join(DATA, "desk-r48000-f512.json")) as f:
                doc = json.load(f)
            doc["jack"] = {"driver": "alsa", "priority": 70, "device": "hw:X", "periods": 3}
            with open(os.path.join(sub, "pi.json"), "w") as f:
                json.dump(doc, f)
            (s,) = matrix.load_sets([sub])
            self.assertEqual((s["rate"], s["frames"], s["periods"], s["reachable"]), (48000, 512, "n3", True))


class Report(unittest.TestCase):
    def setUp(self):
        self.r = matrix.report(matrix.load_sets(everything()))

    def test_one_table_per_periods_value(self):
        self.assertEqual(sorted(self.r), ["dummy", "n2", "n3"])

    def test_rows_are_period_ms_and_columns_rates_like_with_like(self):
        t = self.r["dummy"]
        self.assertEqual(t["rates"], [48000, 96000, 192000])
        for ms in (1.33, 2.67, 5.33, 10.67, 21.33):
            self.assertIn(ms, t["rows"])
        # 48000/128, 96000/256 and 192000/512 share the 2.67 ms row
        row = t["cells"]["2.67"]
        self.assertEqual(sorted(int(r) for r in row), [48000, 96000, 192000])

    def test_a_sub_ms_cell_is_marked(self):
        self.assertTrue(self.r["dummy"]["cells"]["0.67"]["192000"]["sub_ms"])
        self.assertFalse(self.r["dummy"]["cells"]["2.67"]["48000"]["sub_ms"])

    def test_the_safe_minimum_is_the_shortest_clean_period_with_every_longer_one_clean(self):
        safe = self.r["dummy"]["safe"]
        # 48 kHz: 21.33 and 10.67 clean, 5.33 has xruns, 2.67 clean again: the safe minimum stays 10.67
        self.assertEqual(safe["48000"], 10.67)
        self.assertEqual(safe["96000"], 2.67)
        # 192 kHz: 2.67 clean, 1.33 has xruns, 0.67 too
        self.assertEqual(safe["192000"], 2.67)

    def test_a_rate_whose_longest_period_has_xruns_has_no_safe_minimum(self):
        sets = matrix.load_sets(fixtures("desk-r48000-f256.json"))
        self.assertIsNone(matrix.report(sets)["dummy"]["safe"]["48000"])

    def test_an_unreachable_set_is_never_the_safe_minimum(self):
        self.assertIsNone(self.r["n2"]["safe"].get("96000"))
        self.assertEqual(self.r["n3"]["safe"]["48000"], 2.67)
        self.assertIsNone(self.r["n3"]["safe"]["96000"])


class Output(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([sys.executable, "-I", os.path.join(BENCH, "lib", "matrix.py"), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_markdown_lays_out_the_table_with_its_marks(self):
        r = self.run_tool(*everything())
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("## dummy", out)
        self.assertIn("| period | 48000 | 96000 | 192000 |", out)
        self.assertIn("sub-ms", out)
        self.assertIn("not reachable", out)
        self.assertIn("H2 1/2 (3)", out)
        self.assertIn("| safe minimum | 10.67 ms | 2.67 ms | 2.67 ms |", out)

    def test_json_carries_the_same_result(self):
        r = self.run_tool("--json", *everything())
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(doc["dummy"]["safe"]["48000"], 10.67)
        self.assertEqual(doc["dummy"]["cells"]["5.33"]["48000"]["hosts"]["H2"], {"ok": 2, "clean": 1, "xruns": 3})

    def test_a_file_that_is_no_bench_document_is_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"schema": "something-else"}')
        try:
            r = self.run_tool(f.name)
            self.assertEqual(r.returncode, 2)
            self.assertIn("omx-bench/1", r.stderr)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
