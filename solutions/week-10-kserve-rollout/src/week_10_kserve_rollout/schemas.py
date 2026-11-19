"""The data contracts. New in Week 5, and the heart of the week.

Two schemas, not one, because a dataset has two boundaries and they need
different rules:

    batch file ──▶ [RawMeasurements] ──▶ 0 -> NA ──▶ [ModelInput] ──▶ Pipeline
                    ingestion gate                    training gate

`RawMeasurements` describes what a file arriving from the lab is ALLOWED to look
like. It tolerates the physically-impossible zeros that have been in this dataset
since Week 1, because a contract has to describe reality at the boundary rather
than the reality you wish you had — and a gate that rejects every real file is a
gate somebody switches off.

`ModelInput` describes what the MODEL is allowed to see, and there the zeros are
illegal. The one line that does it is:

    glucose: Series[float] = pa.Field(gt=0, nullable=True)

Read it as: *missing is honest; zero is a lie.* `nullable=True` exempts nulls
from the check, so a converted sentinel passes and a surviving `0.0` fails. One
`Field`, both halves of the rule.

Import convention: `import pandera.pandas as pa`, not `import pandera as pa`.
Since pandera 0.24.0 the `pandera.pandas` namespace is the documented path for
pandas, and the base `pandera` install carries no pandas at all — which is why
pyproject asks for `pandera[pandas]`.
https://pandera.readthedocs.io/en/stable/dataframe_models.html
"""

from __future__ import annotations

from typing import Optional

import pandera.pandas as pa
from pandera.typing.pandas import Series

from .data import FEATURE_COLUMNS, TARGET_COLUMN

# The five columns where a recorded 0 is not a measurement of zero — it is a
# measurement that never happened, written down as though it had. Nobody can
# have a glucose of 0 and be alive to be measured.
#
# `pregnancies` is deliberately NOT in this list. A 0 there is a real, correct
# zero. Telling those two cases apart takes domain knowledge, not code, and it
# is the part of a data contract you cannot generate.
SENTINEL_COLUMNS = (
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
)

# Upper bounds. Each is comfortably above the largest value in the canonical
# dataset (the observed maxima are glucose 199, blood_pressure 122,
# skin_thickness 99, insulin 846, bmi 67.1, diabetes_pedigree 2.42, age 81) and
# below what a plausible corruption produces.
#
# `bmi <= 100` is the load-bearing one: it is what catches a BMI column
# multiplied by ten. Without an upper bound, `280.0` is just a number.
MAX_PREGNANCIES = 20
MAX_GLUCOSE = 400.0
MAX_BLOOD_PRESSURE = 200.0
MAX_SKIN_THICKNESS = 110.0
MAX_INSULIN = 1000.0
MAX_BMI = 100.0
MAX_PEDIGREE = 3.0
MAX_AGE = 120


