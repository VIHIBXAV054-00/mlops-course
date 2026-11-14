"""The serving side of the contract — Exercise 6.

One schema guards both boundaries. These tests are the proof, and they need
neither a running model nor a running stack for the validation half: a rejected
payload never reaches the model, so `predict_one` can prove the rejection with no
model file present at all.
"""

from __future__ import annotations

import pytest

from week_08_prefect_flow import inference
from week_08_prefect_flow.data import FEATURE_COLUMNS

pytestmark = pytest.mark.data


def test_the_example_payload_is_legal():
    assert inference.validate_payload(inference.EXAMPLE_PAYLOAD)["passed"]


def test_a_sentinel_zero_is_rejected_at_serving_time():
    """The same lie the training data told, arriving as a request.

    A model cannot tell you its input was nonsense. It returns a probability
    computed from a physiologically impossible patient, and no metric anywhere
    will ever mention it.
    """
    report = inference.validate_payload(inference.ILLEGAL_PAYLOAD)
    assert not report["passed"]
    assert "greater_than(0)" in report["by_check"]
    assert set(report["by_column"]) == {"glucose", "insulin"}


def test_two_swapped_features_are_caught_by_a_range_bound():
    """And be honest about WHY this one is caught.

    `insulin` and `bmi` swapped is caught only because an insulin reading of 155
    is impossible in a column bounded at `bmi <= 100`. Swap two features with
    overlapping plausible ranges and no schema in this lab notices. A contract
    catches implausible values, not wrong ones.
    """
    report = inference.validate_payload(inference.SWAPPED_PAYLOAD)
    assert not report["passed"]
    assert list(report["by_column"]) == ["bmi"]
    assert "less_than_or_equal_to(100.0)" in report["by_check"]


def test_a_missing_feature_is_named():
    """Note the check name, and that it is NOT the same as the one below.

    `column_in_dataframe` — a column the contract declares is absent.
    `column_in_schema`    — a column the contract does not declare is present.

    Two opposite failures, two distinct names. Worth learning, because a report
    full of one of them means something completely different from the other.
    """
    report = inference.validate_payload(inference.INCOMPLETE_PAYLOAD)
    assert not report["passed"]
    assert "column_in_dataframe" in report["by_check"]


def test_an_undeclared_feature_is_rejected():
    payload = {**inference.EXAMPLE_PAYLOAD, "smoker": 1}
    report = inference.validate_payload(payload)
    assert not report["passed"]
    assert "column_in_schema" in report["by_check"]


def test_the_payload_frame_is_built_in_the_contract_order():
    """Ordering is imposed here rather than asserted by the schema.

    A JSON object has no column order, so `PredictionInput` deliberately does not
    set `ordered = True` — it would only be testing this function. `ModelInput`
    does set it, because a CSV's column order is the producer's choice.
    """
    frame = inference.payload_to_frame(
        {k: inference.EXAMPLE_PAYLOAD[k] for k in reversed(list(FEATURE_COLUMNS))}
    )
    assert list(frame.columns) == list(FEATURE_COLUMNS)


def test_a_rejected_payload_never_reaches_the_model(tmp_path):
    """The gate property, on the serving side.

    `model.pkl` does not exist in tmp_path. If validation ran after the model
    load, this would raise FileNotFoundError instead of returning a report.
    """
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
    """The end-to-end serving path, once `make repro` has produced a model.

    A fixture-style guard rather than a static skip, so this becomes a real test
    the moment the model exists.
    """
    model_path = settings.models_dir / "model.pkl"
    if not model_path.exists():
        pytest.skip("No model yet — run `make repro` first.")

    result = inference.predict_one(inference.EXAMPLE_PAYLOAD, model_path)
    assert result["report"]["passed"]
    assert result["prediction"] in (0, 1)
    assert 0.0 <= result["probability"] <= 1.0


def test_a_null_feature_is_accepted_and_imputed_by_the_model(settings):
    """The payoff of putting the imputer inside the Pipeline.

    A request that honestly reports "insulin was not measured" is legal, and the
    model fills it with the median it learned during training. Impute outside the
    Pipeline and this request either crashes or gets a different fill value than
    training used — which is training-serving skew, arriving as a 200 OK.
    """
    model_path = settings.models_dir / "model.pkl"
    if not model_path.exists():
        pytest.skip("No model yet — run `make repro` first.")

    payload = {**inference.EXAMPLE_PAYLOAD, "insulin": None}
    result = inference.predict_one(payload, model_path)
    assert result["report"]["passed"]
    assert result["prediction"] in (0, 1)
