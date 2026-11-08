"""Synthetic reference controls, fixed before real comparison outcomes."""
from fractions import Fraction as F
import random
import unittest
from release_queries import rank_constraints as r

class Controls(unittest.TestCase):
    def test_strict_inclusive_nonzero_threshold(self):
        cal=[[(F(2),F(0),F(2),F(2))]*2]
        rows=[[(F(2),F(1),F(3),F(3)),(F(2),F(1),F(1),F(1))]]
        atoms=r.phase(r.score_lines(cal,[F(1),F(1)]),rows,[F(1),F(1)],1,[F(2),F(2)])
        point=next(a for a in atoms if a[0].left==a[0].right==0)
        self.assertEqual(point[1],1)
    def test_zero_and_coincident_constraints(self):
        self.assertEqual(r.constrain(r.DOMAIN,F(0),F(0),False),r.DOMAIN)
        self.assertIsNone(r.constrain(r.DOMAIN,F(0),F(0),True))
        self.assertIsNone(r.constrain(r.DOMAIN,F(0),F(1),False))
    def test_coverage_singleton_and_disconnected_components(self):
        left=r.Interval(F(-1,2),F(0),True,False);right=r.Interval(F(0),F(1,2),False,True)
        self.assertEqual(r.covered([left,right],1),[left,right])
        self.assertEqual(r.covered([r.DOMAIN,r.Interval(F(0),F(0))],2),[r.Interval(F(0),F(0))])
    def test_open_and_singleton_optima_are_not_filled(self):
        atoms=[(r.Interval(F(-1,2),F(0),False,False),1,0),(r.Interval(F(0),F(0)),0,0),(r.Interval(F(0),F(1,2),False,False),1,0)]
        best,regions=r.optimum(atoms)
        self.assertEqual(best,1);self.assertEqual(len(regions),2);self.assertFalse(any(x.contains(F(0)) for x in regions))
    def test_evaluation_labels_do_not_change_reuse(self):
        cal=[[(F(0),F(0),F(0),F(0))]]
        good=[[(F(3),F(1),F(3),F(1))]];bad=[[(F(3),F(1),F(-3),F(1))]]
        lines=r.score_lines(cal,[F(1)])
        a=r.phase(lines,good,[F(1)],1);b=r.phase(lines,bad,[F(1)],1)
        self.assertEqual([(x,y) for x,y,z in a],[(x,y) for x,y,z in b]);self.assertNotEqual(a,b)
    def test_seeded_rational_fixtures_against_direct_ranks(self):
        rng=random.Random(1701)
        for _ in range(20):
            def family():return [(F(rng.randint(-3,3)),F(rng.randint(-2,2)),F(rng.randint(-3,3)),F(rng.choice([-1,1]))) for j in range(2)]
            cal=[family() for i in range(3)];evaluation=[family() for i in range(2)];scales=[F(1),F(2)]
            for k in [1,2,3]:
                atoms=r.phase(r.score_lines(cal,scales),evaluation,scales,k)
                r.check_atoms(atoms,cal,evaluation,scales,k)
                for i in range(-10,11):
                    beta=F(i,20);at=next(t for t in atoms if t[0].contains(beta))
                    self.assertEqual(at[1:3],r.direct(cal,evaluation,scales,k,beta)[:2])

if __name__=='__main__':unittest.main()
