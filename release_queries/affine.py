"""Complete scalar calibration/decision partitions over recorded rational inputs.

The kernel performs no statistical inference. It enumerates rank and sign events,
including singleton parameters, without a grid tolerance. Fractions preserve the
recorded coefficients exactly; source/log arithmetic is checked separately.
"""
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations


def count_bits(x):
    return bin(x).count("1")


def rational(x):
    """Preserve a recorded binary float exactly; integers and Fractions stay exact."""
    return x if isinstance(x, F) else F(x)


def checked_families(rows, scales):
    """Yield complete families with one query per positive finite fixed scale.

    A truncated zip would change both the family calibration score and the set
    of answers being audited, so reject incompatible widths before pairing.
    """
    if not scales:
        raise ValueError('Positive finite fixed scales required')
    try:
        if any(rational(s) <= 0 for s in scales):
            raise ValueError('Positive finite fixed scales required')
    except (TypeError, OverflowError, ValueError) as error:
        raise ValueError('Positive finite fixed scales required') from error
    for family in rows:
        if len(family) != len(scales):
            raise ValueError('Mismatched family width')
        yield family


@dataclass(frozen=True)
class Line:
    slope: F
    intercept: F

    def __call__(self, x):
        return self.slope*x+self.intercept


@dataclass(frozen=True)
class Piece:
    left: F
    right: F
    line: Line


@dataclass(frozen=True)
class Region:
    left: F
    right: F
    left_closed: bool
    right_closed: bool

    def __post_init__(self):
        # Truthiness would turn a fractional certificate flag into inclusion.
        if type(self.left_closed) is not bool or type(self.right_closed) is not bool:
            raise ValueError('Endpoint inclusion flags must be Boolean')

    def contains(self, x):
        return (x>self.left or self.left_closed and x==self.left) and (x<self.right or self.right_closed and x==self.right)


@dataclass(frozen=True)
class Atom:
    region: Region
    reused: int
    wrong: int
    utility: int

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.reused, self.wrong)):
            raise ValueError('Decision masks must be nonnegative integers')
        if self.wrong & ~self.reused:
            raise ValueError('Wrong-reuse mask must be a subset of reused answers')
        if type(self.utility) is not int:
            raise ValueError('The declared integer-cost reward must be an integer')


def upper_envelope(lines, lower=F(-1,2), upper=F(1,2)):
    """Return the clipped upper hull of affine lines, including exact tie events."""
    unique = {}
    for line in lines:
        unique[line.slope] = max(unique.get(line.slope, line.intercept), line.intercept)
    hull, starts = [], []
    for a,b in sorted(unique.items()):
        line = Line(a,b)
        cross = None
        while hull:
            cross = (hull[-1].intercept-b)/(a-hull[-1].slope)
            if len(hull)==1 or cross>starts[-1]:
                break
            hull.pop(); starts.pop()
        starts.append(cross if hull else None); hull.append(line)
    pieces=[]
    for i,line in enumerate(hull):
        left=max(lower,starts[i]) if starts[i] is not None else lower
        right=min(upper,starts[i+1]) if i+1<len(starts) else upper
        if left<right:
            pieces.append(Piece(left,right,line))
    if not pieces:
        raise ValueError('Empty envelope')
    return pieces


def at(path, x):
    """Find the affine piece at x; adjacent pieces agree at every boundary."""
    i=bisect_right([p.left for p in path],x)-1
    if i<0 or x>path[-1].right:
        raise ValueError('Parameter outside recorded path')
    return path[min(i,len(path)-1)].line


def family_lines(rows, scales, oriented=False):
    """Build maximum-error affine pieces from (base,slope,target,current) rows."""
    out=[]
    for family in checked_families(rows, scales):
        lines=[]
        for (base,slope,target,current),scale in zip(family,scales):
            a,b,s=rational(slope),rational(base)-rational(target),rational(scale)
            if s<=0:
                raise ValueError('Scales must be positive')
            if oriented:
                sign=1 if current>=0 else -1
                lines.append(Line(sign*a/s,sign*b/s))
            else:
                lines.extend((Line(a/s,b/s),Line(-a/s,-b/s)))
        out.append(lines)
    return out


