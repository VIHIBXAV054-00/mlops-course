"""The data contracts: `RawMeasurements` guards ingestion, `ModelInput` guards the model.

    batch file --> [RawMeasurements] --> 0 -> NA --> [ModelInput] --> Pipeline
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# Columns where a recorded 0 means "not measured". A 0 in `pregnancies` is real.
SENTINEL_COLUMNS = (
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
)

# Upper bounds, above the largest value in the dataset. `bmi <= 100` catches a BMI column multiplied by ten.
MAX_PREGNANCIES = 20
MAX_GLUCOSE = 400.0
MAX_BLOOD_PRESSURE = 200.0
MAX_SKIN_THICKNESS = 110.0
MAX_INSULIN = 1000.0
MAX_BMI = 100.0
MAX_PEDIGREE = 3.0
MAX_AGE = 120


class RawMeasurements(pa.DataFrameModel):
    """What an arriving batch may look like. Zeros are allowed here (`ge=0`)."""

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
        coerce = True
        strict = True
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """A duplicated row inflates both the training set and the test metrics."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """What the model may see, in training and in serving.

    The sentinel columns are `gt=0, nullable=True`: a converted zero (NA) passes
    and a surviving 0.0 fails. `strict` rejects extra columns and `ordered`
    rejects reordered ones.
    """

    # The declaration order is the contract (`ordered = True`).
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
    """`ModelInput` minus the label: what a serving request carries."""

    # `Optional` marks the column as allowed to be absent.
    outcome: Optional[Series[int]] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # A JSON request has no column order; `inference.payload_to_frame` sets one.
        ordered = False


# The column order `ModelInput` enforces.
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]

# Fail at import time if the schema and `MODEL_INPUT_COLUMNS` disagree on the order.
# Skipped while `ModelInput` is incomplete.
_declared = list(ModelInput.to_schema().columns)
if set(_declared) == set(MODEL_INPUT_COLUMNS):
    assert _declared == MODEL_INPUT_COLUMNS, (
        "ModelInput declares the right columns in the wrong order; it must match "
        "FEATURE_COLUMNS + TARGET_COLUMN in data.py.\n"
        f"  schema : {_declared}\n"
        f"  data.py: {MODEL_INPUT_COLUMNS}"
    )

# Bump when a rule changes. It is logged on the MLflow run.
SCHEMA_VERSION = "1.0.0"
