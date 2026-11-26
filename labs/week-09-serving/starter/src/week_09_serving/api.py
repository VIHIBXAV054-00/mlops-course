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
    app.state.baked = baked

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="not ready: no model loaded")
        return HealthResponse(
            status="ok",
            model_version=baked.get("model_version"),
            run_id=baked.get("run_id"),
            gate_verdict=baked.get("gate_verdict"),
            schema_version=SCHEMA_VERSION,
            model_source=baked.get("source", "working tree (not baked)"),
        )

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        payload = request.model_dump()
        report = validate_payload(payload)
        if not report.get("passed"):
            raise HTTPException(
                status_code=422,
                detail={
                    "failures": report.get("by_check", {}),
                    "schema_version": SCHEMA_VERSION,
                },
            )
        frame = payload_to_frame(payload)
        # Convert sentinel zeros to nulls, select features in contract order,
        # then cast to plain float64 so sklearn's SimpleImputer gets NaN not pd.NA.
        from .validation import to_nullable
        numeric = to_nullable(frame)[list(FEATURE_COLUMNS)].astype("float64")
        proba = float(app.state.model.predict_proba(numeric)[0][1])
        return PredictionResponse(
            prediction=1 if proba >= 0.5 else 0,
            probability=round(proba, 4),
            model_version=baked.get("model_version"),
            schema_version=SCHEMA_VERSION,
        )

    return app


app = create_app()
