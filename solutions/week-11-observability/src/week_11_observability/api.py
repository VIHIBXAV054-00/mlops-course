"""The serving API: validate a patient against the pandera contract and score it.

It also serves `/metrics`, and a middleware measures and logs every request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, generate_latest
from pydantic import BaseModel, ConfigDict, Field

from .config import load_settings
from .inference import payload_to_frame, validate_payload
from .metrics import build_logger, build_metrics, make_middleware, set_model_info
from .schemas import FEATURE_COLUMNS, SCHEMA_VERSION

# The request model mirrors PredictionInput. test_api.py checks that the field lists match.
# Pydantic checks types and presence, pandera checks the values.


class PredictionRequest(BaseModel):
    """One patient. Field names and order mirror `MODEL_INPUT_COLUMNS`."""

    model_config = ConfigDict(extra="forbid")  # mirrors Config.strict = True

    pregnancies: float = Field(..., description="Number of pregnancies (a real zero is legal)")
    glucose: float = Field(..., description="Plasma glucose. 0 is a missing value, not a reading")
    blood_pressure: float = Field(..., description="Diastolic blood pressure (mm Hg)")
    skin_thickness: float = Field(..., description="Triceps skin fold thickness (mm)")
    insulin: float = Field(..., description="2-hour serum insulin (mu U/ml)")
    bmi: float = Field(..., description="Body mass index")
    diabetes_pedigree: float = Field(..., description="Diabetes pedigree function")
    age: float = Field(..., description="Age in years")


class PredictionResponse(BaseModel):
    """One score, with the model version and revision that produced it."""

    prediction: int
    probability: float
    model_version: str | None
    store_version: str | None
    revision: str | None
    schema_version: str


class InstancesRequest(BaseModel):
    """KServe's V1 protocol body: `{"instances": [ {...}, {...} ]}`."""

    model_config = ConfigDict(extra="forbid")

    instances: list[PredictionRequest] = Field(..., min_length=1)


class HealthResponse(BaseModel):
    """What a running container says when you ask it which model it serves.

    Read from files beside the model, never from the registry.
    """

    status: str
    model_version: str | None
    run_id: str | None
    gate_verdict: str | None
    schema_version: str
    model_source: str
    store_version: str | None = None
    revision: str | None = None
    model_path: str | None = None


# Where the model comes from, in order: MODEL_PATH, then /mnt/models (fetched by
# KServe's storage initializer), then models/model.pkl (baked or working tree).

MOUNT_DIR_ENV = "KSERVE_MODEL_DIR"
DEFAULT_MOUNT_DIR = "/mnt/models"


def _mount_dir() -> Path:
    return Path(os.getenv(MOUNT_DIR_ENV, DEFAULT_MOUNT_DIR))


def _model_location(settings: Any) -> tuple[Path, str]:
    """Return the path to the model and a description of where it came from.

    KServe rewrites STORAGE_URI to the local mount path, so it cannot say where the model came from.
    """
    mount = _mount_dir()
    explicit = os.getenv("MODEL_PATH")
    if explicit:
        path = Path(explicit)
        if mount in path.parents:
            return path, f"fetched at startup, mounted at {mount}"
        return path, f"MODEL_PATH={explicit}"
    fetched = mount / "model.pkl"
    if fetched.exists():
        return fetched, f"fetched at startup, mounted at {mount}"
    local = settings.models_dir / "model.pkl"
    if (settings.project_root / "models" / "baked.json").exists():
        return local, "baked into the image at build time"
    return local, "read from the working tree"


def _provenance(model_path: Path, settings: Any) -> dict[str, Any]:
    """Read provenance.json beside the model, else models/baked.json, else report a working tree."""
    beside = model_path.parent / "provenance.json"
    if beside.exists():
        record = json.loads(beside.read_text())
        record.setdefault("source", "model store")
        return record
    baked = settings.project_root / "models" / "baked.json"
    if baked.exists():
        return json.loads(baked.read_text())
    return {
        "model_version": None,
        "run_id": None,
        "gate_verdict": None,
        "store_version": None,
        "source": "working tree (not baked, not fetched)",
    }


def create_app(registry: CollectorRegistry | None = None) -> FastAPI:
    """Build the application.

    With no registry it builds a private one, so a test can call create_app() twice.
    """
    registry = registry if registry is not None else CollectorRegistry()
    settings = load_settings()
    model_path, origin = _model_location(settings)
    baked = _provenance(model_path, settings)
    # Knative sets K_REVISION in every container it runs
    revision = os.getenv("K_REVISION")

    app = FastAPI(
        title="Diabetes prediction",
        version=SCHEMA_VERSION,
        description=(
            "Online inference for the model this course has been building since "
            "Week 1. The request contract is the training contract minus the label."
        ),
    )

    # loaded once at startup, so a missing model fails the readiness probe, not a request
    app.state.model = joblib.load(model_path) if model_path.exists() else None
    app.state.baked = baked

    # The middleware is outermost, so it also counts 500s and pydantic's 422s.
    metrics = build_metrics(registry)
    logger = build_logger()
    set_model_info(metrics, baked, SCHEMA_VERSION)
    app.state.metrics = metrics
    app.middleware("http")(make_middleware(metrics, logger))

    # A plain route, not make_asgi_app(): a mount redirects /metrics to /metrics/.
    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    def _score(app: FastAPI, request: PredictionRequest) -> PredictionResponse:
        """Score one patient. Both routes call this."""
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model not loaded")

        payload = request.model_dump()

        report = validate_payload(payload)
        if not report["passed"]:
            # Label by check name, never by the value. A 422 does not count against the SLO.
            for check, failures in report["by_check"].items():
                metrics["violations"].labels(check=str(check)).inc(int(failures))
            # name the field and the check, so the caller can fix the request
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

        # two signals about the model rather than the server
        outcome = "positive" if probability >= 0.5 else "negative"
        metrics["predictions"].labels(outcome=outcome).inc()
        metrics["score"].observe(probability)

        return PredictionResponse(
            prediction=int(probability >= 0.5),
            probability=round(probability, 4),
            model_version=baked.get("model_version"),
            store_version=baked.get("store_version"),
            revision=revision,
            schema_version=SCHEMA_VERSION,
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness, readiness and identity. Returns 503 while the model is not loaded."""
        if app.state.model is None:
            raise HTTPException(
                status_code=503,
                detail=f"model not loaded from {model_path} — this pod is not ready",
            )
        return HealthResponse(
            status="ok",
            model_version=baked.get("model_version"),
            run_id=baked.get("run_id"),
            gate_verdict=baked.get("gate_verdict"),
            schema_version=SCHEMA_VERSION,
            # where the model came from, and who recorded its identity
            model_source=f"{origin} — provenance: {baked.get('source', 'unknown')}",
            store_version=baked.get("store_version"),
            revision=revision,
            model_path=str(model_path),
        )

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        """Score one patient.

        Pydantic checks types and presence (422). Pandera checks the values, such as glucose > 0.
        """
        return _score(app, request)

    @app.post("/v1/models/{model_name}:predict")
    def v1_predict(model_name: str, request: InstancesRequest) -> dict[str, Any]:
        """KServe's V1 protocol, with the same contract. `model_name` is only echoed back."""
        scores = [_score(app, instance) for instance in request.instances]
        return {
            "predictions": [s.prediction for s in scores],
            "probabilities": [s.probability for s in scores],
            "model_name": model_name,
            "store_version": baked.get("store_version"),
            "revision": revision,
        }

    return app


# The served app uses the global registry, which adds the process_* and python_* metrics.
app = create_app(REGISTRY)
