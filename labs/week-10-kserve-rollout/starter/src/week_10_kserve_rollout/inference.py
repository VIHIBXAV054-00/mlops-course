"""Validating a single prediction request. New in Week 5.

This module exists to make one argument concrete: **the contract that guarded
training has to guard inference too, and it has to be the same object.**

Nothing here is a web service — serving is Week 9. It is one function that takes
the dict a request would carry, validates it, and predicts. That is enough to
demonstrate the three ways a payload goes wrong:

1. **An illegal value.** `glucose: 0` at serving time is the same lie the
   training data told, and the trained model has no idea it is being lied to. It
   returns a confident probability computed from a physiologically impossible
   patient. Caught by `greater_than(0)`.

2. **Two features swapped.** Every value is legal on its own; the request is
   about a different patient than the caller thinks. Caught only because
   `bmi <= 100` makes an insulin reading impossible in the `bmi` slot — i.e. by
   a RANGE BOUND, not by anything clever. Swap two features with overlapping
   plausible ranges and no schema in this file will notice. Say that out loud;
   it is the honest limit of a contract.

3. **A missing feature.** Caught as `column_in_dataframe`, naming the column.
   (Its mirror image, an EXTRA feature, is `column_in_schema`. Two opposite
   failures with two confusingly similar names — read them carefully.) sklearn
   would also catch a missing column, later and less clearly.

A fourth failure — columns in the wrong ORDER — cannot happen to a dict, because
`payload_to_frame` imposes the order itself. It is a real failure for a frame
read from a file, and that is what `ModelInput.Config.ordered = True` is for.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .data import FEATURE_COLUMNS
from .schemas import PredictionInput
from .validation import to_nullable, validate_frame


def payload_to_frame(payload: dict) -> pd.DataFrame:
    """One request dict -> a one-row DataFrame in the contract's column order.

    Reindexing to FEATURE_COLUMNS is doing real work: it puts the columns in the
    order the model was fitted with and it makes a MISSING key visible as an
    absent column rather than as a silently shifted position.
    """
    frame = pd.DataFrame([payload])
    known = [column for column in FEATURE_COLUMNS if column in frame.columns]
    extra = [column for column in frame.columns if column not in FEATURE_COLUMNS]
    return frame[known + extra]


def validate_payload(payload: dict) -> dict:
    """Validate one request against `PredictionInput`. Returns a report dict.

    `PredictionInput` is `ModelInput` with the label made optional — it inherits
    rather than redeclares, so there is exactly one definition of a legal feature
    row in this project. Two hand-written schemas that are supposed to agree are
    two schemas that will eventually disagree.
    """
    frame = payload_to_frame(payload)
    return validate_frame(frame, PredictionInput, source="request payload")


def predict_one(payload: dict, model_path: Path) -> dict:
    """Validate, then predict. The order is the point.

    Returns a dict carrying the validation report and — only if the payload was
    legal — the prediction. A rejected request never reaches the model, which is
    what makes the schema a gate rather than a log line.
    """
    report = validate_payload(payload)
    result: dict = {"report": report, "prediction": None, "probability": None}

    # `not report` covers the empty report a not-yet-written `validate_frame`
    # returns; `not report["passed"]` is the real rejection. Both must stop here,
    # BEFORE the model is loaded — an unvalidated request is not a safer request.
    if not report or not report["passed"]:
        return result

    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_path.name} is missing. Run `make repro` to train a model first."
        )

    model = joblib.load(model_path)
    frame = to_nullable(payload_to_frame(payload))[list(FEATURE_COLUMNS)]

    # Float64/Int64 (pandas' nullable dtypes) are what to_nullable produces, and
    # sklearn's SimpleImputer wants a plain float array. Converting here keeps
    # the nulls as NaN, which is what the imputer is fitted to expect.
    numeric = frame.astype("float64")

    result["prediction"] = int(model.predict(numeric)[0])
    result["probability"] = round(float(model.predict_proba(numeric)[0][1]), 4)
    return result


def load_payload(source: str) -> dict:
    """A payload from a JSON string or a path to a JSON file."""
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(source)


# A legal request, for the CLI's default and for the tests. Real values from the
# canonical dataset's first row, so the prediction is meaningful rather than
# arbitrary.
EXAMPLE_PAYLOAD = {
    "pregnancies": 6,
    "glucose": 148.0,
    "blood_pressure": 72.0,
    "skin_thickness": 35.0,
    "insulin": 155.0,
    "bmi": 33.6,
    "diabetes_pedigree": 0.627,
    "age": 50,
}

# The same patient with the sentinel that the training data used to carry. It is
# the single most likely thing a real source system sends, and it must not be
# answered.
ILLEGAL_PAYLOAD = {**EXAMPLE_PAYLOAD, "glucose": 0.0, "insulin": 0.0}

# The same eight values with `insulin` and `bmi` swapped. Every value is legal in
# isolation; the request describes a different patient than the caller means.
SWAPPED_PAYLOAD = {**EXAMPLE_PAYLOAD, "insulin": 33.6, "bmi": 155.0}

INCOMPLETE_PAYLOAD = {
    key: value for key, value in EXAMPLE_PAYLOAD.items() if key != "insulin"
}
