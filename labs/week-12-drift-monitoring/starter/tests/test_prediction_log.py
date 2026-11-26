"""The prediction log: off by default, bounded, and joinable with the access log.

Every test runs in-process with a `TestClient` and a `tmp_path`.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from week_12_drift_monitoring.api import create_app
from week_12_drift_monitoring.data import FEATURE_COLUMNS
from week_12_drift_monitoring.prediction_log import (
    EVENT,
    MAX_ROWS_ENV,
    PATH_ENV,
    PredictionLog,
    read_window,
    window_age_seconds,
)

pytestmark = pytest.mark.unit

PATIENT = {
    "pregnancies": 6,
    "glucose": 148,
    "blood_pressure": 72,
    "skin_thickness": 35,
    "insulin": 125,
    "bmi": 33.6,
    "diabetes_pedigree": 0.627,
    "age": 50,
}
ILLEGAL = {**PATIENT, "glucose": 0}


# ── Off by default ───────────────────────────────────────────────────────────


def test_the_log_is_off_unless_a_path_is_set(monkeypatch):
    """With no path set, nothing is written: storing patient data is a deployment decision."""
    monkeypatch.delenv(PATH_ENV, raising=False)
    log = PredictionLog.from_env()
    assert log.enabled is False
    assert log.path is None
    assert log.record(features=PATIENT, probability=0.7, prediction=1) is False


def test_a_disabled_log_costs_one_boolean_and_no_file(tmp_path, monkeypatch):
    monkeypatch.delenv(PATH_ENV, raising=False)
    log = PredictionLog.from_env()
    log.record(features=PATIENT, probability=0.7, prediction=1)
    assert not list(tmp_path.iterdir())


def test_a_malformed_bound_is_refused_at_startup(monkeypatch, tmp_path):
    """A bound that cannot be parsed fails at startup."""
    monkeypatch.setenv(PATH_ENV, str(tmp_path / "p.jsonl"))
    monkeypatch.setenv(MAX_ROWS_ENV, "lots")
    with pytest.raises(ValueError, match=MAX_ROWS_ENV):
        PredictionLog.from_env()
    monkeypatch.setenv(MAX_ROWS_ENV, "-5")
    with pytest.raises(ValueError, match="positive"):
        PredictionLog.from_env()


# ── The format ───────────────────────────────────────────────────────────────


def test_one_json_object_per_line_with_the_features_flat(tmp_path):
    """Features are flat, so `pandas.read_json(lines=True)` gives the reference window's columns."""
    log = PredictionLog(tmp_path / "p.jsonl")
    log.record(features=PATIENT, probability=0.71, prediction=1, model_version="4")
    lines = (tmp_path / "p.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == EVENT
    for column in FEATURE_COLUMNS:
        assert column in record, f"{column} is not in the logged row"
    assert record["prediction"] == 1
    assert record["probability"] == pytest.approx(0.71)
    assert record["model_version"] == "4"
    assert isinstance(record["logged_at"], float)


def test_the_recorded_rows_load_into_a_frame_the_reference_schema_accepts(tmp_path):
    """The logged rows load with the same columns as the reference window."""
    log = PredictionLog(tmp_path / "p.jsonl")
    for _ in range(5):
        log.record(features=PATIENT, probability=0.5, prediction=1)
    frame = read_window(tmp_path / "p.jsonl", columns=list(FEATURE_COLUMNS))
    assert list(frame.columns) == list(FEATURE_COLUMNS)
    assert len(frame) == 5
    assert frame["glucose"].iloc[0] == pytest.approx(148.0)


def test_a_gated_feature_missing_from_the_log_is_a_named_error(tmp_path):
    log = PredictionLog(tmp_path / "p.jsonl")
    log.record(features={"glucose": 148}, probability=0.5, prediction=1)
    with pytest.raises(KeyError, match="bmi"):
        read_window(tmp_path / "p.jsonl", columns=["glucose", "bmi"])


def test_a_truncated_last_line_is_skipped_and_counted(tmp_path):
    """A process killed mid-write leaves a partial last line, which must not stop the monitor."""
    path = tmp_path / "p.jsonl"
    log = PredictionLog(path)
    log.record(features=PATIENT, probability=0.5, prediction=1)
    with path.open("a") as handle:
        handle.write('{"event": "prediction", "glucose": 1')  # killed mid-write
    frame = read_window(path)
    assert len(frame) == 1
    assert frame.attrs["skipped_lines"] == 1


def test_other_json_log_lines_are_ignored(tmp_path):
    """The access log is JSON too, so the `event` field tells the two apart."""
    path = tmp_path / "p.jsonl"
    log = PredictionLog(path)
    log.record(features=PATIENT, probability=0.5, prediction=1)
    with path.open("a") as handle:
        handle.write(json.dumps({"event": "http_request", "status": 200}) + "\n")
    assert len(read_window(path)) == 1


# ── Bounded ──────────────────────────────────────────────────────────────────


def test_the_bound_holds_and_warns_exactly_once(tmp_path, caplog):
    """An unbounded append-only log eventually fills the disk."""
    log = PredictionLog(tmp_path / "p.jsonl", max_rows=3)
    written = [log.record(features=PATIENT, probability=0.5, prediction=1) for _ in range(6)]
    assert written == [True, True, True, False, False, False]
    assert len(read_window(tmp_path / "p.jsonl")) == 3
    with caplog.at_level("WARNING", logger="week12.predictions"):
        log.record(features=PATIENT, probability=0.5, prediction=1)
    # One warning at the bound, not one per rejected request.
    assert log.rows_written == 3


def test_an_existing_log_is_counted_rather_than_re_read_per_request(tmp_path):
    """The rows are counted once at startup, not on every request."""
    path = tmp_path / "p.jsonl"
    first = PredictionLog(path, max_rows=5)
    for _ in range(4):
        first.record(features=PATIENT, probability=0.5, prediction=1)
    second = PredictionLog(path, max_rows=5)
    assert second.rows_written == 4
    assert second.record(features=PATIENT, probability=0.5, prediction=1) is True
    assert second.record(features=PATIENT, probability=0.5, prediction=1) is False


def test_the_window_is_rolling_and_takes_the_newest_rows(tmp_path):
    """The window holds the newest rows, so the question is "is it drifting now"."""
    path = tmp_path / "p.jsonl"
    log = PredictionLog(path)
    for index in range(10):
        log.record(features={**PATIENT, "glucose": 100 + index}, probability=0.5, prediction=1)
    frame = read_window(path, window_rows=3)
    assert list(frame["glucose"]) == [107.0, 108.0, 109.0]


def test_the_window_reports_the_age_of_its_newest_row(tmp_path):
    """The statistics cannot show that no request has arrived for days. The age can."""
    path = tmp_path / "p.jsonl"
    PredictionLog(path).record(features=PATIENT, probability=0.5, prediction=1)
    frame = read_window(path)
    age = window_age_seconds(frame, now=None)
    assert age is not None and 0 <= age < 60
    # An explicit `now` tests staleness without waiting a day.
    newest = float(frame["logged_at"].max())
    assert window_age_seconds(frame, now=newest + 90_000) == pytest.approx(90_000, abs=1)


def test_a_missing_log_names_the_two_commands_that_produce_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="make traffic-drift"):
        read_window(tmp_path / "absent.jsonl")


