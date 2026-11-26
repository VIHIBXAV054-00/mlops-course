"""The serving API: `/health`, `/predict` and KServe's V1 route.

The model is read from MODEL_PATH: baked into the image (Week 9), or copied into
/mnt/models by KServe from the model store. `/health` reports the model's provenance
from the `provenance.json` next to it, and every response names the revision that
answered (`K_REVISION`, set by Knative).
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

# ── The request model ────────────────────────────────────────────────────────
#
# BRIDGING PANDERA TO PYDANTIC — a decision, not a detail.
#
# FastAPI validates request bodies with pydantic; this project's contract is a
# pandera `DataFrameModel`. Three options were considered:
#
#   (a) hand-write a pydantic model, and add a TEST asserting its field set
#       equals PredictionInput's;
#   (b) generate the pydantic model from the pandera schema at import time;
#   (c) accept a raw dict and validate only with pandera.
#
# (a) was chosen. (b) is less drift-prone and much harder to read. (c) is one
# contract but loses FastAPI's generated OpenAPI docs, which are half the
# reason to use FastAPI at all.
#
# The honest cost of (a) is that the field list exists twice. That is exactly
# the drift Week 5 spent a week preventing — so it is not left to vigilance:
# `test_api.py::test_the_request_model_matches_the_pandera_contract` fails the
# moment the two disagree. It is the same device `schemas.py` already uses to
# keep `ModelInput` and `data.py` in step.
#
# Note this model only enforces TYPES and presence. The semantic rules — no
# sentinel zeros, plausible ranges — stay in pandera, so there is one place
# where "what the model may see" is defined.


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
    """One score, and enough identity to attribute it.

    `store_version` and `revision` are new in Week 10 and they are not
    decoration: with two revisions behind one URL, a response that cannot say
    who produced it makes a traffic split unmeasurable. Exercise 3 counts these
    two fields and nothing else.
    """

    prediction: int
    probability: float
    model_version: str | None
    store_version: str | None
    revision: str | None
    schema_version: str


class InstancesRequest(BaseModel):
    """KServe's V1 protocol body: `{"instances": [ {...}, {...} ]}`.

    The same shape `mlflow models serve` accepted in Week 9 (`instances`), and
    the reason it exists here is INTERCHANGEABILITY: a platform's tooling —
    KServe's own clients, its docs, its examples — speaks this protocol, so a
    model that speaks it can be swapped in without rewriting the caller.

    It is a second door to the same room: every instance goes through the same
    pandera contract as `POST /predict`, so conforming to a protocol did not
    cost us the contract. If it had, it would not be worth doing.
    """

    model_config = ConfigDict(extra="forbid")

    instances: list[PredictionRequest] = Field(..., min_length=1)


class HealthResponse(BaseModel):
    """What a running container says when you ask it who it is.

    This is the last link of the traceability chain. Week 6 ended with eight
    links, from a registry alias down to the gate verdict; Week 9 added the one
    that leaves the building, so a pod can be asked *which model are you* and
    the answer joins up with `make trace`.

    Nothing here is read from the registry — not in Week 9 when it was baked in
    at build time, and not in Week 10 when it arrives beside the model. If
    `/health` queried MLflow, the container would need the tracking server at
    runtime, every test would need a stack, and two identical images could give
    different answers.

    New in Week 10: `store_version` and `revision`. A ROLLOUT is a claim about
    which model each revision is serving, and a claim nobody can check is a
    comment.
    """

    status: str
    model_version: str | None
    run_id: str | None
    gate_verdict: str | None
    schema_version: str
    model_source: str
    # Week 10.
    store_version: str | None = None
    revision: str | None = None
    model_path: str | None = None


# ── Where the model came from ────────────────────────────────────────────────
#
# THIS IS THE WEEK'S DESIGN DECISION, and it is eleven lines of code.
#
# Week 9 baked the model into the image: zero runtime dependencies, an
# immutable artifact, provenance in the image digest. It also put the
# counter-argument on a slide, because KServe takes the other branch — the
# storage initializer downloads whatever `storageUri` points at into
# `/mnt/models` before this process starts, so ONE image can serve MANY models
# and a new model version is not a new build.
#
# Both branches are legitimate. What is NOT legitimate is being unable to say
# which one you took, so this function reports it and `/health` publishes it.
#
# Precedence, and the order is deliberate:
#   1. MODEL_PATH        — an explicit instruction wins. KServe manifests set it.
#   2. /mnt/models       — the fetched model, if the storage initializer ran.
#   3. models/model.pkl  — the baked (Week 9) or working-tree model.
#
# The default for KSERVE_MODEL_DIR is KServe's own mount point, so no
# configuration is needed for the common case.

MOUNT_DIR_ENV = "KSERVE_MODEL_DIR"
DEFAULT_MOUNT_DIR = "/mnt/models"


def _mount_dir() -> Path:
    return Path(os.getenv(MOUNT_DIR_ENV, DEFAULT_MOUNT_DIR))


def _model_location(settings: Any) -> tuple[Path, str]:
    """Return (path to the model, a human-readable description of its origin).

    MEASURED, and worth knowing: KServe **rewrites** `STORAGE_URI` inside the
    container to the local mount path once the model is there, so reading that
    variable at runtime tells you where the model IS, not where it came FROM.
    The `storageUri` you wrote is a fact about the manifest; the version identity
    a pod can actually vouch for is the one in `provenance.json`, which travelled
    with the weights. Do not report a URI you did not read.
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
    """Who this model is, according to whoever published it.

    Two sources, in precedence order, and the first one is new this week:

      1. `provenance.json` NEXT TO THE MODEL — written by `make model-publish`
         when the model was put in the store. Provenance travels with the
         model, so one image can serve three versions and tell them apart.
      2. `models/baked.json` — Week 9's build-time record, still correct for a
         baked image.

    Neither present means a working tree, which is reported honestly rather
    than faked.
    """
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


