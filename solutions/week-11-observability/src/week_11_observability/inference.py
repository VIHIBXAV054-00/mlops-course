"""Validate one prediction request against the data contract, then predict.

`PredictionInput` inherits from the training contract `ModelInput`, so both use the same rules.
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
    """One request dict -> a one-row DataFrame, feature columns first and in the model's order."""
    frame = pd.DataFrame([payload])
    known = [column for column in FEATURE_COLUMNS if column in frame.columns]
    extra = [column for column in frame.columns if column not in FEATURE_COLUMNS]
    return frame[known + extra]


def validate_payload(payload: dict) -> dict:
    """Validate one request against `PredictionInput` and return the report dict."""
    frame = payload_to_frame(payload)
    return validate_frame(frame, PredictionInput, source="request payload")


def predict_one(payload: dict, model_path: Path) -> dict:
    """Validate, then predict. A rejected request never reaches the model."""
    report = validate_payload(payload)
    result: dict = {"report": report, "prediction": None, "probability": None}

    # an empty report comes from an unfinished `validate_frame`, so stop then too
    if not report or not report["passed"]:
        return result

    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_path.name} is missing. Run `make repro` to train a model first."
        )

    model = joblib.load(model_path)
    frame = to_nullable(payload_to_frame(payload))[list(FEATURE_COLUMNS)]

    # the imputer needs plain floats, nulls become NaN
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


# A legal request, based on the first row of the dataset.
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

# the same patient with the sentinel zeros the contract rejects
ILLEGAL_PAYLOAD = {**EXAMPLE_PAYLOAD, "glucose": 0.0, "insulin": 0.0}

# `insulin` and `bmi` swapped: each value is legal, the patient is wrong
SWAPPED_PAYLOAD = {**EXAMPLE_PAYLOAD, "insulin": 33.6, "bmi": 155.0}

INCOMPLETE_PAYLOAD = {
    key: value for key, value in EXAMPLE_PAYLOAD.items() if key != "insulin"
}
