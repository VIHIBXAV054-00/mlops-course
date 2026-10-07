"""The validation report, the broken batch, and the sentinel conversion (Exercises 1-3)."""

import json

import pandas as pd
import pytest

from week_05_data_validation.schemas import MODEL_INPUT_COLUMNS, ModelInput, RawMeasurements
from week_05_data_validation.validation import (
    MAX_REPORTED_CASES,
    read_raw,
    read_report,
    sentinel_counts,
    to_nullable,
    validate_frame,
    write_report,
)

# Measured on data/quality/broken_batch.csv (60 rows, 4 faults).
EXPECTED_BY_CHECK = {
    "column_in_schema": 1,
    "coerce_dtype('float64')": 1,
    "dtype('float64')": 1,
    "greater_than_or_equal_to(0)": 1,
    "less_than_or_equal_to(400.0)": 1,
    "less_than_or_equal_to(100.0)": 1,
    "less_than_or_equal_to(120)": 1,
}


@pytest.mark.skip(reason="Exercise 1 — write RawMeasurements and validate_frame, then delete this skip marker.")
def test_the_real_dataset_passes_the_ingestion_contract(measurements_file) -> None:
    report = validate_frame(read_raw(measurements_file), RawMeasurements, "measurements.csv")
    assert report["passed"], f"The real data fails RawMeasurements: {report['by_check']}"
    assert report["rows"] == 768


@pytest.mark.skip(reason="Exercise 1 — write RawMeasurements and validate_frame, then delete this skip marker.")
def test_broken_batch_fails_with_the_expected_report(broken_batch) -> None:
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    assert not report["passed"]
    assert report["rows"] == 60
    assert report["n_failure_cases"] == 7, (
        f"Expected 7 failure cases; got {report['n_failure_cases']}. "
        "Is validate_frame collecting every failure (lazy mode)?"
    )
    assert report["by_check"] == EXPECTED_BY_CHECK


@pytest.mark.skip(reason="Exercise 1 — write RawMeasurements and validate_frame, then delete this skip marker.")
def test_every_fault_is_found_at_its_row(broken_batch) -> None:
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    found = {(case["row"], case["column"]) for case in report["failure_cases"]}
    for row, column in [(3, "glucose"), (7, "age"), (23, "bmi")]:
        assert (row, column) in found, f"No failure case for {column} in row {row}."


@pytest.mark.skip(reason="Exercise 1 — write RawMeasurements and validate_frame, then delete this skip marker.")
def test_report_is_plain_json(broken_batch, tmp_path) -> None:
    """The report holds plain values, so it survives a round trip through a file."""
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    assert json.loads(json.dumps(report)) == report
    path = write_report(report, tmp_path / "reports" / "validation.json")
    assert read_report(path) == report


def test_read_report_returns_empty_when_absent(tmp_path) -> None:
    assert read_report(tmp_path / "nope.json") == {}


def test_sentinel_counts_match_the_dataset(settings) -> None:
    frame = pd.read_csv(settings.data_path)
    assert sentinel_counts(frame) == {
        "glucose": 5, "blood_pressure": 35, "skin_thickness": 227, "insulin": 374, "bmi": 11,
    }


# ── to_nullable (Exercise 3) ─────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_to_nullable_converts_only_the_sentinel_columns() -> None:
    frame = pd.DataFrame(
        {"glucose": [0, 148], "bmi": [0.0, 33.6], "pregnancies": [0, 6], "outcome": [0, 1]}
    )
    converted = to_nullable(frame)
    assert converted["glucose"].isna().tolist() == [True, False]
    assert converted["bmi"].isna().tolist() == [True, False]
    assert converted["pregnancies"].tolist() == [0, 6], "A 0 in pregnancies is a real value."
    assert converted["outcome"].tolist() == [0, 1]


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_to_nullable_uses_the_nullable_float_type() -> None:
    converted = to_nullable(pd.DataFrame({"glucose": [0, 148]}))
    assert str(converted["glucose"].dtype) == "Float64", (
        f"Expected the dtype Float64 (capital F); got {converted['glucose'].dtype}."
    )


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_to_nullable_fills_nothing_in_and_leaves_its_input_alone() -> None:
    frame = pd.DataFrame({"glucose": [0, 148, 0]})
    converted = to_nullable(frame)
    assert converted["glucose"].isna().sum() == 2, "to_nullable must not fill in values."
    assert frame["glucose"].tolist() == [0, 148, 0], "to_nullable changed its input frame."


@pytest.mark.skip(reason="Exercise 3 — write ModelInput and to_nullable, then delete this skip marker.")
def test_model_input_fails_652_times_before_the_conversion_and_never_after(
    measurements_file,
) -> None:
    frame = read_raw(measurements_file)[MODEL_INPUT_COLUMNS]
    before = validate_frame(frame, ModelInput, "measurements.csv")
    assert before["n_failure_cases"] == 652
    assert before["by_check"] == {"greater_than(0)": 652}
    assert len(before["failure_cases"]) == MAX_REPORTED_CASES
    assert before["truncated"] is True

    after = validate_frame(to_nullable(frame), ModelInput, "measurements.csv")
    assert after["passed"], f"ModelInput still fails after to_nullable: {after['by_check']}"
