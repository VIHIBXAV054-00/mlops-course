"""The drift statistics, the reference window and the degradation check.

Real Evidently calls on the two batches committed under `data/raw/`, with no services.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from week_12_drift_monitoring.drift import (
    compute_statistics,
    load_reference,
    measure_degradation,
    read_report,
    write_report,
)
from week_12_drift_monitoring.drift_policy import (
    FeaturePolicy,
    contract_admissible,
    load_policy,
)

pytestmark = pytest.mark.data

LAB = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def policy():
    return load_policy(LAB / "drift.yaml")


@pytest.fixture(scope="module")
def reference(policy, reference_root):
    return load_reference(policy, reference_root)


@pytest.fixture(scope="module")
def cohorts():
    return {
        "reference": contract_admissible(pd.read_csv(LAB / "data/raw/batch_01_baseline.csv")),
        "drifted": contract_admissible(pd.read_csv(LAB / "data/raw/batch_02_new_arrival.csv")),
    }


def test_the_unfiltered_reference_keeps_rows_the_api_rejects(policy, reference_root, reference):
    unfiltered = load_reference(policy, reference_root, filtered=False)
    assert len(unfiltered) > len(reference)
    assert (unfiltered["skin_thickness"] == 0).any()
    assert not (reference["skin_thickness"] == 0).any()


def _one_feature(policy, column="glucose", method="psi", threshold=0.22):
    return replace(
        policy,
        features=(FeaturePolicy(column=column, method=method, threshold=threshold, gated=True),),
    )


# ── The argument-order trap ──────────────────────────────────────────────────


def test_psi_is_symmetric_so_a_swapped_argument_order_is_invisible(
    policy, reference, cohorts
):
    """`Report.run()` takes (current, reference), and psi gives the same number either way.

    So psi cannot show a swapped order. The next test checks the order.
    """
    psi = _one_feature(policy, method="psi")
    forward = compute_statistics(reference, cohorts["drifted"], psi).values["glucose"]
    backward = compute_statistics(cohorts["drifted"], reference, psi).values["glucose"]
    assert forward == pytest.approx(backward, abs=1e-9)


def test_run_takes_current_first_and_reference_second(policy):
    """Normed Wasserstein divides by the reference's standard deviation, so it shows the order.

    Two synthetic normal distributions with the same mean and standard deviations 2 and 40.
    """
    import numpy as np

    rng = np.random.default_rng(0)
    narrow = pd.DataFrame({"glucose": rng.normal(120, 2, 600)})
    wide = pd.DataFrame({"glucose": rng.normal(120, 40, 600)})
    wasserstein = _one_feature(policy, method="wasserstein", threshold=0.1)

    # The wrapper takes (reference, current). A narrow reference gives a large distance.
    with_narrow_reference = compute_statistics(narrow, wide, wasserstein).values["glucose"]
    with_wide_reference = compute_statistics(wide, narrow, wasserstein).values["glucose"]

    assert with_narrow_reference > 10 * with_wide_reference, (
        f"expected an order of magnitude between {with_narrow_reference:.4f} and "
        f"{with_wide_reference:.4f}: check the argument order you pass to Report.run()"
    )


def test_a_window_compared_against_itself_has_no_drift(policy, reference):
    """A window compared with itself scores 0."""
    single = _one_feature(policy)
    value = compute_statistics(reference, reference, single).values["glucose"]
    assert value == pytest.approx(0.0, abs=1e-9)


# ── The statistics themselves ────────────────────────────────────────────────


def test_the_drifted_cohort_drifts_and_the_known_good_one_does_not(policy, reference, cohorts):
    """The threshold in drift.yaml lies between the known-good and the drifted cohort."""
    gated = next(f for f in policy.features if f.gated)
    known_good = compute_statistics(reference, cohorts["reference"], policy).values[gated.column]
    drifted = compute_statistics(reference, cohorts["drifted"], policy).values[gated.column]
    assert not gated.drifted(known_good), (
        f"the known-good cohort scored {known_good:.4f} against a threshold of "
        f"{gated.threshold}: the threshold is below the noise and will raise false alarms."
    )
    assert gated.drifted(drifted), (
        f"the genuinely drifted cohort scored {drifted:.4f} against a threshold of "
        f"{gated.threshold} and was not detected."
    )
    assert drifted > known_good


def test_a_p_value_moves_with_sample_size_and_an_effect_size_does_not(
    policy, reference, cohorts
):
    """Four copies of the same data: the K-S p-value falls, psi stays.

    A drift rule built on a p-value alerts on traffic volume.
    """
    small = cohorts["drifted"].sample(150, replace=True, random_state=7)
    large = pd.concat([small] * 4, ignore_index=True)

    ks = _one_feature(policy, method="ks", threshold=0.05)
    psi = _one_feature(policy, method="psi", threshold=0.22)

    ks_small = compute_statistics(reference, small, ks).values["glucose"]
    ks_large = compute_statistics(reference, large, ks).values["glucose"]
    psi_small = compute_statistics(reference, small, psi).values["glucose"]
    psi_large = compute_statistics(reference, large, psi).values["glucose"]

    assert ks_large < ks_small, (
        "the K-S p-value should fall when the sample is quadrupled with copies of itself"
    )
    assert psi_large == pytest.approx(psi_small, abs=0.02), (
        f"psi moved from {psi_small:.4f} to {psi_large:.4f} on replicated data: "
        f"an effect size should not depend on n"
    )


def test_every_declared_feature_gets_a_statistic(policy, reference, cohorts):
    stats = compute_statistics(reference, cohorts["drifted"], policy)
    assert set(stats.values) == set(policy.columns)
    assert all(value is not None for value in stats.values.values())


def test_the_method_actually_used_is_recorded_next_to_the_one_we_asked_for(
    policy, reference, cohorts
):
    """The library picks a method unless you set one, so the report records the one used."""
    stats = compute_statistics(reference, cohorts["drifted"], policy)
    for feature in policy.features:
        assert stats.methods[feature.column] == feature.method


def test_the_preset_share_is_captured_and_is_a_fraction(policy, reference, cohorts):
    """The preset's share of drifted columns is reported, never used for the verdict."""
    stats = compute_statistics(reference, cohorts["drifted"], policy)
    assert stats.share is not None
    assert 0.0 <= stats.share <= 1.0
    assert stats.share_count is not None


