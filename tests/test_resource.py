"""Small semantic controls plus optional exact-input regression checks."""
import copy
from datetime import date
import json
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from release_queries import sources as s, workloads as w, study as c
from release_queries.reproduce import ROOT, compare, phase_ledger, safe_path, verify_inputs


class Semantics(unittest.TestCase):
    def test_known_state_does_not_backfill_or_erase_explicit_unknown(self):
        rows = [{"release": 106, "issue": 100, "value": 2},
                {"release": 113, "issue": 107, "value": None}]
        self.assertIsNone(w.known_at(rows, 100))
        self.assertEqual(w.known_at(rows, 112)["value"], 2)
        self.assertIsNone(w.known_at(rows, 113)["value"])
        self.assertIsNone(s.evaluate({1: 5}, [("contrast", [(1, 1), (0, -1)])], "ili"))

    def test_epiweek_year_boundary(self):
        self.assertEqual(w.epiweek_end(201453), date(2015, 1, 3))
        self.assertEqual(w.epiweek_end(201501), date(2015, 1, 10))
        with self.assertRaises(ValueError):
            w.epiweek_end(201553)

    def test_answer_boundaries_and_family_quantile(self):
        self.assertFalse(w.reuse(-1, 10, 1))
        self.assertTrue(w.reuse(1, 1, 1))
        self.assertFalse(w.reuse(-1, -1, 1))
        self.assertEqual(s.cp_quantile(list(range(30)), .05), (29, 30))
        self.assertEqual(s.cp_quantile([1, 2], .05), (math.inf, 3))

    def test_cost_and_deferral(self):
        x, y = list(range(1, 12)), list(range(20, 9, -1))
        u = {"raw_inputs": x, "raw_targets": y,
             "inputs": w.project(x, "ili"), "targets": w.project(y, "ili")}
        self.assertEqual(c.evaluate_unit(u, 0, [1]*12, 0, "ili")["utility_total"], -19*12)
        deferred = c.evaluate_unit(u, 0, [1]*12, math.inf, "ili")
        self.assertEqual((deferred["reused"], deferred["utility_total"]), (0, 0))

    def test_shared_execution_and_log_work(self):
        rng = random.Random(260311)
        for _ in range(100):
            values = [rng.uniform(0, 30000) for _ in range(11)]
            for a, b in zip(w.project(values, "ili"), w.project(values, "ili", True)):
                self.assertTrue(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9))
        u = {"source_levels": list(range(100, 108))}
        with patch.object(w.math, "log", wraps=math.log) as logged:
            a = w.predict(u, .01, "gdp")
            self.assertEqual(logged.call_count, 16)
        with patch.object(w.math, "log", wraps=math.log) as logged:
            b = w.predict(u, .01, "gdp", True)
            self.assertEqual(logged.call_count, 8)
        self.assertEqual(a, b)

    def test_input_and_export_paths_reject_escapes_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("../outside", "/outside", "x/../../outside", "x\\outside"):
                with self.assertRaises(ValueError):
                    safe_path(root, name)
            (root/"link").symlink_to(root)
            with self.assertRaises(ValueError):
                safe_path(root, "link/anything")

    def test_changed_input_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/"file").write_bytes(b"x")
            manifest = {"files": [{"path": "file", "bytes": 1, "sha256": "0"*64}]}
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                verify_inputs(Path(temp), manifest, exact=True)

    def test_all_zero_scale_is_unsupported(self):
        with self.assertRaisesRegex(ValueError, "Unsupported scale"):
            c.training_scales([{"inputs": [1, 2], "targets": [1, 2]}])


