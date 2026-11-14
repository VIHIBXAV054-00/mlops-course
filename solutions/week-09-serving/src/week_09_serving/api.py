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
from .inference import payload_to_frame, validate_payload
from .schemas import FEATURE_COLUMNS, SCHEMA_VERSION


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

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """503 until the model is loaded, so a readiness probe sends no traffic to this pod."""
        if app.state.model is None:
            raise HTTPException(
                status_code=503,
                detail=f"model not loaded from {model_path}: this pod is not ready",
            )
        return HealthResponse(
            status="ok",
            model_version=build_info.get("model_version"),
            run_id=build_info.get("run_id"),
            gate_verdict=build_info.get("gate_verdict"),
            schema_version=SCHEMA_VERSION,
            model_source=build_info.get("source", "unknown"),
        )

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        """Score one patient. FastAPI has checked the types; the contract checks the values."""
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model not loaded")

        payload = request.model_dump()
        report = validate_payload(payload)
        if not report["passed"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "payload failed the model-input contract",
                    "schema_version": SCHEMA_VERSION,
                    "failures": report["by_check"],
                },
            )

        frame = payload_to_frame(payload)[list(FEATURE_COLUMNS)]
        probability = float(app.state.model.predict_proba(frame)[0, 1])
        return PredictionResponse(
            prediction=int(probability >= 0.5),
            probability=round(probability, 4),
            model_version=build_info.get("model_version"),
            schema_version=SCHEMA_VERSION,
        )

    return app


app = create_app()
