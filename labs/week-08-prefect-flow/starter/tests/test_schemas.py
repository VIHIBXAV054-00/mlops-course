"""The contracts themselves.

Every test here builds its own frame in memory, so the whole file runs with no
Docker, no Silo, no DVC and no dataset on disk. That is deliberate: a data
contract is the one part of an MLOps stack you can test in complete isolation,
and if you cannot, the contract is entangled with something it should not be.
"""

from __future__ import annotations

import copy

import pandas as pd
import pandera.pandas as pa
import pytest

from week_08_prefect_flow.schemas import (
    MAX_BMI,
    MODEL_INPUT_COLUMNS,
    SENTINEL_COLUMNS,
    ModelInput,
    PredictionInput,
    RawMeasurements,
)
from week_08_prefect_flow.validation import to_nullable, validate_frame

pytestmark = pytest.mark.data

# One legal row, as strings, exactly as read_raw would hand it over.
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
    frame = raw_frame(**overrides)[MODEL_INPUT_COLUMNS]
    return frame


# ── The ingestion contract ────────────────────────────────────────────────────


def test_legal_batch_passes_ingestion_contract():
    assert validate_frame(raw_frame(), RawMeasurements)["passed"]


def test_ingestion_contract_tolerates_the_sentinel_zeros():
    """The whole reason there are two schemas.

    A recorded 0 in these columns is the real dataset's real behaviour. An
    ingestion contract that rejected it would reject every genuine file, and a
    gate that rejects everything gets switched off within a week.
    """
    report = validate_frame(raw_frame(glucose=0, insulin=0, bmi=0), RawMeasurements)
    assert report["passed"], report["by_check"]


@pytest.mark.parametrize(
    "overrides, expected_check",
    [
        ({"insulin": -1}, "greater_than_or_equal_to(0)"),
        ({"age": 250}, "less_than_or_equal_to(120)"),
        ({"outcome": 2}, "isin([0, 1])"),
        ({"bmi": 280.0}, f"less_than_or_equal_to({MAX_BMI})"),
        ({"measurement_date": "2024-13-45"}, "coerce_dtype('datetime64[ns]')"),
    ],
)

def test_ingestion_contract_rejects_each_error_class(overrides, expected_check):
    report = validate_frame(raw_frame(**overrides), RawMeasurements)
    assert not report["passed"]
    assert expected_check in report["by_check"], report["by_check"]


def test_ingestion_contract_rejects_an_undeclared_column():
    """`Config.strict = True` is load-bearing, not decoration.

    The negative half of this test is the interesting half: with strict off, the
    same frame passes. A schema that ignores unexpected columns cannot tell you
    that the producer changed the file.
    """
    frame = raw_frame()
    frame["notes"] = "imported from lab system v2"

    report = validate_frame(frame, RawMeasurements)
    assert not report["passed"]
    assert "column_in_schema" in report["by_check"]

    # deepcopy is NOT optional here. `DataFrameModel.to_schema()` returns a
    # CACHED, SHARED, MUTABLE DataFrameSchema — the same object every call — so
    # `RawMeasurements.to_schema().strict = False` silently disables strictness
    # for the whole process. (Found the hard way: it made a later test in another
    # file see 14 failure cases instead of 15.)
    lenient = copy.deepcopy(RawMeasurements.to_schema())
    lenient.strict = False
    assert validate_frame(frame, lenient)["passed"]
    # ... and the original is untouched.
    assert RawMeasurements.to_schema().strict is True


def test_ingestion_contract_rejects_a_duplicated_row():
    frame = pd.concat([raw_frame(), raw_frame().head(1)], ignore_index=True)
    report = validate_frame(frame, RawMeasurements)
    assert not report["passed"]
    assert "no_duplicate_rows" in report["by_check"]


def test_ingestion_contract_rejects_a_missing_required_value():
    frame = raw_frame()
    frame.loc[0, "blood_pressure"] = None
    report = validate_frame(frame, RawMeasurements)
    assert not report["passed"]
    assert "not_nullable" in report["by_check"]


# ── The training contract ─────────────────────────────────────────────────────


