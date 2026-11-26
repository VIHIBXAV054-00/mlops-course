"""The drift policy: parsing drift.yaml, validating it, and the verdict.

Evidently computes the statistics. `drift.yaml` and `drift_policy.py` decide what they mean.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from week_12_drift_monitoring.data import FEATURE_COLUMNS
from week_12_drift_monitoring.drift_policy import (
    DRIFT,
    DRIFT_WITH_DEGRADATION,
    INSUFFICIENT,
    METHODS,
    NO_DRIFT,
    VERDICTS,
    DriftStatistics,
    FeaturePolicy,
    contract_admissible,
    evaluate,
    load_policy,
)

pytestmark = pytest.mark.unit

LAB = Path(__file__).resolve().parents[1]
POLICY_PATH = LAB / "drift.yaml"


@pytest.fixture(scope="module")
def policy():
    return load_policy(POLICY_PATH)


def _stats(**values):
    return DriftStatistics(values=dict(values), methods={k: "psi" for k in values})


# ── The declaration ──────────────────────────────────────────────────────────


def test_the_reference_is_pinned_to_the_dataset_the_champion_was_trained_on():
    """The md5 in drift.yaml matches DVC's pointer, so the reference window is a fixed dataset."""
    pointer = LAB / "data/measurements.csv.dvc"
    declared = load_policy(POLICY_PATH).reference_md5
    recorded = yaml.safe_load(pointer.read_text())["outs"][0]["md5"]
    assert declared == recorded, (
        f"drift.yaml pins the reference to dataset md5 {declared}, but "
        f"data/measurements.csv.dvc records {recorded}: update drift.yaml after "
        f"rebuilding the dataset."
    )


def test_every_watched_feature_is_a_feature_the_model_actually_reads(policy):
    """Watching a column the model ignores produces a signal with no consequence."""
    for feature in policy.features:
        assert feature.column in FEATURE_COLUMNS


def test_every_method_is_one_the_code_implements_and_knows_the_direction_of(policy):
    """A p-value drifts below its threshold, a distance above. The wrong sign inverts the monitor."""
    for feature in policy.features:
        assert feature.method in METHODS
        assert isinstance(feature.smaller_is_drift, bool)
    assert METHODS["ks"]["smaller_is_drift"] is True
    assert METHODS["psi"]["smaller_is_drift"] is False


def test_the_method_and_threshold_are_written_out_for_every_feature():
    """Evidently's default test depends on the reference size, so drift.yaml states both.

    Reads the raw YAML, because the parser has defaults.
    """
    raw = yaml.safe_load(POLICY_PATH.read_text())
    for spec in raw["features"]:
        assert "method" in spec, f"{spec.get('column')} inherits its method"
        assert "threshold" in spec, f"{spec.get('column')} inherits its threshold"


def test_at_least_one_feature_is_gated(policy):
    """At least one feature decides the verdict."""
    assert policy.gated
    assert all(f.gated for f in policy.gated)


def test_min_samples_is_positive_and_the_window_can_reach_it(policy):
    assert policy.min_samples > 0
    assert policy.window_rows >= policy.min_samples


def test_every_verdict_has_a_written_action(policy):
    for verdict in VERDICTS:
        action = policy.actions[verdict.lower()]
        assert action["severity"] in {"none", "ticket", "page"}
        assert action["action"].strip(), (
            f"{verdict} has a severity and no action: write what the on-call person does."
        )


def test_every_placeholder_is_replaced():
    """Every `<fill in>` in drift.yaml has a value."""
    left: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif node is None or (isinstance(node, str) and node.strip() == "<fill in>"):
            left.append(path)

    walk(yaml.safe_load(POLICY_PATH.read_text()), "")
    assert not left, f"drift.yaml: fill in {', '.join(left)}"


def test_drift_alone_never_pages(policy):
    """Drift alone is a ticket: nobody can fix a changed population at 3 a.m."""
    assert policy.severity_for(DRIFT) == "ticket"
    assert policy.severity_for(NO_DRIFT) == "none"
    assert policy.severity_for(INSUFFICIENT) == "none"
    # Paging needs degradation, which needs labels for the drifted window.
    assert policy.severity_for(DRIFT_WITH_DEGRADATION) == "page"


