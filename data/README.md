# Exact source inputs

Numerical reproduction starts from 34 retained regular files, totalling
20,856,912 bytes. They are excluded from this code distribution. `../inputs.json`
records every relative filename, role, size, SHA-256 and original retrieval URL:

- `ili-revisions.csv`: 19,502,666 bytes; SHA-256
  `cbcf24ae283fe1f1da3efcba6cc0eafad527a9443d978e76a38adefd8fabd03e`.
- `real-output.xlsx`: 700,496 bytes; SHA-256
  `ae854a7518bf3a0504e4c477344bd7ed98c4321326ed2b1952b69ffaa1a7adce`.
- Sixteen `ili-training/lag00.json` through `lag15.json` responses.
- Sixteen `ili-evaluation/lag00.json` through `lag15.json` responses.

The CSV and workbook were retained on 3 November 2026. The dated responses cover
the declared national FluView windows in the manifest. Their payloads, not a
current source website, define this version. No preprocessing repair, zero-fill,
workbook metadata repair or replacement download is part of reproduction.

## Sources and credit

The CSV accompanies Tang, Rumack, Wilder and Rosenfeld, *Real-time forecasting of
data revisions in epidemic surveillance streams*, PLOS Computational Biology
(2025), [doi:10.1371/journal.pcbi.1013709](https://doi.org/10.1371/journal.pcbi.1013709).
Its original retrieval route is the CMU Delphi data repository listed in the
manifest. Only raw counts enter this workload; engineered features and
precomputed targets do not.

Dated records come from the
[Delphi FluView API](https://cmu-delphi.github.io/delphi-epidata/api/fluview.html),
national region, at the sixteen declared revision lags. The recorded release date
is an archive-known-by cutoff, not necessarily the earliest public report or a
clinical reporting time. Missing source counts never become observed zeros.

The workbook comes from the Federal Reserve Bank of Philadelphia
[Real-Time Data Set for Macroeconomists](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists),
[real-output documentation](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/routput).
It contains 733 monthly vintages and 319 quarterly reference rows. Preserve its
exact bytes, including package metadata. Values are billions of real dollars at
seasonally adjusted annual rates; GNP/GDP definitions and fixed/chain weighting
change historically. Both terms of each evaluated log contrast use one vintage.

The Bank's [terms of use](https://www.philadelphiafed.org/about-us/privacy-notice)
limit website content to informational, educational and research use, warn that
some material may require its owner's permission, and prohibit implied
endorsement. Conclusions drawn here belong to the analysis, not the Bank.
The retained Delphi route is a legacy API; current documentation describes a
migration to V5. This replay does not migrate historical payloads or treat a
new endpoint as the same frozen input version.

The implementation's MIT licence grants no rights in these inputs. Provider
terms, attribution requirements and any necessary permissions govern their
acquisition and redistribution. The PLOS article's publication licence does not
by itself establish a redistribution grant for every external source payload.

## Acquisition and preparation

Use a permitted retained copy of the listed files or the exact companion archive.
The archive SHA-256 is
`bd3f4e958fec10a3d50cdcc5bcd863fdc02cbf40b929f00e2ac7887f0fba15c7`.
It is a separate data artifact, not included or promised by the code download.
Run, from the code root:

```sh
python3 -B run.py unpack-inputs --archive /path/to/release-query-inputs.zip --output /path/to/inputs
python3 -B run.py check-inputs --inputs /path/to/inputs
```

The unpacker verifies exact member names, types, sizes and digests before creating
the new directory. It rejects duplicates, extra members, symlinks and altered
bytes. Preserve the manifest's relative filenames. An existing input directory
can instead be checked directly without copying it.

Original URLs provide source provenance and possible acquisition routes, not an
immutable historical archive. The GDP URL and API responses can change; the CSV
URL names a moving repository branch. A newly downloaded file must match the
manifest exactly. If it does not, stop and obtain the retained version through a
permitted route. No untested current-download path is claimed to recover these
bytes, and a checksum or URL is not a backup. Reproduction is unavailable without
all exact inputs. No command downloads data automatically or refreshes digests.

The saved CSV's upstream generation and the providers' complete historical
archives are outside the replay. The replay does reconstruct the bounded dated
source comparisons, all support exclusions, target maturity and numerical
results from the retained payloads. Dependent families and inspected windows do
not establish independent replication or nominal coverage.
