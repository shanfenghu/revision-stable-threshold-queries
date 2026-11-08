"""Exact retrospective least training loss from two complete scalar partitions.

Targets identify witnesses after evaluation; this is not a training-only policy.
"""
from dataclasses import dataclass
from fractions import Fraction as F

def bits(x):return bin(x).count('1')
@dataclass(frozen=True)
class Region:
    lo:F
    hi:F
    lc:bool=True
    rc:bool=True
    def __post_init__(self):
        if type(self.lc) is not bool or type(self.rc) is not bool:
            raise ValueError('Endpoint inclusion flags must be Boolean')
    def contains(self,b):return (b>self.lo or b==self.lo and self.lc) and (b<self.hi or b==self.hi and self.rc)
def intersection(a,b):
    lo,hi=max(a.lo,b.lo),min(a.hi,b.hi)
    lc=(lo>a.lo or a.lc) and (lo>b.lo or b.lc)
    rc=(hi<a.hi or a.rc) and (hi<b.hi or b.rc)
    return Region(lo,hi,lc,rc) if lo<hi or lo==hi and lc and rc else None
def merge(regions):
    out=[]
    for r in sorted(regions,key=lambda z:(z.lo,not z.lc,z.hi)):
        if out and out[-1].hi==r.lo and (out[-1].rc or r.lc):
            p=out.pop();out.append(Region(p.lo,r.hi,p.lc,r.rc))
        else:out.append(r)
    return out
def record(r):return {'left':str(r.lo),'right':str(r.hi),'left_closed':r.lc,'right_closed':r.rc}
def atom(raw):
    r=Region(F(raw['left']),F(raw['right']),raw['left_closed'],raw['right_closed'])
    for name in ('reuse_mask', 'wrong_mask'):
        value = raw[name]
        if not isinstance(value, str) or not value.startswith('0x') or len(value) < 3 or any(c not in '0123456789abcdefABCDEF' for c in value[2:]):
            raise ValueError('Masks must be nonnegative hexadecimal integers')
    reused,wrong=int(raw['reuse_mask'],16),int(raw['wrong_mask'],16)
    if wrong & ~reused or type(raw['utility']) is not int or raw['utility'] != bits(reused)-20*bits(wrong):
        raise ValueError('Invalid fixed-cost decision/reward certificate')
    if not (F(-1,2)<=r.lo<=r.hi<=F(1,2) and (r.lo<r.hi or r.lc and r.rc)):
        raise ValueError('Invalid bounded witness region')
    return r,reused,wrong,raw['utility']
def probes(regions):
    points=sorted({F(-1,2),F(1,2),*(x for r in regions for x in [r.lo,r.hi])})
    return points+[(x+y)/2 for x,y in zip(points,points[1:])]
def at(atoms,b):
    matches=[a for a in atoms if a[0].contains(b)];assert len(matches)==1,(b,len(matches))
    return matches[0]
def solve(training,later,target):
    """Return exact minimum loss, all minimizers, and one attaining joint atom."""
    inner=[atom(a) for a in training];outer=[atom(a) for a in later]
    # Coverage is checked at every point/interval induced by each full partition.
    for rows in [inner,outer]:
        for b in probes([r[0] for r in rows]):at(rows,b)
    joint=[]
    for a in inner:
        for b in outer:
            r=intersection(a[0],b[0])
            if r is not None:joint.append((r,a[3],b[3],bits(b[1]),bits(b[2])))
    pairs={(t,u,r,w) for _,t,u,r,w in joint}
    alternate=set()
    for beta in probes([a[0] for a in inner+outer]):
        a,b=at(inner,beta),at(outer,beta)
        alternate.add((a[3],b[3],bits(b[1]),bits(b[2])))
    assert pairs==alternate,'Interval join differs from merged-event enumeration'
    maximum=max(a[3] for a in inner);eligible=[a for a in joint if a[2]>=target]
    base={'training_maximum':maximum,'target_later_utility':target,'attainable_pairs':[{'training_utility':t,'later_utility':u,'later_reused':r,'later_wrong':w} for t,u,r,w in sorted(pairs)]}
    if not eligible:return {**base,'status':'infeasible','minimum_training_loss':None,'minimizer_regions':[],'witness':None}
    best=max(a[1] for a in eligible);selected=sorted([a for a in eligible if a[1]==best],key=lambda z:(z[0].lo,not z[0].lc,z[0].hi))
    r,t,u,reused,wrong=selected[0];beta=r.lo if r.lc else (r.lo+r.hi)/2
    assert r.contains(beta)
    return {**base,'status':'attained','minimum_training_loss':maximum-best,'minimizer_regions':[record(r) for r in merge([a[0] for a in selected])],'witness':{'beta':str(beta),'training_utility':t,'later_utility':u,'later_reused':reused,'later_wrong':wrong}}
