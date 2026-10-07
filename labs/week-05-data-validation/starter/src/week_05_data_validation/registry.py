"""The model registry: register, promote with an alias, and trace.

You do not need to change this module. `trace_alias` returns the data version
and the validation verdict recorded on the run.
"""

from __future__ import annotations

from datetime import datetime, timezone

import mlflow
import mlflow.sklearn
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient

from .config import Settings


def register_best_model(settings: Settings, run_id: str) -> ModelVersion:
    """Register a run's model as a new version.

    MLflow 3 warns "Run with id ... has no artifacts at artifact path 'model'".
    That is expected: the version is still created and still links to the run.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=settings.registered_model_name,
        tags={"registered_from": "week5-data-validation"},
    )


def latest_version(settings: Settings) -> ModelVersion:
    """Return the highest-numbered version of the registered model."""
    client = MlflowClient(settings.mlflow_tracking_uri)
    versions = client.search_model_versions(
        f"name = '{settings.registered_model_name}'"
    )
    if not versions:
        raise RuntimeError(
            f"No versions registered under '{settings.registered_model_name}'. "
            "Run 'make register' first."
        )
    return max(versions, key=lambda v: int(v.version))


def promote_to_staging(settings: Settings, version: str) -> ModelVersion:
    """Promote a version: record the evidence as tags, then move the aliases."""
    client = MlflowClient(settings.mlflow_tracking_uri)
    name = settings.registered_model_name

    # Read the evidence from the source run.
    source_run_id = client.get_model_version(name, version).run_id
    metrics = client.get_run(source_run_id).data.metrics

    client.set_model_version_tag(name, version, "validation_f1", f"{metrics['f1']:.4f}")
    client.set_model_version_tag(
        name, version, "validation_roc_auc", f"{metrics['roc_auc']:.4f}"
    )
    client.set_model_version_tag(name, version, "promoted_by", settings.model_owner)
    client.set_model_version_tag(
        name,
        version,
        "promoted_at",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    # Facts about the registered model as a whole, not about one version.
    client.set_registered_model_tag(name, "owner", settings.model_owner)
    client.set_registered_model_tag(name, "task", "diabetes-binary-classification")

    client.set_registered_model_alias(name, settings.model_alias, version)
    client.set_registered_model_alias(name, "champion", version)

    return client.get_model_version_by_alias(name, settings.model_alias)


def trace_alias(settings: Settings) -> dict:
    """Walk the chain: alias -> version -> run -> data version -> validation verdict."""
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias

    version = client.get_model_version_by_alias(name, alias)

    # A version without a run id cannot be traced further.
    run_id = version.run_id
    if not run_id:
        raise RuntimeError(
            f"Version {version.version} records no source run — the chain breaks "
            "at hop 2. It was registered from a bare artifact path, not from a run."
        )
    run = client.get_run(run_id)

    return {
        "model_uri": f"models:/{name}@{alias}",
        "version": version.version,
        "aliases": list(version.aliases),
        "run_id": run_id,
        "run_name": run.data.tags.get("mlflow.runName"),
        "git_commit": run.data.tags.get("git_commit"),
        "params": run.data.params,
        "metrics": run.data.metrics,
        "version_tags": version.tags,
        # Recorded by dvc_link.log_data_version and dvc_link.log_validation.
        "dvc_md5": run.data.tags.get("dvc_md5"),
        "dvc_url": run.data.tags.get("dvc_url"),
        "data_validation": run.data.tags.get("data_validation"),
        "schema_version": run.data.tags.get("schema_version"),
        "n_failure_cases": run.data.tags.get("n_failure_cases"),
    }


def load_aliased_model(settings: Settings):
    """Load the model the alias currently points at."""
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.sklearn.load_model(
        f"models:/{settings.registered_model_name}@{settings.model_alias}"
    )