def rank_path(lines_by_family, k, lower=F(-1,2), upper=F(1,2)):
    """Construct the kth ordered family envelope over the entire scalar domain.

    Each family score is convex piecewise affine. The only possible rank events
    are envelope bends or intersections between simultaneously active pieces.
    """
    n=len(lines_by_family)
    if not 1<=k<=n:
        raise ValueError('Insufficient calibration: infinite radius, no finite path')
    if k==n:
        return upper_envelope([line for lines in lines_by_family for line in lines],lower,upper)
    paths=[upper_envelope(lines,lower,upper) for lines in lines_by_family]
    cuts={lower,upper}
    for path in paths:
        cuts.update(p.left for p in path); cuts.update(p.right for p in path)
    for one,two in combinations(paths,2):
        i=j=0
        while i<len(one) and j<len(two):
            a,b=one[i],two[j]
            left,right=max(a.left,b.left),min(a.right,b.right)
            slope=a.line.slope-b.line.slope
            if left<right and slope:
                cross=(b.line.intercept-a.line.intercept)/slope
                if left<cross<right:
                    cuts.add(cross)
            if a.right<=b.right: i+=1
            if b.right<=a.right: j+=1
    cuts=sorted(cuts); result=[]
    for left,right in zip(cuts,cuts[1:]):
        mid=(left+right)/2
        active=sorted((at(path,mid)(mid),i,at(path,mid)) for i,path in enumerate(paths))[k-1][2]
        if result and result[-1].line==active:
            result[-1]=Piece(result[-1].left,right,active)
        else:
            result.append(Piece(left,right,active))
    return result


def verify_rank_path(path, lines_by_family, k):
    """Independently certify the rank via score-minus-candidate sign events.

    This does not enumerate pairwise family crossings as the constructor does.
    Within each verified interval the number of scores below/equal to q is fixed.
    """
    checks=0
    assert path[0].left==F(-1,2) and path[-1].right==F(1,2)
    for a,b in zip(path,path[1:]):
        assert a.right==b.left and a.line(a.right)==b.line(b.left)
    for piece in path:
        cuts={piece.left,piece.right}
        for lines in lines_by_family:
            for seg in upper_envelope(lines,piece.left,piece.right):
                cuts.update((seg.left,seg.right))
                slope=seg.line.slope-piece.line.slope
                if slope:
                    cross=(piece.line.intercept-seg.line.intercept)/slope
                    if seg.left<cross<seg.right:
                        cuts.add(cross)
        cuts=sorted(cuts)
        probes=cuts+[(a+b)/2 for a,b in zip(cuts,cuts[1:])]
        for x in probes:
            values=[max(line(x) for line in lines) for lines in lines_by_family]
            q=piece.line(x)
            if sum(s<q for s in values)>=k or sum(s<=q for s in values)<k:
                raise AssertionError('Incorrect rank certificate')
            checks+=1
    return checks


def decision_atoms(path, rows, scales):
    """Enumerate every open interval and singleton with constant answer decisions."""
    features=[]
    for family in checked_families(rows, scales):
        for (base,slope,target,current),scale in zip(family,scales):
            sign=1 if current>=0 else -1
            features.append((Line(sign*rational(slope)/rational(scale),sign*rational(base)/rational(scale)),current>=0,(current>=0)!=(target>=0)))
    cuts={path[0].left,path[-1].right}
    for p in path:
        cuts.update((p.left,p.right))
        for margin,positive,_ in features:
            slope=margin.slope-p.line.slope
            if slope:
                root=(p.line.intercept-margin.intercept)/slope
                if p.left<root<p.right:
                    cuts.add(root)
    def make(region,x):
        q=at(path,x)(x);reused=wrong=0
        for j,(margin,positive,bad) in enumerate(features):
            accept=margin(x)>=q if positive else margin(x)>q
            if accept:
                reused|=1<<j
                if bad: wrong|=1<<j
        return Atom(region,reused,wrong,count_bits(reused)-20*count_bits(wrong))
    cuts=sorted(cuts);atoms=[]
    for i,x in enumerate(cuts):
        atoms.append(make(Region(x,x,True,True),x))
        if i+1<len(cuts):
            y=cuts[i+1]
            atoms.append(make(Region(x,y,False,False),(x+y)/2))
    return atoms


