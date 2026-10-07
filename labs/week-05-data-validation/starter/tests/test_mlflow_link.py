"""The data version and the validation verdict on the MLflow run (Exercise 6).

These tests need the stack, and skip without it.
"""

import dataclasses
import shutil

import pytest
from mlflow.tracking import MlflowClient

from week_05_data_validation import pipeline
from week_05_data_validation.datasets import build_measurements, file_md5
from week_05_data_validation.dvc_meta import pointer_md5
from week_05_data_validation.schemas import SCHEMA_VERSION
from week_05_data_validation.tracking import search_runs_by_data_version

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def logged_run(live_settings, measurements_pointer, raw_batches, tmp_path_factory):
    """Run the whole pipeline once against the real server, in an isolated workspace."""
    tmp_path = tmp_path_factory.mktemp("link")
    measurements = tmp_path / "data" / "measurements.csv"
    build_measurements(raw_batches, measurements)

    # The pointer travels with the data copy, because log_data_version reads it.
    shutil.copy2(measurements_pointer, measurements.with_suffix(".csv.dvc"))
    assert file_md5(measurements) == pointer_md5(measurements), (
        "the sandbox copy must be the data the committed pointer names"
    )

    sandbox = dataclasses.replace(
        live_settings,
        project_root=tmp_path,
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        measurements_path=measurements,
    )
    # All four stages: promote_to_staging needs the metrics that evaluate logs.
    pipeline.validate(sandbox)
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert result["run_id"], "training produced no MLflow run"
    pipeline.evaluate(sandbox)
    return sandbox, result


@pytest.mark.skip(reason="Exercise 6 (optional) — finish Exercises 4 and 5, then delete this skip marker.")
def test_run_carries_the_data_version(live_settings, logged_run) -> None:
    sandbox, result = logged_run
    tags = MlflowClient(live_settings.mlflow_tracking_uri).get_run(result["run_id"]).data.tags
    assert tags["dvc_md5"] == pointer_md5(sandbox.measurements_path)
    assert tags["dvc_url"].startswith("s3://")
    assert result["mlflow_digest"] and len(result["mlflow_digest"]) == 8


@pytest.mark.skip(reason="Exercise 6 (optional) — finish Exercises 4 and 5, then delete this skip marker.")
def test_run_carries_the_validation_verdict(live_settings, logged_run) -> None:
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    tags = client.get_run(result["run_id"]).data.tags
    assert tags["data_validation"] == "pass", (
        "The training contract did not pass, or did not run (Exercise 5)."
    )
    assert tags["schema_version"] == SCHEMA_VERSION
    assert tags["n_failure_cases"] == "0"
    assert tags["ingestion_validation"] == "pass", (
        "No passing reports/validation.json was found (Exercise 4)."
    )
    artifacts = {a.path for a in client.list_artifacts(result["run_id"], "validation")}
    assert "validation/validation.json" in artifacts


@pytest.mark.skip(reason="Exercise 6 (optional) — finish Exercises 4 and 5, then delete this skip marker.")
def test_search_runs_by_data_version_finds_the_run(live_settings, logged_run) -> None:
    sandbox, result = logged_run
    frame = search_runs_by_data_version(live_settings, pointer_md5(sandbox.measurements_path))
    assert result["run_id"] in set(frame.get("run_id", []))


@pytest.mark.skip(reason="Exercise 6 (optional) — finish Exercises 4 and 5, then delete this skip marker.")
def test_trace_reaches_the_verdict(live_settings, logged_run) -> None:
    from week_05_data_validation.registry import (
        promote_to_staging,
        register_best_model,
        trace_alias,
    )

    sandbox, result = logged_run
    version = register_best_model(live_settings, result["run_id"])
    promote_to_staging(live_settings, version.version)

    chain = trace_alias(live_settings)
    assert chain["run_id"] == result["run_id"]
    assert chain["dvc_md5"] == pointer_md5(sandbox.measurements_path)
    assert chain["data_validation"] == "pass"
    assert chain["schema_version"] == SCHEMA_VERSION
