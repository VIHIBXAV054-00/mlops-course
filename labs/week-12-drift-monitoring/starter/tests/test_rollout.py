"""The model store: publishing a version, its provenance, and the gate check before it.

Runs offline against a temporary store.
"""

from __future__ import annotations

import dataclasses
import json

import joblib
import pytest

from week_12_drift_monitoring import rollout
from week_12_drift_monitoring.data import build_dataset
from week_12_drift_monitoring.model import build_model
from week_12_drift_monitoring.pipeline import _hyperparams

pytestmark = pytest.mark.eval


@pytest.fixture
def workspace(tmp_path, settings):
    """Settings for a throwaway project root, with a model trained here."""
    (tmp_path / "models").mkdir()
    (tmp_path / "metrics").mkdir()
    (tmp_path / "reports").mkdir()

    x_train, _, y_train, _ = build_dataset(settings)
    model = build_model(
        settings.model_family, _hyperparams(settings), settings, impute="median"
    )
    model.fit(x_train, y_train)
    joblib.dump(model, tmp_path / "models" / "model.pkl")
    (tmp_path / "metrics" / "metrics.json").write_text(json.dumps({"f1": 0.6341}))
    (tmp_path / "models" / "mlflow_run_id.json").write_text(
        json.dumps({"run_id": "abc123", "mlflow_digest": None})
    )
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
        measurements_path=tmp_path / "data" / "measurements.csv",
        # Unreachable, so no test touches a tracking server.
        mlflow_tracking_uri="http://127.0.0.1:1",
    )


def _record_verdict(settings, verdict: str) -> None:
    settings.gate_report_path.write_text(
        json.dumps({"verdict": verdict, "criteria_version": "1.0.0"})
    )


def test_publishing_writes_the_model_and_its_provenance(workspace):
    _record_verdict(workspace, "GO")
    result = rollout.publish_version("v1", settings=workspace)

    assert (result.path / "model.pkl").exists()
    provenance = json.loads((result.path / "provenance.json").read_text())
    assert provenance["store_version"] == "v1"
    assert provenance["gate_verdict"] == "GO"
    assert provenance["run_id"] == "abc123"
    assert provenance["family"] == workspace.model_family
    assert provenance["metrics"]["f1"] == 0.6341


def test_the_store_is_the_fourth_door_and_it_is_locked(workspace):
    """Publishing is a path to production, so it checks the gate and refuses a NO-GO."""
    _record_verdict(workspace, "NO-GO")
    with pytest.raises(SystemExit) as refusal:
        rollout.publish_version("v3", settings=workspace)
    assert "NO-GO" in str(refusal.value)
    assert not (rollout.store_dir(workspace) / "v3").exists(), (
        "a refused publish must leave nothing behind"
    )


def test_a_forced_publish_records_the_truth(workspace):
    """`FORCE=1` publishes anyway but records the real verdict, so `/health` shows it."""
    _record_verdict(workspace, "NO-GO")
    result = rollout.publish_version("v3", settings=workspace, force=True)

    assert result.forced
    provenance = json.loads((result.path / "provenance.json").read_text())
    assert provenance["gate_verdict"] == "NO-GO"


def test_publishing_without_a_model_fails_before_it_writes_anything(workspace):
    _record_verdict(workspace, "GO")
    (workspace.models_dir / "model.pkl").unlink()
    with pytest.raises(FileNotFoundError):
        rollout.publish_version("v1", settings=workspace)


def test_the_registry_version_is_never_guessed(workspace):
    """With no reachable registry, `model_version` is null rather than invented."""
    _record_verdict(workspace, "GO")
    result = rollout.publish_version("v2", settings=workspace)
    assert result.provenance["model_version"] is None


def test_listing_reports_what_each_version_claims(workspace):
    _record_verdict(workspace, "GO")
    rollout.publish_version("v1", settings=workspace)
    _record_verdict(workspace, "NO-GO")
    rollout.publish_version("v3", settings=workspace, force=True)

    rows = rollout.list_versions(workspace)
    assert [row["version"] for row in rows] == ["v1", "v3"]
    assert [row["gate_verdict"] for row in rows] == ["GO", "NO-GO"]
    assert all(row["has_model"] for row in rows)

    table = rollout.format_versions(rows)
    assert "NO-GO" in table, "the store listing must not hide an unapproved model"


def test_an_empty_store_says_so_rather_than_crashing(workspace):
    assert rollout.list_versions(workspace) == []
    assert "empty" in rollout.format_versions([])
