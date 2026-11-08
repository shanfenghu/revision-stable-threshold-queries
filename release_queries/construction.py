"""A finite affine example of recalibration changing fixed-answer reuse.

An illustration of decisions, not a statistical coverage or source-data claim.
"""
from fractions import Fraction as F
from pathlib import Path

def verify_construction():
    """Check all decision cells, including equality points, with rational arithmetic.

    Nineteen three-query calibration families give rank ceil(20 * .95) = 19.
    Inner-radius families have prediction/target 3, hence radius zero. One
    inner-utility family has the same predictions and positive targets, giving
    utility 3 for every parameter in [0, 1]. Thus the full interval is optimal.
    Final-calibration families have prediction 1 + beta and target zero, hence
    family score and cutoff 1 + beta. No probabilistic premise is asserted.
    """
    margins = {"a": (F(3), F(0)), "b": (F(5, 4), F(0)),
               "c": (F(1, 4), F(2))}
    cutoff = (F(1), F(1))
    # Derive crossings instead of assuming that a plotting grid finds them.
    roots = {F(0), F(1)}
    for intercept, slope in margins.values():
        if slope != cutoff[1]:
            root = (cutoff[0] - intercept) / (slope - cutoff[1])
            if 0 <= root <= 1:
                roots.add(root)
    events = sorted(roots)
    assert events == [F(0), F(1, 4), F(3, 4), F(1)]

    def retain(beta, frozen=False):
        q = F(1) if frozen else cutoff[0] + cutoff[1] * beta
        return tuple(name for name, (a, b) in margins.items() if a + b * beta >= q)

    cells = []
    for i, beta in enumerate(events):
        cells.append({"kind": "singleton", "left": str(beta), "right": str(beta),
                      "retained": retain(beta)})
        if i + 1 < len(events):
            right = events[i + 1]
            cells.append({"kind": "open_interval", "left": str(beta), "right": str(right),
                          "retained": retain((beta + right) / 2)})
    always = sorted(set.intersection(*(set(c["retained"]) for c in cells)))
    possible = sorted(set.union(*(set(c["retained"]) for c in cells)))
    counts = sorted({len(c["retained"]) for c in cells})
    assert always == ["a"] and possible == ["a", "b", "c"] and counts == [1, 2]
    assert retain(F(0)) == ("a", "b") and retain(F(1)) == ("a", "c")
    assert retain(F(1, 4)) == ("a", "b") and retain(F(3, 4)) == ("a", "c")
    assert retain(F(1), frozen=True) == ("a", "b", "c")
    b_prediction = margins["b"][0]
    b_bands = {str(beta): [str(b_prediction - (1 + beta)),
                           str(b_prediction + (1 + beta))] for beta in (F(0), F(1))}
    assert b_bands == {"0": ["1/4", "9/4"], "1": ["-3/4", "13/4"]}
    # Verify both the training tie and each final-calibration rank, on every cell.
    for cell in cells:
        beta = (F(cell["left"]) + F(cell["right"])) / 2
        inner_scores = [max(abs(F(3) - F(3)) for _ in range(3)) for _ in range(19)]
        assert sorted(inner_scores)[18] == 0
        inner_utility = sum(F(1) if F(3) >= sorted(inner_scores)[18] else F(0)
                            for _ in range(3))
        assert inner_utility == 3  # All three retained answers have positive targets.
        final_scores = [max(abs(1 + beta) for _ in range(3)) for _ in range(19)]
        assert sorted(final_scores)[18] == 1 + beta
    return {"purpose": "Constructed illustration; not an empirical or coverage experiment",
            "parameter_interval": ["0", "1"], "scales": "all one", "thresholds": "all zero",
            "current_answers": "all positive", "nominal_alpha": "1/20", "calibration_families": 19,
            "queries_per_family": 3, "calibration_rank": 19,
            "training": {"inner_radius_predictions_and_targets": "3",
                         "inner_utility_predictions_and_targets": "3",
                         "utility_correct_wrong_defer": [1, -19, 0],
                         "utility_for_every_parameter": 3},
            "final_calibration": {"prediction": "1 + beta", "target": "0", "cutoff": "1 + beta"},
            "test_margins_intercept_slope": {k: [str(x) for x in v] for k, v in margins.items()},
            "retention_rule": "margin >= cutoff (equality retained)", "cells": cells,
            "always": always, "possible": possible, "attainable_counts": counts,
            "unchanged_b_prediction": {"prediction": "5/4", "bands_at_endpoints": b_bands,
                                       "lower_endpoint": "1/4 - beta"},
            "frozen_cutoff_control": {"cutoff": "1", "c_crossing": "3/8", "at_beta_1": retain(F(1), True)},
            "limits": "Illustrative affine inputs; no exchangeability, source-data, or risk validation claim"}