def verify_atoms(path, atoms, rows, scales):
    """Certify complete coverage and absence of unrecorded decision crossings."""
    assert atoms[0].region.left==path[0].left and atoms[-1].region.right==path[-1].right
    for i,atom in enumerate(atoms):
        r=atom.region
        x=(r.left+r.right)/2
        q=at(path,x)(x)
        reuse=wrong=index=0
        for family in checked_families(rows, scales):
            for (base,slope,target,current),scale in zip(family,scales):
                center=rational(base)+rational(slope)*x
                radius=q*rational(scale)
                accepted=center-radius>=0 if current>=0 else center+radius<0
                if accepted:
                    reuse|=1<<index
                    if (current>=0)!=(target>=0):wrong|=1<<index
                index+=1
        assert (reuse,wrong,count_bits(reuse)-20*count_bits(wrong))==(atom.reused,atom.wrong,atom.utility)
        if i%2==0:
            assert r.left==r.right and r.left_closed and r.right_closed
        else:
            assert r.left==atoms[i-1].region.right and r.right==atoms[i+1].region.left
            assert r.left<r.right and not r.left_closed and not r.right_closed
            assert not any(r.left<p.left<r.right for p in path)
            q=at(path,(r.left+r.right)/2)
            for family in checked_families(rows, scales):
                for (base,slope,target,current),scale in zip(family,scales):
                    sign=1 if current>=0 else -1
                    margin=Line(sign*rational(slope)/rational(scale),sign*rational(base)/rational(scale))
                    assert (margin(r.left)-q(r.left))*(margin(r.right)-q(r.right))>=0
    return len(atoms)


def merge_regions(atoms):
    """Union ordered selected atoms while preserving excluded singleton endpoints."""
    out=[]
    for atom in atoms:
        r=atom.region
        if out and out[-1].right==r.left and (out[-1].right_closed or r.left_closed):
            prev=out.pop();out.append(Region(prev.left,r.right,prev.left_closed,r.right_closed))
        else:
            out.append(r)
    return out


def intersects(a,b):
    """Test nonempty intersection including open/closed endpoint conventions."""
    left,right=max(a.left,b.left),min(a.right,b.right)
    return left<right or left==right and a.contains(left) and b.contains(left)


def restrict(atoms, regions):
    """Keep outcome atoms attainable by at least one training-selected parameter."""
    return [a for a in atoms if any(intersects(a.region,r) for r in regions)]


def outcome_range(atoms, answers):
    """Summarize attainable counts and selection-invariant/possible answer masks."""
    if not atoms:raise ValueError('Empty parameter set')
    always=(1<<answers)-1;possible=0
    for atom in atoms:
        always&=atom.reused;possible|=atom.reused
    return {'utility_total':[min(a.utility for a in atoms),max(a.utility for a in atoms)],
            'reused':[min(count_bits(a.reused) for a in atoms),max(count_bits(a.reused) for a in atoms)],
            'wrong_reuses':[min(count_bits(a.wrong) for a in atoms),max(count_bits(a.wrong) for a in atoms)],
            'always_reused':count_bits(always),'possibly_reused':count_bits(possible),
            'selection_sensitive_answers':count_bits(possible^always),
            'always_mask':hex(always),'possible_mask':hex(possible)}


def region_record(r):
    return {'left':str(r.left),'right':str(r.right),'left_approx':float(r.left),'right_approx':float(r.right),
            'left_closed':r.left_closed,'right_closed':r.right_closed}


def path_record(path):
    return [{'left':str(p.left),'right':str(p.right),'slope':str(p.line.slope),'intercept':str(p.line.intercept)} for p in path]


def atoms_record(atoms):
    return [{**region_record(a.region),'reuse_mask':hex(a.reused),'wrong_mask':hex(a.wrong),'utility':a.utility} for a in atoms]
