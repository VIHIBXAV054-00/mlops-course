"""The drift collector, which publishes the drift report as Prometheus metrics.

1. `collect()` never raises: one exception fails the whole `/metrics` response.
2. It publishes a timestamp even with no report, so `DriftReportStale` can fire.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, generate_latest

from week_12_drift_monitoring.api import create_app
from week_12_drift_monitoring.drift_metrics import (
    NO_REPORT_TIMESTAMP,
    DriftCollector,
)
from week_12_drift_monitoring.drift_policy import VERDICTS
from week_12_drift_monitoring.metrics import SCORE_BUCKETS

pytestmark = pytest.mark.unit

LAB = Path(__file__).resolve().parents[1]

REPORT = {
    "schema": "drift-report/1",
    "service": "diabetes-api",
    "computed_at": 1_700_000_000.0,
    "verdict": "DRIFT",
    "severity": "ticket",
    "drifted_count": 2,
    "drifted_gated_count": 1,
    "features_total": 8,
    "n_current": 720,
    "current": {"rows": 720, "age_seconds": 42.5},
    "proxy": {"reference_positive_rate": 0.2674},
    "features": [
        {
            "column": "glucose",
            "method": "psi",
            "threshold": 0.22,
            "value": 0.2358,
            "drifted": True,
            "gated": True,
            "smaller_is_drift": False,
        },
        {
            "column": "insulin",
            "method": "psi",
            "threshold": 0.20,
            "value": 0.2226,
            "drifted": True,
            "gated": False,
            "smaller_is_drift": False,
        },
    ],
}


def _render(path: Path) -> str:
    registry = CollectorRegistry()
    registry.register(DriftCollector(path))
    return generate_latest(registry).decode()


def _write(tmp_path: Path, report) -> Path:
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(report))
    return path


# ── Rule 1: it never raises ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="missing-file"),
        pytest.param("", id="empty"),
        pytest.param("{ not json", id="truncated"),
        pytest.param("[1, 2, 3]", id="a-list-not-an-object"),
        pytest.param('"a string"', id="a-bare-string"),
        pytest.param('{"verdict": "DRIFT", "features": "not a list"}', id="wrong-types"),
        pytest.param(
            '{"computed_at": "yesterday", "features": [{"column": "glucose", "value": "high"}]}',
            id="strings-where-numbers-go",
        ),
        pytest.param('{"features": [null, 3, "glucose"]}', id="junk-in-the-feature-list"),
        pytest.param(b"\xff\xfe\x00binary".decode("latin-1"), id="not-utf8-ish"),
    ],
)
def test_no_report_shape_can_take_metrics_down(tmp_path, content):
    """Every malformed input gives fewer series, never an exception."""
    path = tmp_path / "drift.json"
    if content is not None:
        path.write_text(content)
    output = _render(path)  # must not raise
    # Rule 2: the timestamp is always published.
    assert "model_drift_report_timestamp_seconds" in output


def test_a_missing_report_publishes_a_zero_timestamp_and_nothing_else(tmp_path):
    """Rule 2: `time() - 0` is past any staleness limit, so `DriftReportStale` fires."""
    output = _render(tmp_path / "absent.json")
    assert f"model_drift_report_timestamp_seconds {NO_REPORT_TIMESTAMP}" in output
    assert "model_drift_score" not in output
    assert "model_drift_verdict" not in output


def test_a_null_statistic_is_no_series_and_never_a_zero(tmp_path):
    """A psi of 0 means identical distributions, so a missing value must not become 0."""
    report = json.loads(json.dumps(REPORT))
    report["features"][0]["value"] = None
    output = _render(_write(tmp_path, report))
    assert 'model_drift_score{feature="glucose"' not in output
    # The other feature is unaffected.
    assert 'model_drift_score{feature="insulin",method="psi"} 0.2226' in output


# ── The series themselves ────────────────────────────────────────────────────


def test_every_expected_series_is_published(tmp_path):
    output = _render(_write(tmp_path, REPORT))
    for name in (
        "model_drift_report_timestamp_seconds",
        "model_drift_score",
        "model_drift_threshold",
        "model_drift_feature_gated",
        "model_drift_features_drifted",
        "model_drift_features_drifted_gated",
        "model_drift_features_total",
        "model_drift_window_rows",
        "model_drift_window_age_seconds",
        "model_drift_verdict",
        "model_reference_positive_rate",
    ):
        assert name in output, f"{name} is missing from the exposition"


def test_the_method_is_a_label_because_a_number_without_its_test_is_not_a_measurement(
    tmp_path,
):
    """psi and ks values have different scales and directions, so the method is a label."""
    output = _render(_write(tmp_path, REPORT))
    assert 'model_drift_score{feature="glucose",method="psi"} 0.2358' in output


def test_every_verdict_gets_a_series_and_exactly_one_is_one(tmp_path):
    """One series per verdict keeps each history continuous when the verdict changes."""
    output = _render(_write(tmp_path, REPORT))
    for verdict in VERDICTS:
        assert f'model_drift_verdict{{verdict="{verdict}"}}' in output
    assert 'model_drift_verdict{verdict="DRIFT"} 1.0' in output
    assert 'model_drift_verdict{verdict="NO_DRIFT"} 0.0' in output


def test_the_gated_count_is_published_separately_from_the_total_count(tmp_path):
    """`FeatureDriftDetected` fires on the gated count. The total is for the dashboard."""
    output = _render(_write(tmp_path, REPORT))
    assert "model_drift_features_drifted 2.0" in output
    assert "model_drift_features_drifted_gated 1.0" in output
    assert "model_drift_features_total 8.0" in output


def test_a_stale_report_still_publishes_its_timestamp(tmp_path):
    """A collector that hid an old timestamp would stop `DriftReportStale` from firing."""
    report = json.loads(json.dumps(REPORT))
    report["computed_at"] = time.time() - 30 * 3600
    output = _render(_write(tmp_path, report))
    line = next(
        line for line in output.splitlines()
        if line.startswith("model_drift_report_timestamp_seconds ")
    )
    assert float(line.split()[1]) == pytest.approx(report["computed_at"], abs=1)


# ── The proxy's bucket boundary ──────────────────────────────────────────────


def test_the_proxy_alerts_bucket_boundary_exists_in_the_histogram():
    """`PredictionMixShift` matches `le="0.5"` as a string. Without that bucket it can never fire."""
    assert 0.5 in SCORE_BUCKETS
    rules = (LAB / "prometheus/rules/drift.yml").read_text()
    assert 'le="0.5"' in rules
    # The label must render as `0.5`, not `0.50` or `5e-01`.
    registry = CollectorRegistry()
    app = create_app(registry)
    client = TestClient(app)
    client.post(
        "/predict",
        json={
            "pregnancies": 6, "glucose": 148, "blood_pressure": 72,
            "skin_thickness": 35, "insulin": 125, "bmi": 33.6,
            "diabetes_pedigree": 0.627, "age": 50,
        },
    )
    exposition = client.get("/metrics").text
    assert 'model_prediction_score_bucket{le="0.5"}' in exposition


# ── Through the running app ──────────────────────────────────────────────────


def test_the_collector_is_registered_on_the_apps_registry(tmp_path, monkeypatch):
    """One scrape returns the request metrics and the drift verdict."""
    monkeypatch.setenv("DRIFT_REPORT_PATH", str(_write(tmp_path, REPORT)))
    registry = CollectorRegistry()
    client = TestClient(create_app(registry))
    exposition = client.get("/metrics").text
    assert "http_requests_total" in exposition
    assert "model_drift_verdict" in exposition
    assert 'model_drift_score{feature="glucose",method="psi"} 0.2358' in exposition


def test_metrics_still_answers_when_the_report_is_garbage(tmp_path, monkeypatch):
    """Rule 1 through the app: a corrupt file loses only the drift series."""
    path = tmp_path / "drift.json"
    path.write_text("{{{ not json at all")
    monkeypatch.setenv("DRIFT_REPORT_PATH", str(path))
    client = TestClient(create_app(CollectorRegistry()))
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "model_drift_report_timestamp_seconds 0.0" in response.text
