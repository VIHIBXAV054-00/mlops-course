"""The model registry: versions, aliases, governance tags and traceability.

An alias is a movable name for exactly one version: `models:/<name>@staging`.
MLflow's old model stages are deprecated, so this lab uses aliases only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import mlflow
import mlflow.sklearn
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient

from .config import Settings


def register_best_model(settings: Settings, run_id: str) -> ModelVersion:
    """Register a run's model as a new version, only if the gate recorded a GO.

    MLflow 3 may warn that the run has no artifacts at path 'model' and registers from
    `models:/m-...` instead. That is expected, and the version still links to the run.
    """
    from .pipeline import require_go

    verdict = require_go(settings)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=settings.registered_model_name,
        tags={
            "registered_from": "week6-gate",
            # which rules the version passed
            "gate": verdict["verdict"],
            "gate_criteria_version": verdict["criteria_version"],
        },
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


def promote_to_staging(
    settings: Settings, version: str, champion: bool = False
) -> ModelVersion:
    """Promote a version: check the gate, tag the evidence, move the alias.

    `make promote` moves `staging`. `champion=True` (`make promote-champion`) also moves `champion`,
    which raises the bar the baseline is measured against.
    """
    from .pipeline import require_go

    verdict = require_go(settings)

    client = MlflowClient(settings.mlflow_tracking_uri)
    name = settings.registered_model_name

    # Pull the evidence from the source run, so the tag cannot drift from reality.
    source_run_id = client.get_model_version(name, version).run_id
    metrics = client.get_run(source_run_id).data.metrics

    client.set_model_version_tag(name, version, "validation_f1", f"{metrics['f1']:.4f}")
    client.set_model_version_tag(
        name, version, "validation_roc_auc", f"{metrics['roc_auc']:.4f}"
    )
    client.set_model_version_tag(name, version, "gate", verdict["verdict"])
    client.set_model_version_tag(
        name, version, "gate_criteria_version", verdict["criteria_version"]
    )
    client.set_model_version_tag(
        name, version, "gate_checks_skipped", str(verdict["summary"]["skipped"])
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
    if champion:
        client.set_registered_model_alias(name, settings.champion_alias, version)

    return client.get_model_version_by_alias(name, settings.model_alias)


def trace_alias(settings: Settings) -> dict:
    """Walk the chain: alias -> version -> run -> params -> data version -> gate verdict."""
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias

    version = client.get_model_version_by_alias(name, alias)

    # every registration path records run_id, so an empty one means the chain is broken
    run_id = version.run_id
    if not run_id:
        raise RuntimeError(
            f"Version {version.version} records no source run, so it cannot be "
            "traced. It was registered from an artifact path, not from a run."
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
        "data_validation": run.data.tags.get("data_validation"),
        "schema_version": run.data.tags.get("schema_version"),
        "n_failure_cases": run.data.tags.get("n_failure_cases"),
        "version_tags": version.tags,
        # the data the model was trained on
        "dvc_md5": run.data.tags.get("dvc_md5"),
        "dvc_url": run.data.tags.get("dvc_url"),
        # the gate verdict, and how many criteria were skipped
        "gate": run.data.tags.get("gate"),
        "gate_criteria_version": run.data.tags.get("gate_criteria_version"),
        "gate_checks_failed": run.data.tags.get("gate_checks_failed"),
        "gate_checks_skipped": run.data.tags.get("gate_checks_skipped"),
    }


def champion_version(settings: Settings) -> ModelVersion | None:
    """The version that holds the champion alias, or None if there is none yet."""
    client = MlflowClient(settings.mlflow_tracking_uri)
    try:
        return client.get_model_version_by_alias(
            settings.registered_model_name, settings.champion_alias
        )
    except Exception:
        return None


def load_aliased_model(settings: Settings):
    """Load the model the alias points at.

    The download goes through the tracking server's artifact proxy, so it needs no Silo credentials.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.sklearn.load_model(
        f"models:/{settings.registered_model_name}@{settings.model_alias}"
    )
