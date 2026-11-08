"""Dated FluView ledger, fixed supports and scalar prediction interface.

Known-at selects the last retained dated report, including explicit missingness.
An absent update can carry a previously known value, never an unobserved zero.
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
from . import sources as inherited

def epiweek_end(code):
    """Map a valid CDC epidemiological week code to its Saturday end date."""
    year, week = divmod(code, 100)
    jan = date(year, 1, 4)
    start = jan - timedelta(days=(jan.weekday() + 1) % 7)
    result = start + timedelta(days=week * 7 - 1)
    next_jan = date(year + 1, 1, 4)
    next_start = next_jan - timedelta(days=(next_jan.weekday() + 1) % 7)
    if week < 1 or result >= next_start:
        raise ValueError("Invalid CDC epiweek")
    return result


def read_source(inputs, receipts):
    """Read hash-verified training API responses with recorded release dates."""
    rows = []
    for receipt in receipts:
        path = inputs / receipt["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed source response")
        for index, r in enumerate(json.loads(path.read_text())["epidata"]):
            ref, issue = epiweek_end(r["epiweek"]), epiweek_end(r["issue"])
            release = date.fromisoformat(r["release_date"])
            if (issue-ref).days != 7*r["lag"] or release < issue:
                raise ValueError("Inconsistent source dates")
            rows.append({"reference": ref.toordinal()//7, "issue": issue.toordinal()//7,
                         "release": release.toordinal(), "value": float(r["num_ili"]),
                         "api_epiweek": r["epiweek"], "api_issue": r["issue"],
                         "source": receipt["path"] + f"#epidata[{index}]"})
    if len({(r["reference"], r["issue"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate source reference/issue")
    return rows


def known_at(history, cutoff):
    """Select the last retained report released by cutoff; explicit missing stays missing."""
    known = [r for r in history if r["release"] <= cutoff]
    return max(known, key=lambda r: (r["release"], r["issue"])) if known else None


def ili_ledger(rows, csv_path):
    """Reconstruct the bounded training families and audit each source/CSV term."""
    lookup = {}
    with csv_path.open(newline="") as f:
        for number, r in enumerate(csv.DictReader(f), start=2):
            lookup[(date.fromisoformat(r["time_value"]).toordinal()//7,
                    date.fromisoformat(r["issue_date"]).toordinal()//7)] = (float(r["value_raw"]), number)
    mismatches = [r for r in rows if lookup.get((r["reference"], r["issue"]), (None,))[0] != r["value"]]
    if mismatches:
        raise ValueError("Source/CSV mismatch; inspect before fitting")
    histories = {}
    releases = {}
    for r in rows:
        histories.setdefault(r["reference"], []).append(r)
        releases.setdefault(r["issue"], []).append(r["release"])
    last_issue = epiweek_end(201232).toordinal()//7
    candidates, units = [], []
    for nominal in sorted(releases):
        if nominal > last_issue:
            continue
        cutoff = max(releases[nominal])
        deadline = cutoff + 28
        # Latest reference already reported at cutoff. Freeze its whole support.
        available = {ref: known_at(history, cutoff) for ref, history in histories.items()}
        anchor = max(ref for ref, r in available.items() if r is not None)
        defs = inherited.query_defs("ili", anchor)
        support = sorted({r for _, terms in defs for r, _ in terms}, reverse=True)
        input_rows = [known_at(histories.get(ref, []), cutoff) for ref in support]
        target_rows = [known_at(histories.get(ref, []), deadline) for ref in support]
        reason = "eligible" if all(input_rows) and all(target_rows) else "missing_support_before_source_window"
        entry = {"nominal_issue_week_end": date.fromordinal(nominal*7+6).isoformat(),
                 "input_cutoff": date.fromordinal(cutoff).isoformat(),
                 "target_cutoff": date.fromordinal(deadline).isoformat(), "status": reason}
        if reason != "eligible":
            candidates.append(entry)
            continue
        x = {ref: r["value"] for ref, r in zip(support, input_rows)}
        y = {ref: r["value"] for ref, r in zip(support, target_rows)}
        terms = []
        for ref, r, t in zip(support, input_rows, target_rows):
            nominal_source = lookup.get((ref, nominal))
            target_source = lookup.get((ref, nominal+4))
            if nominal_source is None or target_source is None or nominal_source[0] != r["value"] or target_source[0] != t["value"]:
                raise ValueError("Source as-of reconstruction differs from CSV in the bounded ledger")
            terms.append({"reference_week_end": date.fromordinal(ref*7+6).isoformat(),
                          "input_value": r["value"], "target_value": t["value"],
                          "input_release": date.fromordinal(r["release"]).isoformat(),
                          "target_release": date.fromordinal(t["release"]).isoformat(),
                          "input_source": r["source"], "target_source": t["source"],
                          "input_csv_row": nominal_source[1], "target_csv_row": target_source[1],
                          "input_carried_forward": r["issue"] != nominal,
                          "target_carried_forward": t["issue"] != nominal+4})
        entry["terms"] = terms
        candidates.append(entry)
        units.append({"issue": cutoff, "target": deadline, "anchor": anchor, "support": support,
                      "raw_inputs": [x[r] for r in support], "raw_targets": [y[r] for r in support],
                      "inputs": inherited.evaluate(x, defs, "ili"),
                      "targets": inherited.evaluate(y, defs, "ili")})
    offsets = sorted({r["release"]-(r["issue"]*7+6) for r in rows})
    eligible = [u for u in candidates if u["status"] == "eligible"]
    ledger = {"source_records_checked": len(rows), "source_csv_mismatches": 0,
              "release_minus_nominal_days_in_checked_records": offsets,
              "candidates": len(candidates), "eligible": len(units),
              "excluded": len(candidates)-len(units), "families": candidates,
              "source_csv_asof_term_checks": sum(2*len(u["terms"]) for u in eligible),
              "carried_input_terms": sum(t["input_carried_forward"] for u in eligible for t in u["terms"]),
              "carried_target_terms": sum(t["target_carried_forward"] for u in eligible for t in u["terms"]),
              "scope": "Only the frozen national 2011-2012 window; no global six-day-shift or observed-row claim"}
    return units, ledger


def gdp_units(gdp_path):
    """Construct fixed eight-quarter log-growth families from monthly source states."""
    snapshots, addresses, labels, inventory = inherited.read_gdp(
        gdp_path)
    units = inherited.families("gdp", snapshots, 3)
    units = [u for u in units if u["issue"] >= 2000*12]
    for u in units:
        support = sorted(u["support"], reverse=True)
        u["support"] = support
        u["source_levels"] = [snapshots[u["issue"]][r] for r in support]
        u["raw_inputs"] = [math.log(snapshots[u["issue"]][r]) for r in support]
        u["raw_targets"] = [math.log(snapshots[u["target"]][r]) for r in support]
    return units


def basis(u, domain):
    """Return the declared age basis for the fixed scalar predictor."""
    return [(x if domain == "ili" else 1)/(j+1) for j, x in enumerate(u["raw_inputs"])]


def project(values, domain, shared=False):
    """Project descending reference coordinates onto the domain contrast workload."""
    if domain == "gdp":
        return [values[a]-values[a+lag] for a in range(4) for lag in (1, 4)]
    if not shared:
        return [math.fsum(values[a:a+w])/w-math.fsum(values[a+w:a+2*w])/w
                for a in range(4) for w in (1, 2, 4)]
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1]+v)
    return [(2*prefix[a+w]-prefix[a]-prefix[a+2*w])/w
            for a in range(4) for w in (1, 2, 4)]


def predict(u, beta, domain, shared=False):
    """Predict query values using independent terms or shared prefix/log work."""
    if domain == "gdp":
        levels = u["source_levels"]
        if shared:
            cached = [math.log(x)+beta/(j+1) for j, x in enumerate(levels)]
            return project(cached, domain, True)
        # The generic query executor transforms each term independently.
        return [(math.log(levels[a])+beta/(a+1))-
                (math.log(levels[a+lag])+beta/(a+lag+1))
                for a in range(4) for lag in (1, 4)]
    raw = [x+beta*b for x, b in zip(u["raw_inputs"], basis(u, domain))]
    return project(raw, domain, shared)


def reuse(input_query, center, radius):
    """Accept only if the full band supports the original >=0 Boolean answer."""
    return center-radius >= 0 if input_query >= 0 else center+radius < 0
