"""Record the data version and the validation verdict on the MLflow run.

You do not need to change this module.
"""

from __future__ import annotations

import mlflow

from .config import Settings
from .datasets import file_md5
from .dvc_meta import pointer_md5, remote_object_uri
from .validation import read_report


def dvc_data_url(settings: Settings) -> str:
    """The s3:// URI of the current data version in the DVC remote.

    Uses `dvc.api.get_url`, or builds the same URI from the pointer's md5 when
    the file is outside a DVC project.
    """
    try:
        import dvc.api

        return str(dvc.api.get_url(str(settings.measurements_path)))
    except Exception:
        return remote_object_uri(settings, pointer_md5(settings.measurements_path))


def log_data_version(settings: Settings) -> dict:
    """Tag the active run with the data version. Returns what was logged."""
    tags = {
        "dvc_md5": pointer_md5(settings.measurements_path),
        "dvc_url": dvc_data_url(settings),
        "dvc_remote": f"{settings.dvc_bucket}/{settings.dvc_remote_path}",
        "data_file": settings.measurements_path.name,
    }
    mlflow.set_tags(tags)
    return tags


def log_validation(settings: Settings, input_report: dict) -> dict:
    """Tag the active run with the contract verdicts, and attach the validation report.

    `input_report` is the training contract's report on the training split. The
    ingestion verdict comes from `reports/validation.json`. Returns the tags.
    """
    if input_report:
        verdict = "pass" if input_report["passed"] else "fail"
    else:
        verdict = "not run"
    ingestion = read_report(settings.validation_report_path)
    if ingestion:
        ingestion_verdict = "pass" if ingestion["passed"] else "fail"
    else:
        ingestion_verdict = "not run"

    tags = {
        "data_validation": verdict,
        "schema_version": input_report.get("schema_version", ""),
        "n_failure_cases": str(input_report.get("n_failure_cases", 0)),
        "ingestion_validation": ingestion_verdict,
    }
    mlflow.set_tags(tags)
    if settings.validation_report_path.exists():
        mlflow.log_artifact(str(settings.validation_report_path), artifact_path="validation")
    return tags


def log_dataset_input(frame, settings: Settings, source: str) -> str | None:
    """Log the training data as an MLflow Dataset input. Returns its digest."""
    from .data import TARGET_COLUMN

    dataset = mlflow.data.from_pandas(
        frame,
        source=source,
        targets=TARGET_COLUMN,
        name="diabetes-measurements",
    )
    mlflow.log_input(dataset, context="training")
    return dataset.digest


def require_data_added(settings: Settings) -> str:
    """Check that the data on disk is the data the pointer names. Returns its md5."""
    on_disk = file_md5(settings.measurements_path)
    named = pointer_md5(settings.measurements_path)
    if on_disk != named:
        raise RuntimeError(
            f"{settings.measurements_path.name} has changed since its last `dvc add` "
            f"(md5 {on_disk}, pointer {named}). Run `dvc add` and commit the pointer, "
            "or restore the file with `dvc checkout --force`."
        )
    return on_disk
