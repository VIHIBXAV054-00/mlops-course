"""The model store: publish a model version for the cluster to fetch.

    model-store/
      v1/  model.pkl  provenance.json   logistic regression, GO
      v2/  model.pkl  provenance.json   random forest, GO
      v3/  model.pkl  provenance.json   C=0.001, NO-GO, published with FORCE=1

Publishing is a file copy, so it is a fourth way into production after `register`, `promote`
and `docker build`, and it asks the gate first.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings, load_settings

# the files of a store version; the manifest reads MODEL_PATH=/mnt/models/model.pkl
MODEL_FILE = "model.pkl"
PROVENANCE_FILE = "provenance.json"


@dataclass(frozen=True)
class PublishResult:
    version: str
    path: Path
    provenance: dict[str, Any]
    forced: bool


def store_dir(settings: Settings) -> Path:
    """Where published versions live: a folder the kind node mounts as a PersistentVolume."""
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
    """What a running pod can say about its model, read from what the pipeline wrote.

    The registry version is looked up once, here; with the stack down it is null.
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
    """The registry version made from this run, or None when there is no registry or no version.

    Not the champion's version: a canary is not the champion.
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
    except Exception:  # noqa: BLE001 -- the stack may be down
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
    """Copy the current model into the store as `version`, with its provenance.

    Refuses unless `reports/gate.json` records a GO. `force=True` publishes anyway and records
    the real verdict, so the pod still reports it.
    """
    settings = settings or load_settings()
    model = settings.models_dir / MODEL_FILE
    if not model.exists():
        raise FileNotFoundError(
            f"{model} does not exist. Run `make repro` first."
        )

    provenance = build_provenance(settings, version)
    verdict = provenance.get("gate_verdict")
    # TODO(student) Exercise 1: refuse to publish a model whose gate verdict is not "GO",
    # unless `force` is true. Raise SystemExit with a message that starts with
    # "REFUSING to publish" and names the version and the verdict.
    # Raise before anything is written to the store.

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
