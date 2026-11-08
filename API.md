# Interfaces and assumptions

`run.py` is the offline entrypoint. `inputs.json` records provider routes and the
versions originally analysed. Input hashes are recorded; `check-inputs --exact`
optionally enforces those versions. Source adapters still validate chronology,
missingness and source agreement; output folders must be new. The protocol is a frozen scientific comparison, not a
hyperparameter-search interface. See the root and data READMEs for commands.

## Source states and workloads

`workloads.known_at(history, cutoff)` selects the last retained report available
by the cutoff. Absence may carry an earlier known value forward; explicit
missingness or an unknown value is not zero. Date ties use source vintage order.

A family groups twelve ILI mean contrasts over eleven reference weeks, or eight
same-vintage log contrasts over eight quarters. Supports, coefficients, anchors
and zero thresholds are fixed at the input cutoff. New observations do not
replace an anchor. ILI uses a 28-day recorded-release horizon; output uses three
monthly vintage columns and a conservative month-close convention.

`study.training_parts` selects the 24/24/12 mature phases. `choose_fit` compares
two objectives on the same 201-point scalar grid with deterministic tie breaks.
Revision loss centres output log coordinates and the age basis, removing a
common level shift without changing zero-sum growth contrasts. Scales use
training alone. Final calibration and later outcomes never select a fit.

## Exact scalar calculations

`affine` builds rank paths and decision atoms. `rank_constraints` independently
solves rank-count feasible intervals. An affine row is
`(base, slope, target, current)`; its prediction is `base + beta*slope`.
The domain is the closed interval `[-1/2, 1/2]`. All numbers and scales must be
finite. Mismatched family/scale widths are rejected before calibration or
decision pairing, including in direct witness checks. Family widths must match
the fixed positive scale vector, and the rank must be an available positive
integer. `audit.recorded_scales` preserves a
recorded float's binary rational value, rather than rounding it to a decimal.

```python
from fractions import Fraction as F
from release_queries import affine as a

scales = [F(1)]
calibration = [[(F(0), F(0), F(0), F(1))]]
evaluation = [[(F(0), F(1), F(1), F(1))]]
path = a.rank_path(a.family_lines(calibration, scales), 1)
atoms = a.decision_atoms(path, evaluation, scales)
a.verify_atoms(path, atoms, evaluation, scales)
regions = a.merge_regions([atom for atom in atoms if atom.utility == 1])
assert regions == [a.Region(F(0), F(1, 2), True, True)]
```

The current sign is fixed, not recomputed from each prediction. Positive reuse
includes equality; negative reuse is strict. Singleton boundaries are evaluated
separately. `restrict` retains outcomes intersecting selected regions;
`outcome_range` reports attainable extrema and always/possible masks, not every
intermediate integer or a jointly attainable union.

Endpoint-inclusion flags must be actual Booleans. Masks must be nonnegative
integers; the wrong-reuse mask must be a subset of reuse. Fractional indicators
are rejected, never rounded or treated as truthy. Serialized fixed-cost witness
records also require integer rewards consistent with their masks. Valid
certificates still use the original exact arithmetic. Computation is exact for
recorded coordinates, not exact real logarithms or error-free measurements.

## Diagnostics

`audit.run` replays the original/subsequent windows, selects the support-disjoint
output block from issue/reference identities, audits primary and lower-quartile
scales, and compares ten complete partitions with the direct rank formulation.
Cost changes reweight the same fixed-policy geometric atoms. Relative scale
changes reselect and recalibrate under matched references.

`set_band` calibrates distance from the raw prediction envelope of the fixed
training optimum set. Its joint-family score adapts Nguyen et al., UAI 2026,
Algorithm 1. It can retain more answers than unanimity and can produce a count
outside a fitwise range. Its score exchangeability is a separate premise.

`training_loss.solve` joins complete training/later partitions to find the least
training loss meeting a specified later target. It returns infeasibility when
no eligible atom exists. An attaining witness is checked by direct sorted scores;
it uses later labels and is not a training-only fitting policy.

`adverse` keeps a separate two-case margin-weighted loss, period and scale floor.
It is neither pooled with the utility experiment nor a controlled scale ablation.
`construction.verify_construction` checks the illustrative seven-cell example
without empirical inputs. Optional `figures` renders only verified source and
replay quantities. Descriptive agreement does not validate exchangeability,
nominal coverage, independent replication, acceptance-conditioned risk or
simultaneous guarantees across time.
