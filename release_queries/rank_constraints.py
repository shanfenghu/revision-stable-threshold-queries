"""Exact one-dimensional rank constraints, independently of quantile paths.

Family scores are maxima of normalized affine residuals. Reuse is reduced to
k-fold coverage by feasible family intervals. Explicit endpoint flags preserve
strict negative answers and singleton optima. Inputs are recorded rational rows
(base, slope, target, current), fixed positive scales and a finite closed domain.
"""
from dataclasses import dataclass
from fractions import Fraction as F

@dataclass(frozen=True)
class Interval:
    left:F
    right:F
    lc:bool=True
    rc:bool=True
    def __post_init__(self):
        if type(self.lc) is not bool or type(self.rc) is not bool:
            raise ValueError('Endpoint inclusion flags must be Boolean')
    def contains(self,x):
        return (x>self.left or x==self.left and self.lc) and (x<self.right or x==self.right and self.rc)

DOMAIN=Interval(F(-1,2),F(1,2))

def intersect(a,b):
    """Intersect intervals, returning None for a missing singleton or empty gap."""
    lo,hi=max(a.left,b.left),min(a.right,b.right)
    lc=(a.lc if lo==a.left else True) and (b.lc if lo==b.left else True)
    rc=(a.rc if hi==a.right else True) and (b.rc if hi==b.right else True)
    return Interval(lo,hi,lc,rc) if lo<hi or lo==hi and lc and rc else None

def constrain(region,slope,intercept,strict):
    """Solve slope*beta+intercept <=0 (or <0) exactly within region."""
    if region is None:return None
    if slope==0:
        return region if (intercept<0 if strict else intercept<=0) else None
    root=-intercept/slope
    if slope>0:
        if root<region.left:return None
        bound=Interval(region.left,root,True,not strict)
    else:
        if root>region.right:return None
        bound=Interval(root,region.right,not strict,True)
    return intersect(region,bound)

def merge(regions):
    """Union ordered intervals without filling an excluded boundary point."""
    out=[]
    for r in sorted(regions,key=lambda r:(r.left,not r.lc,r.right)):
        if out and (r.left<out[-1].right or r.left==out[-1].right and (r.lc or out[-1].rc)):
            a=out.pop();right=max(a.right,r.right)
            rc=(a.rc if right==a.right else False) or (r.rc if right==r.right else False)
            out.append(Interval(a.left,right,a.lc,rc))
        else:out.append(r)
    return out

def covered(intervals,k,domain=DOMAIN):
    """Find the set covered by >=k feasible family intervals via exact events."""
    if k<1:raise ValueError('Rank must be positive')
    events={domain.left:[0,0,0,0],domain.right:[0,0,0,0]}
    for r in intervals:
        if r is None:continue
        e=events.setdefault(r.left,[0,0,0,0]);e[0]+=1;e[1]+=r.lc
        e=events.setdefault(r.right,[0,0,0,0]);e[2]+=1;e[3]+=not r.rc
    points=sorted(events);active=0;parts=[]
    for i,x in enumerate(points):
        starts,closed,ends,open_ends=events[x]
        at=active+closed-open_ends
        after=active+starts-ends
        if at>=k and domain.contains(x):parts.append(Interval(x,x))
        if i+1<len(points) and after>=k:parts.append(Interval(x,points[i+1],False,False))
        active=after
    return merge(parts)

def score_lines(calibration,scales):
    """Independent raw affine inequalities for absolute family error scores."""
    if not scales or any(s<=0 for s in scales):raise ValueError('Positive fixed scales required')
    result=[]
    for family in calibration:
        if len(family)!=len(scales):raise ValueError('Mismatched family width')
        lines=[]
        for (base,slope,target,current),s in zip(family,scales):
            lines += [(slope/s,(base-target)/s),(-slope/s,(target-base)/s)]
        result.append(lines)
    return result