@unittest.skipUnless(os.environ.get("RELEASE_QUERY_INPUTS"), "set RELEASE_QUERY_INPUTS for exact-input checks")
class ExactInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = Path(os.environ["RELEASE_QUERY_INPUTS"])
        records = verify_inputs(cls.inputs)
        role = lambda name: [r for r in records if r["role"] == name]
        cls.csv = cls.inputs/role("ili_table")[0]["path"]
        cls.ili, cls.early = w.ili_ledger(w.read_source(cls.inputs, role("ili_training")), cls.csv)
        cls.gdp_path = cls.inputs/role("gdp_table")[0]["path"]
        cls.gdp = [u for u in w.gdp_units(cls.gdp_path) if u["issue"] <= 2005*12+5]
        cls.later, cls.ledger = c.new_ili_units(cls.inputs, role("ili_evaluation"), cls.csv)
        cls.fits = json.loads((ROOT/"expected/fits.json").read_text())
        cls.protocol = json.loads((ROOT/"protocol.json").read_text())

    def test_training_maturity_and_unused_target_poisoning(self):
        for d, units in (("ili", self.ili), ("gdp", self.gdp)):
            a, b, z = c.training_parts(units)
            self.assertEqual(tuple(map(len, (a, b, z))), (24, 24, 12))
            self.assertLess(max(u["target"] for u in a), min(u["issue"] for u in b))
            self.assertLess(max(u["target"] for u in b), min(u["issue"] for u in z))
            changed = copy.deepcopy(units)
            used = {u["issue"] for u in a+b+z}
            for u in changed:
                if u["issue"] not in used:
                    u["targets"] = [1e100]*len(u["targets"])
                    u["raw_targets"] = [1e100]*len(u["raw_targets"])
            compare({k: v for k, v in c.choose_fit(changed, d).items() if k != "candidates"}, self.fits[d])

    def test_revision_grid_matches_independent_projection_and_unit_change(self):
        for d, units in (("ili", self.ili), ("gdp", self.gdp)):
            numerator = denominator = 0
            for phase in c.training_parts(units):
                for u in phase:
                    x, y, b = c.coordinates(u, d)
                    numerator += sum(bb*(yy-xx) for xx, yy, bb in zip(x, y, b))
                    denominator += sum(bb*bb for bb in b)
            projected = max(-.5, min(.5, round(numerator/denominator*200)/200))
            self.assertEqual(projected, self.fits[d]["models"]["revision_loss"])
        for u in self.gdp[:5]:
            changed = copy.deepcopy(u)
            changed["raw_inputs"] = [x+math.log(7) for x in u["raw_inputs"]]
            changed["raw_targets"] = [x+math.log(3) for x in u["raw_targets"]]
            for beta in (-.2, 0, .2):
                def loss(v):
                    x, y, b = c.coordinates(v, "gdp")
                    return sum((yy-xx-beta*bb)**2 for xx, yy, bb in zip(x, y, b))
                self.assertAlmostEqual(loss(u), loss(changed), places=12)

    def test_availability_exclusions_fixed_support_and_maturity(self):
        self.assertEqual((self.early["eligible"], self.early["excluded"]), (74, 10))
        self.assertEqual(self.ledger["csv_mismatches"], 0)
        self.assertEqual(self.ledger["release_offset_days_counts"], {"3": 16, "6": 918, "7": 144, "8": 16})
        phase = phase_ledger(self.ledger, self.protocol)
        self.assertEqual((phase["calibration"]["nominal_slots"], phase["calibration"]["retained"]), (39, 30))
        self.assertEqual((phase["test"]["nominal_slots"], phase["test"]["retained"]), (25, 24))
        self.assertEqual(phase["test"]["slots"][-1]["status"], "dated_release_outside_fixed_window")
        for row in self.ledger["candidates"]:
            if row["status"] != "eligible":
                continue
            cutoff, target = map(date.fromisoformat, (row["input_cutoff"], row["target_cutoff"]))
            self.assertEqual((target-cutoff).days, 28)
            self.assertEqual(len(row["terms"]), 11)
            for term in row["terms"]:
                self.assertLessEqual(date.fromisoformat(term["input_release"]), cutoff)
                self.assertLessEqual(date.fromisoformat(term["target_release"]), target)
        cal, test = c.split_final(self.later, self.fits["ili"], "ili", self.protocol)
        self.assertEqual((len(cal), len(test)), (30, 24))
        self.assertLess(max(u["target"] for u in cal), min(u["issue"] for u in test))


if __name__ == "__main__":
    unittest.main()
