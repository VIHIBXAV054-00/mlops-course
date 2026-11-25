"""The instrumentation, tested with no server, no Docker and no Prometheus.

Everything here runs against a `TestClient` and a fresh `CollectorRegistry`, so
the whole of this week's most defect-prone code is covered in the autograder in
under a second. That is the same constraint Week 9 put on the API tests and
Week 10 on the smoke suite: **a test that needs a running service is a test that
does not run.**

Two of these tests are the week, and they are the two that are easy to skip:

  * `test_the_route_label_is_the_template_not_the_path` — the cardinality
    decision. Three different URLs must produce ONE series.
  * `test_the_latency_slo_threshold_is_a_bucket_boundary` — the seam between
    `slo.yaml` and `metrics.py`. If those two drift, the latency SLI silently
    matches no series and the alert can never fire, which is the safest-looking
    way for a rule to be wrong.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from week_11_observability.api import create_app
from week_11_observability.loadtest import PROBE_PATIENT
from week_11_observability.metrics import (
    LATENCY_BUCKETS,
    SCORE_BUCKETS,
    UNMATCHED_ROUTE,
    render,
)
from week_11_observability.slo import load_slo

pytestmark = pytest.mark.unit


@pytest.fixture
def registry() -> CollectorRegistry:
    """A private universe per test.

    The default registry is a process global, so a second `create_app()` would
    raise `Duplicated timeseries in CollectorRegistry`. Handing each test its
    own registry is why `create_app` grew a parameter this week — a seam that
    exists for testability and costs the production path nothing.
    """
    return CollectorRegistry()


@pytest.fixture
def client(registry: CollectorRegistry, served_model, monkeypatch) -> TestClient:
    """A client over a real app, which needs a real model.

    `models/model.pkl` is git-ignored, so on a fresh clone (which is what the
    autograder is) every route would return 503. `served_model` trains one in
    under a second (see conftest).
    """
    monkeypatch.setenv("MODEL_PATH", str(served_model))
    return TestClient(create_app(registry=registry))


def samples(registry: CollectorRegistry, name: str) -> dict[tuple, float]:
    """Every sample of one metric, keyed by its sorted label tuple."""
    found: dict[tuple, float] = {}
    for metric in registry.collect():
        for sample in metric.samples:
            if sample.name == name:
                found[tuple(sorted(sample.labels.items()))] = sample.value
    return found


# ── The cardinality decision ─────────────────────────────────────────────────


def test_the_route_label_is_the_template_not_the_path(client, registry):
    """Three URLs, one time series. This is the whole point of `route_label`.

    The V1 route is parameterised (`/v1/models/{model_name}:predict`), so a
    caller can produce arbitrarily many distinct PATHS. If the label were the
    path, each one would be its own time series in the collector's memory,
    forever. It is the route TEMPLATE, so they collapse.
    """
    for name in ("diabetes", "diabetes-canary", "some-other-name"):
        response = client.post(
            f"/v1/models/{name}:predict", json={"instances": [PROBE_PATIENT]}
        )
        assert response.status_code == 200

    v1_series = {
        labels
        for labels in samples(registry, "http_requests_total")
        if dict(labels).get("route", "").startswith("/v1/")
    }
    assert len(v1_series) == 1, (
        "three different model names produced more than one time series — the "
        f"route label is not the template: {v1_series}"
    )
    assert dict(next(iter(v1_series)))["route"] == "/v1/models/{model_name}:predict"
    assert samples(registry, "http_requests_total")[next(iter(v1_series))] == 3


def test_an_unmatched_path_collapses_to_one_label_value(client, registry):
    """404s are cardinality arriving through the back door, sourced from strangers.

    A request that matches no route has no route in its ASGI scope. If that fell
    back to the raw path, every scan, typo and probe from the public internet
    would mint a new time series — an unbounded label whose values are chosen by
    whoever is scanning you.
    """
    for index in range(5):
        assert client.get(f"/definitely-not-a-route/{index}").status_code == 404

    unmatched = {
        labels: value
        for labels, value in samples(registry, "http_requests_total").items()
        if dict(labels).get("route") == UNMATCHED_ROUTE
    }
    assert len(unmatched) == 1, f"five bad paths made {len(unmatched)} series: {unmatched}"
    assert next(iter(unmatched.values())) == 5


# ── The seam with slo.yaml ───────────────────────────────────────────────────


def test_the_latency_slo_threshold_is_a_bucket_boundary():
    """`slo.yaml`'s latency threshold must be one of `LATENCY_BUCKETS`.

    THE FAILURE THIS PREVENTS IS SILENT. `prometheus/rules/slo.yml` selects the
    latency SLI with `le="0.25"`. If 0.25 stops being a bucket boundary, that
    matcher selects NO series, the ratio is empty, and the alert can never fire
    — a rule that is broken in the direction nobody investigates.

    It also has to be a boundary for the SLI to be EXACT rather than estimated:
    `histogram_quantile` interpolates linearly inside a bucket, so a threshold
    between two boundaries is a straight-line guess about a distribution that is
    not a straight line.
    """
    threshold = load_slo().objective("latency").threshold_seconds
    assert threshold in LATENCY_BUCKETS, (
        f"slo.yaml promises a latency threshold of {threshold}s, which is not one of "
        f"metrics.py's bucket boundaries {LATENCY_BUCKETS}. The SLI would be "
        "interpolated at best and empty at worst."
    )


def test_buckets_are_sorted_and_bounded():
    """Sorted, positive, and finite — `+Inf` is added by the library, not by us."""
    for buckets in (LATENCY_BUCKETS, SCORE_BUCKETS):
        assert list(buckets) == sorted(buckets), f"{buckets} is not ascending"
        assert all(edge > 0 for edge in buckets)
        assert all(edge != float("inf") for edge in buckets), (
            "prometheus_client appends the +Inf bucket itself; declaring it "
            "produces a duplicate boundary"
        )
    assert SCORE_BUCKETS[-1] == 1.0, "a probability cannot exceed 1"


# ── What the middleware measures ─────────────────────────────────────────────


def test_metrics_endpoint_does_not_count_itself(client, registry):
    """Prometheus scrapes forever. Counting the scrape puts the collector in
    your error budget and adds a permanent floor to every RPS graph."""
    for _ in range(3):
        assert client.get("/metrics").status_code == 200

    routes = {dict(labels).get("route") for labels in samples(registry, "http_requests_total")}
    assert "/metrics" not in routes
    assert UNMATCHED_ROUTE not in routes
    assert not samples(registry, "http_requests_total"), (
        "three scrapes and nothing else produced request metrics — the "
        "thermometer is measuring itself"
    )


def test_a_successful_prediction_moves_four_metrics(client, registry):
    """One request, four observations, and each answers a different question."""
    assert client.post("/predict", json=PROBE_PATIENT).status_code == 200

    requests = samples(registry, "http_requests_total")
    assert any(dict(k).get("status") == "200" for k in requests)

    latency = samples(registry, "http_request_duration_seconds_count")
    assert sum(latency.values()) == 1

    predictions = samples(registry, "model_predictions_total")
    assert sum(predictions.values()) == 1
    assert {dict(k)["outcome"] for k in predictions} <= {"positive", "negative"}

    assert samples(registry, "model_prediction_score_count")[()] == 1


def test_a_contract_violation_is_counted_by_check_name(client, registry):
    """Week 5's 422, aggregated — and NOT as a server error.

    Two assertions, and the second one is a design decision rather than a
    detail: the violation is counted, and the request is recorded as a 422. A
    422 is the service refusing an impossible patient, which is the service
    working. Counting it as a failure would let any caller burn our error budget
    by sending rubbish.
    """
    response = client.post("/predict", json={**PROBE_PATIENT, "glucose": 0.0})
    assert response.status_code == 422

    violations = samples(registry, "model_contract_violations_total")
    assert violations, "a rejected payload recorded no contract violation"
    checks = {dict(labels)["check"] for labels in violations}
    assert "greater_than(0)" in checks, (
        f"the label should name the failing CHECK, a closed set fixed by the "
        f"pandera schema; got {checks}"
    )

    statuses = {dict(labels).get("status") for labels in samples(registry, "http_requests_total")}
    assert "422" in statuses
    assert not any(status.startswith("5") for status in statuses if status), (
        "a contract rejection must not be recorded as a server error"
    )


def test_in_flight_returns_to_zero(client, registry):
    """A gauge that is incremented in a `try` and decremented in a `finally`.

    Get this wrong and the number creeps up forever, which looks exactly like a
    service that is slowly leaking — the most expensive kind of wrong, because
    somebody will spend a day looking for the leak.
    """
    for _ in range(5):
        client.post("/predict", json=PROBE_PATIENT)
    client.post("/predict", json={**PROBE_PATIENT, "glucose": 0.0})
    assert samples(registry, "http_requests_in_flight")[()] == 0


def test_model_info_reports_the_same_identity_as_health(client, registry):
    """The dashboard and `/health` must not disagree about which model this is.

    `model_info` is link ten of the traceability chain, and a chain with two
    different answers at the same link is not evidence.
    """
    health = client.get("/health").json()
    info = samples(registry, "model_info")
    assert len(info) == 1, "model_info should carry exactly one identity"
    labels = dict(next(iter(info)))
    assert next(iter(info.values())) == 1.0, "an info metric's value is always 1"
    assert labels["schema_version"] == health["schema_version"]
    assert labels["model_version"] == str(health["model_version"] or "unknown")
    assert labels["gate_verdict"] == str(health["gate_verdict"] or "unknown")


def test_no_label_value_is_none_shaped(client, registry):
    """`None` becomes the literal string "None" in a label, and then it is on a
    dashboard forever as a model version called None."""
    client.get("/health")
    for labels in samples(registry, "model_info"):
        for key, value in labels:
            assert value != "None", f"{key} was formatted from a None"
            assert value != "", f"{key} is empty"


# ── The wire format ──────────────────────────────────────────────────────────


def test_the_exposition_format_is_what_prometheus_expects(client):
    """A scrape endpoint that is 99% conformant fails on the one metric whose
    help text has a newline in it — which is why the body comes from the
    library's own `generate_latest()` and not from an f-string."""
    client.post("/predict", json=PROBE_PATIENT)

    response = client.get("/metrics", follow_redirects=False)
    assert response.status_code == 200, (
        "a bare GET /metrics must serve the exposition directly. Mounting "
        "make_asgi_app() at /metrics makes this a 307 to /metrics/ — which "
        "Prometheus follows, and `curl` without -L does not."
    )
    assert response.headers["content-type"].startswith("text/plain")

    body = response.text
    assert "# HELP http_requests_total" in body
    assert "# TYPE http_requests_total counter" in body
    assert "# TYPE http_request_duration_seconds histogram" in body
    # Cumulative buckets, one line per boundary, plus the library's +Inf.
    assert 'http_request_duration_seconds_bucket{' in body
    assert 'le="+Inf"' in body


