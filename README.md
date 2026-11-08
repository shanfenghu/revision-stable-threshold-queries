# Calibrated answer reuse

This research software reconstructs fixed-support threshold questions from dated
illness reports and monthly real-output vintages. It compares revision-error and
answer-utility fits, recalibrates every training-optimal scalar fit, and reports
which stored answers survive all or some fits and what one fit can attain.

The exact audit concerns a bounded scalar affine predictor, fixed positive
training scales and recorded numerical coordinates. It does not establish
exchangeability, future coverage, independent samples or forecasting superiority.
The original and subsequent windows, relative-scale sensitivity, enclosing-band
comparison and adverse margin-weighted comparison remain separate analyses.

## Setup and tests

Python 3.9 or later and the standard library suffice for all numerical commands.
No installation or account is needed. Run commands from this directory:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B run.py check-inputs --inputs /path/to/inputs
RELEASE_QUERY_INPUTS=/path/to/inputs python3 -B -m unittest discover -s tests -v
```

Tests requiring the exact data explicitly skip when `RELEASE_QUERY_INPUTS` is
unset. Tests cover source dates/missingness, maturity, rebasing, declared reward,
strict inequalities, rank paths, grid-missed islands, singleton/open optima,
corrupt certificates, fractional flags and retrospective-witness feasibility.
See [API.md](API.md) for conventions and assumptions.

## Reproduce

Obtain the exact inputs described in [data/README.md](data/README.md). Raw inputs
are not bundled. With a permitted copy of the retained input archive:

```sh
python3 -B run.py unpack-inputs --archive /path/to/release-query-inputs.zip --output /path/to/inputs
python3 -B run.py reproduce --inputs /path/to/inputs --output /path/to/new-run
```

Every command validates the 34 input sizes/digests before analysis. A changed
payload is rejected, even when its URL is unchanged. Output directories must be
new; no command refreshes numerical references or selects another window.
The full recipe reconstructs the 201-point fits, source/eligibility/maturity
ledgers, original point outcomes, all four continuous training optimum sets,
all ten policy/window decision partitions, cost controls, one-sided point
controls, enclosing bands, least training loss and the separate adverse comparison.
The direct rank formulation checks the complete envelope partitions and witnesses.

`fits.json`, `comparison.json`, `ledgers.json`, `maturity.json` and `summary.csv`
contain point-fit results. `audits/summary.json` and `audits/summary.csv` contain
all policy/window summaries. `audits/certificates.json` contains exact endpoints,
paths, masks and loss witnesses; `audits/adverse.json` retains the distinct
margin-weighted comparison. Verification records identify actual checks.

Discrete records and rational strings must match their retained references
exactly; floating summaries use relative tolerance 1e-10 and absolute tolerance
1e-12. Timing is observational, not a speedup benchmark. Numerical execution
requires only a CPU, about 256 MiB RAM and 100 MiB free space including inputs
and a run. Allow one minute as a working budget on a recent laptop; actual
resource measurements and interpreter versions are recorded with each checked run.

## Optional figures

Three vector displays and their plotted values can be generated from a verified
run. This optional step uses Python 3.10 or later and Matplotlib 3.10.0; numerical
replay has no third-party dependency. The plotting requirement is pinned in
`requirements-plot.txt`.

```sh
python3 -m pip install -r requirements-plot.txt
python3 -B run.py figures --inputs /path/to/inputs --run /path/to/new-run --output /path/to/new-figures
```

The outputs show an exact illustrative construction, bounded recorded availability,
and matched scale-policy ranges. Ranges describe fit ambiguity; intermediate
counts need not be attainable. They are not confidence intervals. Source
annotations, units and denominators are saved alongside the figures.

## Interpretation and attribution

Training uses 24 scale, 24 radius-proxy and 12 utility families, separated by
strict target-maturity gaps. Final calibration uses actual eligible counts.
Correct reuse earns one, wrong reuse costs nineteen and deferral earns zero.
These are declared rewards, not measured application costs. Reuse of a negative
answer requires a strictly negative upper band endpoint. Always-retained answers
inherit a representative fit's marginal family-risk bound only under the stated
conditional score-exchangeability premise; the possible union has no such bound.

The enclosing-band score adapts Nguyen et al., UAI 2026, Algorithm 1
([source](https://proceedings.mlr.press/v337/nguyen26c.html)) to a joint query
family and requires its own score premise. Split-conformal calibration follows
Angelopoulos and Bates (2023), [doi:10.1561/2200000101](https://doi.org/10.1561/2200000101).
The included MIT licence covers the implementation and documentation, not
third-party inputs. Dataset provenance, attribution and access limits are in the
data README. The adverse comparison uses a different loss, floor and period;
it is not a controlled floor ablation or evidence of successful tuning.
