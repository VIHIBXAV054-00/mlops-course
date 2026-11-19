"""The serving API.

For eight weeks, training and inference were the same process, on the same
machine, reading the same files, in the same interpreter, with the same
installed packages. Every one of those was a coincidence of convenience, and
every one was load-bearing.

Week 9 split them across a process boundary, a container boundary and a network
boundary. Everything that was shared by accident now has to be shared on
purpose — and the first thing that has to survive the trip is the contract.

Week 5 wrote it and said so in a docstring: `PredictionInput` is "`ModelInput`
minus the label — what a serving request carries", declared `strict = True` and
deliberately NOT `ordered`, because "a request arrives as a JSON object, which
has no column order". That was written four weeks before there was an HTTP
request to receive. This is where the promise gets kept.

WEEK 10 CHANGES THREE THINGS, and all three exist so that a ROLLOUT can be
observed rather than believed:

1. **The model may be FETCHED instead of baked.** Week 9 copied `model.pkl`
   into the image and put the counter-argument on a slide. KServe takes the
   other branch: its storage initializer downloads the model into `/mnt/models`
   before this process starts. Nothing here needed rewriting to allow it —
   `MODEL_PATH` already existed — but `_model_location` now reports WHICH
   branch was taken, because a service that cannot say where its model came
   from cannot be audited.
2. **Provenance travels with the MODEL, not with the image.** A fetched model
   carries a `provenance.json` beside it. One image serving three model
   versions must report three different identities, or `/health` is a lie the
   moment a second revision exists.
3. **Every response names the revision that produced it** (`K_REVISION`, which
   Knative injects into this container). That single field is what turns a
   declared 90/10 traffic split into a measured one.

WEEK 11 ADDS ONE ENDPOINT AND ONE MIDDLEWARE, and changes no behaviour at all.

Every existing response body is byte-identical — `tests/test_api.py` asserts it,
because instrumentation that changes what a service returns is not
instrumentation, it is a rewrite. What is new:

  * `GET /metrics`, serving `prometheus_client`'s own `generate_latest()`. The
    library renders the exposition format; reimplementing that is how you end up
    with a subtly non-conforming scrape endpoint. (Its documented `make_asgi_app`
    mount was tried first and measured — see the comment on the route.)
  * a middleware that measures every request and writes one structured JSON log
    line for it. See `metrics.py` — the label choices are the interesting part.

The framing worth keeping: for ten weeks this service could be CHECKED, at
moments, by somebody who decided to look. It could not be WATCHED. Those are
different capabilities, and the second one is what you need at 03:00 when
nobody decided anything.
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
    who produced it makes a traffic split unmeasurable. Week 10's
    `make split-measure` counts these two fields.
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


def create_app(registry: CollectorRegistry | None = None) -> FastAPI:
    """Build the application.

    `registry` is new in Week 11, and its DEFAULT is the interesting part.

    A `prometheus_client` registry is a NAMESPACE, and registering a metric
    called `http_requests_total` into one twice raises `DuplicateTimeseries`.
    That is correct for a process — two collectors under one name is genuinely
    ambiguous — and it means that if `create_app()` used the process-global
    registry, calling it twice anywhere (a test suite, `bench.py`, a smoke run)
    would crash on the second call. Discovered the direct way: 23 previously
    green tests went red the moment the counters were added.

    So an app with no registry builds a PRIVATE one. The served application at
    the bottom of this file passes the global `REGISTRY` explicitly, and gets
    the `process_*`, `python_gc_*` and `python_info` collectors that
    prometheus_client registers there at import time — free CPU, memory and file
    descriptor metrics that nobody had to write.

    The general shape is worth keeping: **process-global state is a decision,
    so make it something a caller opts into rather than something they inherit.**
    """
    registry = registry if registry is not None else CollectorRegistry()
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
    # you are about to measure. It also means the process fails
    # at startup if the model is missing — which is what a readiness probe is
    # for, and much better than failing on a user's first request.
    app.state.model = joblib.load(model_path) if model_path.exists() else None
    app.state.baked = baked

    # ── Week 11: instrumentation ─────────────────────────────────────────────
    #
    # Order matters and is easy to get wrong. `add_middleware` puts the new
    # middleware OUTERMOST, so this one wraps everything including FastAPI's own
    # exception handling — which is what we want: a request that ends in a 500
    # must still be counted, and a request that is rejected by pydantic before
    # any of our code runs must still show up as a 422.
    metrics = build_metrics(registry)
    logger = build_logger()
    set_model_info(metrics, baked, SCHEMA_VERSION)
    app.state.metrics = metrics
    app.middleware("http")(make_middleware(metrics, logger))

    # ── /metrics, and a documented-but-wrong first attempt ───────────────────
    #
    # `prometheus_client` documents `app.mount("/metrics", make_asgi_app())` as
    # the ASGI integration, and that is what this lab tried first. MEASURED, it
    # does something you would not want on a scrape endpoint:
    #
    #     GET /metrics   -> 307 redirect to /metrics/
    #     GET /metrics/  -> 200 text/plain; version=0.0.4
    #
    # A Starlette `Mount` is a directory, so the router redirects the bare path
    # to the trailing-slash form. Prometheus follows redirects, so it WORKS —
    # and pays an extra round trip every 5 seconds forever, while
    # `curl localhost:5562/metrics` prints nothing at all unless you remember
    # `-L`. Neither is a bug in the library; a mount is genuinely a mount.
    #
    # So this is a plain route serving the library's own `generate_latest()`
    # with its own `CONTENT_TYPE_LATEST`. The exposition format — the escaping,
    # the `# HELP`/`# TYPE` preamble, the float formatting that makes `le="0.25"`
    # match the label in the alerting rules — still comes from the people who
    # wrote it. What we gave up is gzip negotiation, on a payload of a few
    # kilobytes, on a local network.
    #
    # `include_in_schema=False` because this is an operational interface for the
    # collector, not part of the API's contract with a caller.
    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    def _score(app: FastAPI, request: PredictionRequest) -> PredictionResponse:
        """The one place a patient is scored. Both routes go through here."""
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model not loaded")

        payload = request.model_dump()

        report = validate_payload(payload)
        if not report["passed"]:
            # WEEK 11: count it before raising.
            #
            # The label is the CHECK NAME — a small, closed set fixed by the
            # pandera schema — and never the field value that failed, which is
            # attacker-controlled and unbounded. A rising
            # model_contract_violations_total is a caller changing under you,
            # which is a real incident that no generic web dashboard surfaces:
            # from the outside it looks like a perfectly healthy service
            # returning perfectly correct 422s.
            #
            # And note what this deliberately is NOT: a 422 does not count
            # against the availability SLO. The service did exactly what Week 5
            # designed it to do. Counting a caller's bad data as our failure
            # would let anyone burn our error budget by sending rubbish.
            # TODO(student) Exercise 1 — count the violation, by CHECK NAME.
            #
            # `report["by_check"]` maps a check name to how many times it
            # failed. The label must be the check name — a small closed set
            # fixed by the pandera schema — and never the offending value,
            # which is attacker-controlled and unbounded.
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

        # WEEK 11: the two signals that are about the MODEL rather than the
        # server. Everything the middleware measures would be identical for a
        # service that returned the weather; these two would not.
        #
        # `outcome` has exactly two values, so the cardinality cost is 2. The
        # score is a histogram because the interesting thing about a stream of
        # probabilities is its SHAPE — a model that has started answering 0.5 to
        # everything is broken in a way that no latency or error-rate graph can
        # show. Watching that shape MOVE, against a reference, is drift, and
        # drift is Week 12; this week only ever emits it.
        # TODO(student) Exercise 1 — the two signals that are about the MODEL
        # rather than the server: count the prediction by outcome
        # ("positive"/"negative", so the cardinality cost is 2) and observe the
        # probability on the score histogram.

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


# THE served application, and the only place the process-global registry is
# used. See create_app's docstring: passing REGISTRY here is what brings in
# prometheus_client's own `process_*`, `python_gc_*` and `python_info`
# collectors — CPU, resident memory and open file descriptors, for free, because
# they were registered there at import time.
app = create_app(REGISTRY)