def test_the_loader_refuses_a_policy_that_pages_on_drift_alone(tmp_path):
    """The loader rejects a policy that pages on drift alone."""
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["actions"]["drift"]["severity"] = "page"
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="does not page"):
        load_policy(path)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda raw: raw.__setitem__("service", ""), "service"),
        (lambda raw: raw["reference"].__setitem__("dataset_md5", ""), "dataset_md5"),
        (lambda raw: raw["current"].__setitem__("min_samples", 0), "min_samples"),
        (lambda raw: raw["current"].__setitem__("window_rows", 10), "smaller than"),
        (lambda raw: raw["features"][0].__setitem__("method", "vibes"), "method"),
        (lambda raw: raw["features"][0].pop("threshold"), "threshold"),
        (lambda raw: raw["features"].__setitem__(1, dict(raw["features"][0])), "twice"),
        (lambda raw: raw["features"][0].__setitem__("column", "not_a_feature"), "not a model feature"),
        (lambda raw: raw.__setitem__("features", []), "no features"),
        (lambda raw: raw["proxy"].__setitem__("reference_positive_rate", 1.5), "between 0 and 1"),
        (lambda raw: raw.pop("staleness"), "max_age"),
        (lambda raw: raw["actions"].pop("insufficient"), "actions.insufficient"),
        (lambda raw: raw["degradation"].__setitem__("min_drop", 0), "min_drop"),
    ],
)
def test_a_malformed_policy_fails_at_load_time_with_a_sentence_you_can_act_on(
    tmp_path, mutate, message
):
    """A malformed threshold must fail at load time, not fall back to a silent default."""
    raw = yaml.safe_load(POLICY_PATH.read_text())
    mutate(raw)
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=message):
        load_policy(path)


def test_a_gated_feature_with_no_declared_method_is_refused(tmp_path):
    """A feature without a method is refused."""
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["features"][0].pop("method")
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="must be one of"):
        load_policy(path)


# ── The verdict ──────────────────────────────────────────────────────────────


def test_too_few_rows_is_INSUFFICIENT_and_not_NO_DRIFT(policy):
    """NO_DRIFT means "we looked". INSUFFICIENT means "we could not look"."""
    report = evaluate(
        policy,
        _stats(glucose=0.9, **{f.column: 0.0 for f in policy.features if f.column != "glucose"}),
        n_current=policy.min_samples - 1,
        n_reference=288,
    )
    assert report["verdict"] == INSUFFICIENT
    assert report["severity"] == "none"
    # Glucose is far past its threshold, but there are too few rows to decide.
    reason = " ".join(report["reasons"])
    assert str(policy.min_samples) in reason
    assert "NOT a clean bill of health" in reason
    # The statistics stay in the report.
    assert report["features"]
    assert any(row["column"] == "glucose" for row in report["features"])


def test_a_gated_feature_over_its_threshold_is_DRIFT(policy):
    values = {f.column: 0.0 for f in policy.features}
    values["glucose"] = 0.30
    report = evaluate(policy, _stats(**values), n_current=720, n_reference=288)
    assert report["verdict"] == DRIFT
    assert report["severity"] == "ticket"
    assert report["drifted_gated_count"] == 1


def test_report_only_features_can_never_produce_a_verdict(policy):
    """Report-only features are shown in the report but never decide the verdict."""
    values = {f.column: 0.99 for f in policy.features if not f.gated}
    values["glucose"] = 0.0
    report = evaluate(policy, _stats(**values), n_current=720, n_reference=288)
    assert report["verdict"] == NO_DRIFT
    assert report["drifted_count"] == len([f for f in policy.features if not f.gated])
    assert report["drifted_gated_count"] == 0
    # The reasons still mention them.
    assert any("report-only" in reason for reason in report["reasons"])


def test_degradation_upgrades_DRIFT_to_a_page(policy):
    values = {f.column: 0.0 for f in policy.features}
    values["glucose"] = 0.30
    report = evaluate(
        policy,
        _stats(**values),
        n_current=720,
        n_reference=288,
        degradation={"degraded": True, "summary": "roc_auc 0.8761 -> 0.8050"},
    )
    assert report["verdict"] == DRIFT_WITH_DEGRADATION
    assert report["severity"] == "page"
    assert "roll back" in report["action"].lower()


