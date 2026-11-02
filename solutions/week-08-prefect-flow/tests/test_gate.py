"""Does the gate actually gate?

The distinction these tests defend: a gate that stops the pipeline AFTER the
downstream work has been done is not a gate, it is a log line. So it is not
enough to check that `validate` raises — the point is that nothing downstream
happened.

Every test builds its own project directory in `tmp_path`, so none of them needs
Docker, Silo, DVC or the tracked dataset.
"""

from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from week_08_prefect_flow import pipeline
from week_08_prefect_flow.pipeline import ValidationFailed
from week_08_prefect_flow.validation import read_report

pytestmark = pytest.mark.data


@pytest.fixture
def sandbox(settings, tmp_path):
    """A settings object pointing entirely inside tmp_path.

    "ENTIRELY" WAS NOT TRUE UNTIL WEEK 13, AND AN EVIDENCE MANIFEST IS WHAT FOUND IT.

    This fixture redirected eight of the eleven path fields in `Settings`. The three
    it missed — `slices_path`, `baseline_path` and `gate_report_path` — arrived in
    Week 6 and nobody came back to the fixture, so every run of this file quietly
    overwrote the REAL `metrics/slices.json` (and friends) in the working tree with
    numbers computed from a synthetic six-row batch.

    Nothing noticed for seven weeks, because nothing was watching those files. Week
    13 hashes them into an evidence manifest, a Model Card staleness check went red,
    and the fix was back-ported to every week from 6 onwards.

    Two things worth keeping. The bug's SHAPE: a fixture whose docstring says
    "entirely" and whose body lists a subset is the most ordinary way isolation
    leaks — not carelessness, but a list extended in one place and not the other.
    And what caught it: not a test of the fixture, not code review, not seven weeks
    of a green suite, but a hash over a file nobody had thought to watch.
    """
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        measurements_path=tmp_path / "data" / "measurements.csv",
        processed_dir=tmp_path / "data" / "processed",
        models_dir=tmp_path / "models",
        metrics_path=tmp_path / "metrics" / "metrics.json",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        validation_report_path=tmp_path / "reports" / "validation.json",
        # The 3 that leaked. Back-ported from Week 13.
        baseline_path=tmp_path / "metrics" / "baseline.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
        slices_path=tmp_path / "metrics" / "slices.json",
        mlflow_tracking_uri="http://127.0.0.1:1",  # unreachable on purpose
    )


def write_measurements(sandbox, frame: pd.DataFrame) -> None:
    sandbox.measurements_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(sandbox.measurements_path, index=False, lineterminator="\n")


def legal_batch(rows: int = 40) -> pd.DataFrame:
    """A synthetic batch that satisfies the ingestion contract.

    Built here rather than read from the real dataset so this file has no data
    dependency at all. Both classes are present because `prepare` does a
    stratified split.
    """
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
    """The `dvc.yaml` edge is enforced by DVC; this is the manual-run half.

    A gate that only holds when you use the front door is not a gate.
    """
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
    """THE assertion of this file.

    Failing loudly is easy. Failing before anything downstream has been written
    is the property that makes the gate worth having — otherwise a later stage,
    a later student, or a CI job picks up the half-built output and trains on it.
    """
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
    """validate -> prepare -> train -> evaluate, offline.

    The MLflow half of `train` is guarded, so the whole pipeline works with the
    stack down. That is what keeps this lab runnable in the autograder.
    """
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
    """Where the imputation happens is the week's central claim.

    Inside the Pipeline means it is fitted on training data, serialised with the
    model, and applied identically at inference. In a notebook it would not
    travel, and that gap is training-serving skew.
    """
    import joblib

    write_measurements(sandbox, legal_batch(60))
    pipeline.validate(sandbox)
    pipeline.prepare(sandbox)
    pipeline.train(sandbox)

    model = joblib.load(sandbox.models_dir / "model.pkl")
    assert list(model.named_steps) == ["imputer", "scaler", "classifier"]
    assert model.named_steps["imputer"].strategy == sandbox.impute_strategy


def test_the_sentinel_conversion_is_what_makes_training_legal(sandbox):
    """The negative test for Exercise 3, stated as a comparison.

    Same frame, same schema, one difference: `to_nullable`. Without it the
    training contract rejects the data; with it the contract passes and no value
    was invented. The conversion is not a convenience — it is the step that makes
    training legal at all.
    """
    from week_08_prefect_flow.schemas import MODEL_INPUT_COLUMNS, ModelInput
    from week_08_prefect_flow.validation import to_nullable, validate_frame

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
    """`measurement_date` must never reach the model.

    It would leak batch identity into the features, and a new patient does not
    have one at inference time.
    """
    features, _, _ = pipeline.prepare_model_input(legal_batch())
    assert "measurement_date" not in features.columns
    assert "outcome" not in features.columns
