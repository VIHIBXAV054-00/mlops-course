"""The model store: publishing a model version for a cluster to fetch.

Week 9 shipped a model by BUILDING AN IMAGE around it. This week the image
never changes and the model is published into a store the cluster reads at pod
startup (`storageUri: pvc://diabetes-models/v2`). So "release a model" stops
being "run docker build" and becomes "put a directory here" — which is faster,
and which is exactly why it needs a gate.

    model-store/
      v1/  model.pkl  provenance.json      <- logistic regression, GO
      v2/  model.pkl  provenance.json      <- random forest, GO
      v3/  model.pkl  provenance.json      <- C=0.005, NO-GO (published on purpose)

THE FOURTH DOOR. Week 6 gave the gate teeth at `register`; Week 9 gave it teeth
at `make image`, calling a container "a third door into production". A model
store is the fourth, and it is the easiest one to walk through: copying a file
needs no build, no registry and no credentials. `publish_version` therefore
refuses a non-GO verdict unless it is forced — and when it is forced it records
the real verdict in `provenance.json`, so the pod can be asked and will tell
the truth. That is Exercise 4: a NO-GO model, serving happily, every probe
green, caught by a smoke test rather than by the platform.

PROVENANCE TRAVELS WITH THE MODEL. Week 9's provenance lived in the image
(`models/baked.json`), because one image meant one model. One image serving
three models needs the identity to sit beside the weights, or `/health` cannot
tell you which of the three you are talking to.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings, load_settings

# What a store version must contain to be deployable. The manifest names
# model.pkl explicitly (MODEL_PATH=/mnt/models/model.pkl), so a version missing
# it produces a pod that starts, fails to load, and is held out of the Service
# by its readiness probe — a slow way to learn a fast fact.
MODEL_FILE = "model.pkl"
PROVENANCE_FILE = "provenance.json"


@dataclass(frozen=True)
class PublishResult:
    version: str
    path: Path
    provenance: dict[str, Any]
    forced: bool


def store_dir(settings: Settings) -> Path:
    """Where published model versions live.

    A plain directory in the lab, bind-mounted into the kind node by
    `k8s/kind-cluster.yaml` and exposed to pods as a PersistentVolume. A real
    deployment would use object storage — `s3://`, `gs://` — and the only thing
    that changes is the `storageUri` scheme. Week 4 already built the Silo
    bucket that would serve; it is deliberately not used here so that the whole
    Kubernetes half of this lab runs with the Compose stack DOWN.
    """
    return settings.project_root / "model-store"


def _git_sha(project_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def build_provenance(settings: Settings, version: str) -> dict[str, Any]:
    """Everything a running pod should be able to say about itself.

    Read from what the pipeline already wrote — the gate report, the metrics,
    the MLflow run id, the DVC pointer — and NOT from the registry at pod
    startup, because a published model must be identifiable by a pod that has
    no network. Same rule as Week 9's `/health`, one indirection further out:
    the lookup happens once, here, at publish time, by a human with a stack.

    The registry version is best-effort for exactly that reason. With the stack
    down it is recorded as `null` rather than guessed, and `/health` then says
    so — Week 9's rule that a container never claims a provenance it does not
    have.
    """
    from . import pipeline

    gate = pipeline.read_gate(settings)
    metrics = pipeline.read_metrics(settings)
    run_id = pipeline.read_run_id(settings)
    return {
        "store_version": version,
        "model_version": _registry_version(settings, run_id),
        "run_id": run_id,
        "gate_verdict": gate.get("verdict"),
        "criteria_version": gate.get("criteria_version"),
        "family": settings.model_family,
        "params": {
            "C": settings.model_c,
            "impute_strategy": settings.impute_strategy,
            "n_estimators": settings.n_estimators,
        },
        "metrics": metrics,
        "data_md5": _data_md5(settings),
        "git_sha": _git_sha(settings.project_root),
        "source": f"model store {version}",
    }


def _registry_version(settings: Settings, run_id: str | None) -> str | None:
    """The registry version produced by THIS run, if there is one.

    Not the champion's version, and the difference is a provenance bug waiting
    to happen: a canary is by definition not the champion, so stamping the
    champion's number on it would make `/health` lie about exactly the model a
    rollout is asking questions about. The join key is the MLflow run id, which
    the train stage already wrote to disk.

    `mlflow_available` is checked first, and the two-second probe is not
    politeness: the MLflow client's own retry policy takes over a minute to give
    up on a closed port, and this lab is designed to run with the stack DOWN.
    A publish step that hangs for a minute is a publish step nobody runs.

    Returns None when there is no registry, no run, or no registered version for
    that run — all three are ordinary, and a null is honest where a guess is
    not. A store version whose `model_version` is null is a model the registry
    never accepted, which for Exercise 4's exhibit is precisely the truth.
    """
    from . import tracking

    if run_id is None or not tracking.mlflow_available(settings):
        return None
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient(settings.mlflow_tracking_uri)
        versions = client.search_model_versions(
            f"name='{settings.registered_model_name}' and run_id='{run_id}'"
        )
    except Exception:  # noqa: BLE001 -- the stack being down is an ordinary state
        return None
    return str(versions[0].version) if versions else None


def _data_md5(settings: Settings) -> str | None:
    """The DVC pointer md5 of the dataset this model was trained on."""
    try:
        from . import dvc_meta

        return dvc_meta.pointer_md5(settings.measurements_path)
    except Exception:  # noqa: BLE001 -- no pointer on a fresh clone
        return None


def publish_version(
    version: str,
    *,
    settings: Settings | None = None,
    force: bool = False,
) -> PublishResult:
    """Copy the current model into the store as `version`.

    Refuses unless `reports/gate.json` records a GO. `force=True` publishes
    anyway and records the real verdict — that is not a loophole, it is the
    exhibit for Exercise 4, and the honesty of the recorded verdict is what
    makes the exhibit teachable rather than merely broken.
    """
    settings = settings or load_settings()
    model = settings.models_dir / MODEL_FILE
    if not model.exists():
        raise FileNotFoundError(
            f"{model} does not exist. Run `make repro` first — publishing a model "
            "the pipeline never produced is not a thing this store can do."
        )

    provenance = build_provenance(settings, version)
    verdict = provenance.get("gate_verdict")
    if verdict != "GO" and not force:
        raise SystemExit(
            f"REFUSING to publish {version}: the recorded gate verdict is {verdict!r}.\n"
            "A model store is the FOURTH door into production (after register, promote\n"
            "and docker build), and it is the widest one — publishing is a file copy.\n"
            "Week 6 said only a GO model may be released, so the gate applies here too.\n"
            "Pass FORCE=1 if you are deliberately staging the Exercise 4 exhibit."
        )

    target = store_dir(settings) / version
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(model, target / MODEL_FILE)
    (target / PROVENANCE_FILE).write_text(json.dumps(provenance, indent=2) + "\n")
    return PublishResult(
        version=version, path=target, provenance=provenance, forced=force and verdict != "GO"
    )


def list_versions(settings: Settings | None = None) -> list[dict[str, Any]]:
    """What is in the store, and what each version claims to be."""
    settings = settings or load_settings()
    root = store_dir(settings)
    if not root.exists():
        return []
    rows = []
    for path in sorted(p for p in root.iterdir() if p.is_dir()):
        provenance = _read_json(path / PROVENANCE_FILE)
        rows.append(
            {
                "version": path.name,
                "has_model": (path / MODEL_FILE).exists(),
                "family": provenance.get("family"),
                "gate_verdict": provenance.get("gate_verdict"),
                "f1": (provenance.get("metrics") or {}).get("f1"),
                "run_id": provenance.get("run_id"),
            }
        )
    return rows


def format_versions(rows: list[dict[str, Any]]) -> str:
    """The store as a table. `gate_verdict` is the column to read."""
    if not rows:
        return "  (the store is empty — `make model-publish VERSION=v1`)"
    header = f"  {'version':8} {'family':8} {'gate':7} {'f1':8} {'model':6} run"
    lines = [header, "  " + "-" * (len(header) + 8)]
    for row in rows:
        lines.append(
            f"  {row['version']:8} {str(row['family']):8} {str(row['gate_verdict']):7} "
            f"{str(row['f1']):8} {'yes' if row['has_model'] else 'MISSING':6} "
            f"{(row['run_id'] or '-')[:12]}"
        )
    return "\n".join(lines)
