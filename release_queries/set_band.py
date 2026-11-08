"""Calibrate enclosing prediction bands over a fixed training-selected model set.

Family-score adaptation of Nguyen et al., UAI 2026, Algorithm 1:
https://proceedings.mlr.press/v337/nguyen26c.html
This score has its own exchangeability premise; later outcomes only score decisions.
"""
from fractions import Fraction as F
import math
from . import affine as p

def band(row,regions):
    """Infimum/supremum of an affine prediction over nonempty bounded regions."""
    base,slope,_,_=row
    if not regions:raise ValueError('Empty model set')
    values=[F(base)+F(slope)*x for r in regions for x in (r.left,r.right)]
    return min(values),max(values)

def quantile(calibration,regions,scales):
    """Calibrate distance from raw enclosing bands using one maximum per family."""
    k=math.ceil((len(calibration)+1)*.95)
    if not calibration or k>len(calibration):raise ValueError('Unsupported finite calibration rank')
    scores=[]
    for family in calibration:
        distances=[]
        for row,scale in zip(family,scales):
            if scale<=0:raise ValueError('Nonpositive scale')
            low,high=band(row,regions);y=row[2]
            distances.append(max(F(0),low-y,y-high)/F(scale))
        scores.append(max(distances))
    return sorted(scores)[k-1],k,scores

def evaluate(evaluation,regions,scales,q):
    """Return fixed-answer decisions; evaluation targets enter scoring only."""
    reused=wrong=index=0;bounds=[]
    for family in evaluation:
        for row,scale in zip(family,scales):
            low,high=band(row,regions);low-=q*F(scale);high+=q*F(scale)
            accept=low>=0 if row[3]>=0 else high<0
            if accept:
                reused|=1<<index
                if (row[3]>=0)!=(row[2]>=0):wrong|=1<<index
            bounds.append([str(low),str(high)]);index+=1
    return {'reused':p.count_bits(reused),'wrong_reuses':p.count_bits(wrong),
            'utility_total':p.count_bits(reused)-20*p.count_bits(wrong),
            'reuse_mask':hex(reused),'wrong_mask':hex(wrong),'expanded_bounds':bounds}

def direct_float(calibration,evaluation,regions,scales):
    """Independent arithmetic route: explicit candidate endpoint predictions."""
    endpoints=[float(x) for r in regions for x in (r.left,r.right)]
    def raw(row):
        values=[float(row[0])+float(row[1])*b for b in endpoints]
        return min(values),max(values)
    scores=[max(max(0.0,raw(row)[0]-float(row[2]),float(row[2])-raw(row)[1])/float(s) for row,s in zip(family,scales)) for family in calibration]
    q=sorted(scores)[math.ceil((len(scores)+1)*.95)-1];mask=0;index=0
    for family in evaluation:
        for row,s in zip(family,scales):
            low,high=raw(row);low-=q*float(s);high+=q*float(s)
            if (low>=0 if row[3]>=0 else high<0):mask|=1<<index
            index+=1
    return mask,q

