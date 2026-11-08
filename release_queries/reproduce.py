"""Offline replay and checks against retained numerical outcomes.

Input paths are relative to an explicit input directory. Output creation is
exclusive, so a replay cannot refresh its own reference or overwrite a prior run.
"""

import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

from . import sources, study, workloads

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILES = ("fits.json", "comparison.json", "ledgers.json", "maturity.json",
                "summary.csv", "verification.json")


def safe_path(root, name):
    """Resolve a regular relative path, rejecting escapes and every symlink."""
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts or "\\" in name:
        raise ValueError("Unsafe relative path: " + name)
    root = Path(root).resolve()
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlink input is unsupported: " + name)
    if not path.resolve().is_relative_to(root):
        raise ValueError("Path escapes input root")
    return path


def read_json(path):
    """Read a UTF-8 JSON record without modifying it."""
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs(inputs, manifest=None, exact=False):
    """Record input provenance; require historical byte identity only on request.

    Each reader still validates dates, support, values and source agreement.
    Returned hashes bind the checked bytes to the subsequent source reads.
    """
    manifest = read_json(ROOT / "inputs.json") if manifest is None else manifest
    names, records = set(), []
    for rec in manifest["files"]:
        if rec["path"] in names:
            raise ValueError("Duplicate input path")
        names.add(rec["path"])
        path = safe_path(inputs, rec["path"])
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Missing or empty input: " + rec["path"])
        body = path.read_bytes()
        actual = hashlib.sha256(body).hexdigest()
        matches = len(body) == rec["bytes"] and actual == rec["sha256"]
        if exact and not matches:
            raise ValueError("Input version mismatch: " + rec["path"])
        records.append({**rec, "bytes": len(body), "sha256": actual,
                        "recorded_sha256": rec["sha256"],
                        "matches_recorded_version": matches})
    return records


def fit_summary(fits):
    """Keep fitted findings without the dense parameter-grid trace."""
    return {d: {k: v for k, v in value.items() if k != "candidates"}
            for d, value in fits.items()}


def comparison_summary(results):
    """Keep aggregate model findings, excluding prepared input/query arrays."""
    keys = ("calibration_units", "test_units", "latest_calibration_target",
            "scales", "models", "summary", "assurance")
    return {d: {k: value[k] for k in keys} for d, value in results.items()}


def adverse_summary(results):
    """Summarise the separate diagnostic without publishing its query inputs."""
    out = {}
    for domain, value in results.items():
        cases = value["cases"]
        out[domain] = {"eligible_pool": value["eligible_pool"],
                       "test_families": value["test_families"],
                       "query_answers": sum(len(v["input_queries"]) for v in cases),
                       "models": {}}
        for model in cases[0]["models"]:
            rows = [v["models"][model] for v in cases]
            out[domain]["models"][model] = {
                "reused": sum(v["reused"] for v in rows),
                "wrong_reuses": sum(v["wrong_reuses"] for v in rows),
                "family_misses": sum(not v["family_covered"] for v in rows)}
    return out


def audit_summary(value):
    """Compare scientific summaries, leaving full masks/certificates local.

    Exact rational calculations are verified internally against direct ranks;
    historical endpoints are compared through their numerical approximations.
    """
    if isinstance(value, dict):
        return {k: audit_summary(v) for k, v in value.items()
                if k not in ("left", "right", "issues") and not k.endswith("mask")}
    if isinstance(value, list):
        return [audit_summary(v) for v in value]
    return value


