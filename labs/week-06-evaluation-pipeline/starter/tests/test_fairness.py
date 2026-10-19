"""The fairness report: fairlearn's rates and gaps, plus the two rules fairlearn does not have."""

from __future__ import annotations

import pytest
from fairlearn.metrics import equal_opportunity_difference

from week_06_evaluation_pipeline.fairness import (
    MIN_GROUP_FOR_GAP,
    fairness_report,
    format_fairness,
)

# Two groups of 10 with known rates: a (TPR 0.8, FPR 0.2), b (TPR 0.4, FPR 0.8).
Y_TRUE = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0] * 2
Y_PRED = [1, 1, 1, 1, 0, 1, 0, 0, 0, 0] + [1, 1, 0, 0, 0, 1, 1, 1, 1, 0]
GROUPS = ["a"] * 10 + ["b"] * 10


@pytest.mark.skip(reason="Exercise 5 — implement rates_by_group and gaps in fairness.py, then delete this skip marker.")
def test_the_report_holds_the_rates_and_the_gaps():
    report = fairness_report(Y_TRUE, Y_PRED, GROUPS)
    assert report["groups"]["a"]["tpr"] == 0.8
    assert report["groups"]["b"]["fpr"] == 0.8
    assert report["selection_rate_gap"] == 0.1
    assert report["tpr_gap"] == 0.4
    assert report["fpr_gap"] == 0.6
    assert report["equalized_odds_difference"] == 0.6  # the larger of the two gaps


@pytest.mark.skip(reason="Exercise 5 — implement rates_by_group and gaps in fairness.py, then delete this skip marker.")
def test_rates_are_none_when_undefined_never_zero():
    """A group with no positives has no TPR, and one with no negatives has no FPR."""
    report = fairness_report(
        y_true=[0, 0, 0, 1, 1, 1],
        y_pred=[0, 1, 0, 1, 1, 0],
        groups=["a", "a", "a", "b", "b", "b"],
    )
    assert report["groups"]["a"]["tpr"] is None  # fairlearn says 0.0
    assert report["groups"]["b"]["fpr"] is None
    assert report["groups"]["a"]["fpr"] == pytest.approx(1 / 3, abs=1e-4)
    assert report["groups"]["b"]["tpr"] == pytest.approx(2 / 3, abs=1e-4)


@pytest.mark.skip(reason="Exercise 5 — implement rates_by_group and gaps in fairness.py, then delete this skip marker.")
def test_a_tiny_group_is_reported_but_left_out_of_the_gaps():
    """Two patients, both missed: fairlearn alone would report a TPR gap of 0.8."""
    y_true, y_pred, groups = Y_TRUE + [1, 1], Y_PRED + [0, 0], GROUPS + ["tiny"] * 2
    report = fairness_report(y_true, y_pred, groups)

    assert report["groups"]["tiny"]["n"] == 2 < MIN_GROUP_FOR_GAP
    assert report["tpr_gap"] == 0.4
    assert equal_opportunity_difference(y_true, y_pred, sensitive_features=groups) == 0.8


@pytest.mark.skip(reason="Exercise 5 — implement rates_by_group and gaps in fairness.py, then delete this skip marker.")
def test_a_group_without_positives_has_no_tpr_and_no_place_in_the_gaps():
    """fairlearn would count its TPR as 0.0 and report a TPR gap of 0.8."""
    y_true = Y_TRUE[:10] + [0] * 6
    y_pred = Y_PRED[:10] + [0, 1, 0, 0, 0, 0]
    groups = ["a"] * 10 + ["healthy"] * 6
    report = fairness_report(y_true, y_pred, groups)

    assert report["groups"]["healthy"]["tpr"] is None
    assert report["tpr_gap"] is None
    assert equal_opportunity_difference(y_true, y_pred, sensitive_features=groups) == 0.8

def test_gaps_are_none_rather_than_zero_when_there_is_nothing_to_compare():
    """With one group, fairlearn returns a gap of 0.0; the report says None."""
    report = fairness_report([1, 0, 1, 0, 1, 0], [1, 0, 1, 0, 1, 0], ["a"] * 6)
    assert report["selection_rate_gap"] is None
    assert report["equalized_odds_difference"] is None


def test_format_fairness_marks_the_gated_axes():
    report = {"insulin_missing": fairness_report([1, 0] * 10, [1, 0] * 10, ["a", "b"] * 10)}
    rendered = format_fairness(report, gated_axes={"insulin_missing": {}})
    assert "[GATED]" in rendered
    assert "insulin_missing" in rendered
