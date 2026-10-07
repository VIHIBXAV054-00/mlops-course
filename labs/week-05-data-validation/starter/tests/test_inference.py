"""One request through PredictionInput and the model (Exercises 3 and 6)."""

import pytest

from week_05_data_validation import inference
from week_05_data_validation.data import FEATURE_COLUMNS


def test_the_payload_frame_has_the_model_column_order() -> None:
    reordered = {k: inference.EXAMPLE_PAYLOAD[k] for k in reversed(FEATURE_COLUMNS)}
    assert list(inference.payload_to_frame(reordered).columns) == FEATURE_COLUMNS


def test_load_payload_accepts_a_json_string_or_a_file(tmp_path) -> None:
    assert inference.load_payload('{"glucose": 148}') == {"glucose": 148}
    path = tmp_path / "payload.json"
    path.write_text('{"glucose": 148}')
    assert inference.load_payload(str(path)) == {"glucose": 148}


# ── The serving contract (Exercise 3) ────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_the_example_request_is_legal() -> None:
    assert inference.validate_payload(inference.EXAMPLE_PAYLOAD)["passed"]


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
@pytest.mark.parametrize(
    "name, check",
    [
        ("illegal", "greater_than(0)"),
        ("swapped", "less_than_or_equal_to(100.0)"),
        ("incomplete", "column_in_dataframe"),
    ],
)
def test_each_bad_request_fails_its_check(name, check) -> None:
    report = inference.validate_payload(inference.PAYLOADS[name])
    assert check in report["by_check"], (
        f"The {name} request should fail {check}; the report has {report['by_check']}."
    )


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_an_extra_field_is_rejected() -> None:
    report = inference.validate_payload({**inference.EXAMPLE_PAYLOAD, "smoker": 1})
    assert "column_in_schema" in report["by_check"]


# ── predict_one (Exercise 6) ─────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 6 (optional) — check the request in predict_one, then delete this skip marker.")
@pytest.mark.parametrize("name", ["illegal", "swapped", "incomplete"])
def test_a_rejected_request_never_reaches_the_model(name, tmp_path) -> None:
    """There is no model file in tmp_path: loading one would raise FileNotFoundError."""
    result = inference.predict_one(inference.PAYLOADS[name], tmp_path / "model.pkl")
    assert result["report"], "predict_one should return the PredictionInput report."
    assert result["report"]["passed"] is False
    assert result["prediction"] is None


def test_a_legal_request_needs_a_model(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="make repro"):
        inference.predict_one(inference.EXAMPLE_PAYLOAD, tmp_path / "model.pkl")


@pytest.mark.skip(reason="Exercise 6 (optional) — check the request in predict_one, then delete this skip marker.")
def test_a_missing_value_is_filled_by_the_trained_model(settings) -> None:
    """A request with insulin = None is legal, and the model's imputer fills it."""
    model_path = settings.models_dir / "model.pkl"
    if not model_path.exists():
        pytest.skip("No model yet — run `make repro` first.")
    result = inference.predict_one({**inference.EXAMPLE_PAYLOAD, "insulin": None}, model_path)
    assert result["report"]["passed"]
    assert result["prediction"] in (0, 1)
