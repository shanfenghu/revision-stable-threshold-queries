"""Read-only source adapters and fixed-support contrast definitions.

Counts are reported visits; monthly levels use a closed-month information
convention. Missing terms invalidate a family and are never imputed as zero.
"""

import calendar
import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
AS_OF = date(2026, 11, 3)

def month_label(m):
    """Format an integer year*12 + month-1 index as YYYY-MM."""
    year, zero_month = divmod(m, 12)
    return f"{year:04d}-{zero_month + 1:02d}"


def month_close(m):
    """Return the last calendar day of a monthly vintage."""
    y, z = divmod(m, 12)
    return date(y, z + 1, calendar.monthrange(y, z + 1)[1])


def quarter_label(q):
    """Format an integer year*4 + quarter-1 reference index."""
    y, z = divmod(q, 4)
    return f"{y}:Q{z + 1}"


def read_ili(path):
    """Read the saved revision table; validate dates, finite counts and its rectangle."""
    snapshots, addresses, references, lags = {}, {}, set(), set()
    target_offsets, rows = set(), 0
    with path.open(newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            ref, issue = (date.fromisoformat(row[x]) for x in ("time_value", "issue_date"))
            if ref.weekday() != 5 or issue.weekday() != 5:
                raise ValueError("Unexpected weekly convention")
            lag = int(row["lag"])
            if issue != ref + timedelta(days=lag) or lag < 0 or lag % 7:
                raise ValueError("Invalid ILI lag/date mapping")
            value = float(row["value_raw"])
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid ILI count")
            snap = snapshots.setdefault(issue.toordinal() // 7, {})
            r = ref.toordinal() // 7
            if r in snap:
                raise ValueError("Duplicate ILI reference/vintage")
            snap[r] = value
            addresses[(issue.toordinal() // 7, r)] = f"CSV row {line}: value_raw"
            references.add(r)
            lags.add(lag)
            target_offsets.add((date.fromisoformat(row["target_date"]) - ref).days)
            rows += 1
    if rows != len(references) * len(lags):
        raise ValueError("Unexpected ILI rectangle")
    # Saturday is ordinal %7==6; original row dates were checked before division.
    labels = {m: date.fromordinal(m * 7 + 6).isoformat() for m in snapshots}
    final_ref = max(references)
    repeated_tail = 0
    for r in references:
        vals = [snapshots[m][r] for m in sorted(snapshots) if r in snapshots[m] and m - r >= 26]
        repeated_tail += len(set(vals)) == 1
    inventory = {
        "rows": rows, "reference_weeks": len(references), "issue_labels": len(snapshots),
        "reference_range": [date.fromordinal(r * 7 + 6).isoformat() for r in (min(references), final_ref)],
        "issue_label_range": [labels[min(snapshots)], labels[max(snapshots)]],
        "lags_days": [min(lags), max(lags), len(lags)],
        "precomputed_target_offsets_days": sorted(target_offsets),
        "references_constant_from_lag_26_weeks": repeated_tail,
        "issue_labels_after_last_reference": sum(m > final_ref for m in snapshots),
        "actual_capture_dates_verified": False,
    }
    return snapshots, addresses, labels, inventory


def read_gdp(path):
    """Read positive monthly levels and cell addresses directly from unchanged XLSX XML."""
    with ZipFile(path) as z:
        strings = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        if root.findall(".//s:f", NS):
            raise ValueError("Unexpected formulas in input vintage matrix")
        cells = {}
        for c in root.findall(".//s:c", NS):
            v = c.find("s:v", NS)
            if v is None:
                continue
            value = strings[int(v.text)] if c.get("t") == "s" else v.text
            if c.attrib["r"] in cells:
                raise ValueError("Duplicate cell")
            cells[c.attrib["r"]] = value
    columns, refs = {}, {}
    for address, value in cells.items():
        if re.fullmatch(r"[A-Z]+1", address) and address != "A1":
            match = re.fullmatch(r"ROUTPUT(\d{2})M(\d{1,2})", value)
            if not match:
                raise ValueError("Unknown vintage header")
            yy, mm = map(int, match.groups())
            year = 1900 + yy if yy >= 65 else 2000 + yy
            if not 1 <= mm <= 12:
                raise ValueError("Invalid vintage month")
            columns[address[:-1]] = year * 12 + mm - 1
        elif re.fullmatch(r"A\d+", address) and address != "A1":
            match = re.fullmatch(r"(\d{4}):Q([1-4])", value)
            if not match:
                raise ValueError("Unknown observation label")
            yy, qq = map(int, match.groups())
            refs[int(address[1:])] = yy * 4 + qq - 1
    if len(set(columns.values())) != len(columns) or len(set(refs.values())) != len(refs):
        raise ValueError("Duplicate vintage or reference labels")
    months = sorted(columns.values())
    if months != list(range(months[0], months[-1] + 1)):
        raise ValueError("Nonconsecutive vintage columns")
    snapshots, addresses, missing = {m: {} for m in months}, {}, 0
    for col, month in columns.items():
        for row, ref in refs.items():
            address = f"{col}{row}"
            value = cells.get(address)
            if value in (None, "#N/A"):
                missing += 1
                continue
            number = float(value)
            if not math.isfinite(number) or number <= 0:
                raise ValueError("Invalid GDP level")
            snapshots[month][ref] = number
            addresses[(month, ref)] = address
    inventory = {
        "vintage_columns": len(columns), "observation_quarters": len(refs),
        "vintage_range": [month_label(months[0]), month_label(months[-1])],
        "observation_range": [quarter_label(min(refs.values())), quarter_label(max(refs.values()))],
        "numeric_cells": len(addresses), "missing_cells": missing,
        "formula_cells": 0, "future_or_unclosed_months_excluded": [month_label(m) for m in months if month_close(m) > AS_OF],
        "reader": "Read-only ZIP/XML; malformed core-properties timestamp left unchanged",
        "actual_capture_days_verified": False,
    }
    # Closing the month is a conservative retrospective information convention,
    # not a claim that this modern download existed at that historical date.
    return {m: v for m, v in snapshots.items() if month_close(m) <= AS_OF}, addresses, {m: month_label(m) for m in months}, inventory


def query_defs(domain, anchor):
    """Return named fixed-support contrasts anchored on a reference index."""
    if domain == "ili":
        return [(f"offset{a}_mean{w}", [(anchor-a-j, 1/w) for j in range(w)] +
                 [(anchor-a-w-j, -1/w) for j in range(w)]) for a in range(4) for w in (1, 2, 4)]
    return [(f"offset{a}_lag{lag}", [(anchor-a, 1), (anchor-a-lag, -1)])
            for a in range(4) for lag in (1, 4)]


def evaluate(snapshot, definitions, domain):
    # A missing term invalidates the whole family; it is never replaced by zero.
    """Evaluate contrasts, returning None when any required reference is absent."""
    if any(r not in snapshot for _, terms in definitions for r, _ in terms):
        return None
    return [sum(w * (math.log(snapshot[r]) if domain == "gdp" else snapshot[r]) for r, w in terms)
            for _, terms in definitions]


def families(domain, snapshots, horizon):
    """Freeze each input anchor and evaluate it at the specified later vintage."""
    result = []
    for issue in sorted(snapshots):
        target = issue + horizon
        if not snapshots[issue] or target not in snapshots:
            continue
        anchor = max(snapshots[issue])
        if domain == "ili" and anchor > issue:
            raise ValueError("Future ILI reference in input")
        if domain == "gdp":
            year, quarter = divmod(anchor, 4)
            # Quarter must have ended before the vintage month begins.
            if year * 12 + (quarter + 1) * 3 - 1 >= issue:
                raise ValueError("Unfinished GDP reference in input")
        definitions = query_defs(domain, anchor)
        inputs = evaluate(snapshots[issue], definitions, domain)
        targets = evaluate(snapshots[target], definitions, domain)
        if inputs is None or targets is None:
            continue
        result.append({"issue": issue, "target": target, "anchor": anchor,
                       "support": sorted({r for _, terms in definitions for r, _ in terms}),
                       "inputs": inputs, "targets": targets})
    return result


def cp_quantile(scores, alpha):
    """Return the finite-sample rank quantile; use infinity for insufficient scores."""
    rank = math.ceil((len(scores) + 1) * (1 - alpha))
    return (sorted(scores)[rank - 1] if rank <= len(scores) else math.inf), rank
