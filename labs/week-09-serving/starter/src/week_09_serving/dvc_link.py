"""Stamp the DVC data version onto an MLflow run — the link Week 3 was missing.

New in Week 4. Week 3's traceability chain ran alias -> version -> run -> params,
and then stopped at a file *path*. These functions attach the data's content
hash to the run, so the chain reaches the bytes.

Two mechanisms, on purpose, because they are not equivalent:

1. `log_data_version` sets plain TAGS (`dvc_md5`, `dvc_url`, `dvc_remote`).
   Boring and completely sufficient: tags are searchable, so
   `tags.dvc_md5 = '<hash>'` answers "which runs trained on this exact data?" —
   a question Week 3 could not ask at all.

2. `log_dataset_input` uses MLflow's purpose-built dataset API
   (`mlflow.data.from_pandas` + `mlflow.log_input`), which records a schema, a
   profile, a source, and a *digest*.

The digest is the interesting part, and it is the exercise's punchline: MLflow's
digest is an 8-character truncated md5 of the first 10,000 rows' PARSED VALUES
plus the row count plus the column names. DVC's md5 is a 32-character hash of
the file's BYTES. They describe the same file and they will never match — and
only one of them is the thing you would produce in an audit.
"""

from __future__ import annotations

import mlflow

from .config import Settings
from .dvc_meta import pointer_md5, remote_object_uri


def dvc_data_url(settings: Settings) -> str:
    """The content-addressed remote URI of the current data version.

    Prefers `dvc.api.get_url`, which is DVC's own answer to "where do these
    bytes live?". Falls back to constructing the URI from the pointer md5 when
    dvc is not importable or the CWD is outside the DVC project (get_url needs
    to be able to find `.dvc/`). Both routes produce the same string.
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
    """Record the contract verdict on the active run. New in Week 5.

    Three tags and one artifact, and each earns its place:

    - `data_validation` — pass/fail, so a search can find every run trained on
      data that was actually checked.
    - `schema_version` — WHICH contract it passed. "It passed validation" ages
      into a meaningless sentence the first time a rule changes.
    - `n_failure_cases` — normally 0. A non-zero value on a run that exists at
      all means somebody trained anyway, and that is worth being able to find.

    The artifact is the ingestion report from `reports/validation.json`, uploaded
    verbatim. Tags answer "was it checked?"; only the report answers "what did
    the check see?".
    """
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
    """Log the training data as an MLflow Dataset input. Returns its digest.

    `source` must be a URI MLflow can resolve — an `s3://...` string resolves to
    an S3 dataset source. Do not invent a scheme like `dvc://`; MLflow raises.
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
