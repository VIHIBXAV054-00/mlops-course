"""The five pipeline stages that `dvc.yaml` declares.

    validate ──▶ prepare ──▶ train ──▶ evaluate ──▶ gate

The stages pass files, not Python objects, so DVC can hash each boundary and skip unchanged work.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from .baseline import read_baseline
from .config import Settings
from .data import FEATURE_COLUMNS, TARGET_COLUMN, load_measurements, split_measurements
from .evaluation import slice_report
from .gates import evaluate_gate
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


def _require_measurements(settings: Settings) -> Path:
    path = settings.measurements_path
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} is missing. It is DVC-tracked, so a fresh clone does "
            "not have it. Run `make dvc-pull` to fetch it, or `make data-v2` "
            "to rebuild it from data/raw/."
        )
    return path


class ValidationFailed(RuntimeError):
    """The data did not satisfy its contract."""


class GateFailed(RuntimeError):
    """The model did not satisfy its acceptance criteria."""


def _hyperparams(settings: Settings) -> dict:
    """The estimator keyword arguments for the configured model family."""
    if settings.model_family == "rf":
        return {"n_estimators": settings.n_estimators}
    return {"C": settings.model_c}


def validate(settings: Settings) -> dict:
    """Stage 0: check the DVC-tracked dataset against the ingestion contract.

    Writes `reports/validation.json` first, then raises `ValidationFailed` if the data failed.
    """
    source = _require_measurements(settings)
    frame = read_raw(source)

    report = validate_frame(
        frame, RawMeasurements, source=str(source.name)
    )
    report["sentinel_zeros"] = sentinel_counts(frame)
    write_report(report, settings.validation_report_path)

    if not report["passed"]:
        raise ValidationFailed(
            f"{source.name} failed the {report['schema']} contract with "
            f"{report['n_failure_cases']} failure case(s). "
            f"See {settings.validation_report_path.name} for the full report, "
            "or run `make validate` to print it."
        )

    return report


def _require_validated(settings: Settings) -> dict:
    """The recorded verdict, or a refusal to continue without one."""
    report = read_report(settings.validation_report_path)
    if not report:
        raise FileNotFoundError(
            f"{settings.validation_report_path.name} is missing: the validate stage "
            "has never run. Run `make validate` or `make repro`."
        )
    if not report.get("passed"):
        raise ValidationFailed(
            f"The last validation run FAILED "
            f"({report.get('n_failure_cases')} failure case(s)). Fix the data "
            "or the contract before training."
        )
    return report


def prepare(settings: Settings) -> dict:
    """Stage 1: split the dataset into train and test CSVs.

    Refuses to run without a passing validation report, also when run by hand.
    `measurement_date` stays in the files, but it is not a feature.
    """
    _require_validated(settings)
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
    """Turn a processed split into `(features, labels, report)` for the model.

    Keeps the model's columns, turns sentinel zeros into nulls, then validates against `ModelInput`.
    """
    projected = frame[MODEL_INPUT_COLUMNS]
    nullable = to_nullable(projected)
    report = validate_frame(nullable, ModelInput, source="model input")
    if not report["passed"]:
        raise ValidationFailed(
            f"The model input failed the ModelInput contract with "
            f"{report['n_failure_cases']} failure case(s). Check that to_nullable "
            "converts every column in SENTINEL_COLUMNS."
        )
    # the imputer needs plain floats, nulls become NaN
    features = nullable[list(FEATURE_COLUMNS)].astype("float64")
    labels = nullable[TARGET_COLUMN].astype("int64")
    return features, labels, report


def train(settings: Settings) -> dict:
    """Stage 2: fit the model and record the run in MLflow.

    With the tracking server down, the model is still written and the run id is null.
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
        _hyperparams(settings),
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
        )
        from .tracking import connect, git_commit

        connect(settings)
        with mlflow.start_run(run_name=f"dvc-{settings.model_family}") as run:
            run_id = run.info.run_id
            mlflow.log_params(
                {
                    "model_family": settings.model_family,
                    **_hyperparams(settings),
                    "max_iter": settings.max_iter,
                    "random_seed": settings.random_seed,
                    "test_size": settings.test_size,
                    "n_rows_train": len(frame),
                    "impute_strategy": settings.impute_strategy,
                }
            )
            mlflow.set_tags({"git_commit": git_commit()})
            # which data, and did it pass its contract?
            log_data_version(settings)
            log_validation(settings, input_report)
            digest = log_dataset_input(frame, settings, dvc_data_url(settings))
            mlflow.sklearn.log_model(model, name="model")

    # written even when MLflow is down, so later stages always find the file
    settings.run_id_path.parent.mkdir(parents=True, exist_ok=True)
    settings.run_id_path.write_text(
        json.dumps({"run_id": run_id, "mlflow_digest": digest}, indent=2) + "\n"
    )

    return {"model_path": str(model_path), "run_id": run_id, "mlflow_digest": digest}