# ── Through the API ──────────────────────────────────────────────────────────


def test_a_scored_request_is_logged_and_carries_the_middlewares_request_id(
    tmp_path, monkeypatch, scoring_model
):
    """The shared request id joins the prediction log with the access log."""
    monkeypatch.setenv(PATH_ENV, str(tmp_path / "p.jsonl"))
    app = create_app(CollectorRegistry())
    client = TestClient(app)
    response = client.post("/predict", json=PATIENT)
    assert response.status_code == 200

    frame = read_window(tmp_path / "p.jsonl")
    assert len(frame) == 1
    request_id = frame["request_id"].iloc[0]
    assert isinstance(request_id, str) and len(request_id) > 8
    assert frame["probability"].iloc[0] == pytest.approx(
        response.json()["probability"], abs=1e-3
    )


def test_a_contract_violation_is_not_in_the_prediction_log(tmp_path, monkeypatch, scoring_model):
    """A rejected request was never scored, so it does not belong in the drift window."""
    monkeypatch.setenv(PATH_ENV, str(tmp_path / "p.jsonl"))
    app = create_app(CollectorRegistry())
    client = TestClient(app)
    assert client.post("/predict", json=ILLEGAL).status_code == 422
    assert not (tmp_path / "p.jsonl").exists() or read_window(tmp_path / "p.jsonl").empty


def test_the_v1_route_logs_every_instance(tmp_path, monkeypatch, scoring_model):
    """Both routes write to the prediction log."""
    monkeypatch.setenv(PATH_ENV, str(tmp_path / "p.jsonl"))
    app = create_app(CollectorRegistry())
    client = TestClient(app)
    response = client.post(
        "/v1/models/diabetes:predict", json={"instances": [PATIENT, PATIENT, PATIENT]}
    )
    assert response.status_code == 200
    assert len(read_window(tmp_path / "p.jsonl")) == 3


def test_instrumentation_did_not_change_the_response_body(tmp_path, monkeypatch, scoring_model):
    """The response is the same with the log off and on."""
    monkeypatch.delenv(PATH_ENV, raising=False)
    off = TestClient(create_app(CollectorRegistry())).post("/predict", json=PATIENT)

    monkeypatch.setenv(PATH_ENV, str(tmp_path / "p.jsonl"))
    on = TestClient(create_app(CollectorRegistry())).post("/predict", json=PATIENT)

    assert off.status_code == on.status_code == 200
    assert off.json() == on.json()