def render_figure(destination):
    """Render a fixed-size vector figure after verifying its exact construction."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    record = verify_construction()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelsize": 8.5, "xtick.labelsize": 8.5,
                         "ytick.labelsize": 8.5, "pdf.fonttype": 42})
    colors = {"a": "#26734d", "b": "#28639b", "c": "#bb4b26"}
    fig = plt.figure(figsize=(7.1, 2.65))
    left = fig.add_axes([.075, .245, .375, .54])
    right = fig.add_axes([.585, .245, .385, .54])
    fig.text(.075, .965, "(a) A constant prediction can lose reuse", va="top", fontsize=9)
    fig.text(.585, .965, "(b) Retained identities and joint counts", va="top", fontsize=9)
    beta = [0, 1]
    for name, ys in (("a", [3, 3]), ("b", [1.25, 1.25]), ("c", [.25, 2.25])):
        left.plot(beta, ys, color=colors[name], lw=1.8)
    left.plot(beta, [1, 2], color="#202020", ls="--", lw=1.5)
    # Shade only b's lost support: its margin stays fixed while calibration rises.
    left.fill_between([.25, 1], [1.25, 1.25], [1.25, 2], color=colors["b"], alpha=.12)
    left.annotate("Same prediction for b;\nrecalibration removes reuse",
                  xy=(.9, 1.43), xytext=(.28, 2.65), va="top", fontsize=8.5,
                  arrowprops={"arrowstyle": "->", "color": colors["b"], "lw": .9},
                  bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
    handles = [Line2D([], [], color=colors[k], lw=1.8, label=label) for k, label in
               (("a", "Da = 3"), ("b", "Db = 5/4"), ("c", "Dc = 1/4 + 2β"))]
    handles.append(Line2D([], [], color="#202020", ls="--", lw=1.5, label="qC = 1 + β"))
    left.legend(handles=handles, loc="lower left", bbox_to_anchor=(-.04, 1.0),
                ncol=2, frameon=False, fontsize=8.5, columnspacing=.8,
                handlelength=1.5, handletextpad=.4, borderaxespad=0)
    left.set(xlim=(0, 1), ylim=(0, 3.35), xlabel="Parameter β",
             ylabel="Normalised margin / cutoff", xticks=[0, .25, .75, 1])
    left.set_xticklabels(["0", "1/4", "3/4", "1"])
    left.set_yticks([0, 1, 2, 3])
    left.grid(axis="y", color="#dadada", lw=.5)
    left.set_axisbelow(True)
    for x in (.25, .75):
        left.axvline(x, color="#999999", lw=.6, ls=":")
    for name, y, start, stop in (("a", 3, 0, 1), ("b", 2, 0, .25), ("c", 1, .75, 1)):
        right.hlines(y, 0, 1, color="#e3e5e7", lw=5)
        right.hlines(y, start, stop, color=colors[name], lw=5)
        right.plot([start, stop], [y, y], "o", color=colors[name], ms=4)
    for x in (.25, .75):
        right.axvline(x, color="#999999", lw=.6, ls=":", ymin=0, ymax=.96)
    right.set(xlim=(0, 1), ylim=(.15, 3.75), yticks=[1, 2, 3],
              yticklabels=["c", "b", "a"], xticks=[0, .25, .75, 1], xlabel="Parameter β")
    right.set_xticklabels(["0", "1/4", "3/4", "1"])
    right.spines["left"].set_visible(False)
    right.tick_params(axis="y", length=0)
    right.text(-.035, .23, "Joint count", ha="right", va="center", fontsize=8.5)
    for x, count in ((.125, 2), (.5, 1), (.875, 2)):
        right.text(x, .23, str(count), ha="center", va="center", fontsize=9)
    right.text(.5, 3.58, "Coloured segment = retained; dot = included", ha="center", fontsize=8.5)
    fig.text(.5, .03, "Always: {a}     Possible: {a, b, c}     Attainable counts: {1, 2}",
             ha="center", fontsize=9)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, metadata={"Creator": "Matplotlib; verified affine construction",
                                       "CreationDate": None, "ModDate": None})
    plt.close(fig)
    return record


