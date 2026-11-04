"""Data contracts: RawMeasurements (ingestion), ModelInput (training), PredictionInput (serving).

In ModelInput a sentinel 0 is illegal and null is allowed: pa.Field(gt=0, nullable=True).
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# A 0 in these columns means "not measured". A 0 in pregnancies is real.
SENTINEL_COLUMNS = (
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
)

# Above every value in the dataset. MAX_BMI catches a BMI column multiplied by ten.
MAX_PREGNANCIES = 20
MAX_GLUCOSE = 400.0
MAX_BLOOD_PRESSURE = 200.0
MAX_SKIN_THICKNESS = 110.0
MAX_INSULIN = 1000.0
MAX_BMI = 100.0
MAX_PEDIGREE = 3.0
MAX_AGE = 120


class RawMeasurements(pa.DataFrameModel):
    """The ingestion contract: what an arriving measurement batch may look like.

    Sentinel zeros are allowed; nulls, negatives, extra columns and duplicate rows are not.
    """

    measurement_date: Series[pa.DateTime] = pa.Field(
        nullable=False,
        description="When the row arrived. Coerced, so an impossible date fails here.",
    )
    pregnancies: Series[int] = pa.Field(ge=0, le=MAX_PREGNANCIES, nullable=False)
    glucose: Series[float] = pa.Field(ge=0, le=MAX_GLUCOSE, nullable=False)
    blood_pressure: Series[float] = pa.Field(ge=0, le=MAX_BLOOD_PRESSURE, nullable=False)
    skin_thickness: Series[float] = pa.Field(ge=0, le=MAX_SKIN_THICKNESS, nullable=False)
    insulin: Series[float] = pa.Field(ge=0, le=MAX_INSULIN, nullable=False)
    bmi: Series[float] = pa.Field(ge=0, le=MAX_BMI, nullable=False)
    diabetes_pedigree: Series[float] = pa.Field(gt=0, le=MAX_PEDIGREE, nullable=False)
    age: Series[int] = pa.Field(ge=0, le=MAX_AGE, nullable=False)
    outcome: Series[int] = pa.Field(isin=[0, 1], nullable=False)

    class Config:
        name = "RawMeasurements"
        # coerce: a non-numeric cell fails here, naming its column.
        coerce = True
        # strict: an undeclared column is an error.
        strict = True
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """No duplicated rows."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """The training contract: sentinel zeros illegal, columns strict and in order."""

    # Declaration order is the contract (ordered = True).
    pregnancies: Series[int] = pa.Field(ge=0, le=MAX_PREGNANCIES, nullable=False)
    glucose: Series[float] = pa.Field(gt=0, le=MAX_GLUCOSE, nullable=True)
    blood_pressure: Series[float] = pa.Field(gt=0, le=MAX_BLOOD_PRESSURE, nullable=True)
    skin_thickness: Series[float] = pa.Field(gt=0, le=MAX_SKIN_THICKNESS, nullable=True)
    insulin: Series[float] = pa.Field(gt=0, le=MAX_INSULIN, nullable=True)
    bmi: Series[float] = pa.Field(gt=0, le=MAX_BMI, nullable=True)
    diabetes_pedigree: Series[float] = pa.Field(gt=0, le=MAX_PEDIGREE, nullable=False)
    age: Series[int] = pa.Field(ge=0, le=MAX_AGE, nullable=False)
    outcome: Series[int] = pa.Field(isin=[0, 1], nullable=False)

    class Config:
        name = "ModelInput"
        coerce = True
        strict = True
        ordered = True


class PredictionInput(ModelInput):
    """ModelInput with the label optional: the serving contract."""

    # `typing.Optional` — not a `Field` argument — is how a DataFrameModel marks
    # a column as "may be absent". (`pa.Field(required=False)` looks plausible
    # and raises `SchemaInitError: custom check 'required' is not available`,
    # because unknown Field kwargs are treated as registered custom checks.)
    outcome: Optional[Series[int]] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # A JSON object has no column order; payload_to_frame sets it.
        ordered = False


# The column order `ModelInput` enforces. Derived from data.py rather than
# retyped, so the schema and the pipeline cannot disagree about it.
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]

# Fail at import time if ModelInput's column order differs from data.py's.
_declared = list(ModelInput.to_schema().columns)
if set(_declared) == set(MODEL_INPUT_COLUMNS):
    assert _declared == MODEL_INPUT_COLUMNS, (
        "ModelInput declares the right columns in the wrong order; it must match "
        "data.py's FEATURE_COLUMNS + TARGET_COLUMN.\n"
        f"  schema : {_declared}\n"
        f"  data.py: {MODEL_INPUT_COLUMNS}"
    )

SCHEMA_VERSION = "1.0.0"
"""Bump when a rule changes. Logged on every MLflow run."""
