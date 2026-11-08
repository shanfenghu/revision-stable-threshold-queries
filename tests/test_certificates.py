"""Reject fractional indicators and malformed certificates before witness use."""
from fractions import Fraction as F
import unittest
from release_queries import affine as p, rank_constraints as r, training_loss


class CertificateValidation(unittest.TestCase):
    def test_fractional_endpoint_flags_are_rejected(self):
        for flags in [(.5, True), (True, .5), (1, True)]:
            with self.assertRaises(ValueError):
                p.Region(F(0), F(1), *flags)
            with self.assertRaises(ValueError):
                r.Interval(F(0), F(1), *flags)

    def test_fractional_reuse_or_wrong_masks_are_rejected(self):
        region = p.Region(F(0), F(1), True, True)
        for reused, wrong in [(.5, 0), (1, .5), (-1, 0), (1, 2), (True, 0)]:
            with self.assertRaises(ValueError):
                p.Atom(region, reused, wrong, 1)

    def test_serialized_fractional_flags_do_not_create_a_witness(self):
        record = {'left': '-1/2', 'right': '1/2', 'left_closed': .5,
                  'right_closed': True, 'reuse_mask': '0x1', 'wrong_mask': '0x0', 'utility': 1}
        with self.assertRaises(ValueError):
            training_loss.solve([record], [record], 1)

    def test_noninteger_reward_does_not_pass_integer_certificate_equality(self):
        record = {'left': '-1/2', 'right': '1/2', 'left_closed': True,
                  'right_closed': True, 'reuse_mask': '0x1', 'wrong_mask': '0x0', 'utility': 1.0}
        with self.assertRaises(ValueError):
            training_loss.atom(record)

    def test_valid_zero_one_masks_and_witness_survive(self):
        record = {'left': '-1/2', 'right': '1/2', 'left_closed': True,
                  'right_closed': True, 'reuse_mask': '0x1', 'wrong_mask': '0x0', 'utility': 1}
        result = training_loss.solve([record], [record], 1)
        self.assertEqual(result['status'], 'attained')
        self.assertEqual(result['minimum_training_loss'], 0)
        self.assertEqual(result['witness']['later_reused'], 1)


if __name__ == '__main__':
    unittest.main()
