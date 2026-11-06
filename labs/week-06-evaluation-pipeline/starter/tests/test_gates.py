"""The acceptance criteria, one kind of check at a time.

`evaluate_gate` is a pure function over four plain dicts, so this file needs no
model, no data and no services.
"""

from __future__ import annotations

import pytest

from week_06_evaluation_pipeline.gates import evaluate_gate, format_gate

GOOD_METRICS = {
    "accuracy": 0.7656,
    "precision": 0.6964,
    "recall": 0.5821,
    "f1": 0.6341,
    "roc_auc": 0.8345,
}
BASELINE = {"metrics": dict(GOOD_METRICS)}

ACCEPTANCE = {
    "criteria_version": "1.0.0",
    "minimum": {"accuracy": 0.70, "f1": 0.55, "roc_auc": 0.75},
    "regression": {"primary_metric": "f1", "max_drop": 0.01,
                   "also_report": ["accuracy", "roc_auc"]},
    "slice_rules": {"min_support": 20, "min_positives": 10,
                    "min_f1": 0.50, "max_f1_gap": 0.10},
    "fairness": {"grp": {"max_selection_rate_gap": 0.10, "max_tpr_gap": 0.20}},
}


def slices(groups: dict, fairness: dict | None = None) -> dict:
    return {
        "n_rows": sum(g["n"] for g in groups.values()),
        "n_positives": sum(g["n_positives"] for g in groups.values()),
        "slices": {"grp": groups},
        "fairness": {"grp": fairness or {
            "groups": {}, "selection_rate_gap": 0.0070, "tpr_gap": 0.1562,
            "fpr_gap": 0.0139, "equalized_odds_difference": 0.1562,
            "min_group_for_gap": 5,
        }},
    }


HEALTHY = slices({
    "big": {"n": 100, "n_positives": 40, "f1": 0.62, "accuracy": 0.77,
            "precision": 0.7, "recall": 0.58, "roc_auc": 0.83,
            "selection_rate": 0.3, "fpr": 0.12},
})


def by_id(report: dict) -> dict:
    return {c["id"]: c for c in report["checks"]}


# ── the happy path ────────────────────────────────────────────────────────────


def test_everything_passing_is_a_go():
    report = evaluate_gate(GOOD_METRICS, HEALTHY, BASELINE, ACCEPTANCE)
    assert report["verdict"] == "GO"
    assert report["summary"]["failed"] == 0
    assert report["criteria_version"] == "1.0.0"


def test_the_report_records_the_deltas_it_did_not_gate_on():
    """`also_report` metrics are informational — visible, but never a verdict."""
    metrics = dict(GOOD_METRICS, roc_auc=0.9000)
    report = evaluate_gate(metrics, HEALTHY, BASELINE, ACCEPTANCE)
    assert report["deltas"]["roc_auc"] == pytest.approx(0.0655)
    assert report["verdict"] == "GO"


# ── absolute floors ───────────────────────────────────────────────────────────


def test_a_metric_below_its_floor_is_a_no_go():
    report = evaluate_gate(dict(GOOD_METRICS, f1=0.40), HEALTHY, BASELINE, ACCEPTANCE)
    assert report["verdict"] == "NO-GO"
    assert by_id(report)["minimum.f1"]["status"] == "fail"
    assert "0.4000" in by_id(report)["minimum.f1"]["reason"]


def test_the_floor_is_inclusive():
    """`>=`, not `>`. Stated by a test so nobody has to guess from the code."""
    report = evaluate_gate(dict(GOOD_METRICS, f1=0.55), HEALTHY, BASELINE, ACCEPTANCE)
    assert by_id(report)["minimum.f1"]["status"] == "pass"


def test_a_metric_the_evaluate_stage_never_wrote_is_skipped_not_passed():
    metrics = {k: v for k, v in GOOD_METRICS.items() if k != "roc_auc"}
    report = evaluate_gate(metrics, HEALTHY, BASELINE, ACCEPTANCE)
    check = by_id(report)["minimum.roc_auc"]
    assert check["status"] == "skipped"
    assert report["summary"]["skipped"] >= 1


def test_the_all_negative_classifier_is_caught_by_f1_and_not_by_roc_auc():
    """A model that predicts "no diabetes" for everyone has ROC-AUC 0.8407, so only F1 and the floors catch it."""
    degenerate = {"accuracy": 0.6510, "precision": 0.0, "recall": 0.0,
                  "f1": 0.0, "roc_auc": 0.8407}

    roc_only = {"criteria_version": "bad", "minimum": {"roc_auc": 0.75}}
    assert evaluate_gate(degenerate, {}, {}, roc_only)["verdict"] == "GO"

    full = evaluate_gate(degenerate, HEALTHY, BASELINE, ACCEPTANCE)
    assert full["verdict"] == "NO-GO"
    failed = {c["id"] for c in full["checks"] if c["status"] == "fail"}
    assert {"minimum.accuracy", "minimum.f1", "regression.f1"} <= failed


