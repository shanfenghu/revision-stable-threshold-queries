"""Prevent silently changing a query family when scales or ranks are invalid."""
from fractions import Fraction as F
import unittest
from release_queries import affine as p, rank_constraints as r, set_band as b


class FamilyShapes(unittest.TestCase):
    def setUp(self):
        self.row = (F(0), F(0), F(0), F(1))
        self.hidden = (F(0), F(0), F(100), F(1))
        self.regions = [p.Region(F(-1, 2), F(1, 2), True, True)]
        self.path = [p.Piece(F(-1, 2), F(1, 2), p.Line(F(0), F(0)))]
        self.atoms = p.decision_atoms(self.path, [[self.row]], [F(1)])

    def calls(self, family, scales):
        cal = [family] * 19
        return [lambda: p.family_lines(cal, scales),
                lambda: p.decision_atoms(self.path, [family], scales),
                lambda: p.verify_atoms(self.path, self.atoms, [family], scales),
                lambda: b.quantile(cal, self.regions, scales),
                lambda: b.evaluate([family], self.regions, scales, F(0)),
                lambda: b.direct_float(cal, [family], self.regions, scales),
                lambda: r.direct(cal, [family], scales, 19, F(0))]

    def test_mismatched_widths_are_never_truncated(self):
        for family, scales in [([self.row, self.hidden], [F(1)]),
                               ([self.row], [F(1), F(1)]),
                               ([], [F(1)]), ([self.row], [])]:
            for index, call in enumerate(self.calls(family, scales)):
                with self.subTest(width=len(family), scales=len(scales), route=index):
                    with self.assertRaises(ValueError):
                        call()

    def test_scales_must_be_positive_and_finite(self):
        for scale in [F(0), F(-1), float('inf'), float('nan')]:
            for index, call in enumerate(self.calls([self.row], [scale])):
                with self.subTest(scale=scale, route=index):
                    with self.assertRaises(ValueError):
                        call()

    def test_valid_second_query_controls_the_cutoff_and_is_retained(self):
        cal = [[self.row, self.hidden]] * 19
        scales = [F(1), F(1)]
        evaluation = [[(F(101), F(0), F(1), F(1))] * 2]
        q, rank, _ = b.quantile(cal, self.regions, scales)
        self.assertEqual((q, rank), (F(100), 19))
        band = b.evaluate(evaluation, self.regions, scales, q)
        self.assertEqual(band['reuse_mask'], '0x3')
        path = p.rank_path(p.family_lines(cal, scales), rank)
        atoms = p.decision_atoms(path, evaluation, scales)
        p.verify_atoms(path, atoms, evaluation, scales)
        self.assertTrue(all(atom.reused == 3 for atom in atoms))
        self.assertEqual(r.direct(cal, evaluation, scales, rank, F(0))[:2], (3, 0))
        self.assertEqual(b.direct_float(cal, evaluation, self.regions, scales), (3, 100.0))

    def test_direct_rank_requires_available_integer_rank_and_matching_thresholds(self):
        cal = [[self.row, self.hidden]] * 19
        for rank in [0, 20, False, 1.5]:
            with self.subTest(rank=rank), self.assertRaises(ValueError):
                r.direct(cal, cal[:1], [F(1), F(1)], rank, F(0))
        with self.assertRaises(ValueError):
            r.direct(cal, cal[:1], [F(1), F(1)], 19, F(0), thresholds=[F(0)])
