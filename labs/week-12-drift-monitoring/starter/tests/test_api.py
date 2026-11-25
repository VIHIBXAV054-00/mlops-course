"""The serving API, tested in-process.

`TestClient` runs the whole app without a server, a port or a container, so these
tests run in CI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from week_12_drift_monitoring.api import PredictionRequest, create_app
from week_12_drift_monitoring.schemas import FEATURE_COLUMNS

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
    """A client backed by a model trained here, so no pipeline run is needed."""
    import os

    import joblib

    from week_12_drift_monitoring.config import load_settings
    from week_12_drift_monitoring.data import build_dataset
    from week_12_drift_monitoring.model import build_model
    from week_12_drift_monitoring.pipeline import _hyperparams

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
    """The pydantic request fields and the pandera contract list the same features."""
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
    """Same patient, same answer."""
    first = client.post("/predict", json=VALID).json()
    second = client.post("/predict", json=VALID).json()
    assert first == second


# ── The contract, over HTTP ─────────────────────────────────────────────────


def test_a_sentinel_zero_is_rejected_by_name(client):
    """`glucose: 0` breaks the contract (`gt=0`), and the 422 names the check."""
    response = client.post("/predict", json={**VALID, "glucose": 0})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "greater_than(0)" in str(detail), detail


def test_an_extra_field_is_rejected(client):
    """`extra="forbid"` mirrors the contract's `Config.strict = True`."""
    response = client.post("/predict", json={**VALID, "cholesterol": 180})
    assert response.status_code == 422


def test_a_missing_field_is_rejected(client):
    payload = {k: v for k, v in VALID.items() if k != "bmi"}
    assert client.post("/predict", json=payload).status_code == 422


def test_field_order_does_not_matter(client):
    """A JSON object has no column order, so the contract is `strict` but not `ordered`."""
    reversed_payload = dict(reversed(list(VALID.items())))
    assert client.post("/predict", json=reversed_payload).status_code == 200


def test_a_non_numeric_value_is_rejected(client):
    assert client.post("/predict", json={**VALID, "age": "fifty"}).status_code == 422


# ── Identity ────────────────────────────────────────────────────────────────


def test_health_reports_who_this_process_is(client):
    """A running container answers "which model are you"."""
    response = client.get("/health")
    assert response.status_code in (200, 503)
    body = response.json()
    if response.status_code == 200:
        assert body["status"] == "ok"
        assert body["schema_version"]
        assert "model_source" in body
    else:
        # No model on disk in a fresh checkout: the readiness probe sees 503.
        assert "not ready" in str(body["detail"])


def test_health_does_not_need_the_registry(client):
    """`/health` reads the record that arrived with the model, never the tracking server."""
    import inspect

    from week_12_drift_monitoring import api

    source = inspect.getsource(api)
    reader = source[source.index("def _provenance("):source.index("def create_app(")]
    for forbidden in ("MlflowClient", "mlflow.tracking", "get_model_version", "requests."):
        assert forbidden not in reader, (
            f"`_provenance()` reaches for {forbidden} — /health must report what "
            "was recorded when the model was published, not what the registry "
            "says right now"
        )


def test_the_openapi_schema_is_generated(client):
    spec = client.get("/openapi.json").json()
    assert "/predict" in spec["paths"]
    assert "/health" in spec["paths"]


# ── Provenance of a fetched model ───────────────────────────────────────────


@pytest.fixture(scope="module")
def fetched_client(tmp_path_factory) -> TestClient:
    """A client set up like a KServe pod: model and `provenance.json` mounted, revision injected."""
    import json
    import os

    import joblib

    from week_12_drift_monitoring.config import load_settings
    from week_12_drift_monitoring.data import build_dataset
    from week_12_drift_monitoring.model import build_model
    from week_12_drift_monitoring.pipeline import _hyperparams

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
    """One image serves many versions, so `/health` reads the record beside the weights."""
    body = fetched_client.get("/health").json()
    assert body["store_version"] == "v2"
    assert body["model_version"] == "3"
    assert body["run_id"] == "cafef00d"
    assert body["gate_verdict"] == "GO"
    assert "fetched at startup" in body["model_source"]
    assert body["model_path"].endswith("model.pkl"), "the reported path is a model file"
    assert "model store v2" in body["model_source"], (
        "read the version from provenance.json, not from STORAGE_URI, which KServe "
        "rewrites to the local mount path"
    )


def test_every_response_names_the_revision_that_produced_it(fetched_client):
    """`K_REVISION` is Knative's own name for the revision, so a traffic split is measurable."""
    assert fetched_client.get("/health").json()["revision"] == "diabetes-predictor-00002"
    scored = fetched_client.post("/predict", json=VALID).json()
    assert scored["revision"] == "diabetes-predictor-00002"
    assert scored["store_version"] == "v2"


def test_fetching_changes_nothing_about_the_prediction(client, fetched_client):
    """Same model, same rows, two ways of getting the file onto the disk."""
    baked = client.post("/predict", json=VALID).json()
    fetched = fetched_client.post("/predict", json=VALID).json()
    assert baked["probability"] == fetched["probability"]


# ── The V1 inference protocol ───────────────────────────────────────────────


def test_the_v1_protocol_route_returns_predictions(client):
    """`{"instances": [...]}` in, `{"predictions": [...]}` out, as KServe clients expect."""
    response = client.post("/v1/models/diabetes:predict", json={"instances": [VALID, VALID]})
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"] == [1, 1]
    assert len(body["probabilities"]) == 2
    assert body["model_name"] == "diabetes"


def test_the_v1_route_enforces_the_same_contract(client):
    """A second route must not be a way around the contract."""
    response = client.post(
        "/v1/models/diabetes:predict", json={"instances": [{**VALID, "glucose": 0}]}
    )
    assert response.status_code == 422
    assert "greater_than(0)" in str(response.json()["detail"]["failures"])


def test_the_v1_route_rejects_an_empty_batch(client):
    """Zero instances is a caller bug, and a 200 with no predictions would hide it."""
    assert client.post("/v1/models/diabetes:predict", json={"instances": []}).status_code == 422


def test_both_routes_agree(client):
    """Also in the smoke suite: this one runs on every commit, that one against a deployment."""
    direct = client.post("/predict", json=VALID).json()
    v1 = client.post("/v1/models/diabetes:predict", json={"instances": [VALID]}).json()
    assert direct["prediction"] == v1["predictions"][0]
    assert direct["probability"] == v1["probabilities"][0]
