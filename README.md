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

Provider-data tests explicitly skip when `RELEASE_QUERY_INPUTS` is
unset. Tests cover source dates/missingness, maturity, rebasing, declared reward,
strict inequalities, rank paths, grid-missed islands, singleton/open optima,
corrupt certificates, fractional flags and retrospective-witness feasibility.
See [API.md](API.md) for conventions and assumptions.

## Reproduce

Download inputs from their original providers using [data/README.md](data/README.md).
Store them outside this checkout; no provider data archive is distributed here.

```sh
DATA_DIR="$(mktemp -d)/release-inputs"
python3 -B data/fetch_inputs.py --output "$DATA_DIR"
python3 -B run.py reproduce --inputs "$DATA_DIR" --output /path/to/new-run
```

Commands record input provenance and validate scientific source/cohort conditions.
`check-inputs --exact` optionally enforces historical byte identity. A different
serialization alone is not a reproduction failure; changed observations or
findings must be investigated. Output directories must be new.
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

Small summaries in `expected/` record our fitted findings and comparisons, without
provider observations or prepared query arrays. Counts and logical conditions are
checked exactly; floating summaries use relative tolerance 1e-8 and absolute
tolerance 1e-10. Full masks and certificates are verified internally for the
recorded model rather than compared bitwise to every historical output. Dense
ledgers and arrays are local analysis outputs, not distributed datasets.
Timing is observational, not a speedup benchmark. A CPU, about 300 MiB RAM,
100 MiB free local disk and one minute after acquisition are working budgets.

## Selected outputs

The actual selected scientific outputs are included:

- [Illustrative construction](figures/construction.pdf),
  [recorded availability](figures/availability.pdf) and
  [scale-policy comparisons](figures/sensitivity.pdf).
- [Point-fit table](tables/point-fits.csv) and
  [complete policy/window table](tables/policy-comparison.csv).
- [Plotted findings](figures/values.json), [key fitted comparisons](expected/comparison-summary.json)
  and [key audit findings](expected/audits.json). The other compact references in
  `expected/` retain fitted parameters, maturity and the separate adverse results.

These are our scientific displays, tables and findings, retained with their
source credit. Provider input datasets and bulky intermediate arrays are separate.
`run.py reproduce` generates the point table as `summary.csv` and the policy table
as `audits/summary.csv`; `run.py figures` generates the three PDFs and `values.json`.
The commands below regenerate them in fresh external output directories. Selected
outputs remain usable without installing plotting software or acquiring inputs.

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