def test_a_feature_missing_from_the_current_window_is_an_error(policy, reference, cohorts):
    """A monitor that silently skips a column would report NO_DRIFT for it forever."""
    truncated = cohorts["drifted"].drop(columns=["glucose"])
    with pytest.raises(KeyError):
        compute_statistics(reference, truncated, policy)


# ── The reference window ─────────────────────────────────────────────────────


def test_the_reference_is_filtered_and_says_so(policy, reference):
    """The CLI prints these attrs, so the output shows how many rows the filter removed."""
    assert reference.attrs["reference_rows_raw"] == 576
    assert reference.attrs["reference_rows_admissible"] == len(reference)
    assert len(reference) < reference.attrs["reference_rows_raw"]


def test_an_unfiltered_reference_manufactures_the_largest_signal_in_the_report(
    policy, reference, cohorts, reference_root
):
    """With sentinel zeros left in the reference, unchanged `skin_thickness` outscores `glucose`.

    Build the reference window the way the current window is collected.
    """
    unfiltered = pd.read_csv(reference_root / "data/processed/train.csv")
    watched = _one_feature(policy, column="skin_thickness", method="psi", threshold=0.2)
    glucose = _one_feature(policy, column="glucose", method="psi", threshold=0.22)

    bad_skin = compute_statistics(unfiltered, cohorts["reference"], watched).values[
        "skin_thickness"
    ]
    good_skin = compute_statistics(reference, cohorts["reference"], watched).values[
        "skin_thickness"
    ]
    real_signal = compute_statistics(reference, cohorts["drifted"], glucose).values["glucose"]

    assert bad_skin > real_signal, (
        "the unfiltered reference should give skin_thickness a larger psi than the "
        "real glucose drift"
    )
    assert good_skin < bad_skin / 2, (
        "filtering both windows the same way should remove most of the skin_thickness signal"
    )


# ── Does the drift matter? ───────────────────────────────────────────────────


def test_f1_and_roc_auc_disagree_about_the_drifted_cohort(policy, reference, cohorts):
    """On the drifted cohort F1 rises (more positives) while ROC-AUC falls.

    F1 depends on prevalence, ROC-AUC does not.
    """
    model = LAB / "models/model.pkl"
    if not model.exists():
        pytest.skip("models/model.pkl is absent — run `make repro`")

    result = measure_degradation(
        model, reference, cohorts["drifted"], primary_metric="roc_auc", min_drop=0.03
    )
    before, after = result["reference"], result["current"]

    assert after["f1"] > before["f1"], (
        "F1 should rise on the drifted cohort, which has more positives"
    )
    assert after["roc_auc"] < before["roc_auc"]
    assert result["degraded"] is True, (
        "with roc_auc as the primary metric this window should be degraded"
    )


def test_f1_as_the_primary_metric_gets_the_known_good_cohort_backwards(
    policy, reference, cohorts
):
    """On the known-good cohort F1 falls, so an F1-based check raises a false alarm."""
    model = LAB / "models/model.pkl"
    if not model.exists():
        pytest.skip("models/model.pkl is absent — run `make repro`")

    on_f1 = measure_degradation(
        model, reference, cohorts["reference"], primary_metric="f1", min_drop=0.03
    )
    on_auc = measure_degradation(
        model, reference, cohorts["reference"], primary_metric="roc_auc", min_drop=0.03
    )
    assert on_f1["degraded"] is True, "F1 was supposed to produce a FALSE alarm here"
    assert on_auc["degraded"] is False, "roc_auc was supposed to get this one right"


def test_degradation_refuses_a_window_with_no_labels(policy, reference, cohorts):
    """In production a monitor gets inputs but no outcomes, so the error names the labels."""
    model = LAB / "models/model.pkl"
    if not model.exists():
        pytest.skip("models/model.pkl is absent — run `make repro`")
    unlabelled = cohorts["drifted"].drop(columns=["outcome"])
    with pytest.raises(KeyError, match="labels"):
        measure_degradation(model, reference, unlabelled)


# ── The report as an artifact ────────────────────────────────────────────────


def test_a_report_round_trips_through_disk(tmp_path, policy, reference, cohorts):
    from week_12_drift_monitoring.drift import build_report

    report = build_report(policy, reference, cohorts["drifted"], now=1_700_000_000.0)
    path = write_report(report, tmp_path / "drift.json")
    again = read_report(path)
    assert again["verdict"] == report["verdict"]
    assert again["computed_at"] == 1_700_000_000.0
    # The report records which reference it compared against.
    assert again["reference"]["dataset_md5"] == policy.reference_md5
    assert again["proxy"]["reference_positive_rate"] == policy.proxy_reference_rate


def test_read_report_names_the_command_that_produces_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="make drift-report"):
        read_report(tmp_path / "nope.json")