def create_app() -> FastAPI:
    settings = load_settings()
    model_path, origin = _model_location(settings)
    baked = _provenance(model_path, settings)
    # Knative injects these into every user container. Free, exact, and the
    # only honest way to attribute a response to a revision — a header we
    # invented ourselves would just be us restating our own opinion.
    revision = os.getenv("K_REVISION")

    app = FastAPI(
        title="Diabetes prediction",
        version=SCHEMA_VERSION,
        description=(
            "Online inference for the model this course has been building since "
            "Week 1. The request contract is the training contract minus the label."
        ),
    )

    # Loaded ONCE, at startup, not per request.
    #
    # Deserialising a scikit-learn Pipeline takes milliseconds and a request
    # budget is milliseconds, so per-request loading would dominate the latency
    # you are about to measure in Exercise 3. It also means the process fails
    # at startup if the model is missing — which is what a readiness probe is
    # for, and much better than failing on a user's first request.
    app.state.model = joblib.load(model_path) if model_path.exists() else None
    app.state.baked = baked

    def _score(app: FastAPI, request: PredictionRequest) -> PredictionResponse:
        """The one place a patient is scored. Both routes go through here."""
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model not loaded")

        payload = request.model_dump()

        report = validate_payload(payload)
        if not report["passed"]:
            # 422, naming the field AND the check that failed. A caller who
            # gets "invalid input" learns nothing; a caller who gets
            # "glucose failed greater_than(0)" can fix their request.
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
            model_version=baked.get("model_version"),
            store_version=baked.get("store_version"),
            revision=revision,
            schema_version=SCHEMA_VERSION,
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness, readiness, and identity in one endpoint.

        Returns 503 while the model is not loaded, so a readiness probe can
        hold traffic away from a pod that is not ready to serve. A 200 here is
        the promise that this process can answer a real request.
        """
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
            # Two different facts, and both matter this week: WHERE the model
            # came from (fetched or baked) and WHO said what it is.
            model_source=f"{origin} — provenance: {baked.get('source', 'unknown')}",
            store_version=baked.get("store_version"),
            revision=revision,
            model_path=str(model_path),
        )

    @app.post("/predict", response_model=PredictionResponse)
    def predict(request: PredictionRequest) -> PredictionResponse:
        """Score one patient.

        TWO validation layers, and the split is deliberate:

          1. pydantic, above — types and presence, enforced by FastAPI before
             this function is entered. Produces a 422 automatically.
          2. pandera, here — the SEMANTIC contract. This is the one that knows
             `glucose: 0` is a sentinel rather than a reading, because Week 5
             wrote `pa.Field(gt=0, nullable=True)` and that rule has to hold at
             inference time or it was never a rule at all.

        Layer 2 is what `mlflow models serve` cannot do for you. It validates
        against the model's *signature* — dtypes and column names — and will
        score a physiologically impossible patient without complaint.
        """
        return _score(app, request)

    @app.post("/v1/models/{model_name}:predict")
    def v1_predict(model_name: str, request: InstancesRequest) -> dict[str, Any]:
        """KServe's V1 protocol, on top of the same contract.

        Two doors, one room. This route exists so the service is
        INTERCHANGEABLE with a platform's tooling — KServe's clients, docs and
        examples all speak `{"instances": [...]}` and expect
        `{"predictions": [...]}` back — and it reuses `_score`, so the pandera
        contract, the 422 and the identity fields are identical on both paths.

        `model_name` is accepted and deliberately ignored beyond an echo: this
        pod serves exactly one model, and pretending otherwise would be a
        multi-model-serving feature nobody asked for.
        """
        scores = [_score(app, instance) for instance in request.instances]
        return {
            "predictions": [s.prediction for s in scores],
            "probabilities": [s.probability for s in scores],
            "model_name": model_name,
            "store_version": baked.get("store_version"),
            "revision": revision,
        }

    return app


app = create_app()
