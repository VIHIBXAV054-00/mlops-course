"""The serving API, tested in-process.

`TestClient` runs the whole ASGI app without a server, a port or a container,
which is the single most important test-design decision of the week: the entire
API surface — validation, the 422 shape, `/health` — is testable in the
autograder, where there is no Docker and no cluster.

Resist trading this for an "integration test" that shells out to uvicorn and
polls a port. It would be slower, flakier, and would test the same code.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from week_10_kserve_rollout.api import PredictionRequest, create_app
from week_10_kserve_rollout.schemas import FEATURE_COLUMNS

pytestmark = pytest.mark.data

VALID = {
    "pregnancies": 6,
    "glucose": 148,
    "blood_pressure": 72,
    "skin_thickness": 35,
    "insulin": 125,
    "bmi": 33.6,
    "diabetes_pedigree": 0.627,
    "age": 50,
}


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    """A client backed by a model this fixture builds itself.

    Deliberately NOT `models/model.pkl` from the working tree. That file is
    git-ignored, so it does not exist in the autograder, on a fresh clone, or
    for a student who has not run the pipeline yet — and a test suite that
    quietly skips its most important assertions in exactly those situations is
    the failure mode this course keeps naming.

    Training a `Pipeline(SimpleImputer, StandardScaler, LogisticRegression)` on
    the committed `data/diabetes.csv` takes well under a second, so the API
    surface is testable with no pipeline run, no stack and no container.
    """
    import os

    import joblib

    from week_10_kserve_rollout.config import load_settings
    from week_10_kserve_rollout.data import build_dataset
    from week_10_kserve_rollout.model import build_model
    from week_10_kserve_rollout.pipeline import _hyperparams

    settings = load_settings()
    x_train, _, y_train, _ = build_dataset(settings)
    model = build_model(settings.model_family, _hyperparams(settings), settings,
                        impute="median")
    model.fit(x_train, y_train)

    path = tmp_path_factory.mktemp("model") / "model.pkl"
    joblib.dump(model, path)

    os.environ["MODEL_PATH"] = str(path)
    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        os.environ.pop("MODEL_PATH", None)


# ── The bridge that must not drift ──────────────────────────────────────────


def test_the_request_model_matches_the_pandera_contract():
    """The load-bearing test of `api.py`.

    The request fields are hand-written in pydantic while the semantic contract
    lives in pandera, so the field list exists twice — exactly the drift Week 5
    spent a week preventing. This is what stops it being left to vigilance.

    Same device `schemas.py` already uses to keep `ModelInput` and `data.py` in
    step. If you add a feature, this fails until both sides know about it.
    """
    assert set(PredictionRequest.model_fields) == set(FEATURE_COLUMNS), (
        "the API request model and the pandera contract disagree about the "
        "feature set — one of them was edited and the other was not"
    )


# ── Scoring ─────────────────────────────────────────────────────────────────


def test_a_valid_payload_scores(client):
    response = client.post("/predict", json=VALID)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prediction"] in (0, 1)
    assert 0.0 <= body["probability"] <= 1.0
    assert body["schema_version"]


def test_the_response_is_deterministic(client):
    """Same patient, same answer. Obvious, and worth an assertion.

    An endpoint that returns a different probability for an identical request
    has non-determinism somewhere — a re-fitted model, a random seed, a race —
    and it will be discovered by a user rather than by you.
    """
    first = client.post("/predict", json=VALID).json()
    second = client.post("/predict", json=VALID).json()
    assert first == second


# ── The contract, over HTTP ─────────────────────────────────────────────────


def test_a_sentinel_zero_is_rejected_by_name(client):
    """Training-serving skew, reproduced over HTTP, in one request.

    `glucose: 0` is the sentinel Week 5 declared illegal (`gt=0, nullable=True`
    — "missing is honest; zero is a lie"). `mlflow models serve` scores this
    happily, because it validates against the model's SIGNATURE, not against
    the contract. That difference is why this service exists.
    """
    response = client.post("/predict", json={**VALID, "glucose": 0})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "greater_than(0)" in str(detail), detail


def test_an_extra_field_is_rejected(client):
    """`extra="forbid"` mirrors the contract's `Config.strict = True`.

    A caller sending an unexpected field is usually sending it for a reason —
    a renamed column, a version mismatch — and silently ignoring it is how you
    serve confident predictions from the wrong data.
    """
    response = client.post("/predict", json={**VALID, "cholesterol": 180})
    assert response.status_code == 422


def test_a_missing_field_is_rejected(client):
    payload = {k: v for k, v in VALID.items() if k != "bmi"}
    assert client.post("/predict", json=payload).status_code == 422


def test_field_order_does_not_matter(client):
    """`PredictionInput` is `strict` but deliberately NOT `ordered`.

    Week 5's reasoning, four weeks before there was an HTTP request to receive:
    "a request arrives as a JSON object, which has no column order".
    Asserting order here would test our own serialiser, not the caller.
    """
    reversed_payload = dict(reversed(list(VALID.items())))
    assert client.post("/predict", json=reversed_payload).status_code == 200


def test_a_non_numeric_value_is_rejected(client):
    assert client.post("/predict", json={**VALID, "age": "fifty"}).status_code == 422


# ── Identity ────────────────────────────────────────────────────────────────


def test_health_reports_who_this_process_is(client):
    """The last link of the traceability chain.

    A running container has to be able to answer "which model are you", and the
    answer has to join up with `make trace`.
    """
    response = client.get("/health")
    assert response.status_code in (200, 503)
    body = response.json()
    if response.status_code == 200:
        assert body["status"] == "ok"
        assert body["schema_version"]
        assert "model_source" in body
    else:
        # No model on disk in a fresh checkout. Honest, and exactly what a
        # readiness probe needs to see.
        assert "not ready" in str(body["detail"])


def test_health_does_not_need_the_registry(client):
    """`/health` reads what arrived WITH THE MODEL, never the tracking server.

    If it queried MLflow, the container would need the registry at runtime,
    every test would need a stack, and two identical images could give
    different answers depending on what somebody promoted that morning.

    Week 10 changes where the record comes from — a `provenance.json` beside a
    fetched model rather than a `baked.json` inside the image — and does not
    change this rule at all. The lookup happens once, at publish time, by a
    human who has a stack; the pod only ever reads a file.
    """
    import inspect

    from week_10_kserve_rollout import api

    source = inspect.getsource(api)
    reader = source[source.index("def _provenance("):source.index("def create_app(")]
    for forbidden in ("MlflowClient", "mlflow.tracking", "get_model_version", "requests."):
        assert forbidden not in reader, (
            f"`_provenance()` reaches for {forbidden} — /health must report what "
            "was recorded when the model was published, not what the registry "
            "says right now"
        )


def test_the_openapi_schema_is_generated(client):
    """Half the reason to use FastAPI rather than a bare dict endpoint."""
    spec = client.get("/openapi.json").json()
    assert "/predict" in spec["paths"]
    assert "/health" in spec["paths"]


# ── Week 10: the model came from somewhere, and the response says where ──────


@pytest.fixture(scope="module")
def fetched_client(tmp_path_factory) -> TestClient:
    """A client in the shape KServe produces: model mounted, revision injected.

    Two environment variables are all that separates Week 9's deployment from
    Week 10's — `MODEL_PATH` pointing into the mount and `K_REVISION` supplied by
    Knative — so the fetched path is testable with no cluster at all. The
    `provenance.json` beside the model is what `make model-publish` writes.
    """
    import json
    import os

    import joblib

    from week_10_kserve_rollout.config import load_settings
    from week_10_kserve_rollout.data import build_dataset
    from week_10_kserve_rollout.model import build_model
    from week_10_kserve_rollout.pipeline import _hyperparams

    settings = load_settings()
    x_train, _, y_train, _ = build_dataset(settings)
    model = build_model(settings.model_family, _hyperparams(settings), settings,
                        impute="median")
    model.fit(x_train, y_train)

    mount = tmp_path_factory.mktemp("mnt-models")
    joblib.dump(model, mount / "model.pkl")
    (mount / "provenance.json").write_text(
        json.dumps({
            "store_version": "v2",
            "model_version": "3",
            "run_id": "cafef00d",
            "gate_verdict": "GO",
            "family": "logreg",
            "source": "model store v2",
        })
    )

    os.environ["KSERVE_MODEL_DIR"] = str(mount)
    os.environ["MODEL_PATH"] = str(mount / "model.pkl")
    os.environ["STORAGE_URI"] = "pvc://diabetes-models/v2"
    os.environ["K_REVISION"] = "diabetes-predictor-00002"
    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        for name in ("KSERVE_MODEL_DIR", "MODEL_PATH", "STORAGE_URI", "K_REVISION"):
            os.environ.pop(name, None)


def test_health_reports_the_fetched_provenance_not_the_images(fetched_client):
    """Provenance travels with the MODEL.

    Week 9 read `models/baked.json`, which was correct when one image meant one
    model. One image serving three versions has to read the record that arrived
    with the weights, or `/health` describes the wrong model the moment a second
    revision exists.
    """
    body = fetched_client.get("/health").json()
    assert body["store_version"] == "v2"
    assert body["model_version"] == "3"
    assert body["run_id"] == "cafef00d"
    assert body["gate_verdict"] == "GO"
    assert "fetched at startup" in body["model_source"]
    assert body["model_path"].endswith("model.pkl"), "the reported path is a model file"
    assert "model store v2" in body["model_source"], (
        "the version identity must come from provenance.json, which travelled with "
        "the weights — NOT from STORAGE_URI, which KServe rewrites in the "
        "container to the local mount path once the model is there"
    )


def test_every_response_names_the_revision_that_produced_it(fetched_client):
    """The field that makes a traffic split measurable.

    `K_REVISION` is injected by Knative, so this is the platform's own name for
    the revision rather than a label we made up and might disagree with.
    """
    assert fetched_client.get("/health").json()["revision"] == "diabetes-predictor-00002"
    scored = fetched_client.post("/predict", json=VALID).json()
    assert scored["revision"] == "diabetes-predictor-00002"
    assert scored["store_version"] == "v2"


def test_fetching_changes_nothing_about_the_prediction(client, fetched_client):
    """Same model, same rows, two ways of getting the file onto the disk.

    If this ever fails, the storage mechanism has started affecting the answer,
    which would make every measurement in this week's lab meaningless.
    """
    baked = client.post("/predict", json=VALID).json()
    fetched = fetched_client.post("/predict", json=VALID).json()
    assert baked["probability"] == fetched["probability"]


# ── Week 10: the V1 inference protocol ──────────────────────────────────────


def test_the_v1_protocol_route_returns_predictions(client):
    """`{"instances": [...]}` in, `{"predictions": [...]}` out.

    The shape `mlflow models serve` accepted in Week 9 and the one KServe's own
    clients speak. Interchangeability is the point: a caller written against the
    platform's protocol works against this service unchanged.
    """
    response = client.post("/v1/models/diabetes:predict", json={"instances": [VALID, VALID]})
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"] == [1, 1]
    assert len(body["probabilities"]) == 2
    assert body["model_name"] == "diabetes"


def test_the_v1_route_enforces_the_same_contract(client):
    """A second door must not be a second, weaker set of rules.

    Serving a standard protocol is only worth doing if it did not cost the
    contract — otherwise the way to bypass Week 5 is to send your request to a
    different path.
    """
    response = client.post(
        "/v1/models/diabetes:predict", json={"instances": [{**VALID, "glucose": 0}]}
    )
    assert response.status_code == 422
    assert "greater_than(0)" in str(response.json()["detail"]["failures"])


def test_the_v1_route_rejects_an_empty_batch(client):
    """Zero instances is a caller bug, and a 200 with no predictions hides it."""
    assert client.post("/v1/models/diabetes:predict", json={"instances": []}).status_code == 422


def test_both_routes_agree(client):
    """Asserted here as well as in the smoke suite, on purpose: this one runs on
    every commit, the smoke suite runs against a deployment."""
    direct = client.post("/predict", json=VALID).json()
    v1 = client.post("/v1/models/diabetes:predict", json={"instances": [VALID]}).json()
    assert direct["prediction"] == v1["predictions"][0]
    assert direct["probability"] == v1["probabilities"][0]
