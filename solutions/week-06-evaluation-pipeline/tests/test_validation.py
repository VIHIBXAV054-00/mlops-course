"""The validation report, the sentinel conversion and the corrupted batch."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from week_06_evaluation_pipeline.schemas import RawMeasurements
from week_06_evaluation_pipeline.validation import (
    read_raw,
    read_report,
    sentinel_counts,
    to_nullable,
    validate_frame,
    write_report,
)

# Measured on datasets/quality/broken_batch.csv (60 rows, 4 faults).
EXPECTED_FAILURE_CASES = 7

EXPECTED_BY_CHECK = {
    "column_in_schema": 1,               # the `notes` column
    "coerce_dtype('float64')": 1,        # glucose "unknown"
    "dtype('float64')": 1,
    "greater_than_or_equal_to(0)": 1,    # glucose TypeError knock-on
    "less_than_or_equal_to(400.0)": 1,   # glucose TypeError knock-on
    "less_than_or_equal_to(100.0)": 1,   # bmi x10
    "less_than_or_equal_to(120)": 1,     # age 250
}


def test_broken_batch_fails_with_the_expected_report(broken_batch):
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    assert not report["passed"]
    assert report["rows"] == 60
    assert report["n_failure_cases"] == EXPECTED_FAILURE_CASES
    assert report["by_check"] == EXPECTED_BY_CHECK


def test_every_injected_fault_is_caught_at_the_documented_row(broken_batch):
    """Each edit in datasets/quality/README.md maps to a case at that row."""
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    at = {(case["row"], case["column"]) for case in report["failure_cases"]}

    assert (3, "glucose") in at            # "unknown"
    assert (7, "age") in at               # 250
    assert (23, "bmi") in at              # x10


def test_one_bad_cell_can_produce_several_failure_cases(broken_batch):
    """One bad `glucose` cell gives four failure cases: coercion, dtype and two range checks that fail on text."""
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    assert report["by_column"]["glucose"] == 4


def test_a_dtype_error_is_reported_with_the_offending_value(broken_batch):
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    cases = [c for c in report["failure_cases"] if c["row"] == 3]
    assert any(c["failure_case"] == "unknown" for c in cases)


# ── The sentinel conversion ───────────────────────────────────────────────────


def test_sentinel_counts_match_the_canonical_dataset(settings):
    """The sentinel zeros in the dataset are counted per column."""
    frame = pd.read_csv(settings.data_path)
    assert sentinel_counts(frame) == {
        "glucose": 5,
        "blood_pressure": 35,
        "skin_thickness": 227,
        "insulin": 374,
        "bmi": 11,
    }


def test_to_nullable_converts_only_the_sentinel_columns():
    frame = pd.DataFrame(
        {
            "glucose": [0, 148],
            "bmi": [0.0, 33.6],
            "pregnancies": [0, 6],   # a real zero — must survive
            "outcome": [0, 1],       # a real zero — must survive
        }
    )
    converted = to_nullable(frame)
    assert converted["glucose"].isna().tolist() == [True, False]
    assert converted["bmi"].isna().tolist() == [True, False]
    assert converted["pregnancies"].tolist() == [0, 6]
    assert converted["outcome"].tolist() == [0, 1]


def test_to_nullable_uses_a_nullable_dtype():
    """`Float64`, not `float64`. Plain float64 cannot hold pd.NA."""
    converted = to_nullable(pd.DataFrame({"glucose": [0, 148]}))
    assert str(converted["glucose"].dtype) == "Float64"


def test_to_nullable_does_not_mutate_its_input():
    frame = pd.DataFrame({"glucose": [0, 148]})
    to_nullable(frame)
    assert frame["glucose"].tolist() == [0, 148]


def test_to_nullable_fills_nothing_in():
    """`to_nullable` fills nothing in; imputation belongs to the model's Pipeline."""
    converted = to_nullable(pd.DataFrame({"glucose": [0, 148, 0]}))
    assert converted["glucose"].isna().sum() == 2


# ── The report as an artifact ─────────────────────────────────────────────────


def test_report_round_trips_through_json(tmp_path):
    report = validate_frame(
        pd.DataFrame({"glucose": ["0"]}), RawMeasurements, "synthetic"
    )
    path = write_report(report, tmp_path / "reports" / "validation.json")
    assert path.exists()
    assert read_report(path) == report


def test_report_is_json_serialisable_with_no_pandas_objects(broken_batch):
    """The report holds only plain Python values, so it is JSON-serialisable."""
    report = validate_frame(read_raw(broken_batch), RawMeasurements, broken_batch.name)
    round_tripped = json.loads(json.dumps(report))
    assert round_tripped == report


def test_read_report_returns_empty_when_absent(tmp_path):
    assert read_report(tmp_path / "nope.json") == {}


def test_report_records_the_true_count_even_when_truncated(settings):
    """No silent caps. `n_failure_cases` is the real number, always."""
    from week_06_evaluation_pipeline.schemas import MODEL_INPUT_COLUMNS, ModelInput
    from week_06_evaluation_pipeline.validation import MAX_REPORTED_CASES

    if not settings.measurements_path.exists():
        pytest.skip("measurements.csv absent — build it with `make data-v2`.")

    frame = read_raw(settings.measurements_path)[MODEL_INPUT_COLUMNS]
    report = validate_frame(frame, ModelInput, "measurements.csv")
    assert report["n_failure_cases"] == 652
    assert len(report["failure_cases"]) == MAX_REPORTED_CASES
    assert report["truncated"] is True