def phase(lines,evaluation,scales,k,thresholds=None,domain=DOMAIN,cost=19):
    """Solve all reuse predicates and return complete (region,reuse,wrong) atoms."""
    thresholds=thresholds if thresholds is not None else [F(0)]*len(scales)
    if len(thresholds)!=len(scales):raise ValueError('Mismatched thresholds')
    ranges=[];bad=0;index=0
    for family in evaluation:
        if len(family)!=len(scales):raise ValueError('Mismatched family width')
        for (base,slope,target,current),s,c in zip(family,scales,thresholds):
            positive=current>=c;sign=1 if positive else -1
            da,db=sign*slope/s,sign*(base-c)/s
            feasible=[]
            for group in lines:
                r=domain
                for a,b in group:
                    r=constrain(r,a-da,b-db,not positive)
                    if r is None:break
                if r is not None:feasible.append(r)
            ranges.append(covered(feasible,k,domain))
            if positive!=(target>=c):bad|=1<<index
            index+=1
    # Separate singleton bits from starts/ends, which refer to open neighborhoods.
    events={domain.left:[0,0,0,0,0],domain.right:[0,0,0,0,0]}
    for j,regions in enumerate(ranges):
        bit=1<<j
        for r in regions:
            if r.left==r.right:
                events.setdefault(r.left,[0,0,0,0,0])[4]|=bit;continue
            e=events.setdefault(r.left,[0,0,0,0,0]);e[0]|=bit
            if r.lc:e[1]|=bit
            e=events.setdefault(r.right,[0,0,0,0,0]);e[2]|=bit
            if not r.rc:e[3]|=bit
    points=sorted(events);active=0;atoms=[]
    for i,x in enumerate(points):
        starts,closed,ends,open_ends,singletons=events[x]
        at=(active&~open_ends)|closed|singletons
        after=(active&~ends)|starts
        if domain.contains(x):atoms.append((Interval(x,x),at,at&bad))
        if i+1<len(points):atoms.append((Interval(x,points[i+1],False,False),after,after&bad))
        active=after
    return atoms

def bits(value):return bin(value).count("1")

def utility(atom,cost=19):return bits(atom[1])-(cost+1)*bits(atom[2])
def optimum(atoms,cost=19):
    value=max(utility(a,cost) for a in atoms)
    return value,merge([a[0] for a in atoms if utility(a,cost)==value])

def restrict(atoms,regions):
    return [(i,a,b) for r,a,b in atoms for s in regions if (i:=intersect(r,s)) is not None]

def canonical(atoms):
    """Remove irrelevant subdivisions while retaining exact decision regions."""
    out=[]
    for r,a,b in atoms:
        if out and (a,b)==out[-1][1:] and out[-1][0].right==r.left and (out[-1][0].rc or r.lc):
            prev=out.pop()[0];out.append((Interval(prev.left,r.right,prev.lc,r.rc),a,b))
        else:out.append((r,a,b))
    return out

def record_region(r):return {'left':str(r.left),'right':str(r.right),'left_closed':r.lc,'right_closed':r.rc}
def record_atoms(atoms):return [{**record_region(r),'reuse_mask':hex(a),'wrong_mask':hex(b)} for r,a,b in canonical(atoms)]

def summary(atoms,answers):
    if not atoms:raise ValueError('Empty selected set')
    always=(1<<answers)-1;possible=0
    for _,a,b in atoms:always&=a;possible|=a
    return {'reused':[min(bits(a) for _,a,b in atoms),max(bits(a) for _,a,b in atoms)],
            'wrong_reuses':[min(bits(b) for _,a,b in atoms),max(bits(b) for _,a,b in atoms)],
            'utility_total':[min(utility(t) for t in atoms),max(utility(t) for t in atoms)],
            'always_mask':hex(always),'possible_mask':hex(possible)}

def direct(calibration,evaluation,scales,k,beta,thresholds=None):
    """Check a witness by sorting exact raw family maxima, without any paths."""
    thresholds=thresholds if thresholds is not None else [F(0)]*len(scales)
    calibration, evaluation = list(calibration), list(evaluation)
    if type(k) is not int or not 1 <= k <= len(calibration):
        raise ValueError('An available positive integer rank is required')
    try:
        if not scales or any(F(s) <= 0 for s in scales):
            raise ValueError('Positive finite fixed scales required')
    except (TypeError, OverflowError, ValueError) as error:
        raise ValueError('Positive finite fixed scales required') from error
    if len(thresholds) != len(scales) or any(len(v) != len(scales) for v in calibration + evaluation):
        raise ValueError('Mismatched family or threshold width')
    q=sorted(max(abs(y-base-slope*beta)/s for (base,slope,y,cur),s in zip(family,scales)) for family in calibration)[k-1]
    reused=wrong=idx=0
    for family in evaluation:
        for (base,slope,y,cur),s,c in zip(family,scales,thresholds):
            mu=base+slope*beta;accept=mu-q*s>=c if cur>=c else mu+q*s<c
            if accept:
                reused|=1<<idx
                if (cur>=c)!=(y>=c):wrong|=1<<idx
            idx+=1
    return reused,wrong,q

def check_atoms(atoms,calibration,evaluation,scales,k):
    for region,a,b in atoms:
        x=region.left if region.left==region.right else (region.left+region.right)/2
        aa,bb,_=direct(calibration,evaluation,scales,k,x)
        if (aa,bb)!=(a,b):raise AssertionError(('direct rank mismatch',region,a,b,aa,bb))
    return len(atoms)
