"""A request is validated with the same contract as the training data, before the model is called."""

from __future__ import annotations

import pytest

from week_07_ci_workflow import inference
from week_07_ci_workflow.data import FEATURE_COLUMNS

# TODO(student) Exercise 3: mark this module's layer with `pytestmark`:
# unit, data, eval or integration.


def test_the_example_payload_is_legal():
    assert inference.validate_payload(inference.EXAMPLE_PAYLOAD)["passed"]


def test_a_sentinel_zero_is_rejected_at_serving_time():
    """A sentinel zero in a request is rejected."""
    report = inference.validate_payload(inference.ILLEGAL_PAYLOAD)
    assert not report["passed"]
    assert "greater_than(0)" in report["by_check"]
    assert set(report["by_column"]) == {"glucose", "insulin"}


def test_two_swapped_features_are_caught_by_a_range_bound():
    """Swapped `insulin` and `bmi` are caught only because 155 is above the `bmi` bound of 100."""
    report = inference.validate_payload(inference.SWAPPED_PAYLOAD)
    assert not report["passed"]
    assert list(report["by_column"]) == ["bmi"]
    assert "less_than_or_equal_to(100.0)" in report["by_check"]


def test_a_missing_feature_is_named():
    """A missing column fails `column_in_dataframe`; an extra column fails `column_in_schema`."""
    report = inference.validate_payload(inference.INCOMPLETE_PAYLOAD)
    assert not report["passed"]
    assert "column_in_dataframe" in report["by_check"]


def test_an_undeclared_feature_is_rejected():
    payload = {**inference.EXAMPLE_PAYLOAD, "smoker": 1}
    report = inference.validate_payload(payload)
    assert not report["passed"]
    assert "column_in_schema" in report["by_check"]


def test_the_payload_frame_is_built_in_the_contract_order():
    """`payload_to_frame` puts the columns in the model's order; `PredictionInput` does not assert an order."""
    frame = inference.payload_to_frame(
        {k: inference.EXAMPLE_PAYLOAD[k] for k in reversed(list(FEATURE_COLUMNS))}
    )
    assert list(frame.columns) == list(FEATURE_COLUMNS)


def test_a_rejected_payload_never_reaches_the_model(tmp_path):
    """A rejected payload returns a report with no model file present."""
    result = inference.predict_one(
        inference.ILLEGAL_PAYLOAD, tmp_path / "model.pkl"
    )
    assert not result["report"]["passed"]
    assert result["prediction"] is None


def test_a_legal_payload_needs_a_model(tmp_path):
    with pytest.raises(FileNotFoundError, match="make repro"):
        inference.predict_one(inference.EXAMPLE_PAYLOAD, tmp_path / "model.pkl")


def test_load_payload_accepts_a_json_string():
    assert inference.load_payload('{"glucose": 148}') == {"glucose": 148}


def test_load_payload_accepts_a_file(tmp_path):
    path = tmp_path / "payload.json"
    path.write_text('{"glucose": 148}')
    assert inference.load_payload(str(path)) == {"glucose": 148}


def test_prediction_against_the_trained_model(settings):
    """The full serving path with the trained model; skipped until `make repro` has produced it."""
    model_path = settings.models_dir / "model.pkl"
    if not model_path.exists():
        pytest.skip("No model yet — run `make repro` first.")

    result = inference.predict_one(inference.EXAMPLE_PAYLOAD, model_path)
    assert result["report"]["passed"]
    assert result["prediction"] in (0, 1)
    assert 0.0 <= result["probability"] <= 1.0


def test_a_null_feature_is_accepted_and_imputed_by_the_model(settings):
    """A null feature is accepted and filled by the imputer inside the model."""
    model_path = settings.models_dir / "model.pkl"
    if not model_path.exists():
        pytest.skip("No model yet — run `make repro` first.")

    payload = {**inference.EXAMPLE_PAYLOAD, "insulin": None}
    result = inference.predict_one(payload, model_path)
    assert result["report"]["passed"]
    assert result["prediction"] in (0, 1)
