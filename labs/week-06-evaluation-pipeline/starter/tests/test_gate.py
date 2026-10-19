"""The data gate: a failing `validate` must stop everything downstream.

Every test builds its project directory in `tmp_path`, so no Docker, Silo or DVC is needed.
"""

from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from week_06_evaluation_pipeline import pipeline
from week_06_evaluation_pipeline.pipeline import ValidationFailed
from week_06_evaluation_pipeline.validation import read_report


@pytest.fixture
def sandbox(settings, tmp_path):
    """A settings object with every path inside `tmp_path` and MLflow unreachable."""
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=tmp_path / "data" / "measurements.csv",
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        baseline_path=tmp_path / "metrics" / "baseline.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
        slices_path=tmp_path / "metrics" / "slices.json",
        mlflow_tracking_uri="http://127.0.0.1:1",  # unreachable on purpose
    )


def write_measurements(sandbox, frame: pd.DataFrame) -> None:
    sandbox.measurements_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(sandbox.measurements_path, index=False, lineterminator="\n")


def legal_batch(rows: int = 40) -> pd.DataFrame:
    """A synthetic batch that satisfies the ingestion contract, with both classes."""
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


def test_validate_passes_on_a_legal_batch_and_writes_a_report(sandbox):
    write_measurements(sandbox, legal_batch())
    report = pipeline.validate(sandbox)
    assert report["passed"]
    assert read_report(sandbox.validation_report_path)["passed"]


def test_validate_raises_on_an_illegal_batch(sandbox):
    frame = legal_batch()
    frame.loc[0, "age"] = 250
    write_measurements(sandbox, frame)
    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)


def test_the_report_is_written_even_when_validation_fails(sandbox):
    """A gate that blocks the pipeline and leaves no evidence is untriageable."""
    frame = legal_batch()
    frame.loc[0, "outcome"] = 2
    write_measurements(sandbox, frame)

    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)

    report = read_report(sandbox.validation_report_path)
    assert report["passed"] is False
    assert "isin([0, 1])" in report["by_check"]


def test_prepare_refuses_to_run_without_a_passing_report(sandbox):
    """`prepare` run by hand also refuses without a passing report (`dvc.yaml` enforces it for `dvc repro`)."""
    write_measurements(sandbox, legal_batch())
    with pytest.raises(FileNotFoundError, match="validate"):
        pipeline.prepare(sandbox)


def test_prepare_refuses_to_run_after_a_failed_report(sandbox):
    frame = legal_batch()
    frame.loc[0, "insulin"] = -1
    write_measurements(sandbox, frame)
    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)
    with pytest.raises(ValidationFailed):
        pipeline.prepare(sandbox)


def test_a_blocked_run_writes_no_processed_data(sandbox):
    """A blocked run writes no processed data, so no later stage can use half-built output."""
    frame = legal_batch()
    frame.loc[0, "bmi"] = 280.0
    write_measurements(sandbox, frame)

    with pytest.raises(ValidationFailed):
        pipeline.validate(sandbox)
    with pytest.raises(ValidationFailed):
        pipeline.prepare(sandbox)

    assert not (sandbox.processed_dir / "train.csv").exists()
    assert not (sandbox.processed_dir / "test.csv").exists()
    assert not (sandbox.models_dir / "model.pkl").exists()
    assert not sandbox.metrics_path.exists()


def test_the_happy_path_runs_end_to_end_without_mlflow(sandbox):
    """validate, prepare, train and evaluate run end to end with MLflow unreachable."""
    write_measurements(sandbox, legal_batch(60))

    assert pipeline.validate(sandbox)["passed"]
    prepared = pipeline.prepare(sandbox)
    assert prepared["rows_in"] == 60

    trained = pipeline.train(sandbox)
    assert trained["run_id"] is None  # tracking URI is deliberately unreachable
    assert (sandbox.models_dir / "model.pkl").exists()

    evaluated = pipeline.evaluate(sandbox)
    assert set(evaluated["metrics"]) == {
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
    }
    assert json.loads(sandbox.metrics_path.read_text())


def test_the_trained_pipeline_carries_an_imputer(sandbox):
    """The imputer is a step of the saved Pipeline, so it is applied again at inference."""
    import joblib

    write_measurements(sandbox, legal_batch(60))
    pipeline.validate(sandbox)
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)

    model = joblib.load(sandbox.models_dir / "model.pkl")
    assert list(model.named_steps) == ["imputer", "scaler", "classifier"]
    assert model.named_steps["imputer"].strategy == sandbox.impute_strategy


def test_the_sentinel_conversion_is_what_makes_training_legal(sandbox):
    """The same frame fails `ModelInput` without `to_nullable` and passes with it."""
    from week_06_evaluation_pipeline.schemas import MODEL_INPUT_COLUMNS, ModelInput
    from week_06_evaluation_pipeline.validation import to_nullable, validate_frame

    frame = legal_batch()
    frame.loc[0, "glucose"] = 0
    projected = frame[MODEL_INPUT_COLUMNS]

    unconverted = validate_frame(projected, ModelInput, "unconverted")
    assert not unconverted["passed"]
    assert "greater_than(0)" in unconverted["by_check"]

    converted = validate_frame(to_nullable(projected), ModelInput, "converted")
    assert converted["passed"]

    # prepare_model_input does the conversion for you, so it succeeds — and hands
    # back a features frame carrying one real null rather than one fake zero.
    features, labels, report = pipeline.prepare_model_input(frame)
    assert report["passed"]
    assert features["glucose"].isna().sum() == 1
    assert len(labels) == len(frame)


def test_prepare_model_input_rejects_a_frame_it_cannot_repair(sandbox):
    """Not every violation is a sentinel. Those must still stop the pipeline."""
    frame = legal_batch()
    frame.loc[0, "bmi"] = 280.0  # a unit change, not a sentinel
    with pytest.raises(ValidationFailed):
        pipeline.prepare_model_input(frame)


def test_prepare_model_input_drops_the_metadata_column(sandbox):
    """`measurement_date` must not reach the model."""
    features, _, _ = pipeline.prepare_model_input(legal_batch())
    assert "measurement_date" not in features.columns
    assert "outcome" not in features.columns
