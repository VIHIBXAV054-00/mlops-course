"""The prediction service and the benchmark, tested in-process.

`TestClient` runs the FastAPI app without a server, a port or a container, so
these tests need no stack, no Docker and no cluster.
"""

from __future__ import annotations

import time
import typing

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from week_09_serving.api import PredictionRequest, create_app
from week_09_serving.schemas import FEATURE_COLUMNS, PredictionInput

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
    """A client for an app whose model this fixture trains on `data/diabetes.csv`.

    `models/model.pkl` is not in Git, so the tests do not depend on it.
    """
    import os

    import joblib

    from week_09_serving.config import load_settings
    from week_09_serving.data import build_dataset
    from week_09_serving.model import build_model
    from week_09_serving.pipeline import _hyperparams

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


# ── The request model (provided) ────────────────────────────────────────────


def test_the_request_model_matches_the_pandera_contract():
    """The Pydantic fields and the contract's columns must agree, and so must which may be null."""
    assert set(PredictionRequest.model_fields) == set(FEATURE_COLUMNS), (
        "the API request model and the pandera contract disagree about the "
        "feature set: one of them was edited and the other was not"
    )
    columns = PredictionInput.to_schema().columns
    for name, field in PredictionRequest.model_fields.items():
        accepts_null = not field.is_required() or type(None) in typing.get_args(field.annotation)
        assert accepts_null == columns[name].nullable, (
            f"{name}: the contract says nullable={columns[name].nullable}, but the request "
            f"model {'accepts' if accepts_null else 'rejects'} null"
        )


# ── What the image records (provided) ───────────────────────────────────────


class _Version:
    def __init__(self, version, run_id):
        self.version, self.run_id = version, run_id


def test_the_image_names_the_champion_only_when_it_holds_the_champion():
    from week_09_serving.cli import bake_values

    same = bake_values("GO", "run-a", _Version(2, "run-a"))
    assert same["MODEL_VERSION"] == "2" and same["MODEL_SOURCE"] == "registry champion"

    other = bake_values("GO", "run-b", _Version(2, "run-a"))
    assert other["MODEL_VERSION"] == "unknown", (
        "the local model was trained by another run, so the image must not claim version 2"
    )

    offline = bake_values(None, None, None)
    assert offline == {"MODEL_VERSION": "unknown", "RUN_ID": "unknown",
                       "GATE_VERDICT": "unknown", "MODEL_SOURCE": "local models/model.pkl"}


# ── Your service (Exercise 2) ───────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_a_valid_payload_scores(client):
    response = client.post("/predict", json=VALID)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prediction"] in (0, 1)
    assert 0.0 <= body["probability"] <= 1.0
    assert body["schema_version"]


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_the_response_is_deterministic(client):
    first = client.post("/predict", json=VALID)
    second = client.post("/predict", json=VALID)
    assert first.status_code == 200, first.text
    assert first.json() == second.json()


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_a_sentinel_zero_is_rejected_by_name(client):
    """pydantic accepts `glucose: 0`; the contract rejects it and says which check failed."""
    response = client.post("/predict", json={**VALID, "glucose": 0})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "greater_than(0)" in str(detail), (
        f"the 422 should name the failed check, greater_than(0); got {detail}"
    )


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_a_missing_measurement_is_scored(client):
    """A value that was not measured is sent as null; the model's imputer fills it in."""
    response = client.post("/predict", json={**VALID, "insulin": None})
    assert response.status_code == 200, response.text
    assert 0.0 <= response.json()["probability"] <= 1.0


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_an_extra_field_is_rejected(client):
    response = client.post("/predict", json={**VALID, "cholesterol": 180})
    assert response.status_code == 422


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_a_missing_field_is_rejected(client):
    payload = {k: v for k, v in VALID.items() if k != "bmi"}
    assert client.post("/predict", json=payload).status_code == 422


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_field_order_does_not_matter(client):
    """A JSON object has no column order, so the contract does not ask for one."""
    reversed_payload = dict(reversed(list(VALID.items())))
    assert client.post("/predict", json=reversed_payload).status_code == 200


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_a_non_numeric_value_is_rejected(client):
    assert client.post("/predict", json={**VALID, "age": "fifty"}).status_code == 422


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_health_reports_the_baked_model(client):
    response = client.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"]
    assert body["model_source"] == "working tree (not baked)"


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_health_is_503_without_a_model(monkeypatch, tmp_path):
    """No model, no traffic: the readiness probe in Exercise 5 relies on this 503."""
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.pkl"))
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 503, response.text
    assert "not ready" in str(response.json()["detail"])


