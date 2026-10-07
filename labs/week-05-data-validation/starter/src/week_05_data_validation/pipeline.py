"""The four pipeline stages that `dvc.yaml` declares: validate, prepare, train, evaluate.

Each stage reads and writes files, and each runs by hand through `src/main.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from .config import Settings
from .data import FEATURE_COLUMNS, TARGET_COLUMN, load_measurements, split_measurements
from .model import build_model, evaluate_model
from .schemas import MODEL_INPUT_COLUMNS, ModelInput, RawMeasurements
from .validation import (
    read_raw,
    read_report,
    sentinel_counts,
    to_nullable,
    validate_frame,
    write_report,
)


class ValidationFailed(RuntimeError):
    """The data broke its contract."""


def _require_measurements(settings: Settings) -> Path:
    path = settings.measurements_path
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} is missing. It is DVC-tracked, so a fresh clone does "
            "not have it. Run `make build-data` to rebuild it from data/raw/, "
            "or `make dvc-pull` to fetch it."
        )
    return path


def _require_validated(settings: Settings) -> dict:
    """The last validation report, or an error if it is missing or failed."""
    report = read_report(settings.validation_report_path)
    if not report:
        raise FileNotFoundError(
            f"{settings.validation_report_path.name} is missing: the validate stage "
            "has not run. Run `make repro`."
        )
    if not report.get("passed"):
        raise ValidationFailed(
            f"The last validation failed with {report.get('n_failure_cases')} "
            "failure case(s). Fix the data before you train on it."
        )
    return report


def validate(settings: Settings) -> dict:
    """Stage 0: check the dataset against RawMeasurements and write the report.

    Raises ValidationFailed, after the report is written, if the data fails.
    """
    source = _require_measurements(settings)
    frame = read_raw(source)
    # TODO(student) Exercise 4: check `frame` against RawMeasurements, and add
    # the zero counts of `sentinel_counts` to the report as "sentinel_zeros".
    # Write the report to settings.validation_report_path. Then, if the data
    # failed, raise ValidationFailed with a message that names the number of
    # failure cases. Return the report.
    raise NotImplementedError("pipeline.validate is not written yet (Exercise 4).")


def prepare(settings: Settings) -> dict:
    """Stage 1: split the versioned dataset into train and test CSVs.

    It runs only after a passing validation. `measurement_date` stays in the
    files, but `train` does not use it as a feature.
    """
    # TODO(student) Exercise 4: stop here unless the last validation passed.
    # `_require_validated` does that check.
    source = _require_measurements(settings)
    frame = load_measurements(source)
    train_frame, test_frame = split_measurements(frame, settings)

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    train_path = settings.processed_dir / "train.csv"
    test_path = settings.processed_dir / "test.csv"
    train_frame.to_csv(train_path, index=False, lineterminator="\n")
    test_frame.to_csv(test_path, index=False, lineterminator="\n")

    return {
        "rows_in": len(frame),
        "rows_train": len(train_frame),
        "rows_test": len(test_frame),
        "train_path": str(train_path),
        "test_path": str(test_path),
    }


def prepare_model_input(frame) -> tuple:
    """Turn a processed split into model input. Returns (features, labels, report).

    The sentinel zeros become missing values, and ModelInput checks the result.
    """
    # TODO(student) Exercise 5: first replace the sentinel zeros in
    # frame[MODEL_INPUT_COLUMNS] with missing values. Check the result against
    # ModelInput, and raise ValidationFailed if it fails. Return the features
    # as float64, the type `predict_one` sends, and the ModelInput report.
    features = frame[FEATURE_COLUMNS]
    labels = frame[TARGET_COLUMN]
    return features, labels, {}


def train(settings: Settings) -> dict:
    """Stage 2: fit the model, and record the data version and verdict on the MLflow run.

    Without a tracking server the stage still writes the model, and writes
    `{"run_id": null}` as the run id.
    """
    train_path = settings.processed_dir / "train.csv"
    if not train_path.exists():
        raise FileNotFoundError(
            f"{train_path.name} is missing. Run the prepare stage first "
            "(`make repro`)."
        )

    frame = load_measurements(train_path)
    features, labels, input_report = prepare_model_input(frame)
    model = build_model(
        settings.model_family,
        {"C": settings.model_c},
        settings,
        impute=settings.impute_strategy,
    )
    model.fit(features, labels)

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    model_path = settings.models_dir / "model.pkl"
    joblib.dump(model, model_path)

    run_id = None
    digest = None
    from .tracking import mlflow_available

    if mlflow_available(settings):
        import mlflow

        from .dvc_link import (
            dvc_data_url,
            log_data_version,
            log_dataset_input,
            log_validation,
            require_data_added,
        )
        from .tracking import connect, git_commit

        # Refuse to record a run whose data tag would be wrong.
        require_data_added(settings)
        connect(settings)
        with mlflow.start_run(run_name=f"dvc-{settings.model_family}") as run:
            run_id = run.info.run_id
            mlflow.log_params(
                {
                    "model_family": settings.model_family,
                    "C": settings.model_c,
                    "max_iter": settings.max_iter,
                    "random_seed": settings.random_seed,
                    "test_size": settings.test_size,
                    "impute_strategy": settings.impute_strategy,
                    "n_rows_train": len(frame),
                }
            )
            mlflow.set_tags({"git_commit": git_commit()})
            log_data_version(settings)
            log_validation(settings, input_report)
            digest = log_dataset_input(frame, settings, dvc_data_url(settings))
            mlflow.sklearn.log_model(model, name="model")

    # Written even when MLflow is down, so `evaluate` always has a file to read.
    settings.run_id_path.parent.mkdir(parents=True, exist_ok=True)
    settings.run_id_path.write_text(
        json.dumps({"run_id": run_id, "mlflow_digest": digest}, indent=2) + "\n"
    )

    return {"model_path": str(model_path), "run_id": run_id, "mlflow_digest": digest}


def evaluate(settings: Settings) -> dict:
    """Stage 3: score the model, write metrics/metrics.json, and log it to the run."""
    model_path = settings.models_dir / "model.pkl"
    test_path = settings.processed_dir / "test.csv"
    for path in (model_path, test_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} is missing. Run the earlier stages first (`make repro`)."
            )

    model = joblib.load(model_path)
    frame = load_measurements(test_path)
    # The test split goes through the same steps as the training split.
    features, labels, _ = prepare_model_input(frame)
    metrics = evaluate_model(model, features, labels)

    settings.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    settings.metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")

    # Attach the scores to the run that produced the model, if there was one.
    run_id = read_run_id(settings)
    if run_id:
        from .tracking import mlflow_available

        if mlflow_available(settings):
            from mlflow.tracking import MlflowClient

            client = MlflowClient(settings.mlflow_tracking_uri)
            for key, value in metrics.items():
                client.log_metric(run_id, key, value)

    return {"metrics": metrics, "run_id": run_id}


def read_run_id(settings: Settings) -> str | None:
    """The MLflow run id recorded by the train stage, if any."""
    if not settings.run_id_path.exists():
        return None
    payload = json.loads(settings.run_id_path.read_text() or "{}")
    return payload.get("run_id")


def read_metrics(settings: Settings) -> dict:
    """The metrics recorded by the evaluate stage, if any."""
    if not settings.metrics_path.exists():
        return {}
    return json.loads(settings.metrics_path.read_text() or "{}")
