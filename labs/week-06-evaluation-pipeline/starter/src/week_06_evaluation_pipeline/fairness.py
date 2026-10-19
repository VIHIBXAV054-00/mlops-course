"""Group-fairness metrics with fairlearn: rates per group, and the gaps between groups.

Rates per group: selection rate, TPR and FPR. Gaps (the largest rate minus the
smallest): demographic parity (selection rate), equal opportunity (TPR) and
equalized odds (the larger of the TPR and FPR gaps).
Reference: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equal_opportunity_difference,
    equalized_odds_difference,
    false_positive_rate,
    false_positive_rate_difference,
    selection_rate,
    true_positive_rate,
)

# Smaller groups are reported, but left out of the gaps. fairlearn has no such rule.
MIN_GROUP_FOR_GAP = 5


def rates_by_group(y_true, y_pred, groups) -> pd.DataFrame:
    """One row per group, with the columns selection_rate, tpr and fpr."""
    # TODO(student) Exercise 5: build a fairlearn `MetricFrame` with `groups` as the
    # sensitive features and three metrics, named selection_rate, tpr and fpr:
    # fairlearn's `selection_rate`, `true_positive_rate` and `false_positive_rate`.
    # Return its `by_group` table. `group_scores` in evaluation.py has the same shape.
    return pd.DataFrame()


def gaps(y_true, y_pred, groups) -> dict:
    """The four gaps between the groups, as a dict of floats."""
    # TODO(student) Exercise 5: return a dict with these four keys, each computed by
    # one fairlearn function with `groups` as the sensitive features:
    #   selection_rate_gap: the demographic parity difference;
    #   tpr_gap: the equal opportunity difference;
    #   fpr_gap: the false positive rate difference;
    #   equalized_odds_difference: the equalized odds difference.
    # Reference: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
    return {}


def _r(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def fairness_report(y_true, y_pred, groups) -> dict:
    """Rates and gaps for one axis, as plain JSON-able values rounded to 4 decimals.

    A rate with nothing to measure (TPR without positives, FPR without negatives)
    is None, where fairlearn reports 0.0. Only groups with at least
    MIN_GROUP_FOR_GAP rows and both classes enter the gaps; with fewer than two
    such groups the gaps are None.
    """
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    groups = pd.Series(groups).astype(str).to_numpy()

    rates = rates_by_group(y_true, y_pred, groups)
    report_groups = {}
    for group in sorted(set(groups)):
        truth = y_true[groups == group]
        positives = int(truth.sum())
        negatives = int(truth.size) - positives
        row = rates.loc[group] if group in rates.index else {}
        report_groups[group] = {
            "n": int(truth.size),
            "n_positives": positives,
            "selection_rate": _r(row.get("selection_rate")),
            "tpr": _r(row.get("tpr")) if positives else None,
            "fpr": _r(row.get("fpr")) if negatives else None,
        }

    comparable = [
        group
        for group, r in report_groups.items()
        if r["n"] >= MIN_GROUP_FOR_GAP and r["tpr"] is not None and r["fpr"] is not None
    ]
    rows = np.isin(groups, comparable)
    measured = (
        gaps(y_true[rows], y_pred[rows], groups[rows]) if len(comparable) >= 2 else {}
    )
    return {
        "groups": report_groups,
        "selection_rate_gap": _r(measured.get("selection_rate_gap")),
        "tpr_gap": _r(measured.get("tpr_gap")),
        "fpr_gap": _r(measured.get("fpr_gap")),
        "equalized_odds_difference": _r(measured.get("equalized_odds_difference")),
        "min_group_for_gap": MIN_GROUP_FOR_GAP,
    }


def format_fairness(report: dict, gated_axes=()) -> str:
    """The fairness tables, for the CLI."""
    if not report:
        return "No fairness report."

    def cell(value) -> str:
        return "    —  " if value is None else f"{value:7.4f}"

    lines = []
    for axis, block in report.items():
        marker = "  [GATED]" if axis in gated_axes else "  (report only)"
        lines.append("")
        lines.append(f"  axis: {axis}{marker}")
        lines.append(
            f"  {'group':<18} {'n':>4} {'pos':>4} {'sel_rate':>9} {'tpr':>7} {'fpr':>7}"
        )
        lines.append(f"  {'-' * 18} {'-' * 4} {'-' * 4} {'-' * 9} {'-' * 7} {'-' * 7}")
        for group, r in block["groups"].items():
            sel = "        —" if r["selection_rate"] is None else f"{r['selection_rate']:9.4f}"
            lines.append(
                f"  {group:<18} {r['n']:>4} {r['n_positives']:>4} {sel} "
                f"{cell(r['tpr'])} {cell(r['fpr'])}"
            )
        lines.append(
            f"    demographic parity difference (selection-rate gap): "
            f"{cell(block['selection_rate_gap']).strip()}"
        )
        lines.append(
            f"    equal opportunity difference  (TPR gap)           : "
            f"{cell(block['tpr_gap']).strip()}"
        )
        lines.append(
            f"    equalized odds difference     (max of TPR/FPR gap): "
            f"{cell(block['equalized_odds_difference']).strip()}"
        )
    return "\n".join(lines)
