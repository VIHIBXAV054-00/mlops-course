"""The Pandera data contracts: `RawMeasurements` at ingestion, `ModelInput` before the model.

The raw contract allows the sentinel zeros. `ModelInput` rejects them (`gt=0, nullable=True`).
https://pandera.readthedocs.io/en/stable/dataframe_models.html
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

# Upper bounds, above the largest value in the dataset. `bmi <= 100` catches a BMI times ten.
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

    The sentinel columns allow 0 here (`ge=0`), because that is what the source system sends.
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
        # a non-numeric cell fails here, with the column named
        coerce = True
        # an undeclared column is an error
        strict = True
        # column order is not part of the ingestion contract
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """A duplicated row inflates both the training set and the test metrics."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """The training and serving contract: what the model is allowed to see.

    `gt=0, nullable=True` lets a converted null pass and rejects a 0. `strict` rejects an extra
    column. `ordered` rejects reordered columns, which sklearn would match by position.
    """

    # declaration order is the contract, and must match FEATURE_COLUMNS + TARGET_COLUMN
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
    """`ModelInput` without the label: what a prediction request carries."""

    # `Optional` marks a column that may be absent (`pa.Field(required=False)` raises)
    outcome: Optional[Series[int]] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # a JSON request has no column order, `payload_to_frame` sets it
        ordered = False


# the column order `ModelInput` enforces, derived from data.py
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]

# Fail at import time if `ModelInput` declares the right columns in the wrong order.
# Only checked once every column is declared, so an unfinished schema does not break the tests.
_declared = list(ModelInput.to_schema().columns)
if set(_declared) == set(MODEL_INPUT_COLUMNS):
    assert _declared == MODEL_INPUT_COLUMNS, (
        "ModelInput declares the right columns in the wrong order. With "
        "`Config.ordered = True` the declaration order must match data.py's "
        "FEATURE_COLUMNS + TARGET_COLUMN.\n"
        f"  schema : {_declared}\n"
        f"  data.py: {MODEL_INPUT_COLUMNS}"
    )

# Bump when a rule changes. Logged on the MLflow run, so a recorded run names its contract.
SCHEMA_VERSION = "1.0.0"
