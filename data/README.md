# Data sources and reproduction

Download the data directly from the original providers below. This repository
supplies code, acquisition metadata and small summaries of our analysis. It does
not distribute provider data, prepared copies of provider observations or a data
archive in Git or release assets. Keep downloaded data, prepared arrays, dense
run records, caches and weights in local storage outside your checkout.

## Sources, access and citation

**Illness counts.** The national ILINet counts originate with the US Centers for
Disease Control and Prevention and are served by CMU Delphi. We use `num_ili`
(reported visits), not a population infection count. Obtain the revision CSV
from the authors' [original CMU Delphi dataset repository](https://github.com/cmu-delphi/data-revisions-forecasting-paper):
[download CSV](https://media.githubusercontent.com/media/cmu-delphi/data-revisions-forecasting-paper/main/data/raw/ilicases_weekly_preprocessed.csv).
Credit Tang, Rumack, Wilder and Rosenfeld, *Real-time forecasting of data
revisions in epidemic surveillance streams*, PLOS Computational Biology (2025),
[doi:10.1371/journal.pcbi.1013709](https://doi.org/10.1371/journal.pcbi.1013709).
Only raw counts in that provider-prepared CSV enter this analysis; its engineered
features and precomputed prediction targets are not used. This is the dataset
creator's distribution, not a mirror maintained by this project.

Dated reports come from the [Delphi FluView API](https://cmu-delphi.github.io/delphi-epidata/api/fluview.html).
An example of the actual training request is
[National 2011w01–2012w36 at lag zero](https://api.delphi.cmu.edu/epidata/fluview/?regions=nat&epiweeks=201101-201236&lag=0).
The provider documents this as legacy V3, being phased out in favour of V5.
Do not substitute a V5 signal without checking vintage and release-date semantics.
The provider describes the national source as publicly accessible US government
data; see its [licensing guidance](https://cmu-delphi.github.io/delphi-epidata/api/README.html#data-licensing).
Credit Farrow, Brooks, Rumack, Tibshirani and Rosenfeld (2015), *Delphi Epidata API*,
as recommended by that provider. Private imputed series can require authorization
and are not used here. Respect
current provider terms and API limits, retain the source credit and do not imply
CDC or Delphi endorsement. An upstream repository's software licence does not
by itself settle every source payload's terms.

**Real output.** Download the Federal Reserve Bank of Philadelphia's
[Real-Time Data Set for Macroeconomists, real GNP/GDP](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/routput).
Choose **Monthly Vintages, 1965:M11 to present**. The actual workbook URL is in
`../inputs.json` and is downloaded as `real-output.xlsx`. Credit the Bank and its
listed University of Richmond/BEA collaborators; consult the linked general and
real-output documentation. Levels are billions of real dollars at seasonally
adjusted annual rates. Historical GNP/GDP definitions and fixed/chain weighting
change; each evaluated log contrast uses one vintage consistently.
The Bank's [terms](https://www.philadelphiafed.org/about-us/privacy-notice)
allow informational, educational and research use subject to stated restrictions;
material owned by others can require permission. Conclusions are ours, without
Bank endorsement. The implementation's MIT licence does not license provider
inputs. We supply acquisition instructions rather than redistribute those inputs.

## Versions and scientific selections

`../inputs.json` lists the 34 original provider URLs, local filenames, roles,
recorded sizes and SHA-256 values. The CSV and workbook were retained on
3 November 2026. The recorded workbook has 733 monthly vintages and 319 quarterly
reference rows. Its package metadata is not a scientific input and is not repaired.
The CSV branch and provider workbook may change. Digests identify the version
previously analysed; equivalent serialization or workbook metadata need not match
bit for bit to reproduce substantive findings.

The other 32 files are national FluView responses at lags 0–15 weeks: sixteen
training requests over 2011w01–2012w36 and sixteen later requests over
2012w51–2014w30. Each URL states its exact reference-week range; upper endpoints
are shortened at positive lags to keep reports within the acquired window.
Filenames are `ili-training/lag00.json` through `lag15.json`, and the corresponding
`ili-evaluation/` names. Preserve that layout; do not concatenate responses or
replace release dates with nominal issue weeks.

`../protocol.json` gives the fixed analysis windows and selections. Training
uses 24 scale families, then 24 radius-proxy families, then 12 utility families,
with strict target-maturity gaps. Output training starts in January 2000. ILI
uses twelve fixed-support contrasts over eleven weeks and a 28-day later release;
output uses eight contrasts over eight quarters and three monthly vintages.
Final calibration, subsequent diagnostics and the support-disjoint output block
are selected by the recorded dates and support identities. No later outcomes
select a fit. These are retrospective, previously inspected, dependent windows.

## Download and prepare

Python 3.9+ and its standard library suffice. Run from the code root. Choose an
external directory; the script downloads directly from each URL in `inputs.json`,
rejects failed API responses/error pages and preserves existing files:

```sh
DATA_DIR="$(mktemp -d)/release-inputs"
python3 -B data/fetch_inputs.py --output "$DATA_DIR"
python3 -B run.py check-inputs --inputs "$DATA_DIR"
```

For a small acquisition check before requesting all files:

```sh
python3 -B data/fetch_inputs.py --output "$DATA_DIR" --path ili-training/lag00.json
```

Use a fresh directory for a complete download after this check; existing files
are never overwritten. If an endpoint is retired, denied or returns no records,
consult the provider for historical access. Do not obtain the data from this
project's Git history or release assets. No data archive upload is requested.
The provider URLs are acquisition routes, not an immutable backup or a promise
that every historical version remains obtainable.

No separate input-copy preparation is necessary. The analysis reads the CSV,
API JSON and XLSX XML directly: it uses CSV `value_raw`, API `num_ili`, `epiweek`,
`issue`, `lag`, `release_date`, and the workbook's dated level columns. It checks
finite/nonnegative counts, positive output levels, duplicate keys, epiweek/lag
consistency, release chronology, required support and agreement of dated counts
with the CSV. Missing counts remain missing. Families are reconstructed at their
recorded known-by cutoffs; both terms of output contrasts use the same vintage.
No zero-fill, retrospective replacement of an anchor or silent window change is
part of preparation. Generated provenance ledgers and query arrays stay local.

## Analyse and assess reproduction

```sh
RELEASE_QUERY_INPUTS="$DATA_DIR" python3 -B -m unittest discover -s tests -v
python3 -B run.py reproduce --inputs "$DATA_DIR" --output /path/to/new-run
```

Allow about 21 MB of input transfer/storage, at least 100 MiB free local disk,
about 300 MiB RAM and one minute on a recent laptop for analysis after acquisition.
API latency can make downloading longer. No GPU or third-party numerical package
is required. Use a new output directory. See the root README for optional display
and table-ready CSV generation.

The run records the actual input hashes and whether they match recorded versions,
then compares compact fitted, aggregate-outcome, maturity and audit findings.
Discrete counts, eligibility conditions and logical decisions remain exact.
Floating summaries use relative tolerance `1e-8`, absolute tolerance `1e-10`,
well above observed interpreter roundoff while far below the reported effects;
this does not excuse a changed decision or cohort. Scalar certificates are still
verified against direct ranks for the coordinates actually read. Full historical
arrays, ZIP bytes and every old mask are not publication gates. A failed source,
cohort or summary check is a discrepancy to investigate, not permission to refresh
expected results or claim the original findings were reproduced. Optional
`check-inputs --exact` diagnoses historical byte identity when provenance requires it.

Checked on 8 November 2026: one actual training API response and the actual
monthly workbook downloaded successfully; the CSV URL responded to a HEAD
request. The small acquisition command and local source reconstruction are
validated separately in the recorded checks. A fresh download of all 34 payloads
and a V5 migration have not been tested. Available retained inputs support the
analysis checks; complete acquisition remains dependent on the providers.
