"""Deterministic replay of the fixed scalar comparison.

Training uses only the 24/24/12 mature phases, shared scales and fixed grid.
Calibration/test outcomes never select either fit. Quantiles are family maxima;
chronology alone supplies no exchangeability or coverage guarantee.
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
from . import workloads as old
BASE = old.inherited
GRID = [i/200 for i in range(-100, 101)]

def digest(path):
    """Identify exact source bytes before reconstructing the later ledger."""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def centered(values):
    """Remove the common coordinate mean without changing zero-sum contrasts."""
    avg = statistics.mean(values)
    return [x-avg for x in values]


def coordinates(u, domain):
    """Return loss coordinates; center GDP logs and basis to remove base shifts."""
    x, y, b = u["raw_inputs"], u["raw_targets"], old.basis(u, domain)
    return (centered(x), centered(y), centered(b)) if domain == "gdp" else (x, y, b)


def training_parts(units):
    """Select 24/24/12 chronological families with strict target-maturity gaps."""
    ordered = sorted(units, key=lambda u: u["issue"])
    scale = ordered[:24]
    radius = [u for u in ordered if u["issue"] > max(v["target"] for v in scale)][:24]
    utility = [u for u in ordered if u["issue"] > max(v["target"] for v in radius)][:12]
    if (len(scale), len(radius), len(utility)) != (24, 24, 12):
        raise ValueError("Insufficient mature training phases; no replacement/tuning")
    return scale, radius, utility


def training_scales(scale_units):
    """Use first-phase median revisions, floored by the pooled positive median."""
    revisions = [[abs(y-x) for x, y in zip(u["inputs"], u["targets"])] for u in scale_units]
    positive = [v for row in revisions for v in row if v > 0]
    if not positive:
        raise ValueError("Unsupported scale: no positive training revision; defer")
    floor = statistics.median(positive)
    medians = [statistics.median(row[j] for row in revisions) for j in range(len(revisions[0]))]
    return [max(v, floor) for v in medians], floor, medians


def quantile(units, beta, scales, domain):
    """Calibrate the maximum standardized query error for the given predictor."""
    scores = [max(abs(y-mu)/s for y, mu, s in zip(u["targets"], old.predict(u, beta, domain), scales))
              for u in units]
    return BASE.cp_quantile(scores, .05)


def evaluate_unit(u, beta, scales, q, domain):
    """Record all decisions, errors and declared utility; verify shared execution."""
    mu = old.predict(u, beta, domain)
    shared = old.predict(u, beta, domain, True)
    radii = [q*s for s in scales]
    reuse = [old.reuse(x, center, r) for x, center, r in zip(u["inputs"], mu, radii)]
    shared_reuse = [old.reuse(x, center, r) for x, center, r in zip(u["inputs"], shared, radii)]
    if reuse != shared_reuse or not all(math.isclose(x, y, abs_tol=1e-9, rel_tol=1e-12) for x, y in zip(mu, shared)):
        raise ValueError("Independent/shared query execution differs")
    wrong = [a and ((x>=0)!=(y>=0)) for a, x, y in zip(reuse, u["inputs"], u["targets"])]
    x, y, b = coordinates(u, domain)
    raw_error = [abs(yy-xx-beta*bb) for xx, yy, bb in zip(x, y, b)]
    errors = [abs(y-center) for y, center in zip(u["targets"], mu)]
    return {"predictions": mu, "radii": radii, "reuse": reuse, "wrong": wrong,
            "reused": sum(reuse), "deferred": len(reuse)-sum(reuse), "wrong_reuses": sum(wrong),
            "utility_total": sum(reuse)-20*sum(wrong),
            "query_mae": statistics.mean(errors), "raw_coordinate_mae": statistics.mean(raw_error),
            "family_miss": any(e>r for e, r in zip(errors, radii)), "shared_execution_equal": True}


def choose_fit(units, domain):
    """Replay both objectives over the fixed grid using training phases only."""
    scale, radius, utility = training_parts(units)
    scales, floor, medians = training_scales(scale)
    all_train = scale+radius+utility
    candidates = []
    for beta in GRID:
        loss = 0.0
        for u in all_train:
            x, y, b = coordinates(u, domain)
            loss += math.fsum((yy-xx-beta*bb)**2 for xx, yy, bb in zip(x, y, b))
        q, rank = quantile(radius, beta, scales, domain)
        outcomes = [evaluate_unit(u, beta, scales, q, domain) for u in utility]
        candidates.append({"beta": beta, "revision_squared_loss": loss, "proxy_q": q,
                           "proxy_rank": rank, "inner_utility_total": sum(r["utility_total"] for r in outcomes),
                           "inner_reused": sum(r["reused"] for r in outcomes),
                           "inner_wrong_reuses": sum(r["wrong_reuses"] for r in outcomes)})
    revision = min(candidates, key=lambda r: (r["revision_squared_loss"], abs(r["beta"]), r["beta"]))
    utility_best = min(candidates, key=lambda r: (-r["inner_utility_total"], abs(r["beta"]), r["beta"]))
    def labels(group):
        return [unit_label(u["issue"], domain) for u in group]
    return {"scales": scales, "pooled_positive_median_floor": floor, "template_medians": medians,
            "models": {"revision_loss": revision["beta"], "utility_fit": utility_best["beta"], "carry_forward": 0.0},
            "training_phases": {"scale": labels(scale), "radius": labels(radius), "utility": labels(utility)},
            "training_latest_target": unit_label(max(u["target"] for u in all_train), domain),
            "candidates": candidates}


def unit_label(value, domain):
    """Format a day or monthly vintage index for the specified domain."""
    return date.fromordinal(value).isoformat() if domain == "ili" else BASE.month_label(value)


def new_ili_units(inputs, receipts, csv_path):
    """Construct later dated families, preserving missing/late slots and source keys."""
    histories, release_groups, undated = {}, {}, []
    source_rows = []
    for receipt in receipts:
        path = inputs/receipt["path"]
        if digest(path)!=receipt["sha256"]:
            raise ValueError("Changed later-window source bytes")
        for index, r in enumerate(json.loads(path.read_text()).get("epidata", [])):
            ref, nominal = old.epiweek_end(r["epiweek"]), old.epiweek_end(r["issue"])
            if (nominal-ref).days!=7*r["lag"]:
                raise ValueError("Source epiweek/lag inconsistency")
            rec = {"reference": ref.toordinal()//7, "nominal": nominal.toordinal()//7,
                   "value": r.get("num_ili"), "source": receipt["path"]+f"#epidata[{index}]"}
            if not r.get("release_date"):
                undated.append(rec)
                continue
            rec["release"] = date.fromisoformat(r["release_date"]).toordinal()
            if rec["release"] < nominal.toordinal():
                raise ValueError("Release precedes nominal source week")
            if rec["value"] is not None:
                rec["value"] = float(rec["value"])
                if not math.isfinite(rec["value"]) or rec["value"]<0:
                    raise ValueError("Invalid source count")
            histories.setdefault(rec["reference"], []).append(rec)
            release_groups.setdefault(rec["nominal"], []).append(rec["release"])
            source_rows.append(rec)
    if len({(r["reference"], r["nominal"]) for r in source_rows})!=len(source_rows):
        raise ValueError("Duplicate source state")
    lookup = {}
    with csv_path.open(newline="") as f:
        for row, rec in enumerate(csv.DictReader(f), start=2):
            key = tuple(date.fromisoformat(rec[k]).toordinal()//7 for k in ("time_value", "issue_date"))
            lookup[key] = (float(rec["value_raw"]), row)
    mismatches = [r for r in source_rows if r["value"] is not None and lookup.get((r["reference"], r["nominal"]), (None,))[0]!=r["value"]]
    if mismatches:
        raise ValueError("Later source/CSV version mismatch; retain evidence and stop")
    def known(ref, cutoff):
        rows = [r for r in histories.get(ref, []) if r["release"]<=cutoff]
        return max(rows, key=lambda r: (r["release"], r["nominal"])) if rows else None
    first = old.epiweek_end(201251).toordinal()//7
    last = old.epiweek_end(201430).toordinal()//7
    latest_release = max(r["release"] for r in source_rows)
    units, entries = [], []
    for nominal in range(first, last+1):
        entry = {"nominal_week_end": date.fromordinal(nominal*7+6).isoformat()}
        if nominal not in release_groups:
            entry["status"] = "no_dated_release_in_acquired_source"
            entries.append(entry)
            continue
        cutoff = max(release_groups[nominal])
        deadline = cutoff+28
        entry.update(input_cutoff=date.fromordinal(cutoff).isoformat(), target_cutoff=date.fromordinal(deadline).isoformat())
        available = {ref: known(ref, cutoff) for ref in histories}
        anchor = max(ref for ref, r in available.items() if r is not None and r["value"] is not None)
        support = list(range(anchor, anchor-11, -1))
        xrows, yrows = [known(r, cutoff) for r in support], [known(r, deadline) for r in support]
        entry["input_eligible"] = all(r is not None and r["value"] is not None for r in xrows)
        entry["target_scoreable"] = all(r is not None and r["value"] is not None for r in yrows) and deadline <= latest_release
        if any(r["reference"] in support and r["nominal"]<=deadline//7 for r in undated):
            entry["status"] = "undated_report_in_support"
        elif any(r is None or r["value"] is None for r in xrows+yrows):
            entry["status"] = "missing_or_explicitly_unknown_support"
        elif deadline > latest_release:
            entry["status"] = "target_beyond_acquired_release_window"
        else:
            entry["status"] = "eligible"
            terms = []
            for ref, x, y in zip(support, xrows, yrows):
                terms.append({"reference_week_end": date.fromordinal(ref*7+6).isoformat(),
                              "input": x["value"], "target": y["value"],
                              "input_release": date.fromordinal(x["release"]).isoformat(),
                              "target_release": date.fromordinal(y["release"]).isoformat(),
                              "input_source": x["source"], "target_source": y["source"],
                              "input_csv_row": lookup[(ref, x["nominal"])][1],
                              "target_csv_row": lookup[(ref, y["nominal"])][1],
                              "input_carried_forward": x["nominal"]!=nominal,
                              "target_last_report_before_deadline": y["release"]<deadline})
            entry["terms"] = terms
            xvalues, yvalues = [r["value"] for r in xrows], [r["value"] for r in yrows]
            units.append({"issue": cutoff, "target": deadline, "anchor": anchor, "support": support,
                          "raw_inputs": xvalues, "raw_targets": yvalues,
                          "inputs": old.project(xvalues, "ili"), "targets": old.project(yvalues, "ili")})
        entries.append(entry)
    offsets = {}
    for r in source_rows:
        offset = str(r["release"]-(r["nominal"]*7+6))
        offsets[offset] = offsets.get(offset, 0)+1
    return units, {"records_checked_against_csv": len(source_rows), "csv_mismatches": 0,
                   "undated_reports": undated, "release_offset_days_counts": offsets,
                   "candidates": entries, "latest_acquired_release": date.fromordinal(latest_release).isoformat()}


def phase_windows(domain, p):
    """Read the frozen calibration and test windows in domain index units."""
    if domain == "ili":
        parse = lambda x: date.fromisoformat(x).toordinal()
        cal, test = p["final_calibration"]["ili_input_cutoffs"], p["validation"]["ili_input_release_days"]
    else:
        parse = lambda x: int(x[:4])*12+int(x[5:])-1
        cal, test = p["final_calibration"]["gdp_issue_months"], p["validation"]["gdp_issue_months"]
    return [parse(x) for x in cal], [parse(x) for x in test]


def split_final(units, fit, domain, protocol):
    """Select eligible windows and require training/calibration target maturity."""
    cal_range, test_range = phase_windows(domain, protocol)
    calibration = [u for u in units if cal_range[0]<=u["issue"]<=cal_range[1]]
    test = [u for u in units if test_range[0]<=u["issue"]<=test_range[1]]
    if not test or not calibration:
        raise ValueError("Frozen window empty; no alternate window")
    if max(u["target"] for u in calibration)>=min(u["issue"] for u in test):
        raise ValueError("Calibration target not mature before first test")
    if fit["training_latest_target"]>=unit_label(min(u["issue"] for u in calibration), domain):
        raise ValueError("Training labels overlap final calibration")
    return calibration, test


def summarize(cases, model):
    """Aggregate per-answer outcomes without pooling domains or assuming independence."""
    records = [r["models"][model] for r in cases]
    total = sum(len(r["reuse"]) for r in records)
    reused = sum(r["reused"] for r in records)
    return {"query_answers": total, "reused": reused, "deferred": total-reused,
            "reuse_fraction": reused/total, "defer_fraction": (total-reused)/total,
            "wrong_reuses": sum(r["wrong_reuses"] for r in records),
            "utility_per_query": sum(r["utility_total"] for r in records)/total,
            "mean_abs_query_error": statistics.mean(r["query_mae"] for r in records),
            "mean_abs_raw_coordinate_error": statistics.mean(r["raw_coordinate_mae"] for r in records),
            "mean_radius": statistics.mean(v for r in records for v in r["radii"]),
            "median_radius": statistics.median(v for r in records for v in r["radii"]),
            "family_misses_descriptive_only": sum(r["family_miss"] for r in records)}


def run_final(units, fit, domain, protocol):
    """Calibrate fixed fits once and retain every later per-family model outcome."""
    calibration, test = split_final(units, fit, domain, protocol)
    scales = fit["scales"]
    models = {}
    for name, beta in fit["models"].items():
        q, rank = quantile(calibration, beta, scales, domain)
        models[name] = {"beta": beta, "calibrated_q": q, "rank": rank}
    cases = []
    for u in test:
        cases.append({"issue": unit_label(u["issue"], domain), "target": unit_label(u["target"], domain),
                      "input_queries": u["inputs"], "target_queries": u["targets"],
                      "models": {name: evaluate_unit(u, rec["beta"], scales, rec["calibrated_q"], domain)
                                 for name, rec in models.items()}})
    return {"calibration_units": len(calibration), "test_units": len(test),
            "calibration_issues": [unit_label(u["issue"], domain) for u in calibration],
            "latest_calibration_target": unit_label(max(u["target"] for u in calibration), domain),
            "scales": scales, "models": models, "cases": cases,
            "summary": {name: summarize(cases, name) for name in models},
            "assurance": "Descriptive chronological comparison; no empirical coverage, acceptance-conditional or time-uniform promise"}


def gdp_audit(units, gdp_path, protocol):
    """Record monthly phase slots, fixed reference terms and worksheet addresses."""
    snapshots, addresses, _, _ = BASE.read_gdp(gdp_path)
    lookup = {u["issue"]: u for u in units}
    cal_range, test_range = phase_windows("gdp", protocol)
    entries = []
    for phase, (start, end) in (("calibration", cal_range), ("test", test_range)):
        for month in range(start, end+1):
            entry = {"phase": phase, "issue": BASE.month_label(month), "target": BASE.month_label(month+3),
                     "input_cutoff": BASE.month_close(month).isoformat(),
                     "target_cutoff": BASE.month_close(month+3).isoformat()}
            if month not in lookup:
                entry["status"] = "missing_input_or_target_support"
            else:
                u = lookup[month]
                entry["status"] = "eligible"
                entry["terms"] = [{"reference": BASE.quarter_label(r),
                                   "input": snapshots[month][r], "target": snapshots[month+3][r],
                                   "input_cell": addresses[(month, r)], "target_cell": addresses[(month+3, r)]}
                                  for r in u["support"]]
            entries.append(entry)
    return entries