def test_model_input_rejects_a_sentinel_zero():
    """`gt=0, nullable=True`, first half: zero is a lie."""
    report = validate_frame(model_frame(glucose=0), ModelInput)
    assert not report["passed"]
    assert report["by_check"] == {"greater_than(0)": 1}


def test_model_input_accepts_a_null():
    """`gt=0, nullable=True`, second half: missing is honest.

    This is the assertion that makes the whole remediation flow legal. If a
    pandera upgrade ever changed it so that checks applied to nulls, this test
    would fail loudly instead of the pipeline failing mysteriously.
    """
    frame = to_nullable(model_frame(glucose=0))
    assert frame["glucose"].isna().sum() == 1
    assert validate_frame(frame, ModelInput)["passed"]


def test_model_input_enforces_column_order():
    """`Config.ordered = True`.

    sklearn matches features by POSITION when handed a bare array, so a
    reordered frame produces a confident prediction about a different patient.
    A `column_ordered` failure is cheap; that bug is not.
    """
    frame = to_nullable(model_frame())
    swapped = frame[
        ["glucose", "pregnancies"] + [c for c in MODEL_INPUT_COLUMNS
                                      if c not in ("glucose", "pregnancies")]
    ]
    report = validate_frame(swapped, ModelInput)
    assert not report["passed"]
    assert "column_ordered" in report["by_check"]


def test_model_input_declaration_order_matches_the_pipeline():
    """The import-time assertion in schemas.py, restated as a test.

    Two places name the model's columns; this is what stops them drifting.
    """
    assert list(ModelInput.to_schema().columns) == MODEL_INPUT_COLUMNS


def test_sentinel_columns_are_the_five_documented_ones():
    """`pregnancies` must NOT be in here — a 0 there is a real zero.

    Telling a real zero from a sentinel takes domain knowledge, which is the
    part of a data contract that cannot be generated from the data.
    """
    assert set(SENTINEL_COLUMNS) == {
        "glucose",
        "blood_pressure",
        "skin_thickness",
        "insulin",
        "bmi",
    }
    assert "pregnancies" not in SENTINEL_COLUMNS


# ── The serving contract ──────────────────────────────────────────────────────


def test_prediction_input_makes_the_label_optional():
    """The serving contract is the training contract minus the answer.

    It INHERITS from ModelInput rather than restating the rules, so there is one
    definition of a legal feature row. Two copies would eventually disagree.
    """
    features = to_nullable(model_frame()).drop(columns=["outcome"])
    assert validate_frame(features, PredictionInput)["passed"]
    assert not validate_frame(features, ModelInput)["passed"]


def test_prediction_input_inherits_the_value_rules():
    features = to_nullable(model_frame(glucose=0)).drop(columns=["outcome"])
    features["glucose"] = 0.0  # undo the conversion: a raw sentinel arrives
    report = validate_frame(features, PredictionInput)
    assert not report["passed"]
    assert "greater_than(0)" in report["by_check"]


def test_to_schema_returns_a_shared_mutable_object():
    """A trap worth knowing about before it costs you an afternoon.

    `to_schema()` is cached per model class, so two calls return the SAME object
    and any mutation is global and permanent for the process. If you need a
    variant of a schema — to demonstrate what a flag does, or to relax a rule in
    one place — deepcopy it first.
    """
    assert RawMeasurements.to_schema() is RawMeasurements.to_schema()

    variant = copy.deepcopy(RawMeasurements.to_schema())
    variant.strict = False
    assert RawMeasurements.to_schema().strict is True


def test_lazy_validation_reports_every_violation_at_once():
    """Why `lazy=True` is not optional.

    Non-lazy validation raises on the FIRST problem, so fixing a broken file
    becomes one round trip per fault. Lazy collects them all in one pass.
    """
    frame = raw_frame(age=250, outcome=2, insulin=-1)
    report = validate_frame(frame, RawMeasurements)
    assert report["n_failure_cases"] >= 3

    with pytest.raises(pa.errors.SchemaError):
        RawMeasurements.validate(frame)  # lazy defaults to False
