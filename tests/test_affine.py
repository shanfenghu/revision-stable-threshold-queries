"""Exact controls for rank changes, missed grid islands and strict boundaries."""
from fractions import Fraction as F
import random
import unittest
from release_queries import affine as p


class ExactPartition(unittest.TestCase):
    def test_rank_paths_match_independent_sort_at_random_rationals(self):
        rng=random.Random(2601104)
        for n in (1,3,7):
            lines=[[p.Line(F(rng.randrange(-9,10),7),F(rng.randrange(-9,10),11)) for _ in range(4)] for _ in range(n)]
            for k in (1,(n+1)//2,n):
                path=p.rank_path(lines,k)
                self.assertGreater(p.verify_rank_path(path,lines,k),0)
                for _ in range(100):
                    x=F(rng.randrange(-1000,1001),2000)
                    expected=sorted(max(line(x) for line in family) for family in lines)[k-1]
                    self.assertEqual(p.at(path,x)(x),expected)

    def test_narrow_reuse_region_missed_by_every_original_grid_point(self):
        # q=|beta-1/800|, margin=1/10000: a genuine open-region grid miss.
        path=p.upper_envelope([p.Line(F(1),F(-1,800)),p.Line(F(-1),F(1,800))])
        rows=[[(F(1,10000),F(0),F(1),F(1))]]
        atoms=p.decision_atoms(path,rows,[F(1)])
        p.verify_atoms(path,atoms,rows,[F(1)])
        self.assertEqual(max(a.utility for a in atoms),1)
        for i in range(-100,101):
            beta=F(i,200)
            a=next(a for a in atoms if a.region.contains(beta))
            self.assertEqual(a.utility,0)
        best=p.merge_regions([a for a in atoms if a.utility==1])
        self.assertEqual(best,[p.Region(F(23,20000),F(27,20000),True,True)])

    def test_positive_and_negative_equality_are_not_interchangeable(self):
        path=[p.Piece(F(-1,2),F(1,2),p.Line(F(0),F(0)))]
        rows=[[(F(0),F(1),F(1),F(1)),(F(0),F(-1),F(-1),F(-1))]]
        atoms=p.decision_atoms(path,rows,[F(1),F(1)])
        p.verify_atoms(path,atoms,rows,[F(1),F(1)])
        point=next(a for a in atoms if a.region.left==a.region.right==0)
        self.assertEqual(point.reused,1)
        self.assertEqual(next(a for a in atoms if a.region.contains(F(1,4))).reused,3)

    def test_singleton_optimum_is_retained(self):
        path=p.upper_envelope([p.Line(F(-1),F(0)),p.Line(F(1),F(0))])
        atoms=p.decision_atoms(path,[[(F(0),F(0),F(1),F(1))]],[F(1)])
        chosen=p.merge_regions([a for a in atoms if a.utility==1])
        self.assertEqual(chosen,[p.Region(F(0),F(0),True,True)])
        p.verify_atoms(path,atoms,[[(F(0),F(0),F(1),F(1))]],[F(1)])

    def test_rank_certificate_detects_wrong_piece(self):
        lines=[[p.Line(F(0),F(1))],[p.Line(F(0),F(2))]]
        wrong=[p.Piece(F(-1,2),F(1,2),p.Line(F(0),F(3)))]
        with self.assertRaises(AssertionError):p.verify_rank_path(wrong,lines,1)

    def test_atom_certificate_detects_a_corrupt_mask(self):
        path=[p.Piece(F(-1,2),F(1,2),p.Line(F(0),F(0)))]
        rows=[[(F(1),F(0),F(1),F(1))]]
        atoms=p.decision_atoms(path,rows,[F(1)])
        atoms[0]=p.Atom(atoms[0].region,0,0,0)
        with self.assertRaises(AssertionError):p.verify_atoms(path,atoms,rows,[F(1)])

    def test_open_endpoints_and_restriction(self):
        point=p.Region(F(0),F(0),True,True)
        self.assertFalse(p.intersects(point,p.Region(F(0),F(1),False,True)))
        self.assertTrue(p.intersects(point,p.Region(F(0),F(1),True,False)))
        with self.assertRaises(ValueError):p.rank_path([[p.Line(F(0),F(1))]],2)


if __name__=='__main__':unittest.main()
