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


def register_best_model(settings: Settings, run_id: str) -> ModelVersion:
    """Register a run's model into the registry as a new version.

    NEW IN WEEK 6 — the first line of the body. `pipeline.require_go` raises
    unless `reports/gate.json` records a GO, so an ungated or rejected model
    never enters the registry at all.

    That call is where the gate actually acquires teeth. The `gate` stage
    already exits non-zero, which stops `dvc repro` — but a human who runs
    `make register` by hand has walked around the pipeline entirely. A gate that
    only holds when you use the front door is not a gate; it is a convention.

    The URI names the run explicitly — `runs:/<run_id>/model` reads as "this
    run's model", so a reviewer sees the provenance in the call itself. (The
    `models:/m-<id>` URI that `log_model` returns also records `run_id` on
    mlflow==3.13.0, measured; the `runs:/` form is a readability choice.)

    You will see a warning here — "Run with id ... has no artifacts at artifact
    path 'model', registering model based on models:/m-... instead". That is
    expected, not an error: MLflow 3 stores logged-model files outside the run's
    own artifact root. The version is still created and still links to the run.
    """
    from .pipeline import require_go

    verdict = require_go(settings)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=settings.registered_model_name,
        tags={
            "registered_from": "week6-gate",
            # The evidence travels with the version. Six months from now the
            # question is not "did it pass?" but "which rules did it pass?".
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
            "Run 'make register' first (Exercise 5)."
        )
    return max(versions, key=lambda v: int(v.version))


def promote_to_staging(
    settings: Settings, version: str, champion: bool = False
) -> ModelVersion:
    """Promote a version: check the gate, attach the evidence, move the alias.

    "Promote" is three things, and only the third is an API call:

      1. A GATE — evidence that this version deserves to be promoted. Week 3
         recorded the metrics as version tags and called that the mechanism;
         Week 6 makes it a real decision, by refusing outright unless
         `reports/gate.json` says GO.
      2. EVIDENCE — the numbers and the criteria version, recorded on the
         version so the decision can be reconstructed later.
      3. A POINTER MOVE — `set_registered_model_alias`. Nothing is copied. The
         version does not change. Only the name now resolves elsewhere.

    NEW IN WEEK 6 — `champion` is now opt-in rather than automatic.

    Week 5 set both aliases on every promotion, which was fine as a
    demonstration that two aliases can coexist and wrong as a policy: `staging`
    means "we are trying this" and `champion` means "this is the bar everything
    else is measured against". Conflating them makes the ratchet meaningless,
    because the baseline would move every time anyone promoted anything.

    So: `make promote` moves `staging`; `make promote-champion` moves both, and
    that is the deliberate act that raises the bar. `make baseline-sync` then
    writes the new champion's scores into `metrics/baseline.json`, and the loop
    closes.
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
    """Walk the chain: alias -> version -> run -> params -> data version -> VERDICT.

    This is what "traceability" means as a procedure rather than a slogan. Every
    hop is one lookup a human can do months later, from a laptop, having never
    seen the training code.

    Week 4 added `dvc_md5` and `dvc_url` — the chain reaching the bytes rather
    than a file path. Week 5 adds `data_validation` and `schema_version`, and the
    second of those is the one that ages well: "this run's data passed
    validation" is a claim with no referent once a rule changes, because it
    silently re-points at whatever the contract says today. With the version on
    the run, the claim names a specific set of rules recoverable from Git.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    name, alias = settings.registered_model_name, settings.model_alias

    version = client.get_model_version_by_alias(name, alias)

    # Hop 2. Every registration path records run_id on mlflow==3.13.0 (runs:/
    # and models:/m-<id> alike), so an empty one means the chain really is
    # broken. Fail loudly: ModelVersion.model_id comes back None from this
    # server, so there is nothing to fall back on.
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
        "data_validation": run.data.tags.get("data_validation"),
        "schema_version": run.data.tags.get("schema_version"),
        "n_failure_cases": run.data.tags.get("n_failure_cases"),
        "version_tags": version.tags,
        # The Week 4 additions — which exact BYTES this model was trained on.
        "dvc_md5": run.data.tags.get("dvc_md5"),
        "dvc_url": run.data.tags.get("dvc_url"),
        # The Week 6 additions — was this model ALLOWED OUT, under which rules,
        # and how much of the decision was actually checked. The last one is the
        # least obvious and the most useful: a GO with eight skipped criteria is
        # a different claim from a GO with none.
        "gate": run.data.tags.get("gate"),
        "gate_criteria_version": run.data.tags.get("gate_criteria_version"),
        "gate_checks_failed": run.data.tags.get("gate_checks_failed"),
        "gate_checks_skipped": run.data.tags.get("gate_checks_skipped"),
    }


def champion_version(settings: Settings) -> ModelVersion | None:
    """Which version currently holds the champion alias, if any. New in Week 6.

    Returns None rather than raising when nothing has been crowned yet, because
    "there is no champion" is the ordinary state of a project's first week and
    the ratchet has to be able to say so.
    """
    client = MlflowClient(settings.mlflow_tracking_uri)
    try:
        return client.get_model_version_by_alias(
            settings.registered_model_name, settings.champion_alias
        )
    except Exception:
        return None


def load_aliased_model(settings: Settings):
    """Load the model the alias currently points at.

    Two things worth noticing. First, the URI names a ROLE, not a version — the
    caller never changes when the champion changes. Second, this download goes
    through the tracking server's artifact proxy, so the client needs no Silo
    credentials at all. Check your `.env`: there are no AWS_* variables in it.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.sklearn.load_model(
        f"models:/{settings.registered_model_name}@{settings.model_alias}"
    )
