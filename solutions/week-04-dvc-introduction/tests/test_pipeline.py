"""The three pipeline stages. They ship complete, so these tests pass from the start.

Each test builds its own dataset in `tmp_path`.
"""

import dataclasses
import json

import joblib
import pytest

from week_04_dvc_introduction import pipeline
from week_04_dvc_introduction.data import FEATURE_COLUMNS, load_measurements


@pytest.fixture
def sandbox(settings, all_batches, tmp_path):
    """A separate workspace holding the full dataset, without an MLflow server."""
    import pandas as pd

    measurements = tmp_path / "data" / "measurements.csv"
    measurements.parent.mkdir(parents=True, exist_ok=True)
    frames = [pd.read_csv(path) for path in sorted(all_batches.glob("batch_*.csv"))]
    pd.concat(frames, ignore_index=True).to_csv(
        measurements, index=False, lineterminator="\n"
    )
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=measurements,
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        # No server on this port, so these tests never create MLflow runs.
        mlflow_tracking_uri="http://127.0.0.1:1",
    )


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
    with pytest.raises(FileNotFoundError, match="dvc-pull|build-data"):
        pipeline.prepare(sandbox)


def test_train_writes_loadable_model(sandbox) -> None:
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    model = joblib.load(result["model_path"])
    train = load_measurements(sandbox.processed_dir / "train.csv")
    assert len(model.predict(train[FEATURE_COLUMNS].head(5))) == 5


def test_train_writes_null_run_id_when_server_absent(sandbox) -> None:
    """Without a tracking server, train still succeeds and records no run."""
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
    """Version 2 does not reproduce the Week 1-3 metrics (Exercise 5, written answer)."""
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    metrics = pipeline.evaluate(sandbox)["metrics"]
    assert metrics["f1"] != pytest.approx(0.5785, abs=0.001)
    assert metrics["accuracy"] != pytest.approx(0.7344, abs=0.001)
