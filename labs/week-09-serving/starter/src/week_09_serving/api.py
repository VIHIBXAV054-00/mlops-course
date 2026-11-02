"""The prediction service: `POST /predict` and `GET /health`.

Start it with `make serve-api`, then open http://127.0.0.1:5541/docs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException  # noqa: F401 -- you need HTTPException in Exercise 2
from pydantic import BaseModel, ConfigDict, Field

from .config import load_settings
from .inference import payload_to_frame, validate_payload  # noqa: F401 -- Exercise 2
from .schemas import FEATURE_COLUMNS, SCHEMA_VERSION  # noqa: F401


class PredictionRequest(BaseModel):
    """One patient. Pydantic checks that every field is present and is a number or null.

    The fields are the same as in `PredictionInput` (schemas.py), and the same five
    may be null: a value that was not measured. A test checks that the two agree.
    The value rules stay in `PredictionInput`.
    """

    # An unknown field is a 422, as `strict = True` makes it in the contract.
    model_config = ConfigDict(extra="forbid")

    pregnancies: float = Field(..., description="Number of pregnancies (0 is a real value)")
    glucose: float | None = Field(..., description="Plasma glucose. null if not measured; 0 is not allowed")
    blood_pressure: float | None = Field(..., description="Diastolic blood pressure (mm Hg), or null")
    skin_thickness: float | None = Field(..., description="Triceps skin fold thickness (mm), or null")
    insulin: float | None = Field(..., description="2-hour serum insulin (mu U/ml), or null")
    bmi: float | None = Field(..., description="Body mass index, or null")
    diabetes_pedigree: float = Field(..., description="Diabetes pedigree function")
    age: float = Field(..., description="Age in years")


class PredictionResponse(BaseModel):
    prediction: int
    probability: float
    model_version: str | None
    schema_version: str


class HealthResponse(BaseModel):
    """What `/health` reports: the model this image was built with."""

    status: str
    model_version: str | None
    run_id: str | None
    gate_verdict: str | None
    schema_version: str
    model_source: str


def _baked() -> dict[str, Any]:
    """The model version, run ID and gate verdict that `serve.Dockerfile` wrote into the image.

    Outside a container the file does not exist, and `/health` says so.
    """
    settings = load_settings()
    path = settings.project_root / "models" / "baked.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "model_version": None,
        "run_id": None,
        "gate_verdict": None,
        "source": "working tree (not baked)",
    }


def create_app() -> FastAPI:
    settings = load_settings()
    baked = _baked()
    model_path = Path(os.getenv("MODEL_PATH", settings.models_dir / "model.pkl"))

    app = FastAPI(
        title="Diabetes prediction",
        version=SCHEMA_VERSION,
        description=(
            "Predicts the diabetes risk of one patient. Every request must pass the "
            "model-input contract, `PredictionInput`."
        ),
    )

    # Loaded once, when the app starts. None when there is no model file.
    app.state.model = joblib.load(model_path) if model_path.exists() else None
    app.state.baked = baked

    # TODO(student) Exercise 2: add both endpoints inside create_app.
    #
    # For GET /health, return a HealthResponse.
    #   - If `app.state.model` is None, raise an HTTPException with status 503
    #     and include "not ready" in its detail.
    #   - Otherwise, return status "ok", the schema version, and the values in
    #     `baked`: model_version, run_id, gate_verdict and `source` as model_source.
    #
    # For POST /predict, take a PredictionRequest and return a PredictionResponse.
    #   - FastAPI checks the request types before your function runs. Check the
    #     values with `validate_payload`.
    #   - If the report did not pass, raise an HTTPException with status 422.
    #     Put the report's `by_check` under "failures" and SCHEMA_VERSION under
    #     "schema_version" in its detail dict.
    #   - Build a frame with `payload_to_frame`, select FEATURE_COLUMNS in that
    #     order and score it with the model's `predict_proba`.
    #   - Return the probability of class 1 rounded to 4 decimals. Set prediction
    #     to 1 when the unrounded probability is at least 0.5. Include model_version
    #     from `baked` and SCHEMA_VERSION as schema_version.
    # Reference: https://fastapi.tiangolo.com/tutorial/body/ and
    # https://fastapi.tiangolo.com/tutorial/handling-errors/

    return app


app = create_app()
