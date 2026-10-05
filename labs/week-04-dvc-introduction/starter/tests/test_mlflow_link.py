"""The DVC to MLflow link (Exercise 6).

These tests need the stack and a DVC pointer, and skip without either.
"""

import dataclasses
import shutil

import pytest
from mlflow.tracking import MlflowClient

from week_04_dvc_introduction import pipeline
from week_04_dvc_introduction.datasets import build_measurements, file_md5
from week_04_dvc_introduction.dvc_meta import pointer_md5
from week_04_dvc_introduction.tracking import search_runs_by_data_version

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def logged_run(live_settings, measurements_pointer, all_batches, tmp_path_factory):
    """Train once against the real server, in an isolated workspace."""
    tmp_path = tmp_path_factory.mktemp("link")
    measurements = tmp_path / "data" / "measurements.csv"
    build_measurements(all_batches, measurements)

    # The pointer travels with the data copy, because log_data_version reads it.
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
        measurements_path=measurements,
    )
    # All three stages: promote_to_staging needs the metrics that evaluate logs.
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert result["run_id"], "training produced no MLflow run"
    pipeline.evaluate(sandbox)
    return sandbox, result


@pytest.mark.skip(reason="Exercise 6 — implement log_data_version(), then delete this skip marker.")
def test_run_carries_the_dvc_data_version(live_settings, logged_run) -> None:
    """The run records WHICH BYTES it trained on."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    tags = client.get_run(result["run_id"]).data.tags
    for key in ("dvc_md5", "dvc_url", "dvc_remote", "data_file"):
        assert key in tags, f"The run has no `{key}` tag."
    assert tags["dvc_md5"] == pointer_md5(sandbox.measurements_path), (
        "`dvc_md5` is not the md5 in the pointer file."
    )
    assert tags["dvc_url"].startswith("s3://"), "`dvc_url` should be an s3:// URI."
    assert tags["dvc_remote"] == f"{sandbox.dvc_bucket}/{sandbox.dvc_remote_path}", (
        "`dvc_remote` should be <bucket>/<remote path>."
    )
    assert tags["data_file"] == "measurements.csv", "`data_file` should be the file name."


@pytest.mark.skip(reason="Exercise 6 — implement log_dataset_input(), then delete this skip marker.")
def test_run_has_a_dataset_input(live_settings, logged_run) -> None:
    """mlflow.log_input recorded the training data as a Dataset."""
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    inputs = client.get_run(result["run_id"]).inputs.dataset_inputs
    assert inputs, "The run has no dataset input: is mlflow.log_input called?"
    contexts = {t.value for i in inputs for t in i.tags if t.key == "mlflow.data.context"}
    assert "training" in contexts, "The dataset input's context should be 'training'."


@pytest.mark.skip(reason="Exercise 6 — implement log_dataset_input(), then delete this skip marker.")
def test_mlflow_digest_differs_from_dvc_md5(live_settings, logged_run) -> None:
    """MLflow's digest and DVC's md5 of the same file are different values."""
    sandbox, result = logged_run
    digest = result["mlflow_digest"]
    md5 = pointer_md5(sandbox.measurements_path)
    assert digest and len(digest) == 8, "log_dataset_input should return the digest."
    assert len(md5) == 32
    assert digest != md5[:8]


@pytest.mark.skip(reason="Exercise 6 — implement log_data_version(), then delete this skip marker.")
def test_search_runs_by_data_version_finds_the_run(live_settings, logged_run) -> None:
    """A search by the data's md5 finds the run."""
    sandbox, result = logged_run
    md5 = pointer_md5(sandbox.measurements_path)
    frame = search_runs_by_data_version(live_settings, md5)
    assert result["run_id"] in set(frame.get("run_id", [])), (
        "No run found with tags.dvc_md5 equal to the pointer's md5."
    )


@pytest.mark.skip(reason="Exercise 6 — implement both dvc_link functions, then delete this skip marker.")
def test_trace_reaches_the_data(live_settings, logged_run) -> None:
    """The traceability chain includes the data version."""
    from week_04_dvc_introduction.registry import (
        promote_to_staging,
        register_best_model,
        trace_alias,
    )

    sandbox, result = logged_run
    version = register_best_model(live_settings, result["run_id"])
    promote_to_staging(live_settings, version.version)

    chain = trace_alias(live_settings)
    assert chain["run_id"] == result["run_id"]
    assert chain["dvc_md5"] == pointer_md5(sandbox.measurements_path), (
        "The traced run does not carry the data version."
    )
    assert chain["dvc_url"], "The traced run has no `dvc_url` tag."
