"""The model registry: versions, aliases, governance tags, and traceability.

New in Week 3. Tracking answers "which run scored best?". It cannot answer
"what are we serving?" — for that you need a NAME, a stable address, an approval
record, and a rollback target. That is the registry.

Four nouns:
  registered model  a name, e.g. "diabetes-classifier"
  version           an immutable, numbered snapshot of one run's model
  alias             a MUTABLE pointer to exactly one version: models:/<name>@staging
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


def register_best_model(settings: Settings, run_id: str) -> ModelVersion | None:
    """Register a run's model into the registry as a new version.

    IMPORTANT — use the `runs:/<run_id>/model` URI form, NOT the
    `model_info.model_uri` returned by `log_model` (which is `models:/<model_id>`
    in MLflow 3). Against the open-source registry only the `runs:/` form
    records `run_id` on the resulting ModelVersion, and that `run_id` is what
    makes the Exercise 6 traceability chain a single hop instead of a dead end.

    You will see a warning here — "Run with id ... has no artifacts at artifact
    path 'model', registering model based on models:/m-... instead". That is
    expected, not an error: MLflow 3 stores logged-model files outside the run's
    own artifact root. The version is still created and still links to the run.

    TODO(student) — Exercise 5:
    Return a real registration instead of the stub below:
        mlflow.register_model(
            model_uri=f"runs:/{run_id}/model",
            name=settings.registered_model_name,
            tags={"registered_from": "week3-sweep"},
        )
    Then run `make register` TWICE and watch the version number go 1 -> 2.
    Versions are immutable and monotonic: you never edit version 1, you register
    version 2. Open the UI's Models tab and follow the "Source run" link back to
    the sweep run it came from.
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


def promote_to_staging(settings: Settings, version: str) -> ModelVersion | None:
    """Promote a version: attach the evidence, then move the alias.

    "Promote to staging" is two things, and only the second is an API call:

      1. A GATE — evidence that this version deserves to be promoted. Here that
         evidence is recorded as version tags. Designing real gates (metric
         regression thresholds, slice metrics, fairness checks, go/no-go rules)
         is Week 6's topic; this week is the mechanism.
      2. A POINTER MOVE — `set_registered_model_alias`. Nothing is copied. The
         version does not change. Only the name now resolves elsewhere.

    We set TWO aliases on the same version on purpose. A stage could never do
    that, and alias coexistence is the headline reason MLflow replaced stages.

    TODO(student) — Exercise 6, part 1. Build this function in three steps.

    Step A — pull the evidence from the SOURCE RUN, not from a variable you are
    holding, so the tag can never drift from what was actually measured:
        source_run_id = client.get_model_version(name, version).run_id
        metrics = client.get_run(source_run_id).data.metrics

    Step B — record the evidence as version tags with
    client.set_model_version_tag(name, version, key, value):
        "validation_f1"      f"{metrics['f1']:.4f}"
        "validation_roc_auc" f"{metrics['roc_auc']:.4f}"
        "promoted_by"        settings.model_owner
        "promoted_at"        datetime.now(timezone.utc).isoformat(timespec="seconds")
    And two facts about the registered model as a whole, with
    client.set_registered_model_tag(name, key, value):
        "owner"  settings.model_owner
        "task"   "diabetes-binary-classification"

    Step C — move the pointer. THIS is the promotion:
        client.set_registered_model_alias(name, settings.model_alias, version)
        client.set_registered_model_alias(name, "champion", version)
    Two aliases on one version. Look for both in the UI's Models tab, and note
    that neither is a built-in MLflow concept — you invented both names.

    Finally return client.get_model_version_by_alias(name, settings.model_alias)
    so the caller sees the version the alias now resolves to.

    Do NOT reach for transition_model_version_stage(). It still exists in this
    MLflow version but is deprecated and absent from the current API reference —
    see the lecture slide on stages vs. aliases.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name = settings.registered_model_name
    source_run_id = client.get_model_version(name, version).run_id
    metrics = client.get_run(source_run_id).data.metrics

    version_tags = {
        "validation_f1": f"{metrics['f1']:.4f}",
        "validation_roc_auc": f"{metrics['roc_auc']:.4f}",
        "promoted_by": settings.model_owner,
        "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    for key, value in version_tags.items():
        client.set_model_version_tag(name, version, key, value)

    client.set_registered_model_tag(name, "owner", settings.model_owner)
    client.set_registered_model_tag(
        name, "task", "diabetes-binary-classification"
    )
    client.set_registered_model_alias(name, settings.model_alias, version)
    client.set_registered_model_alias(name, "champion", version)
    return client.get_model_version_by_alias(name, settings.model_alias)


def trace_alias(settings: Settings) -> dict:
    """Walk the chain: alias -> version -> run -> the params that produced it.

    This is what "traceability" means as a procedure rather than a slogan. Every
    hop is one lookup a human can do months later, from a laptop, having never
    seen the training code.

    TODO(student) — Exercise 6, part 2. Walk the four hops:

      1. alias   -> version:  client.get_model_version_by_alias(name, alias)
      2. version -> run:      version.run_id
                              (fall back to
                               client.get_logged_model(version.model_id).source_run_id
                               so the chain survives a version that was
                               registered from a models:/ URI instead)
      3. run     -> evidence: run = client.get_run(run_id), then read
                              run.data.params, run.data.metrics, and
                              run.data.tags["git_commit"]
      4. commit  -> code:     `git checkout <git_commit>` — that hop is yours,
                              not MLflow's

    Return a dict with these keys, which is what the CLI prints:
        model_uri, version, aliases, run_id, run_name, git_commit,
        params, metrics, version_tags

    One thing to notice when it works: run.data.params values come back as
    STRINGS, not the ints and floats you logged. "42", not 42.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias
    version = client.get_model_version_by_alias(name, alias)
    run_id = version.run_id
    if not run_id:
        run_id = client.get_logged_model(version.model_id).source_run_id
    run = client.get_run(run_id)

    return {
        "model_uri": f"models:/{name}@{alias}",
        "version": version.version,
        "aliases": version.aliases,
        "run_id": run_id,
        "run_name": run.info.run_name,
        "git_commit": run.data.tags.get("git_commit", "unknown"),
        "params": run.data.params,
        "metrics": run.data.metrics,
        "version_tags": version.tags,
    }


def load_aliased_model(settings: Settings):
    """Load the model the alias currently points at.

    Two things worth noticing. First, the URI names a ROLE, not a version — the
    caller never changes when the champion changes. Second, this download goes
    through the tracking server's artifact proxy, so the client needs no MinIO
    credentials at all. Check your `.env`: there are no AWS_* variables in it.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.sklearn.load_model(
        f"models:/{settings.registered_model_name}@{settings.model_alias}"
    )