# ── regression against the champion ───────────────────────────────────────────


def test_a_drop_past_the_tolerance_is_a_no_go():
    report = evaluate_gate(dict(GOOD_METRICS, f1=0.6087), HEALTHY, BASELINE, ACCEPTANCE)
    check = by_id(report)["regression.f1"]
    assert check["status"] == "fail"
    assert check["delta"] == pytest.approx(-0.0254)


def test_a_drop_inside_the_tolerance_is_not_a_regression():
    report = evaluate_gate(dict(GOOD_METRICS, f1=0.6300), HEALTHY, BASELINE, ACCEPTANCE)
    assert by_id(report)["regression.f1"]["status"] == "pass"
    assert by_id(report)["regression.f1"]["delta"] == pytest.approx(-0.0041)


def test_no_baseline_is_skipped_and_emphatically_not_passed():
    """"The first model is always fine" is how a ratchet starts at the bottom."""
    report = evaluate_gate(GOOD_METRICS, HEALTHY, {}, ACCEPTANCE)
    check = by_id(report)["regression.f1"]
    assert check["status"] == "skipped"
    assert "no baseline" in check["reason"]
    assert report["verdict"] == "GO"
    assert report["summary"]["skipped"] >= 1


def test_the_primary_metric_choice_flips_the_verdict_on_the_same_model():
    """With `C: 0.01` F1 falls 0.0254 and ROC-AUC rises 0.0100: the primary metric decides the verdict."""
    observed = dict(GOOD_METRICS, f1=0.6087, roc_auc=0.8445, accuracy=0.7656)

    on_f1 = evaluate_gate(observed, HEALTHY, BASELINE,
                          dict(ACCEPTANCE, minimum={}, slice_rules={}, fairness={}))
    on_auc = evaluate_gate(
        observed, HEALTHY, BASELINE,
        dict(ACCEPTANCE, minimum={}, slice_rules={}, fairness={},
             regression={"primary_metric": "roc_auc", "max_drop": 0.01}),
    )
    assert on_f1["verdict"] == "NO-GO"
    assert on_auc["verdict"] == "GO"


# ── slices ────────────────────────────────────────────────────────────────────


def test_a_slice_below_min_support_is_skipped_with_the_numbers_in_the_reason():
    thin = slices({"tiny": {"n": 19, "n_positives": 7, "f1": 0.50}})
    report = evaluate_gate(GOOD_METRICS, thin, BASELINE, ACCEPTANCE)
    check = by_id(report)["slice.grp.tiny"]
    assert check["status"] == "skipped"
    assert "19" in check["reason"] and "20" in check["reason"]


def test_a_slice_with_enough_rows_but_too_few_positives_is_also_skipped():
    """The second support rule, and the one this dataset forces on us."""
    degenerate = slices({"under_normal": {"n": 30, "n_positives": 1, "f1": 0.0}})
    report = evaluate_gate(GOOD_METRICS, degenerate, BASELINE, ACCEPTANCE)
    check = by_id(report)["slice.grp.under_normal"]
    assert check["status"] == "skipped"
    assert "positives 1" in check["reason"]
    assert report["verdict"] == "GO"  # an unmeasurable slice is not a failure


def test_dropping_min_positives_makes_that_same_slice_fail_for_a_meaningless_reason():
    """With `min_positives: 1` a slice with one positive is gated, and fails on an F1 computed from one patient."""
    degenerate = slices({"under_normal": {"n": 30, "n_positives": 1, "f1": 0.0}})
    loose = dict(ACCEPTANCE, slice_rules=dict(ACCEPTANCE["slice_rules"],
                                              min_positives=1))
    report = evaluate_gate(GOOD_METRICS, degenerate, BASELINE, loose)
    assert report["verdict"] == "NO-GO"
    assert by_id(report)["slice.grp.under_normal"]["status"] == "fail"


def test_a_gated_slice_below_the_floor_fails():
    weak = slices({"older": {"n": 40, "n_positives": 15, "f1": 0.30}})
    report = evaluate_gate(GOOD_METRICS, weak, BASELINE, ACCEPTANCE)
    assert report["verdict"] == "NO-GO"
    assert "0.3000" in by_id(report)["slice.grp.older"]["reason"]


