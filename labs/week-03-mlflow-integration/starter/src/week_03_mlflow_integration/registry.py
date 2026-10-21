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


def register_best_model(settings: Settings, run_id: str) -> ModelVersion | None:
    """Register a run's model into the registry as a new version.

    TODO(student) — Exercise 5:
    Create a new version of the registered model `settings.registered_model_name`
    from the model logged by run `run_id`, tagged `registered_from=week3-sweep`,
    and return the ModelVersion.
    Reference (read "Adding an MLflow Model to the Model Registry"):
    https://mlflow.org/docs/latest/ml/model-registry/workflow/

    The docs show two URI forms. We use `runs:/<run_id>/<name>`, where <name>
    is the `name=` you gave log_model in Exercise 1, because it states the
    source run in the call itself. On mlflow==3.13.0 it prints this warning,
    which is expected and not an error: "Run with id ... has no artifacts at
    artifact path 'model', registering model based on models:/m-... instead".
    MLflow 3 stores logged-model files outside the run's artifact root.
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
) -> ModelVersion | None:
    """Promote a version: attach the evidence, then move the alias.

    "Promote to staging" is two things, and only the second is an API call:

      1. A gate: evidence that this version deserves to be promoted. Here that
         evidence is recorded as version tags. Designing real gates (metric
         regression thresholds, slice metrics, fairness checks, go/no-go rules)
         is Week 6's topic; this week is the mechanism.
      2. A pointer move: `set_registered_model_alias`. Nothing is copied. The
         version does not change. Only the name now resolves elsewhere.

    TODO(student) — Exercise 6, part 1. Using the `client` below:

    A. Read the evidence from the version's source run, not from a variable you
       happen to hold, so the tags cannot drift from what was measured.
    B. Tag the version with these keys (the tests check the names):
         validation_f1, validation_roc_auc   the run's metrics, formatted "%.4f"
         promoted_by                         settings.model_owner
         promoted_at                         now, UTC, ISO 8601, to the second
         promotion_reason                    `reason`, only when one is given
       and tag the registered model with:
         owner  settings.model_owner      task  "diabetes-binary-classification"
    C. Move both aliases, settings.model_alias ("staging") and "champion", to
       `version`. Neither name is built into MLflow; you chose them.
    D. Return the version that settings.model_alias now resolves to.

    The MlflowClient methods you need: get_model_version, get_run,
    set_model_version_tag, set_registered_model_tag, set_registered_model_alias,
    get_model_version_by_alias. Signatures:
    https://mlflow.org/docs/latest/api_reference/python_api/mlflow.client.html

    Do not use transition_model_version_stage(). It still exists in this
    MLflow version but is deprecated. See the lecture slide on stages vs. aliases.
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

    TODO(student) — Exercise 6, part 2. Walk the hops with the client:

      1. alias   -> version    (which client method resolves an alias?)
      2. version -> run        (the version records its source run's id; if it
                                is empty, raise RuntimeError — the chain is broken)
      3. run     -> evidence   (the run's params, metrics and tags)
      4. commit  -> code       `git checkout <git_commit>`. That hop is yours,
                                not MLflow's, and Exercise 6 part 2 asks you
                                to actually take it.

    Return a dict with these keys, which is what the CLI prints:
        model_uri, version, aliases, run_id, run_name, git_commit,
        params, metrics, version_tags
    (run_name is the run's `mlflow.runName` tag. Exercise 6, part 3 adds one
    more key here.)

    One thing to notice when it works: params come back as strings, not the
    ints and floats you logged. "42", not 42.
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


def roll_back(
    settings: Settings, to_version: str, reason: str
) -> tuple[str, ModelVersion] | None:
    """Point both aliases back at an earlier version, and record why.

    A rollback is the same pointer move as a promotion, in the other direction.
    Rolling back what a serving container actually runs is Week 10; this is
    the registry half.

    TODO(student) — Exercise 7:
    1. Find the version settings.model_alias points at now.
    2. Refuse, with ValueError and before anything moves, if `to_version`
       - is the version the alias already points at, or
       - has no `promoted_at` tag. A version that never passed promotion is
         not a known-good target, and "rolling back" to it would be an
         unreviewed promotion in disguise.
       (A `to_version` that does not exist already raises in get_model_version.)
    3. Tag the version you are rolling back from with
         rolled_back_at   now, UTC, ISO 8601
         rolled_back_to   to_version
         rollback_reason  reason
    4. Move both aliases, settings.model_alias and "champion", to `to_version`.
    5. Return (the version you rolled back from, the ModelVersion the alias
       now resolves to).
    """
    _ = (settings, to_version, reason)  # silence unused-argument warnings until you implement
    return None  # placeholder — the CLI reports this as "not implemented yet"


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