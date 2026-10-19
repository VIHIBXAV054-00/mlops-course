"""The DVC, validation and gate tags on the MLflow run, and `register` and `promote`.

These tests need the MLflow stack and a DVC pointer, and skip when either is absent.
"""

import dataclasses

import pytest
from mlflow.tracking import MlflowClient

from week_06_evaluation_pipeline import pipeline
from week_06_evaluation_pipeline.datasets import build_measurements
from week_06_evaluation_pipeline.dvc_meta import pointer_md5
from week_06_evaluation_pipeline.schemas import SCHEMA_VERSION
from week_06_evaluation_pipeline.tracking import search_runs_by_data_version

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def logged_run(live_settings, measurements_pointer, raw_batches, tmp_path_factory):
    """Train once against the real server, in an isolated workspace."""
    tmp_path = tmp_path_factory.mktemp("link")
    measurements = tmp_path / "data" / "measurements.csv"
    build_measurements(2, raw_batches, measurements)

    # Copy the pointer into the sandbox: `log_data_version` reads `<measurements_path>.dvc`.
    import shutil

    from week_06_evaluation_pipeline.datasets import file_md5

    shutil.copy2(measurements_pointer, measurements.with_suffix(".csv.dvc"))
    assert file_md5(measurements) == pointer_md5(measurements), (
        "the sandbox copy must be the bytes the committed pointer names"
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
        # The gate artifacts live in the sandbox, so the project's reports are not overwritten.
        slices_path=tmp_path / "metrics" / "slices.json",
        baseline_path=tmp_path / "metrics" / "baseline.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
    )
    # Run the whole chain: `promote_to_staging` needs the metrics from `evaluate`.
    assert pipeline.validate(sandbox)["passed"]
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert result["run_id"], "training produced no MLflow run"
    pipeline.evaluate(sandbox)
    # `register_best_model` needs a GO verdict. No baseline is seeded, so the
    # regression check is skipped and the floors decide.
    assert pipeline.gate(sandbox)["verdict"] == "GO"
    return sandbox, result


def test_run_carries_the_dvc_data_version(live_settings, logged_run) -> None:
    """The run records WHICH BYTES it trained on."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    tags = client.get_run(result["run_id"]).data.tags
    assert len(tags["dvc_md5"]) == 32
    assert tags["dvc_url"].startswith("s3://") or tags["dvc_url"]
    assert tags["dvc_remote"]


def test_run_has_a_dataset_input(live_settings, logged_run) -> None:
    """mlflow.log_input recorded the training data as a Dataset."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    inputs = client.get_run(result["run_id"]).inputs.dataset_inputs
    assert inputs, "no dataset inputs recorded"
    contexts = {t.value for i in inputs for t in i.tags if t.key == "mlflow.data.context"}
    assert "training" in contexts


def test_mlflow_digest_differs_from_dvc_md5(live_settings, logged_run) -> None:
    """MLflow's dataset digest differs from the DVC md5: they hash different things."""
    sandbox, result = logged_run
    digest = result["mlflow_digest"]
    md5 = pointer_md5(sandbox.measurements_path)
    assert digest and len(digest) == 8
    assert len(md5) == 32
    assert digest != md5[:8]


def test_search_runs_by_data_version_finds_the_run(live_settings, logged_run) -> None:
    """Searching by `dvc_md5` finds the runs trained on this data."""
    sandbox, result = logged_run
    md5 = pointer_md5(sandbox.measurements_path)
    frame = search_runs_by_data_version(live_settings, md5)
    assert not frame.empty
    assert result["run_id"] in set(frame["run_id"])


def test_trace_reaches_the_data(live_settings, logged_run) -> None:
    """The traceability chain reaches the data version, the validation verdict and the gate."""
    from week_06_evaluation_pipeline.registry import (
        promote_to_staging,
        register_best_model,
        trace_alias,
    )

    sandbox, result = logged_run
    # `sandbox` has the `-tests` names and a gate report.
    version = register_best_model(sandbox, result["run_id"])
    promote_to_staging(sandbox, version.version)

    chain = trace_alias(sandbox)
    assert chain["run_id"] == result["run_id"]
    assert chain["dvc_md5"] == pointer_md5(sandbox.measurements_path)
    assert chain["dvc_url"]

    assert chain["data_validation"] == "pass"
    assert chain["schema_version"] == SCHEMA_VERSION
    assert chain["n_failure_cases"] == "0"


def test_run_carries_the_validation_verdict(live_settings, logged_run) -> None:
    """The run carries the validation tags and the ingestion report as an artifact."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    tags = client.get_run(result["run_id"]).data.tags

    assert tags["data_validation"] == "pass"
    assert tags["schema_version"] == SCHEMA_VERSION
    assert tags["n_failure_cases"] == "0"
    assert tags["ingestion_validation"] == "pass"

    artifacts = {a.path for a in client.list_artifacts(result["run_id"], "validation")}
    assert "validation/validation.json" in artifacts


def test_run_carries_the_gate_verdict(live_settings, logged_run) -> None:
    """The run carries the gate verdict, the number of skipped checks and the report artifacts."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    tags = client.get_run(result["run_id"]).data.tags

    assert tags["gate"] == "GO"
    assert tags["gate_criteria_version"]
    assert tags["gate_checks_failed"] == "0"
    assert "gate_checks_skipped" in tags

    artifacts = {a.path for a in client.list_artifacts(result["run_id"], "evaluation")}
    assert "evaluation/gate.json" in artifacts
    assert "evaluation/slices.json" in artifacts


def test_slice_metrics_reach_the_run(live_settings, logged_run) -> None:
    """Per-slice scores are logged as metrics on the run."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    metrics = client.get_run(result["run_id"]).data.metrics

    sliced = {k: v for k, v in metrics.items() if k.startswith("slice.")}
    assert sliced, "no per-slice metrics logged"
    # `50+` is not a legal MLflow metric name; it has to have been sanitised.
    assert "slice.age_band.50plus.f1" in sliced
    assert not any("+" in name for name in sliced)