def test_a_slice_far_below_the_aggregate_fails_even_above_the_floor():
    """The gap rule fails a slice that clears the F1 floor but is far below the aggregate F1."""
    lagging = slices({"older": {"n": 40, "n_positives": 15, "f1": 0.52}})
    report = evaluate_gate(GOOD_METRICS, lagging, BASELINE, ACCEPTANCE)
    check = by_id(report)["slice.grp.older"]
    assert check["status"] == "fail"
    assert check["gap_to_aggregate"] == pytest.approx(0.1141)
    assert "below the aggregate" in check["reason"]
    # It cleared the absolute floor. Only the gap rule caught it.
    assert check["f1"] > check["min_f1"]


def test_no_slice_report_is_one_visible_skip_not_silence():
    report = evaluate_gate(GOOD_METRICS, {}, BASELINE, ACCEPTANCE)
    check = by_id(report)["slice"]
    assert check["status"] == "skipped"
    assert "no slice report" in check["reason"]


# ── fairness ──────────────────────────────────────────────────────────────────


def test_a_gap_over_its_limit_is_a_no_go():
    unfair = slices(
        {"big": {"n": 100, "n_positives": 40, "f1": 0.62}},
        fairness={"selection_rate_gap": 0.05, "tpr_gap": 0.31,
                  "fpr_gap": 0.02, "equalized_odds_difference": 0.31},
    )
    report = evaluate_gate(GOOD_METRICS, unfair, BASELINE, ACCEPTANCE)
    assert report["verdict"] == "NO-GO"
    assert by_id(report)["fairness.grp.tpr_gap"]["status"] == "fail"
    assert by_id(report)["fairness.grp.selection_rate_gap"]["status"] == "pass"


def test_an_undefined_gap_is_skipped():
    single = slices(
        {"big": {"n": 100, "n_positives": 40, "f1": 0.62}},
        fairness={"selection_rate_gap": None, "tpr_gap": None,
                  "fpr_gap": None, "equalized_odds_difference": None},
    )
    report = evaluate_gate(GOOD_METRICS, single, BASELINE, ACCEPTANCE)
    assert by_id(report)["fairness.grp.tpr_gap"]["status"] == "skipped"


def test_each_gated_axis_has_its_own_limit():
    gap = {"groups": {}, "selection_rate_gap": 0.01, "tpr_gap": 0.22,
           "fpr_gap": 0.01, "equalized_odds_difference": 0.22, "min_group_for_gap": 5}
    two_axes = dict(HEALTHY, fairness={"grp": gap, "age": gap})
    acceptance = dict(ACCEPTANCE, fairness={"grp": {"max_tpr_gap": 0.20},
                                            "age": {"max_tpr_gap": 0.25}})
    report = evaluate_gate(GOOD_METRICS, two_axes, BASELINE, acceptance)
    assert by_id(report)["fairness.grp.tpr_gap"]["status"] == "fail"
    assert by_id(report)["fairness.age.tpr_gap"]["status"] == "pass"


def test_an_axis_that_was_never_measured_is_skipped_not_ignored():
    acceptance = dict(ACCEPTANCE, fairness={"sex": ACCEPTANCE["fairness"]["grp"]})
    report = evaluate_gate(GOOD_METRICS, HEALTHY, BASELINE, acceptance)
    check = by_id(report)["fairness.sex"]
    assert check["status"] == "skipped"
    assert "sex" in check["reason"]


# ── the report itself ─────────────────────────────────────────────────────────


def test_the_headline_names_the_skipped_count():
    """A guard whose failure mode is a green tick is worse than no guard."""
    report = evaluate_gate(GOOD_METRICS, {}, {}, ACCEPTANCE)
    headline = format_gate(report).splitlines()[0]
    assert "SKIPPED" in headline
    assert str(report["summary"]["skipped"]) in headline


def test_a_no_go_names_the_failing_checks_before_anything_else():
    report = evaluate_gate(dict(GOOD_METRICS, f1=0.10), HEALTHY, BASELINE, ACCEPTANCE)
    rendered = format_gate(report)
    assert rendered.index("FAILED:") < rendered.index("check ")
    assert "minimum.f1" in rendered


def test_the_verdict_is_a_pure_function_of_its_four_inputs():
    """Same inputs, same bytes. This is what makes the DVC output stable."""
    import json

    a = json.dumps(evaluate_gate(GOOD_METRICS, HEALTHY, BASELINE, ACCEPTANCE))
    b = json.dumps(evaluate_gate(GOOD_METRICS, HEALTHY, BASELINE, ACCEPTANCE))
    assert a == b
    assert "time" not in a.lower()  # no timestamp anywhere in the verdict