def evaluate(settings: Settings) -> dict:
    """Stage 3: score the model on the test set, in aggregate and per slice.

    Writes `metrics/metrics.json` and `metrics/slices.json`. It measures only, the gate decides.
    """
    model_path = settings.models_dir / "model.pkl"
    test_path = settings.processed_dir / "test.csv"
    for path in (model_path, test_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} is missing. Run the earlier stages first (`make repro`)."
            )

    model = joblib.load(model_path)
    frame = load_measurements(test_path)
    # the same steps as the training set, so the model sees the same kind of input
    features, labels, _ = prepare_model_input(frame)
    metrics = evaluate_model(model, features, labels)

    # slice on the raw split, so an unmeasured value stays in its own `missing` group
    slices = slice_report(
        frame,
        labels,
        model.predict(features),
        model.predict_proba(features)[:, 1],
        settings.slice_specs,
    )

    settings.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    settings.metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    # no timestamp: a value that changes on every run would make the gate stage always stale
    settings.slices_path.write_text(json.dumps(slices, indent=2) + "\n")

    # Attach the scores to the run that produced the model, if there was one.
    run_id = read_run_id(settings)
    if run_id:
        from .tracking import mlflow_available

        if mlflow_available(settings):
            from mlflow.tracking import MlflowClient

            client = MlflowClient(settings.mlflow_tracking_uri)
            for key, value in metrics.items():
                client.log_metric(run_id, key, value)
            for key, value in flatten_slice_metrics(slices).items():
                client.log_metric(run_id, key, value)

    return {"metrics": metrics, "slices": slices, "run_id": run_id}


# MLflow metric names cannot contain `+`, which the `50+` label has.
_METRIC_NAME_SAFE = str.maketrans({"+": "plus", " ": "_", "/": "_"})


def flatten_slice_metrics(slices: dict, keys=("f1", "recall", "roc_auc")) -> dict:
    """Per-slice scores as flat MLflow metric names, such as `slice.age_band.50plus.f1`.

    Null values are left out, because MLflow cannot store "undefined".
    """
    flat = {}
    for axis, groups in (slices.get("slices") or {}).items():
        for group, m in groups.items():
            safe = str(group).translate(_METRIC_NAME_SAFE)
            for key in keys:
                if m.get(key) is not None:
                    flat[f"slice.{axis}.{safe}.{key}"] = float(m[key])
    return flat


def gate(settings: Settings) -> dict:
    """Stage 4: the model quality gate.

    Writes `reports/gate.json` first, then raises `GateFailed` on NO-GO.
    The model stays on disk, so a failed model can still be investigated.
    """
    metrics = read_metrics(settings)
    if not metrics:
        raise FileNotFoundError(
            f"{settings.metrics_path.name} is missing. The evaluate stage has "
            "never run — run `make repro`."
        )
    slices = read_slices(settings)
    baseline = read_baseline(settings.baseline_path)

    report = evaluate_gate(metrics, slices, baseline, settings.acceptance)

    settings.gate_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.gate_report_path.write_text(json.dumps(report, indent=2) + "\n")

    log_gate_to_run(settings, report)

    if report["verdict"] != "GO":
        failed = [c["id"] for c in report["checks"] if c["status"] == "fail"]
        raise GateFailed(
            f"NO-GO. {report['summary']['failed']} acceptance criteria failed: "
            f"{', '.join(failed)}. See "
            f"reports/{settings.gate_report_path.name} for the numbers, or run "
            "`make gate` to print them. The model is still on disk."
        )

    return report


def log_gate_to_run(settings: Settings, report: dict) -> dict:
    """Tag the MLflow run that produced the model with the gate verdict, even on NO-GO.

    Does nothing when there is no run id or MLflow is not reachable.
    """
    run_id = read_run_id(settings)
    if not run_id:
        return {}
    from .tracking import mlflow_available

    if not mlflow_available(settings):
        return {}

    from mlflow.tracking import MlflowClient

    client = MlflowClient(settings.mlflow_tracking_uri)
    tags = {
        "gate": report.get("verdict", ""),
        "gate_criteria_version": str(report.get("criteria_version", "")),
        "gate_checks_failed": str(report.get("summary", {}).get("failed", "")),
        # "0 failed" and "0 failed, 8 skipped" are different results
        "gate_checks_skipped": str(report.get("summary", {}).get("skipped", "")),
    }
    for key, value in tags.items():
        client.set_tag(run_id, key, value)

    for path in (settings.gate_report_path, settings.slices_path):
        if path.exists():
            client.log_artifact(run_id, str(path), artifact_path="evaluation")
    return tags


def read_slices(settings: Settings) -> dict:
    """The per-slice scores recorded by the evaluate stage, if any."""
    if not settings.slices_path.exists():
        return {}
    return json.loads(settings.slices_path.read_text() or "{}")


def read_gate(settings: Settings) -> dict:
    """The last recorded verdict, or {} if the gate has never run."""
    if not settings.gate_report_path.exists():
        return {}
    return json.loads(settings.gate_report_path.read_text() or "{}")


def require_go(settings: Settings) -> dict:
    """The recorded GO verdict, or `GateFailed`.

    The single release check: `register` and `promote` both call it.
    """
    report = read_gate(settings)
    if not report:
        raise GateFailed(
            f"reports/{settings.gate_report_path.name} is missing: the gate has never "
            "run for this model. Run `make gate` or `make repro`."
        )
    if report.get("verdict") != "GO":
        failed = [c["id"] for c in report.get("checks", []) if c["status"] == "fail"]
        raise GateFailed(
            f"The recorded verdict is {report.get('verdict')} "
            f"(criteria v{report.get('criteria_version')}): "
            f"{', '.join(failed) or 'no checks recorded'}. Refusing to release."
        )
    return report


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
