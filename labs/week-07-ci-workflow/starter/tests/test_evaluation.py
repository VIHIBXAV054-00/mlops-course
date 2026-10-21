"""Slice definitions and slice metrics. Every test builds its frame in memory."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from week_07_ci_workflow.evaluation import (
    OUT_OF_RANGE,
    format_slices,
    group_metrics,
    slice_labels,
    slice_report,
)

# TODO(student) Exercise 3: mark this module's layer with `pytestmark`:
# unit, data, eval or integration.

AGE_SPEC = {
    "column": "age",
    "kind": "bins",
    "bins": [21, 30, 40, 50, float("inf")],
    "labels": ["21-29", "30-39", "40-49", "50+"],
}
BMI_SPEC = {
    "column": "bmi",
    "kind": "bins",
    "bins": [0, 25, 30, float("inf")],
    "labels": ["under_normal", "overweight", "obese"],
    "missing_label": "missing",
}
INSULIN_SPEC = {
    "column": "insulin",
    "kind": "missing_flag",
    "labels": ["insulin_present", "insulin_missing"],
}


def test_bins_are_left_closed_right_open():
    """Bands are left-closed: [21, 30) is 21 to 29, so 29 is in the first band and 30 in the second."""
    frame = pd.DataFrame({"age": [21, 29, 30, 39, 40, 49, 50, 81]})
    labels = list(slice_labels(frame, AGE_SPEC))
    assert labels == [
        "21-29", "21-29", "30-39", "30-39", "40-49", "40-49", "50+", "50+",
    ]


def test_value_below_the_first_edge_is_reported_not_dropped():
    """A value outside every band gets the label OUT_OF_RANGE; the row is not dropped."""
    frame = pd.DataFrame({"age": [18, 25]})
    assert list(slice_labels(frame, AGE_SPEC)) == [OUT_OF_RANGE, "21-29"]


def test_a_sentinel_zero_gets_its_own_slice_not_the_lowest_band():
    """bmi == 0 is an absent measurement, not a very thin patient."""
    frame = pd.DataFrame({"bmi": [0.0, 22.0, 27.0, 35.0]})
    assert list(slice_labels(frame, BMI_SPEC)) == [
        "missing", "under_normal", "overweight", "obese",
    ]


def test_missing_flag_splits_on_whether_the_value_was_recorded():
    frame = pd.DataFrame({"insulin": [0, 130, 0, 94]})
    assert list(slice_labels(frame, INSULIN_SPEC)) == [
        "insulin_missing", "insulin_present", "insulin_missing", "insulin_present",
    ]


def test_slicing_after_imputation_invents_group_membership():
    """After imputation the unmeasured patients join a band and the `missing` slice disappears."""
    raw = pd.DataFrame({"bmi": [0.0, 0.0, 22.0, 27.0, 35.0, 40.0]})
    median = raw.loc[raw["bmi"] > 0, "bmi"].median()  # 31.0, in the obese band
    imputed = raw.replace(0.0, median)

    raw_groups = pd.Series(slice_labels(raw, BMI_SPEC)).value_counts().to_dict()
    imputed_groups = (
        pd.Series(slice_labels(imputed, BMI_SPEC)).value_counts().to_dict()
    )

    assert raw_groups["missing"] == 2
    assert "missing" not in imputed_groups
    assert imputed_groups["obese"] == raw_groups["obese"] + 2


def test_a_metric_over_no_positives_is_none_not_zero():
    """With no positives, `roc_auc` is None and `f1` is 0.0. Read both with `n_positives`."""
    metrics = group_metrics([0, 0, 0], [0, 1, 0], [0.1, 0.6, 0.2], ["g"] * 3)["g"]
    assert metrics["n"] == 3
    assert metrics["n_positives"] == 0
    assert metrics["roc_auc"] is None  # one class only
    assert metrics["f1"] == 0.0  # zero_division=0
    assert metrics["fpr"] == pytest.approx(1 / 3, abs=1e-4)


def test_fpr_is_none_when_a_group_has_no_negatives():
    metrics = group_metrics([1, 1], [1, 0], [0.9, 0.4], ["g"] * 2)["g"]
    assert metrics["fpr"] is None
    assert metrics["recall"] == 0.5


def test_one_positive_produces_two_metrics_that_contradict_each_other():
    """One positive gives F1 0.0 and ROC-AUC 1.0 on the same rows; this is why `min_positives` exists."""
    y_true = [0] * 9 + [1]
    y_pred = [0] * 10
    y_prob = [0.1] * 9 + [0.9]  # the positive has the highest score
    metrics = group_metrics(y_true, y_pred, y_prob, ["g"] * 10)["g"]
    assert metrics["n"] == 10
    assert metrics["n_positives"] == 1
    assert metrics["f1"] == 0.0
    assert metrics["roc_auc"] == 1.0


def test_every_group_is_scored_in_one_call():
    """One MetricFrame scores all groups; each record matches scoring that group alone."""
    groups = ["a"] * 6 + ["b"] * 6
    y_true = [1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1]
    y_pred = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1]
    y_prob = [0.9, 0.4, 0.2, 0.6, 0.1, 0.8, 0.3, 0.7, 0.45, 0.2, 0.1, 0.9]
    both = group_metrics(y_true, y_pred, y_prob, groups)
    alone = group_metrics(y_true[6:], y_pred[6:], y_prob[6:], groups[6:])
    assert set(both) == {"a", "b"}
    assert both["b"] == alone["b"]
    assert both["a"]["accuracy"] == pytest.approx(4 / 6, abs=1e-4)

def build_frame() -> pd.DataFrame:
    """A synthetic cohort that covers every slice group."""
    rng = np.random.default_rng(42)
    n = 60
    return pd.DataFrame(
        {
            "age": rng.integers(21, 70, n),
            "bmi": rng.choice([0.0, 22.0, 27.0, 35.0], n),
            "insulin": rng.choice([0, 100, 150], n),
            "outcome": rng.integers(0, 2, n),
        }
    )


def test_slice_report_is_json_able_and_carries_counts():
    frame = build_frame()
    y_true = frame["outcome"].to_numpy()
    y_pred = (frame["age"] > 40).astype(int).to_numpy()
    y_prob = np.linspace(0.05, 0.95, len(frame))

    report = slice_report(
        frame, y_true, y_pred, y_prob,
        {"age_band": AGE_SPEC, "bmi_band": BMI_SPEC, "insulin_missing": INSULIN_SPEC},
    )

    assert report["n_rows"] == len(frame)
    assert set(report["slices"]) == {"age_band", "bmi_band", "insulin_missing"}
    # Every axis covers all rows.
    for axis, groups in report["slices"].items():
        assert sum(g["n"] for g in groups.values()) == len(frame), axis
        for group in groups.values():
            assert "n" in group and "n_positives" in group

    import json

    json.dumps(report)


def test_groups_appear_in_declaration_order_not_alphabetical():
    """Groups come in the order the spec declares them, not alphabetically."""
    frame = build_frame()
    report = slice_report(
        frame, frame["outcome"], frame["outcome"], None, {"bmi_band": BMI_SPEC}
    )
    assert list(report["slices"]["bmi_band"]) == [
        "under_normal", "overweight", "obese", "missing",
    ]


def test_an_empty_slice_spec_produces_an_empty_report():
    """Without slice specs the report is an empty dict."""
    assert slice_report(build_frame(), [], [], None, {}) == {}


def test_format_slices_says_so_when_nothing_has_been_computed():
    rendered = format_slices({})
    assert "TODO" in rendered and "Exercise 1" in rendered


def test_mismatched_bins_and_labels_are_rejected():
    bad = dict(AGE_SPEC, labels=["a", "b"])
    with pytest.raises(ValueError, match="label"):
        slice_labels(pd.DataFrame({"age": [30]}), bad)


def test_an_unknown_slice_kind_is_rejected():
    with pytest.raises(ValueError, match="Unknown slice kind"):
        slice_labels(pd.DataFrame({"age": [30]}), {"column": "age", "kind": "quantile"})


def test_a_missing_slice_column_names_what_is_available():
    with pytest.raises(KeyError, match="glucose"):
        slice_labels(pd.DataFrame({"age": [30]}), dict(AGE_SPEC, column="glucose"))
