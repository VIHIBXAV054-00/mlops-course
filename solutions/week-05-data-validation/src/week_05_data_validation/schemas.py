"""The data contracts, as Pandera DataFrame models.

    batch file -> RawMeasurements -> to_nullable -> ModelInput -> model

https://pandera.readthedocs.io/en/stable/dataframe_models.html
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# The five columns where a recorded 0 means "not measured". A 0 in
# `pregnancies` is a real value, so it is not in this list.
SENTINEL_COLUMNS = ("glucose", "blood_pressure", "skin_thickness", "insulin", "bmi")

# Upper bounds. The largest values in our 768 patients are glucose 199,
# blood_pressure 122, skin_thickness 99, insulin 846, bmi 67.1,
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

    measurement_date: Series[pa.DateTime] = pa.Field(nullable=False)
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
        coerce = True  # the CSV is read as text; the contract converts the types
        strict = True  # a column that is not declared here is an error
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """The same row twice is one patient counted twice."""
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """The training contract: what the model may see. A sentinel zero is illegal here."""

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
