"""The prediction service: `POST /predict` and `GET /health`.

Start it with `make serve-api`, then open http://127.0.0.1:5541/docs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .config import load_settings
from .inference import payload_to_frame, validate_payload  # noqa: F401 -- Exercise 2
from .schemas import FEATURE_COLUMNS, SCHEMA_VERSION  # noqa: F401


class PredictionRequest(BaseModel):
    """One patient, with the fields of `PredictionInput`. The five sentinel fields may be null.

    Pydantic checks the types here; `PredictionInput` checks the values.
    """

    # An unknown field is a 422, as `strict = True` makes it in the contract.
    model_config = ConfigDict(extra="forbid")

    pregnancies: float = Field(description="Number of pregnancies (0 is a real value)")
    glucose: float | None = Field(description="Plasma glucose. null if not measured; 0 is not allowed")
    blood_pressure: float | None = Field(description="Diastolic blood pressure (mm Hg), or null")
    skin_thickness: float | None = Field(description="Triceps skin fold thickness (mm), or null")
    insulin: float | None = Field(description="2-hour serum insulin (mu U/ml), or null")
    bmi: float | None = Field(description="Body mass index, or null")
    diabetes_pedigree: float = Field(description="Diabetes pedigree function")
    age: float = Field(description="Age in years")


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


def _build_info() -> dict[str, Any]:
    """The model version, run ID and gate verdict that `serve.Dockerfile` wrote into the image.

    Outside a container the file does not exist, and `/health` says so.
    """
    settings = load_settings()
    path = settings.project_root / "models" / "build_info.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "model_version": None,
        "run_id": None,
        "gate_verdict": None,
        "source": "working tree (not a built image)",
    }


def create_app() -> FastAPI:
    settings = load_settings()
    build_info = _build_info()
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
    app.state.build_info = build_info

    # TODO(student) Exercise 2, step 2: make `health` the GET /health endpoint. Replace the
    # line below with a FastAPI path operation decorator: the HTTP method in lower case, the
    # path, and HealthResponse as the response model. Then replace each `...` in the function.
    # Reference: https://fastapi.tiangolo.com/tutorial/first-steps/
    # @app.<fill in>(<fill in>, response_model=<fill in>)
    def health() -> HealthResponse:
        """503 until the model is loaded, so a readiness probe sends no traffic to this pod."""
        if ...:  # no model is loaded
            raise HTTPException(status_code=..., detail=...)  # the detail includes "not ready"

        return HealthResponse(
            status=...,  # "ok"
            model_version=...,  # this field and the next two come from `build_info`
            run_id=...,
            gate_verdict=...,
            schema_version=...,
            model_source=...,  # `build_info` calls it "source"
        )

    # TODO(student) Exercise 2, step 3: make `predict` the POST /predict endpoint, with
    # PredictionResponse as the response model, as for `health` above. Then replace each `...`.
    # Reference: https://fastapi.tiangolo.com/tutorial/body/
    # @app.<fill in>(<fill in>, response_model=<fill in>)
    def predict(request: PredictionRequest) -> PredictionResponse:
        """Score one patient. FastAPI has checked the types; the contract checks the values."""
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model not loaded")

        # `predict_one` in inference.py runs the same steps for `make predict`.
        payload = ...  # the request as a dict
        report = ...  # the contract's report on `payload`, from `validate_payload`

        # A request that breaks the contract never reaches the model.
        if ...:  # the report did not pass
            raise HTTPException(
                status_code=...,
                detail={
                    "message": "payload failed the model-input contract",
                    "schema_version": ...,
                    "failures": ...,  # the report's `by_check`
                },
            )

        frame = ...  # `payload_to_frame`, with FEATURE_COLUMNS in that order
        # `predict_proba` gives one row per patient and one column per class. Take class 1
        # (diabetes) of the only row, as a float.
        probability = ...
        return PredictionResponse(
            prediction=...,  # 1 when `probability` is at least 0.5, otherwise 0
            probability=...,  # rounded to 4 decimals
            model_version=...,  # from `build_info`
            schema_version=...,
        )

    return app


app = create_app()