def test_the_bucket_label_renders_the_declared_boundary_exactly(client, registry):
    """`le="0.25"` in the rules must match `le=` in the exposition, character
    for character. Prometheus compares label values as strings — `0.25` and
    `0.250` are different series."""
    client.post("/predict", json=PROBE_PATIENT)
    rendered = render(registry)
    assert 'le="0.25"' in rendered, (
        "the 0.25 bucket is not rendered as `0.25`; prometheus/rules/slo.yml "
        "selects it by exact string match"
    )


# ── The log line, which is the other half of the three-pillars story ─────────


def test_every_request_writes_one_structured_log_line(client, caplog):
    """JSON, one object per line, carrying what a metric cannot.

    The `request_id` is the point: as a log field it is free, as a metric label
    it would mint one time series per request forever. That single contrast is
    more useful than any diagram of three pillars.
    """
    with caplog.at_level("INFO", logger="week11.access"):
        client.post("/predict", json=PROBE_PATIENT)

    lines = [record.getMessage() for record in caplog.records]
    assert lines, "no access log line was written"
    entry = json.loads(lines[-1])
    assert entry["event"] == "http_request"
    assert entry["route"] == "/predict"
    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0
    # Present in the log, absent from every metric label. On purpose.
    assert len(entry["request_id"]) == 36


def test_instrumentation_did_not_change_any_response(client):
    """The whole week must be invisible to a caller.

    Instrumentation that changes what a service returns is not instrumentation,
    it is a rewrite — and it invalidates every assertion Weeks 5, 9 and 10 made
    about this API's contract.
    """
    prediction = client.post("/predict", json=PROBE_PATIENT)
    assert prediction.status_code == 200
    assert set(prediction.json()) == {
        "prediction",
        "probability",
        "model_version",
        "store_version",
        "revision",
        "schema_version",
    }

    rejected = client.post("/predict", json={**PROBE_PATIENT, "glucose": 0.0})
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["message"] == "payload failed the model-input contract"