class RawMeasurements(pa.DataFrameModel):
    """The INGESTION contract: what an arriving measurement batch may look like.

    Note the asymmetry with `ModelInput` below. Here the five sentinel columns
    are `ge=0` — zero is permitted, because it is what the source system
    actually sends. What is NOT permitted is a negative measurement, a label
    outside {0, 1}, a missing value, an unparseable date, a duplicated row, or a
    column nobody agreed to.
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
        # coerce: read the CSV as text and let the contract do the type work, so
        # a non-numeric cell fails HERE with a named column instead of somewhere
        # downstream as a confusing pandas error.
        coerce = True
        # strict: a column that is not declared is an error. The producer changed
        # the file without telling the consumer; this time it was harmless.
        strict = True
        # Not ordered: column order is not part of the ingestion agreement.
        # It IS part of ModelInput's — see below for why.
        unique_column_names = True

    @pa.dataframe_check(name="no_duplicate_rows")
    def no_duplicate_rows(cls, frame) -> bool:
        """A dataframe-level check: the same patient twice is one patient.

        A duplicated row inflates the training set and the test metrics at the
        same time, so it flatters the model twice over and shows up in neither
        a row count nor a column summary.
        """
        return not frame.duplicated().any()


class ModelInput(pa.DataFrameModel):
    """The TRAINING and SERVING contract: what the model is allowed to see.

    The same schema object guards both directions, and that is the whole
    training-serving-skew lesson in one sentence: if training and inference
    validate against different rules, or against no rules, the model is fed two
    different things and only one of them was ever tested.

    Three properties, each catching a different real failure:

    - `gt=0, nullable=True` on the sentinel columns — a converted sentinel (NA)
      passes, a surviving `0.0` fails. The zeros became illegal here, not in
      `RawMeasurements`.
    - `strict = True` — an extra feature is an error, not a silently ignored
      column.
    - `ordered = True` — sklearn matches features BY POSITION when handed a bare
      array, so a reordered payload predicts confidently and wrongly. This is
      the most expensive bug in this file and the cheapest to prevent.
    """

    # Declaration order IS the contract, because `ordered = True` below. It must
    # match data.py's FEATURE_COLUMNS + TARGET_COLUMN exactly — the assertion at
    # the bottom of this module fails loudly if the two ever drift apart.
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
    """`ModelInput` minus the label — what a serving request carries.

    Inheriting rather than re-declaring is the point: there is exactly one
    definition of a legal feature row in this project, and the serving contract
    is the training contract with the answer removed. Re-typing the rules here
    would be how the two drift apart.
    """

    # `typing.Optional` — not a `Field` argument — is how a DataFrameModel marks
    # a column as "may be absent". (`pa.Field(required=False)` looks plausible
    # and raises `SchemaInitError: custom check 'required' is not available`,
    # because unknown Field kwargs are treated as registered custom checks.)
    outcome: Optional[Series[int]] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        name = "PredictionInput"
        coerce = True
        strict = True
        # NOT ordered, unlike ModelInput, and the difference is not an oversight.
        # A request arrives as a JSON object, which has no column order —
        # `inference.payload_to_frame` imposes one. Ordering is therefore OUR
        # invariant here, not the caller's, and asserting it would only test our
        # own code. A frame read from a CSV is the opposite case: the column
        # order is the producer's choice and can change without warning, which is
        # why ModelInput does assert it.
        ordered = False


# The column order `ModelInput` enforces. Derived from data.py rather than
# retyped, so the schema and the pipeline cannot disagree about it.
MODEL_INPUT_COLUMNS = list(FEATURE_COLUMNS) + [TARGET_COLUMN]

# `ordered = True` means the DECLARATION order above is the contract, and the
# pipeline projects its frames with MODEL_INPUT_COLUMNS. If someone reorders one
# and not the other, every validation call starts failing with a confusing
# `column_ordered` error. Fail here instead, at import time, with a clear one.
#
# Guarded by the set comparison on purpose: while ModelInput is still being
# written, its columns are a SUBSET, and that is an unfinished exercise rather
# than a bug. Hard-failing at import time then would take the whole test suite
# down with it and tell the student nothing the skip markers do not already say.
_declared = list(ModelInput.to_schema().columns)
if set(_declared) == set(MODEL_INPUT_COLUMNS):
    assert _declared == MODEL_INPUT_COLUMNS, (
        "ModelInput declares the right columns in the WRONG ORDER. Because "
        "`Config.ordered = True`, the declaration order IS the contract, and it "
        "must match data.py's FEATURE_COLUMNS + TARGET_COLUMN.\n"
        f"  schema : {_declared}\n"
        f"  data.py: {MODEL_INPUT_COLUMNS}"
    )

SCHEMA_VERSION = "1.0.0"
"""Bump when a rule changes. Logged onto the MLflow run, so a run recorded
against version 1.0.0 of the contract stays interpretable after the contract
moves on — otherwise 'it passed validation' is a claim with no referent."""
