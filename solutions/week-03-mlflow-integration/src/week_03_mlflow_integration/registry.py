"""The model registry: versions, aliases, governance tags, and traceability.

New in Week 3. Tracking answers "which run scored best?". It cannot answer
"what are we serving?" — for that you need a name, a stable address, an approval
record, and a rollback target. That is the registry.

Four nouns:
  registered model  a name, e.g. "diabetes-classifier"
  version           an immutable, numbered snapshot of one run's model
  alias             a mutable pointer to exactly one version: models:/<name>@staging
  tag               a recorded fact attached to a version (who promoted it, on what)

Note what is absent: model *stages*. MLflow deprecated the fixed
None/Staging/Production/Archived state machine in 2.9 and the official registry
tutorial now uses aliases exclusively. See the lab README for the one-line
deviation note, and the lecture for why the change was an improvement.
"""

from __future__ import annotations

from datetime import datetime, timezone

import mlflow
import mlflow.sklearn
from mlflow.entities.model_registry import ModelVersion
from mlflow.tracking import MlflowClient

from .config import Settings


def register_best_model(settings: Settings, run_id: str) -> ModelVersion:
    """Register a run's model into the registry as a new version.

    The URI names the run explicitly — `runs:/<run_id>/model` reads as "this
    run's model", so a reviewer sees the provenance in the call itself. (The
    `models:/m-<id>` URI that `log_model` returns also records `run_id` on
    mlflow==3.13.0, measured; the `runs:/` form is a readability choice.)

    You will see a warning here — "Run with id ... has no artifacts at artifact
    path 'model', registering model based on models:/m-... instead". That is
    expected, not an error: MLflow 3 stores logged-model files outside the run's
    own artifact root. The version is still created and still links to the run.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=settings.registered_model_name,
        tags={"registered_from": "week3-sweep"},
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
            "Run 'make register' first (Exercise 5)."
        )
    return max(versions, key=lambda v: int(v.version))


def promote_to_staging(
    settings: Settings, version: str, reason: str | None = None
) -> ModelVersion:
    """Promote a version: attach the evidence, then move the alias.

    "Promote to staging" is two things, and only the second is an API call:

      1. A gate: evidence that this version deserves to be promoted. Here that
         evidence is recorded as version tags. Designing real gates (metric
         regression thresholds, slice metrics, fairness checks, go/no-go rules)
         is Week 6's topic; this week is the mechanism.
      2. A pointer move: `set_registered_model_alias`. Nothing is copied. The
         version does not change. Only the name now resolves elsewhere.

    We set TWO aliases on the same version on purpose. A stage could never do
    that, and alias coexistence is the headline reason MLflow replaced stages.

    `reason` is the human half of the evidence: the one-sentence argument from
    Exercise 4 for why THIS version, recorded where the next person will look.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name = settings.registered_model_name

    # Pull the evidence from the source run, so the tag cannot drift from reality.
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
    if reason:
        client.set_model_version_tag(name, version, "promotion_reason", reason)

    # Facts about the registered model as a whole, not about one version.
    client.set_registered_model_tag(name, "owner", settings.model_owner)
    client.set_registered_model_tag(name, "task", "diabetes-binary-classification")

    client.set_registered_model_alias(name, settings.model_alias, version)
    client.set_registered_model_alias(name, "champion", version)

    return client.get_model_version_by_alias(name, settings.model_alias)


def trace_alias(settings: Settings) -> dict:
    """Walk the chain: alias -> version -> run -> the params that produced it.

    This is what "traceability" means as a procedure rather than a slogan. Every
    hop is one lookup a human can do months later, from a laptop, having never
    seen the training code.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias

    version = client.get_model_version_by_alias(name, alias)
    if not version.run_id:
        raise RuntimeError(
            f"Version {version.version} records no source run — the chain breaks "
            "at hop 2. It was registered from a bare artifact path, not from a run."
        )
    run = client.get_run(version.run_id)

    return {
        "model_uri": f"models:/{name}@{alias}",
        "version": version.version,
        "aliases": list(version.aliases),
        "run_id": version.run_id,
        "run_name": run.data.tags.get("mlflow.runName"),
        "git_commit": run.data.tags.get("git_commit"),
        # Exercise 6, part 3: hop 4 is only true if the tree was clean.
        "git_dirty": run.data.tags.get("git_dirty"),
        "params": run.data.params,
        "metrics": run.data.metrics,
        "version_tags": version.tags,
    }


def roll_back(settings: Settings, to_version: str, reason: str) -> tuple[str, ModelVersion]:
    """Point both aliases back at an earlier version, and record why.

    A rollback is the same pointer move as a promotion, in the other direction.
    What it is NOT is self-documenting: the registry stores only where each
    alias points NOW (see `registered_model_aliases` in Postgres: name, alias,
    version — no timestamp, no history). Unless you write a tag, nothing remembers that the
    rolled-back version was ever champion.

    Two guards, both deliberate:
      - the target must exist before anything moves, so a typo cannot leave the
        aliases half-updated;
      - the target must carry a `promoted_at` tag. Rolling back to a version
        that never passed promotion is an unreviewed promotion in disguise.

    Returns (the version rolled back FROM, the version the alias now resolves to).
    Rolling back what a serving container actually runs is Week 10.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias

    current = client.get_model_version_by_alias(name, alias)
    target = client.get_model_version(name, to_version)
    if target.version == current.version:
        raise ValueError(f"@{alias} already points at version {target.version}.")
    if "promoted_at" not in target.tags:
        raise ValueError(
            f"Version {target.version} was never promoted, so it is not a known-good "
            "rollback target. Promote it deliberately instead."
        )

    # Record the rollback on the version being demoted — the only history there is.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    client.set_model_version_tag(name, current.version, "rolled_back_at", now)
    client.set_model_version_tag(name, current.version, "rolled_back_to", target.version)
    client.set_model_version_tag(name, current.version, "rollback_reason", reason)

    client.set_registered_model_alias(name, alias, target.version)
    client.set_registered_model_alias(name, "champion", target.version)

    return current.version, client.get_model_version_by_alias(name, alias)


def load_aliased_model(settings: Settings):
    """Load the model the alias currently points at.

    Two things worth noticing. First, the URI names a role, not a version — the
    caller never changes when the champion changes. Second, this download goes
    through the tracking server's artifact proxy, so the client needs no Silo
    credentials at all. Check your `.env`: there are no AWS_* variables in it.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.sklearn.load_model(
        f"models:/{settings.registered_model_name}@{settings.model_alias}"
    )
