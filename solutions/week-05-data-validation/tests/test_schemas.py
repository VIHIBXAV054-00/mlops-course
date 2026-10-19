"""The contracts, on small frames built in memory (Exercises 1 and 3)."""

import copy

import pandas as pd
import pandera.pandas as pa
import pytest

from week_05_data_validation.schemas import (
    MODEL_INPUT_COLUMNS,
    ModelInput,
    PredictionInput,
    RawMeasurements,
)
from week_05_data_validation.validation import to_nullable, validate_frame

# One legal row, as text, the way read_raw hands it over.
LEGAL_ROW = {
    "measurement_date": "2024-01-01",
    "pregnancies": "6",
    "glucose": "148",
    "blood_pressure": "72",
    "skin_thickness": "35",
    "insulin": "155",
    "bmi": "33.6",
    "diabetes_pedigree": "0.627",
    "age": "50",
    "outcome": "1",
}


def raw_frame(**overrides) -> pd.DataFrame:
    """A two-row legal frame, with named cells overridden in the first row."""
    first = {**LEGAL_ROW, **{k: str(v) for k, v in overrides.items()}}
    second = {**LEGAL_ROW, "measurement_date": "2024-01-02", "age": "44"}
    return pd.DataFrame([first, second])


def model_frame(**overrides) -> pd.DataFrame:
    return raw_frame(**overrides)[MODEL_INPUT_COLUMNS]


# ── RawMeasurements (Exercise 1) ─────────────────────────────────────────────


def test_a_legal_batch_passes() -> None:
    assert validate_frame(raw_frame(), RawMeasurements)["passed"]


def test_the_ingestion_contract_allows_sentinel_zeros() -> None:
    report = validate_frame(raw_frame(glucose=0, insulin=0, bmi=0), RawMeasurements)
    assert report["passed"], (
        f"A zero in a sentinel column fails RawMeasurements: {report['by_check']}. "
        "The clinic sends these zeros in every batch."
    )


@pytest.mark.parametrize(
    "overrides, expected_check",
    [
        ({"insulin": -1}, "greater_than_or_equal_to(0)"),
        ({"age": 250}, "less_than_or_equal_to(120)"),
        ({"outcome": 2}, "isin([0, 1])"),
        ({"bmi": 280.0}, "less_than_or_equal_to(100.0)"),
        ({"diabetes_pedigree": 0}, "greater_than(0)"),
        ({"measurement_date": "2024-13-45"}, "coerce_dtype('datetime64[ns]')"),
    ],
)
def test_the_ingestion_contract_rejects_a_bad_value(overrides, expected_check) -> None:
    report = validate_frame(raw_frame(**overrides), RawMeasurements)
    assert expected_check in report["by_check"], (
        f"{overrides} should fail {expected_check}; the report has {report['by_check']}."
    )


def test_the_ingestion_contract_rejects_a_missing_value() -> None:
    frame = raw_frame()
    frame.loc[0, "blood_pressure"] = None
    assert "not_nullable" in validate_frame(frame, RawMeasurements)["by_check"]


def test_the_ingestion_contract_rejects_an_extra_column() -> None:
    frame = raw_frame()
    frame["notes"] = "imported from lab system v2"
    assert "column_in_schema" in validate_frame(frame, RawMeasurements)["by_check"]


def test_the_ingestion_contract_rejects_a_duplicated_row() -> None:
    frame = pd.concat([raw_frame(), raw_frame().head(1)], ignore_index=True)
    assert "no_duplicate_rows" in validate_frame(frame, RawMeasurements)["by_check"]


def test_validate_frame_collects_every_failure() -> None:
    """Lazy mode reports all three faults; the default stops at the first."""
    frame = raw_frame(age=250, outcome=2, insulin=-1)
    assert validate_frame(frame, RawMeasurements)["n_failure_cases"] == 3
    with pytest.raises(pa.errors.SchemaError):
        RawMeasurements.validate(frame)


def test_to_schema_returns_one_shared_object() -> None:
    """Changing `to_schema()` changes it everywhere; copy it before you change it."""
    assert RawMeasurements.to_schema() is RawMeasurements.to_schema()
    variant = copy.deepcopy(RawMeasurements.to_schema())
    variant.strict = False
    assert RawMeasurements.to_schema().strict is True


# ── ModelInput and PredictionInput (Exercise 3) ──────────────────────────────


def test_model_input_has_the_model_columns_in_order() -> None:
    assert list(ModelInput.to_schema().columns) == MODEL_INPUT_COLUMNS, (
        "Declare the ModelInput columns in the order of FEATURE_COLUMNS, then outcome."
    )


def test_model_input_rejects_a_sentinel_zero() -> None:
    report = validate_frame(model_frame(glucose=0), ModelInput)
    assert report["by_check"] == {"greater_than(0)": 1}


def test_model_input_accepts_a_missing_sentinel_value() -> None:
    frame = to_nullable(model_frame(glucose=0))
    report = validate_frame(frame, ModelInput)
    assert report["passed"], f"A missing glucose fails ModelInput: {report['by_check']}"


def test_model_input_rejects_columns_in_another_order() -> None:
    frame = to_nullable(model_frame())
    reordered = frame[["glucose", "pregnancies"] + MODEL_INPUT_COLUMNS[2:]]
    assert "column_ordered" in validate_frame(reordered, ModelInput)["by_check"]


def test_model_input_rejects_the_date_column() -> None:
    frame = to_nullable(raw_frame())
    assert "column_in_schema" in validate_frame(frame, ModelInput)["by_check"]


def test_prediction_input_is_model_input_without_the_label() -> None:
    features = to_nullable(model_frame()).drop(columns=["outcome"])
    assert validate_frame(features, PredictionInput)["passed"]
    assert not validate_frame(features, ModelInput)["passed"]

    features["glucose"] = 0.0
    assert "greater_than(0)" in validate_frame(features, PredictionInput)["by_check"]