def test_degradation_without_gated_drift_is_still_NO_DRIFT(policy):
    """A known limit: `evaluate` sees only input statistics, so it cannot detect concept drift."""
    values = {f.column: 0.0 for f in policy.features}
    report = evaluate(
        policy,
        _stats(**values),
        n_current=720,
        n_reference=288,
        degradation={"degraded": True, "summary": "roc_auc fell and nothing moved"},
    )
    assert report["verdict"] == NO_DRIFT


def test_a_missing_statistic_is_an_absence_and_not_a_drift(policy):
    """A missing statistic is not a drift."""
    feature = FeaturePolicy(column="glucose", method="psi", threshold=0.22, gated=True)
    assert feature.drifted(None) is False
    assert feature.drifted(0.21) is False
    assert feature.drifted(0.23) is True


def test_a_p_value_method_drifts_downward():
    """A p-value drifts when it falls below the threshold."""
    feature = FeaturePolicy(column="glucose", method="ks", threshold=0.05, gated=True)
    assert feature.drifted(0.04) is True
    assert feature.drifted(0.06) is False


def test_the_share_is_reported_and_never_used_as_the_verdict(policy):
    """Evidently's dataset-level answer is a vote over columns. A gated feature decides instead."""
    values = {f.column: 0.0 for f in policy.features}
    values["glucose"] = 0.30
    stats = DriftStatistics(values=values, methods={}, share=0.125, share_count=1.0)
    report = evaluate(policy, stats, n_current=720, n_reference=288)
    assert report["evidently_share"] == 0.125
    assert report["verdict"] == DRIFT


# ── The admissibility filter ─────────────────────────────────────────────────


def test_the_reference_is_filtered_the_way_the_current_window_is_collected(
    reference_root,
):
    """The API never scores a row with a sentinel zero, so the reference drops those rows too."""
    train = pd.read_csv(reference_root / "data/processed/train.csv")
    admissible = contract_admissible(train)
    assert len(admissible) < len(train)
    # No sentinel zero survives, in any sentinel column.
    for column in ("glucose", "blood_pressure", "skin_thickness", "insulin", "bmi"):
        assert (admissible[column] != 0).all()
    # A zero in `pregnancies` is a real zero.
    assert (admissible["pregnancies"] == 0).any(), (
        "the filter dropped rows for `pregnancies == 0`: filter only SENTINEL_COLUMNS."
    )


def test_the_filter_does_not_move_the_axis_it_is_supposed_to_measure():
    """The filter drops about half of each batch but keeps the glucose gap between them."""
    b1 = pd.read_csv(LAB / "data/raw/batch_01_baseline.csv")
    b2 = pd.read_csv(LAB / "data/raw/batch_02_new_arrival.csv")
    gap_before = b2["glucose"].mean() - b1["glucose"].mean()
    gap_after = (
        contract_admissible(b2)["glucose"].mean() - contract_admissible(b1)["glucose"].mean()
    )
    assert gap_before > 20
    assert gap_after > 20
    assert abs(gap_after - gap_before) < 3


def test_a_frame_with_no_sentinel_columns_passes_through_unchanged():
    """A frame without sentinel columns is returned unchanged."""
    frame = pd.DataFrame({"a": [0, 1, 2]})
    assert contract_admissible(frame).equals(frame)


# ── The policy and the rules cannot drift apart ──────────────────────────────


def test_the_alerting_rules_derive_their_thresholds_from_this_file(policy):
    """The thresholds are written twice, in drift.yaml and the alert rules, and this test keeps them equal."""
    from week_12_drift_monitoring.slo import parse_duration

    rules = yaml.safe_load((LAB / "prometheus/rules/drift.yml").read_text())
    expressions = {
        rule["alert"]: rule["expr"]
        for group in rules["groups"]
        for rule in group["rules"]
        if "alert" in rule
    }

    # staleness.max_age, in seconds
    max_age = int(parse_duration(policy.staleness_max_age))
    assert str(max_age) in expressions["DriftReportStale"], (
        f"DriftReportStale does not use drift.yaml's staleness.max_age "
        f"({policy.staleness_max_age} = {max_age}s). Its expression is "
        f"{expressions['DriftReportStale']!r}."
    )
    assert str(max_age) in expressions["DriftWindowStale"]

    # proxy.max_deviation, as written
    assert f"{policy.proxy_max_deviation:.2f}" in expressions["PredictionMixShift"]