def compare(actual, expected, trail="root"):
    """Require exact structure/discrete fields; floats use rtol=1e-8, atol=1e-10."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError("Different keys at " + trail)
        for key in expected:
            compare(actual[key], expected[key], trail + "." + key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("Different list at " + trail)
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, trail + f"[{i}]")
    elif isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
                actual, expected, rel_tol=1e-8, abs_tol=1e-10):
            raise ValueError("Different numerical value at " + trail)
    elif type(actual) is not type(expected) or actual != expected:
        raise ValueError("Different value at " + trail)


def phase_ledger(ledger, protocol):
    """Retain planned slots, including undated and late out-of-window releases."""
    by_nominal = {r["nominal_week_end"]: r for r in ledger["candidates"]}
    out = {}
    for phase, bounds in protocol["ili_nominal_slots"].items():
        window = study.phase_windows("ili", protocol)[phase == "test"]
        first_test = study.phase_windows("ili", protocol)[1][0]
        start, end = map(date.fromisoformat, bounds)
        rows = []
        for i in range((end - start).days // 7 + 1):
            nominal = (start + timedelta(days=7*i)).isoformat()
            entry = by_nominal[nominal]
            cutoff = entry.get("input_cutoff")
            target = entry.get("target_cutoff")
            status = entry["status"]
            in_window = cutoff is not None and window[0] <= date.fromisoformat(cutoff).toordinal() <= window[1]
            if cutoff is not None and not in_window:
                status = "dated_release_outside_fixed_window"
            elif status == "eligible":
                status = "retained"
            rows.append({"nominal_week_end": nominal, "input_cutoff": cutoff,
                         "target_cutoff": target, "status": status,
                         "input_eligible": entry.get("input_eligible", False),
                         "target_scoreable": entry.get("target_scoreable", False),
                         "target_mature_before_first_test": target is not None and
                         date.fromisoformat(target).toordinal() < first_test})
        out[phase] = {"nominal_slots": len(rows), "retained": sum(r["status"] == "retained" for r in rows), "slots": rows}
    return out


def reproduce(inputs, output):
    """Run both adapters, reproduce frozen fits, calibrate, score and verify.

    This is a deterministic replay of one declared comparison, not a procedure
    for selecting new windows or tuning against the retained reference outcomes.
    """
    records = verify_inputs(inputs)
    inputs, output = Path(inputs).resolve(), Path(output)
    if output.exists():
        raise ValueError("Output already exists; choose a new run directory")
    protocol = read_json(ROOT / "protocol.json")
    role = lambda name: [r for r in records if r["role"] == name]
    csv_path = safe_path(inputs, role("ili_table")[0]["path"])
    gdp_path = safe_path(inputs, role("gdp_table")[0]["path"])
    early, early_ledger = workloads.ili_ledger(workloads.read_source(inputs, role("ili_training")), csv_path)
    gdp = workloads.gdp_units(gdp_path)
    training = {"ili": early, "gdp": [u for u in gdp if u["issue"] <= 2005*12+5]}
    fits = {d: study.choose_fit(units, d) for d, units in training.items()}
    # Check the reconstructed training record before evaluating later outcomes.
    compare(fit_summary(fits), read_json(ROOT / "expected/fits.json"))
    ili, later_ledger = study.new_ili_units(inputs, role("ili_evaluation"), csv_path)
    comparison = {d: study.run_final(units, fits[d], d, protocol) for d, units in (("ili", ili), ("gdp", gdp))}
    compare(comparison_summary(comparison), read_json(ROOT / "expected/comparison-summary.json"))
    phases = phase_ledger(later_ledger, protocol)
    compare({k: {n: v[n] for n in ("nominal_slots", "retained")} for k, v in phases.items()},
            {"calibration": {"nominal_slots": 39, "retained": 30}, "test": {"nominal_slots": 25, "retained": 24}})
    maturity = {}
    for d, units in training.items():
        groups = study.training_parts(units)
        maturity[d] = {name: {"inputs": [study.unit_label(u["issue"], d) for u in group],
                             "latest_target": study.unit_label(max(u["target"] for u in group), d)}
                       for name, group in zip(("scale", "inner_radius", "inner_utility"), groups)}
        maturity[d]["final_calibration_latest_target"] = comparison[d]["latest_calibration_target"]
        maturity[d]["first_test_input"] = comparison[d]["cases"][0]["issue"]
    ledgers = {"ili_training": early_ledger, "ili_evaluation": later_ledger,
               "ili_phase_eligibility": phases, "gdp": study.gdp_audit(gdp, gdp_path, protocol)}
    compare(maturity, read_json(ROOT / "expected/maturity.json"))
    verification = {"maturity_summary_matches": True, "required_input_files": len(records), "exact_input_versions": all(v["matches_recorded_version"] for v in records), "input_provenance": records,
                    "fit_summaries_match": True, "aggregate_later_findings_match": True,
                    "ili_nominal_and_retained_denominators_match": True,
                    "float_relative_tolerance": 1e-8, "float_absolute_tolerance": 1e-10,
                    "source_csv_mismatches": early_ledger["source_csv_mismatches"] + later_ledger["csv_mismatches"],
                    "assurance": "Descriptive replay; exchangeability is a premise, not verified by this run"}
    output.mkdir(parents=True)
    for name, value in (("fits", fits), ("comparison", comparison), ("ledgers", ledgers),
                        ("maturity", maturity), ("verification", verification)):
        (output / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    with (output / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "model"] + list(comparison["ili"]["summary"]["revision_loss"]))
        writer.writeheader()
        for d, result in comparison.items():
            for model, values in result["summary"].items():
                writer.writerow({"domain": d, "model": model, **values})
    return verification



def unpack_inputs(archive, output, manifest=None):
    """Validate the complete frozen ZIP before writing a new input directory."""
    from zipfile import ZipFile
    import stat
    manifest = read_json(ROOT/'inputs.json') if manifest is None else manifest
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Input output directory already exists')
    entries = {value['path']: value for value in manifest['files']}
    if len(entries) != len(manifest['files']):
        raise ValueError('Duplicate input manifest path')
    bodies = {}
    with ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != set(entries):
            raise ValueError('Missing, duplicate or unclassified input ZIP members')
        for item in source.infolist():
            safe_path(output, item.filename)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if mode not in (0, stat.S_IFREG) or item.file_size != entries[item.filename]['bytes']:
                raise ValueError('Invalid input ZIP member type or size')
            body = source.read(item.filename)
            if hashlib.sha256(body).hexdigest() != entries[item.filename]['sha256']:
                raise ValueError('Input version mismatch: '+item.filename)
            bodies[item.filename] = body
    output.mkdir(parents=True)
    for name, body in bodies.items():
        path = safe_path(output, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return {'verified_input_files': len(verify_inputs(output, manifest))}
