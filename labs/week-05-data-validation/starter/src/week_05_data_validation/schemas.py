"""The data contracts, as Pandera DataFrame models.

    batch file -> RawMeasurements -> to_nullable -> ModelInput -> model

https://pandera.readthedocs.io/en/stable/dataframe_models.html
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# Exercises 1 and 3: the five columns where a recorded 0 means "not measured".
# A 0 in `pregnancies` is a real value, so it is not in this list.
SENTINEL_COLUMNS = ("glucose", "blood_pressure", "skin_thickness", "insulin", "bmi")

# Exercises 1 and 3: the upper bounds. The largest values in our 768 patients
# are glucose 199, blood_pressure 122, skin_thickness 99, insulin 846, bmi 67.1,
# diabetes_pedigree 2.42 and age 81.
MAX_PREGNANCIES = 20
MAX_GLUCOSE = 400.0
MAX_BLOOD_PRESSURE = 200.0
MAX_SKIN_THICKNESS = 110.0
MAX_INSULIN = 1000.0
MAX_BMI = 100.0
MAX_PEDIGREE = 3.0
MAX_AGE = 120

# The columns ModelInput expects, in this order.
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]


class RawMeasurements(pa.DataFrameModel):
    """The ingestion contract: what a batch from the clinic may contain."""

    # TODO(student) Exercise 1: declare the ten columns of a batch, in the order
    # of the CSV header. `measurement_date` is done; continue the list below it.
    # Give each column its type and its rules: no missing values, nothing below 0
    # (so the zeros in SENTINEL_COLUMNS pass), the MAX_* bounds above,
    # `diabetes_pedigree` above 0, and 0 or 1 for `outcome`.
    # Reference: https://pandera.readthedocs.io/en/stable/dataframe_models.html
    measurement_date: Series[pa.DateTime] = pa.Field(nullable=False)

    class Config:
        name = "RawMeasurements"
        coerce = True  # the CSV is read as text; the contract converts the types
        strict = True  # a column that is not declared here is an error
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """The same row twice is one patient counted twice."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """The training contract: what the model may see. A sentinel zero is illegal here."""

    # TODO(student) Exercise 3: declare the nine columns of MODEL_INPUT_COLUMNS,
    # in that order. In the five SENTINEL_COLUMNS, a 0 must fail and a missing
    # value must pass. The other columns keep their RawMeasurements rules.
    ...

    class Config:
        name = "ModelInput"
        coerce = True
        strict = True
        ordered = True


class PredictionInput(ModelInput):
    """The serving contract: ModelInput without the label."""

    # `Optional` marks a column that may be absent.
    outcome: Optional[Series[int]] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # A JSON request has no column order: `inference.payload_to_frame` sets it.
        ordered = False


SCHEMA_VERSION = "1.0.0"
"""Raise it whenever a rule above changes. Every training run records it."""
