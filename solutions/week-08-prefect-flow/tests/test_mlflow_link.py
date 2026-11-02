"""The DVC to MLflow link (Exercise 6).

Needs the stack AND a DVC pointer. Both guards are fixtures, so this file is
green with either one absent.
"""

import dataclasses

import pytest
from mlflow.tracking import MlflowClient

from week_08_prefect_flow import pipeline
from week_08_prefect_flow.datasets import build_measurements
from week_08_prefect_flow.dvc_meta import pointer_md5
from week_08_prefect_flow.schemas import SCHEMA_VERSION
from week_08_prefect_flow.tracking import search_runs_by_data_version

pytestmark = [pytest.mark.integration, pytest.mark.live]


@pytest.fixture(scope="module")
def logged_run(live_settings, measurements_pointer, raw_batches, tmp_path_factory):
    """Train once against the real server, in an isolated workspace."""
    tmp_path = tmp_path_factory.mktemp("link")
    measurements = tmp_path / "data" / "measurements.csv"
    build_measurements(2, raw_batches, measurements)

    # The pointer has to travel WITH the data copy. `log_data_version` reads
    # `<measurements_path>.dvc`, so pointing `measurements_path` into the sandbox
    # without bringing the pointer along raises FileNotFoundError from
    # dvc_meta.read_pointer — and it does so only when MLflow is reachable, which
    # is why this went unnoticed while the stack was down.
    #
    # Copying it is honest rather than a fudge: `build_measurements(2, ...)` is
    # byte-deterministic, so the sandbox file IS the bytes the project's pointer
    # names. The assertion below is what keeps that true.
    import shutil

    from week_08_prefect_flow.datasets import file_md5

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
        # New in Week 6. The three gate artifacts have to live in the sandbox
        # too, or `pipeline.gate` would read and overwrite the project's real
        # reports/gate.json — and `register` would then be gated on whatever
        # state the student's workspace happens to be in.
        slices_path=tmp_path / "metrics" / "slices.json",
        baseline_path=tmp_path / "metrics" / "baseline.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
    )
    # The WHOLE chain, in order, including `evaluate` — which is not optional
    # here. `promote_to_staging` reads `f1` and `roc_auc` off the source run to
    # build its evidence tags, and those metrics are written by `evaluate`. A
    # fixture that stops after `train` produces a run with params and tags but no
    # scores, and the failure surfaces four tests later as `KeyError: 'f1'`.
    assert pipeline.validate(sandbox)["passed"]
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert result["run_id"], "training produced no MLflow run"
    pipeline.evaluate(sandbox)
    # And `gate`, for the same reason `evaluate` is here: `register_best_model`
    # now calls `pipeline.require_go`, so a fixture that stops before the gate
    # produces a run nothing can be registered from. Same lesson as Week 4's —
    # every stage a later test reads from has to actually have run.
    #
    # No baseline is seeded in the sandbox, deliberately: the regression check
    # reports SKIPPED and the verdict is still a GO earned by the floors, which
    # is exactly the first-model-in-a-new-project path.
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
    """The punchline of the week, as an assertion.

    MLflow's digest is an 8-character truncated md5 of the first 10,000 rows'
    PARSED VALUES plus the row count and column names. DVC's md5 is a
    32-character hash of the file's BYTES. Same file, different claims — and
    only the DVC one proves "these exact bytes".
    """
    sandbox, result = logged_run
    digest = result["mlflow_digest"]
    md5 = pointer_md5(sandbox.measurements_path)
    assert digest and len(digest) == 8
    assert len(md5) == 32
    assert digest != md5[:8]


def test_search_runs_by_data_version_finds_the_run(live_settings, logged_run) -> None:
    """The query Week 3 could not express: which runs saw THIS data?"""
    sandbox, result = logged_run
    md5 = pointer_md5(sandbox.measurements_path)
    frame = search_runs_by_data_version(live_settings, md5)
    assert not frame.empty
    assert result["run_id"] in set(frame["run_id"])


def test_trace_reaches_the_data(live_settings, logged_run) -> None:
    """The Week 3 chain, now with its final link."""
    from week_08_prefect_flow.registry import (
        promote_to_staging,
        register_best_model,
        trace_alias,
    )

    sandbox, result = logged_run
    # `sandbox`, not `live_settings` — it carries the same `-tests` experiment
    # and model names, plus the sandbox gate report that register/promote now
    # insist on.
    version = register_best_model(sandbox, result["run_id"])
    promote_to_staging(sandbox, version.version)

    chain = trace_alias(sandbox)
    assert chain["run_id"] == result["run_id"]
    assert chain["dvc_md5"] == pointer_md5(sandbox.measurements_path)
    assert chain["dvc_url"]

    # New in Week 5 — the chain reaches the VERDICT, not just the bytes. The
    # schema version is the load-bearing half: without it, "passed validation"
    # silently re-points at whatever the contract says today.
    assert chain["data_validation"] == "pass"
    assert chain["schema_version"] == SCHEMA_VERSION
    assert chain["n_failure_cases"] == "0"


def test_run_carries_the_validation_verdict(live_settings, logged_run) -> None:
    """The Week 5 tags, and the ingestion report as a run artifact.

    Tags answer "was it checked?". Only the artifact answers "what did the check
    see?" — which is the difference between a claim and evidence.
    """
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
    """New in Week 6 — the eighth link, and the artifacts behind it.

    Two things are asserted and only one of them is the verdict. The other is
    `gate_checks_skipped`, because "GO with four criteria unchecked" and "GO"
    are different claims, and the only way to tell them apart six months later
    is if the run recorded both.
    """
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
    """Per-slice scores are metrics on the run, not only a file next to it.

    Only a few keys per group, on purpose: the full table is the artifact, and a
    run carrying two hundred metrics is a run nobody reads.
    """
    sandbox, result = logged_run
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    metrics = client.get_run(result["run_id"]).data.metrics

    sliced = {k: v for k, v in metrics.items() if k.startswith("slice.")}
    assert sliced, "no per-slice metrics logged"
    # `50+` is not a legal MLflow metric name; it has to have been sanitised.
    assert "slice.age_band.50plus.f1" in sliced
    assert not any("+" in name for name in sliced)
