"""The pipeline stages carried over from Week 4: prepare, train, evaluate.

Each test builds its own dataset into `tmp_path` and points a copy of Settings
at it, so these run identically on a finished machine and in the autograder.

Week 5 change: `prepare` now refuses to run without a PASSING validation report,
so the fixture writes one directly. That keeps these tests about the split and
the stages — which ship complete — rather than about Exercise 4. The gate itself
is covered by `test_gate.py`, which writes no report on purpose.
"""

import dataclasses
import json

import joblib
import pytest

from week_08_prefect_flow import pipeline
from week_08_prefect_flow.data import FEATURE_COLUMNS, load_measurements

pytestmark = pytest.mark.eval


@pytest.fixture
def sandbox(settings, raw_batches, tmp_path):
    """A complete, isolated workspace holding dataset version 2.

    The data is assembled here directly rather than through
    `datasets.build_measurements`, so these tests exercise the pipeline stages
    (which ship complete) independently of Exercise 2. That means a student gets
    real signal that prepare/train/evaluate work on their machine before they
    have written a line — and a failure here points at the pipeline, not at
    their dataset builder. `test_datasets.py` is what covers the builder.
    """
    import pandas as pd

    measurements = tmp_path / "data" / "measurements.csv"
    measurements.parent.mkdir(parents=True, exist_ok=True)
    frames = [
        pd.read_csv(raw_batches / name)
        for name in ("batch_01_baseline.csv", "batch_02_new_arrival.csv")
    ]
    pd.concat(frames, ignore_index=True).to_csv(
        measurements, index=False, lineterminator="\n"
    )
    sandbox = dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=measurements,
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        # Unreachable on purpose: these tests must never touch a real server.
        mlflow_tracking_uri="http://127.0.0.1:1",
    )
    # A passing verdict, written by hand rather than produced by `validate`, so a
    # student who has not done Exercise 4 yet still gets real signal from the
    # stages that ship complete. `test_gate.py` is where the gate is tested.
    sandbox.validation_report_path.parent.mkdir(parents=True, exist_ok=True)
    sandbox.validation_report_path.write_text(
        json.dumps({"passed": True, "n_failure_cases": 0, "schema": "RawMeasurements"})
    )
    return sandbox


def test_prepare_writes_train_and_test(sandbox) -> None:
    result = pipeline.prepare(sandbox)
    assert (sandbox.processed_dir / "train.csv").exists()
    assert (sandbox.processed_dir / "test.csv").exists()
    assert result["rows_in"] == 768


def test_prepare_split_sizes_sum_to_input(sandbox) -> None:
    result = pipeline.prepare(sandbox)
    assert result["rows_train"] + result["rows_test"] == result["rows_in"]


def test_prepare_keeps_measurement_date(sandbox) -> None:
    """Lineage survives into the processed splits."""
    pipeline.prepare(sandbox)
    train = load_measurements(sandbox.processed_dir / "train.csv")
    assert "measurement_date" in train.columns


def test_prepare_is_missing_data_aware(sandbox) -> None:
    """A helpful error, not a traceback, when the DVC-tracked file is absent."""
    sandbox.measurements_path.unlink()
    with pytest.raises(FileNotFoundError, match="dvc-pull|data-v2"):
        pipeline.prepare(sandbox)


def test_train_writes_loadable_model(sandbox) -> None:
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    model = joblib.load(result["model_path"])
    train = load_measurements(sandbox.processed_dir / "train.csv")
    assert len(model.predict(train[FEATURE_COLUMNS].head(5))) == 5


def test_train_writes_null_run_id_when_server_absent(sandbox) -> None:
    """The MLflow guard: no server means no run, but the stage still succeeds.

    This is what lets `dvc repro` work in CI, and why the pipeline is not
    hostage to a running container.
    """
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert result["run_id"] is None
    payload = json.loads(sandbox.run_id_path.read_text())
    assert payload["run_id"] is None


def test_evaluate_writes_metrics_json(sandbox) -> None:
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    result = pipeline.evaluate(sandbox)
    assert set(result["metrics"]) == {
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
    }
    assert json.loads(sandbox.metrics_path.read_text()) == result["metrics"]


def test_v2_metrics_differ_from_the_canonical_pins(sandbox) -> None:
    """Version 2 holds the same 768 rows as diabetes.csv — and scores differently.

    Not a bug, and worth locking in so nobody "fixes" it: v2's rows are in
    batch-arrival order rather than the original file order, so the stratified
    split selects different rows and the metrics move. Week 5's imputer moves them
    again — see the comparison table in the lab README.
    """
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    metrics = pipeline.evaluate(sandbox)["metrics"]
    assert metrics["f1"] != pytest.approx(0.5785, abs=0.001)
    assert metrics["accuracy"] != pytest.approx(0.7344, abs=0.001)
