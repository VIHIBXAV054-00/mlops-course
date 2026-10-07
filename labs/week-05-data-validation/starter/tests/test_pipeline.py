"""The prepare, train and evaluate stages, run on the full dataset in `tmp_path`.

The fixture writes a passing validation report, so these tests do not depend on
Exercise 4. `test_gate.py` tests the gate.
"""

import dataclasses
import json

import joblib
import pandas as pd
import pytest

from week_05_data_validation import pipeline
from week_05_data_validation.datasets import build_measurements


@pytest.fixture
def sandbox(settings, raw_batches, tmp_path):
    """A separate workspace holding the full dataset, without an MLflow server."""
    measurements = tmp_path / "data" / "measurements.csv"
    build_measurements(raw_batches, measurements)
    sandbox = dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=measurements,
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        # No server on this port, so these tests never create MLflow runs.
        mlflow_tracking_uri="http://127.0.0.1:1",
    )
    sandbox.validation_report_path.parent.mkdir(parents=True)
    sandbox.validation_report_path.write_text(json.dumps({"passed": True}))
    return sandbox


def test_prepare_writes_train_and_test(sandbox) -> None:
    result = pipeline.prepare(sandbox)
    assert (sandbox.processed_dir / "train.csv").exists()
    assert (sandbox.processed_dir / "test.csv").exists()
    assert result["rows_in"] == 768
    assert result["rows_train"] + result["rows_test"] == 768


def test_prepare_keeps_measurement_date(sandbox) -> None:
    pipeline.prepare(sandbox)
    train = pd.read_csv(sandbox.processed_dir / "train.csv")
    assert "measurement_date" in train.columns


def test_prepare_is_missing_data_aware(sandbox) -> None:
    """A helpful error, not a traceback, when the DVC-tracked file is absent."""
    sandbox.measurements_path.unlink()
    with pytest.raises(FileNotFoundError, match="build-data|dvc-pull"):
        pipeline.prepare(sandbox)


def test_train_writes_a_model_and_a_null_run_id(sandbox) -> None:
    """Without a tracking server, train still writes the model and records no run."""
    pipeline.prepare(sandbox)
    result = pipeline.train(sandbox)
    assert hasattr(joblib.load(result["model_path"]), "predict_proba")
    assert result["run_id"] is None
    assert json.loads(sandbox.run_id_path.read_text())["run_id"] is None


def test_evaluate_writes_metrics_json(sandbox) -> None:
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    result = pipeline.evaluate(sandbox)
    assert set(result["metrics"]) == {"accuracy", "precision", "recall", "f1", "roc_auc"}
    assert json.loads(sandbox.metrics_path.read_text()) == result["metrics"]
