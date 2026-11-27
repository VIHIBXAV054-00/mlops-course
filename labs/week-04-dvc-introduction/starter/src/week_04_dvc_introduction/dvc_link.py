"""Record the DVC data version on the MLflow run (Exercises 6 and 7)."""

from __future__ import annotations

import mlflow

from .config import Settings
from .data import TARGET_COLUMN
from .datasets import file_md5
from .dvc_meta import pointer_md5, remote_object_uri


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
    """Tag the active run with the data version. Returns what was logged.

    Tags include the pointer's content hash, its remote URL, remote root and
    local filename so runs can be found by the data version they used.
    """
    tags = {
        "dvc_md5": pointer_md5(settings.measurements_path),
        "dvc_url": dvc_data_url(settings),
        "dvc_remote": f"{settings.dvc_bucket}/{settings.dvc_remote_path}",
        "data_file": settings.measurements_path.name,
    }
    mlflow.set_tags(tags)
    return tags


def log_dataset_input(frame, settings: Settings, source: str) -> str | None:
    """Log the training data as an MLflow Dataset input. Returns its digest.

    The MLflow digest identifies the table representation; `source` points back
    to the DVC object containing its exact bytes.
    """
    dataset = mlflow.data.from_pandas(
        frame,
        source=source,
        name="diabetes-measurements",
        targets=TARGET_COLUMN,
    )
    mlflow.log_input(dataset, context="training")
    return dataset.digest


def require_data_added(settings: Settings) -> str:
    """Check that the data on disk is the data the pointer names. Returns its md5.

    Refuse to train when the workspace file has changed since the last `dvc add`.
    """
    workspace_md5 = file_md5(settings.measurements_path)
    expected_md5 = pointer_md5(settings.measurements_path)
    if workspace_md5 != expected_md5:
        raise RuntimeError(
            "Cannot run `train` yet: data/measurements.csv differs from its DVC "
            "pointer. Run `dvc add data/measurements.csv` before training."
        )
    return workspace_md5
