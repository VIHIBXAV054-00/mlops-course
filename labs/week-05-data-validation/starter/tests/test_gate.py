"""The validate stage (Exercise 4) and the model input (Exercise 5).

Every test builds its own workspace in `tmp_path`, without an MLflow server.
"""

import dataclasses

import joblib
import pandas as pd
import pytest

from week_05_data_validation import pipeline
from week_05_data_validation.datasets import build_measurements
from week_05_data_validation.pipeline import ValidationFailed
from week_05_data_validation.validation import read_report


@pytest.fixture
def sandbox(settings, tmp_path):
    """Settings that point inside tmp_path."""
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=tmp_path / "data" / "measurements.csv",
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        # No server on this port, so these tests never create MLflow runs.
        mlflow_tracking_uri="http://127.0.0.1:1",
    )


def legal_batch(rows: int = 40) -> pd.DataFrame:
    """A small batch that passes RawMeasurements, with both outcomes."""
    return pd.DataFrame(
        {
            "measurement_date": ["2024-01-01"] * rows,
            "pregnancies": [i % 5 for i in range(rows)],
            "glucose": [90 + i for i in range(rows)],
            "blood_pressure": [60 + (i % 20) for i in range(rows)],
            "skin_thickness": [20 + (i % 15) for i in range(rows)],
            "insulin": [80 + i for i in range(rows)],
            "bmi": [22.0 + (i % 10) for i in range(rows)],
            "diabetes_pedigree": [0.1 + (i % 9) * 0.1 for i in range(rows)],
            "age": [21 + (i % 40) for i in range(rows)],
            "outcome": [i % 2 for i in range(rows)],
        }
    )


def write_measurements(sandbox, frame: pd.DataFrame) -> None:
    sandbox.measurements_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(sandbox.measurements_path, index=False, lineterminator="\n")


# ── The validate stage (Exercise 4) ──────────────────────────────────────────


def test_validate_passes_a_legal_batch_and_writes_the_report(sandbox) -> None:
    write_measurements(sandbox, legal_batch())
    report = pipeline.validate(sandbox)
    assert report["passed"]
    assert read_report(sandbox.validation_report_path)["passed"], (
        "validate did not write a passing report to settings.validation_report_path."
    )
    assert "sentinel_zeros" in report, "Add the sentinel counts to the report."


def test_validate_writes_the_report_and_then_stops_a_bad_batch(sandbox) -> None:
    frame = legal_batch()
    frame.loc[0, "outcome"] = 2
    write_measurements(sandbox, frame)
    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)

    report = read_report(sandbox.validation_report_path)
    assert report, "validate stopped without writing the report. Write it first."
    assert report["passed"] is False
    assert "isin([0, 1])" in report["by_check"]


def test_prepare_refuses_to_run_without_a_report(sandbox) -> None:
    write_measurements(sandbox, legal_batch())
    with pytest.raises(FileNotFoundError, match="validate"):
        pipeline.prepare(sandbox)


def test_a_failed_validation_blocks_prepare_and_writes_nothing(sandbox) -> None:
    frame = legal_batch()
    frame.loc[0, "bmi"] = 280.0
    write_measurements(sandbox, frame)
    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)
    with pytest.raises(ValidationFailed):
        pipeline.prepare(sandbox)
    assert not (sandbox.processed_dir / "train.csv").exists()
    assert not (sandbox.models_dir / "model.pkl").exists()


# ── The model input and the imputer (Exercise 5) ─────────────────────────────


def test_prepare_model_input_turns_zeros_into_missing_values() -> None:
    frame = legal_batch()
    frame.loc[0, "glucose"] = 0
    features, labels, report = pipeline.prepare_model_input(frame)
    assert report["passed"], "prepare_model_input should return the ModelInput report."
    assert report["schema"] == "ModelInput"
    assert features["glucose"].isna().sum() == 1, "The zero glucose should be missing now."
    assert str(features["glucose"].dtype) == "float64"
    assert list(features.columns) == list(pipeline.FEATURE_COLUMNS)
    assert len(labels) == len(frame)


def test_prepare_model_input_stops_a_value_it_cannot_repair() -> None:
    frame = legal_batch()
    frame.loc[0, "bmi"] = 280.0
    with pytest.raises(ValidationFailed):
        pipeline.prepare_model_input(frame)


def test_the_model_carries_an_imputer(sandbox) -> None:
    write_measurements(sandbox, legal_batch(60))
    pipeline.validate(sandbox)
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    model = joblib.load(sandbox.models_dir / "model.pkl")
    assert list(model.named_steps) == ["imputer", "scaler", "classifier"]
    assert model.named_steps["imputer"].strategy == sandbox.impute_strategy


def test_the_pipeline_reaches_the_week_5_metrics(sandbox, raw_batches) -> None:
    """On the full dataset, the median imputer gives the course's pinned metrics."""
    build_measurements(raw_batches, sandbox.measurements_path)
    pipeline.validate(sandbox)
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)
    metrics = pipeline.evaluate(sandbox)["metrics"]
    assert metrics == {
        "accuracy": 0.7656,
        "precision": 0.6964,
        "recall": 0.5821,
        "f1": 0.6341,
        "roc_auc": 0.8345,
    }
