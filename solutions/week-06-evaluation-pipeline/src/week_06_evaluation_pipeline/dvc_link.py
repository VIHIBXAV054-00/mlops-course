"""Record the data version and the validation verdict on an MLflow run. You do not need to read it."""

from __future__ import annotations

import mlflow

from .config import Settings
from .dvc_meta import pointer_md5, remote_object_uri


def dvc_data_url(settings: Settings) -> str:
    """The remote URI of the current data version.

    Uses `dvc.api.get_url`; falls back to building the URI from the pointer md5
    when DVC cannot find the project.
    """
    try:
        import dvc.api

        return str(dvc.api.get_url(str(settings.measurements_path)))
    except Exception:
        return remote_object_uri(settings, pointer_md5(settings.measurements_path))


def log_data_version(settings: Settings) -> dict:
    """Tag the active run with the data version. Returns what was logged."""
    md5 = pointer_md5(settings.measurements_path)
    tags = {
        "dvc_md5": md5,
        "dvc_url": dvc_data_url(settings),
        "dvc_remote": f"{settings.dvc_bucket}/{settings.dvc_remote_path}",
        "data_file": settings.measurements_path.name,
    }
    mlflow.set_tags(tags)
    return tags


def log_validation(settings: Settings, input_report: dict) -> dict:
    """Tag the active run with the contract verdict and log the ingestion report."""
    report_path = settings.validation_report_path
    ingestion = {}
    if report_path.exists():
        import json

        ingestion = json.loads(report_path.read_text() or "{}")

    tags = {
        "data_validation": "pass" if input_report.get("passed") else "fail",
        "schema_version": input_report.get("schema_version", ""),
        "n_failure_cases": str(input_report.get("n_failure_cases", 0)),
        "ingestion_validation": "pass" if ingestion.get("passed") else "unknown",
    }
    mlflow.set_tags(tags)

    if report_path.exists():
        mlflow.log_artifact(str(report_path), artifact_path="validation")

    return tags


def log_dataset_input(frame, settings: Settings, source: str) -> str | None:
    """Log the training data as an MLflow Dataset input and return its digest.

    `source` must be a URI that MLflow can resolve, such as `s3://...`.
    """
    from .data import TARGET_COLUMN

    dataset = mlflow.data.from_pandas(
        frame,
        source=source,
        targets=TARGET_COLUMN,
        name="diabetes-measurements",
    )
    mlflow.log_input(dataset, context="training")
    return getattr(dataset, "digest", None)
