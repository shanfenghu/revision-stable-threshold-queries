"""Replay a separate two-case margin-weighted comparison under its original policy.

This uses a different period/loss/floor from the later utility criterion. It is
an adverse reference, not a controlled floor ablation or successful-tuning claim.
"""
from datetime import date
import math
import statistics
from . import sources as inherited
from .workloads import basis, project

def fit(train, scales, domain, mode):
    if mode == "carry_forward":
        return 0.0
    numerator, denominator = 0.0, 0.0
    for u in train:
        b = basis(u, domain)
        residual = [y-x for x, y in zip(u["raw_inputs"], u["raw_targets"])]
        if mode == "revision_loss":
            features, responses, weights = b, residual, [1]*len(b)
        else:
            features, responses = project(b, domain), project(residual, domain)
            weights = [1/(s*s) for s in scales]
            if mode == "margin_query_loss":
                weights = [w/max(1, abs(x)/s)**2 for w, x, s in zip(weights, u["inputs"], scales)]
        numerator += math.fsum(w*f*y for w, f, y in zip(weights, features, responses))
        denominator += math.fsum(w*f*f for w, f in zip(weights, features))
    return max(-.5, min(.5, numerator/denominator)) if denominator else 0.0


def predict(u, beta, domain, shared=False):
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
    return center-radius >= 0 if input_query >= 0 else center+radius < 0


def fit_and_calibrate(units, issue, domain, mode):
    mature = [u for u in units if u["target"] < issue]
    if len(mature) < 63:
        return None
    train, calibration = mature[:24], mature[24:63]
    floor = 1 if domain == "ili" else 1e-6
    scales = [max(floor, statistics.median(abs(u["targets"][j]-u["inputs"][j]) for u in train))
              for j in range(len(train[0]["inputs"]))]
    beta = fit(train, scales, domain, mode)
    scores = [max(abs(y-mu)/s for y, mu, s in zip(u["targets"], predict(u, beta, domain), scales))
              for u in calibration]
    q, rank = inherited.cp_quantile(scores, .05)
    return {"beta": beta, "scales": scales, "q": q, "rank": rank,
            "train_issues": [u["issue"] for u in train], "calibration_issues": [u["issue"] for u in calibration],
            "latest_label": max(u["target"] for u in train+calibration)}


def run_domain(units, domain):
    label = (lambda n: date.fromordinal(n).isoformat()) if domain == "ili" else inherited.month_label
    results = []
    modes = ("carry_forward", "revision_loss", "query_loss", "margin_query_loss")
    for u in units:
        if results and u["issue"]-results[-1]["issue_ordinal"] < (28 if domain == "ili" else 3):
            continue
        fits = {m: fit_and_calibrate(units, u["issue"], domain, m) for m in modes}
        if fits["carry_forward"] is None:
            continue
        entry = {"issue_ordinal": u["issue"], "issue": label(u["issue"]), "target": label(u["target"]),
                 "input_queries": u["inputs"], "target_queries": u["targets"], "models": {}}
        for m, f in fits.items():
            mu = predict(u, f["beta"], domain)
            shared = predict(u, f["beta"], domain, True)
            radii = [f["q"]*s for s in f["scales"]]
            decisions = [reuse(x, center, r) for x, center, r in zip(u["inputs"], mu, radii)]
            shared_decisions = [reuse(x, center, r) for x, center, r in zip(u["inputs"], shared, radii)]
            if not all(math.isclose(x, y, abs_tol=1e-9, rel_tol=1e-12) for x, y in zip(mu, shared)) or decisions != shared_decisions:
                raise ValueError("Shared execution differs")
            error = [y-center for y, center in zip(u["targets"], mu)]
            entry["models"][m] = {"beta": f["beta"], "q": f["q"], "rank": f["rank"],
                                   "scales": f["scales"], "radii": radii, "predictions": mu,
                                   "reuse": decisions, "reused": sum(decisions),
                                   "wrong_reuses": sum(d and ((x>=0)!=(y>=0)) for d, x, y in zip(decisions, u["inputs"], u["targets"])),
                                   "family_covered": all(abs(e)<=r for e, r in zip(error, radii)),
                                   "mean_abs_query_error": statistics.mean(abs(e) for e in error),
                                   "latest_mature_label": label(f["latest_label"]),
                                   "shared_execution_equal": True,
                                   "train_issues": [label(i) for i in f["train_issues"]],
                                   "calibration_issues": [label(i) for i in f["calibration_issues"]]}
        results.append(entry)
        if len(results) == 2:
            break
    return {"eligible_pool": len(units), "test_families": len(results), "cases": results,
            "independent_contrast_term_uses": 56 if domain == "ili" else 16,
            "unique_contrast_terms_shared": 11 if domain == "ili" else 8,
            "speed_measured": False, "coverage_estimated": False}