def test_health_does_not_need_the_registry():
    """`/health` reads what was written into the image, not the tracking server."""
    import inspect

    from week_09_serving import api

    source = inspect.getsource(api)
    baked = source[source.index("def _baked("):source.index("def create_app(")]
    for forbidden in ("MlflowClient", "mlflow.tracking", "get_model_version"):
        assert forbidden not in baked, (
            f"`_baked()` uses {forbidden}: /health must report what was "
            "written at build time, not what the registry says now"
        )


@pytest.mark.skip(reason="Exercise 2 — write the endpoints in api.py, then delete this skip marker.")
def test_the_openapi_schema_lists_both_endpoints(client):
    spec = client.get("/openapi.json").json()
    assert "/predict" in spec["paths"]
    assert "/health" in spec["paths"]


# ── Batch versus online (Exercise 3) ────────────────────────────────────────


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


class _OneSlowRequest:
    """A client whose third request takes 50 ms and every other one about 1 ms."""

    def __init__(self):
        self.calls = 0

    def post(self, url, json):
        self.calls += 1
        time.sleep(0.05 if self.calls == 3 else 0.001)
        return _Response(200)


class _RejectsEveryFourth:
    """A client that answers 422 to every fourth request."""

    def __init__(self):
        self.calls = 0

    def post(self, url, json):
        self.calls += 1
        return _Response(422 if self.calls % 4 == 0 else 200)


@pytest.mark.skip(reason="Exercise 3 — write online_score in bench.py, then delete this skip marker.")
def test_online_score_sends_one_request_per_row():
    from week_09_serving.bench import online_score

    client = _OneSlowRequest()
    result = online_score(client, pd.DataFrame([VALID] * 20))

    assert client.calls == 20, f"expected one request per row, got {client.calls}"
    assert result["mode"] == "online"
    assert result["rows"] == 20
    assert result["wall_clock_s"] >= 0.05
    assert result["rows_per_second"] == pytest.approx(20 / result["wall_clock_s"], rel=0.05)


@pytest.mark.skip(reason="Exercise 3 — write online_score in bench.py, then delete this skip marker.")
def test_online_score_times_each_request():
    """An average hides the slow request; a time for each request shows it."""
    from week_09_serving.bench import online_score

    result = online_score(_OneSlowRequest(), pd.DataFrame([VALID] * 20))

    assert result["max_ms"] >= 45, (
        f"max_ms is {result['max_ms']}, but one request took 50 ms: "
        "time each request on its own"
    )
    assert result["p50_ms"] < 20, f"p50_ms is {result['p50_ms']}; most requests took 1 ms"
    assert result["p50_ms"] <= result["p95_ms"] <= result["max_ms"]


@pytest.mark.skip(reason="Exercise 3 — write online_score in bench.py, then delete this skip marker.")
def test_online_score_counts_failed_requests():
    """A rejected request never reaches the model, so it must not count as a scored row."""
    from week_09_serving.bench import online_score

    result = online_score(_RejectsEveryFourth(), pd.DataFrame([VALID] * 20))
    assert result["failed"] == 5, f"5 of 20 requests got a 422; failed is {result['failed']}"


@pytest.mark.skip(reason="Exercise 3 — write online_score in bench.py, then delete this skip marker.")
def test_online_score_sends_missing_values_as_null(client):
    """NaN is not valid JSON: a missing value must reach the service as null."""
    from week_09_serving.bench import online_score

    frame = pd.DataFrame([VALID, {**VALID, "insulin": float("nan")}])
    result = online_score(client, frame)
    assert result["failed"] == 0, "the row with a missing insulin was rejected"


@pytest.mark.skip(reason="Exercise 3 — write online_score in bench.py, then delete this skip marker.")
def test_online_score_runs_against_the_service(client):
    from week_09_serving.bench import online_score

    result = online_score(client, pd.DataFrame([VALID] * 5))
    assert result["rows"] == 5
    assert 0 < result["p50_ms"] <= result["max_ms"]
