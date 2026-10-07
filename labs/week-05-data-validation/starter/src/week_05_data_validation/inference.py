"""Predict for one request, as a serving endpoint would (serving itself is Week 9)."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .data import FEATURE_COLUMNS
from .schemas import PredictionInput
from .validation import validate_frame


def payload_to_frame(payload: dict) -> pd.DataFrame:
    """One request -> a one-row DataFrame, with the known features in the model's order."""
    frame = pd.DataFrame([payload])
    known = [column for column in FEATURE_COLUMNS if column in frame.columns]
    extra = [column for column in frame.columns if column not in FEATURE_COLUMNS]
    return frame[known + extra]


def validate_payload(payload: dict) -> dict:
    """Check one request against PredictionInput. Returns a report."""
    return validate_frame(payload_to_frame(payload), PredictionInput, source="request")


def predict_one(payload: dict, model_path: Path) -> dict:
    """Check the request, then predict.

    Returns {"report", "prediction", "probability"}. A rejected request gets no
    prediction, and the model is not loaded.
    """
    result: dict = {"report": {}, "prediction": None, "probability": None}
    # TODO(student) Exercise 6: check the request with `validate_payload`, and
    # store its report in result["report"]. The report's "passed" field says
    # whether the request meets the contract. If it does not, return the result
    # now, before the model is loaded.

    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_path.name} is missing. Run `make repro` to train a model first."
        )
    model = joblib.load(model_path)
    # A missing value (None) becomes NaN, which the model's imputer fills.
    features = payload_to_frame(payload).astype("float64")
    result["prediction"] = int(model.predict(features)[0])
    result["probability"] = round(float(model.predict_proba(features)[0][1]), 4)
    return result


def load_payload(source: str) -> dict:
    """A payload from a JSON string or a path to a JSON file."""
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(source)


# The first patient of the dataset, with every value measured.
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

# The same patient, with glucose and insulin sent as 0 ("not measured").
ILLEGAL_PAYLOAD = {**EXAMPLE_PAYLOAD, "glucose": 0.0, "insulin": 0.0}

# The same patient, with the insulin and bmi values swapped.
SWAPPED_PAYLOAD = {**EXAMPLE_PAYLOAD, "insulin": 33.6, "bmi": 155.0}

# The same patient, without the insulin field.
INCOMPLETE_PAYLOAD = {
    key: value for key, value in EXAMPLE_PAYLOAD.items() if key != "insulin"
}

PAYLOADS = {
    "example": EXAMPLE_PAYLOAD,
    "illegal": ILLEGAL_PAYLOAD,
    "swapped": SWAPPED_PAYLOAD,
    "incomplete": INCOMPLETE_PAYLOAD,
}
