"""Controls for exact orchestration, enclosing bands and hindsight witnesses."""
from fractions import Fraction as F
import unittest
from release_queries import audit, affine as p, rank_constraints as r, set_band, training_loss


class AuditControls(unittest.TestCase):
    def test_float_scale_is_preserved_as_recorded_binary_rational(self):
        scales = audit.recorded_scales([.1])
        self.assertEqual(scales, [F(.1)])
        self.assertNotEqual(scales, [F(1, 10)])
        cal = [[(F(1, 3), F(2), F(0), F(1))]]
        rows = [[(F(1, 7), F(-1), F(1), F(1))]]
        path = p.rank_path(p.family_lines(cal, scales), 1)
        atoms = p.decision_atoms(path, rows, scales)
        reference = r.phase(r.score_lines(cal, scales), rows, scales, 1)
        self.assertEqual(r.record_atoms(audit.rank_atoms(atoms)), r.record_atoms(reference))

    def test_scale_normalisation_requires_positive_values(self):
        for values in [[], [0], [-1]]:
            with self.assertRaises(ValueError):
                audit.recorded_scales(values)

    def test_open_negative_endpoint_is_not_filled_by_enclosing_band(self):
        regions = [p.Region(F(-1, 2), F(1, 2), True, False)]
        row = (F(-1, 2), F(1), F(-1), F(-1))
        self.assertTrue(all(row[0]+row[1]*b < 0 for b in [F(-1, 2), F(0), F(1, 3)]))
        self.assertEqual(set_band.band(row, regions), (F(-1), F(0)))
        self.assertEqual(set_band.evaluate([[row]], regions, [F(1)], F(0))['reused'], 0)

    def test_infeasible_later_target_is_not_a_successful_witness(self):
        atom = {'left': '-1/2', 'right': '1/2', 'left_closed': True,
                'right_closed': True, 'reuse_mask': '0x1', 'wrong_mask': '0x0', 'utility': 1}
        result = training_loss.solve([atom], [atom], 2)
        self.assertEqual(result['status'], 'infeasible')
        self.assertIsNone(result['witness'])
        self.assertIsNone(result['minimum_training_loss'])


if __name__ == '__main__':
    unittest.main()
