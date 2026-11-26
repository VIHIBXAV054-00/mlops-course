"""Prefect tasks: the pipeline's steps, with retries only where it touches the network.

A retry helps only when the failure is transient and the operation is safe to repeat.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

import yaml
from prefect import get_run_logger, task
from prefect.tasks import exponential_backoff

from . import pipeline, registry
from .config import Settings
from .datasets import build_measurements

def _log():
    """The run logger inside a flow, an ordinary logger outside one.

    `get_run_logger()` raises outside a run, which would break `task.fn(...)` in unit tests.
    """
    try:
        return get_run_logger()
    except Exception:  # noqa: BLE001 -- MissingContextError and friends
        return logging.getLogger(__name__)


def _dvc_env() -> dict:
    """The environment `dvc` needs to reach Silo: the `.env` `S3_*` keys copied to `AWS_*`."""
    env = dict(os.environ)
    if "S3_ACCESS_KEY" in env:
        env.setdefault("AWS_ACCESS_KEY_ID", env["S3_ACCESS_KEY"])
    if "S3_SECRET_KEY" in env:
        env.setdefault("AWS_SECRET_ACCESS_KEY", env["S3_SECRET_KEY"])
    return env


def _run_dvc(settings: Settings, *args: str) -> str:
    """Run a dvc subcommand, and report its failure in a way you can act on."""
    result = subprocess.run(
        ["uv", "run", "dvc", *args],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
        env=_dvc_env(),
    )
    if result.returncode != 0:
        # keep the last lines of output, so the final error says what went wrong
        detail = ((result.stderr or "") + (result.stdout or "")).strip()
        tail = "\n  ".join(detail.splitlines()[-4:]) or "no output"
        raise RuntimeError(f"dvc {' '.join(args)} failed (exit {result.returncode}):\n  {tail}")
    return result.stdout


# the retry policy for network calls, in one place
NETWORK_RETRIES = {
    "retries": 3,
    # doubling delays give a restarting service time to come back
    "retry_delay_seconds": exponential_backoff(backoff_factor=2),
    # jitter stops tasks that failed together from retrying together
    "retry_jitter_factor": 0.5,
}


# ── No retries: local, deterministic work ───────────────────────────────────


@task
def build_dataset(settings: Settings, version: int = 2) -> str:
    """Rebuild the DVC-tracked dataset from the committed raw batches."""
    rows = build_measurements(
        version=version,
        raw_dir=settings.project_root / "data" / "raw",
        out_path=settings.measurements_path,
    )
    _log().info("built %s rows -> %s", rows, settings.measurements_path.name)
    return str(settings.measurements_path)


@task
def write_params(settings: Settings, overrides: dict | None = None) -> dict:
    """Write the runtime parameters into `params.yaml` before `dvc repro` runs.

    DVC decides what is stale from `params.yaml`, so a parameter it cannot see gives the old model.
    The change is not reverted, so `dvc.lock` and `params.yaml` agree.
    Two concurrent runs would race on this file.
    """
    if not overrides:
        return {}

    path = settings.project_root / "params.yaml"
    document = yaml.safe_load(path.read_text())

    applied: dict = {}
    for dotted, value in overrides.items():
        node = document
        *parents, leaf = dotted.split(".")
        for key in parents:
            node = node.setdefault(key, {})
        node[leaf] = value
        applied[dotted] = value

    path.write_text(yaml.safe_dump(document, sort_keys=False))
    _log().info("wrote %s into params.yaml", applied)
    return applied


@task
def run_pipeline(settings: Settings) -> dict:
    """`dvc repro` as one task: DVC decides which stages are stale. No retries."""
    logger = _log()
    result = subprocess.run(
        ["uv", "run", "dvc", "repro"],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
        env=_dvc_env(),
    )
    for line in (result.stdout or "").splitlines():
        if line.strip():
            logger.info(line.rstrip())

    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError(
            "dvc repro failed (exit %s):\n  %s" % (result.returncode, "\n  ".join(tail))
        )
    return pipeline.read_gate(settings)


@task
def verify_params_applied(settings: Settings, requested: dict) -> dict:
    """Check in `dvc.lock` that the pipeline saw the parameters the flow was asked to run."""
    if not requested:
        return {}

    lock = yaml.safe_load((settings.project_root / "dvc.lock").read_text())
    mismatches = []
    for dotted, want in requested.items():
        found = None
        for stage in lock.get("stages", {}).values():
            for _file, values in (stage.get("params") or {}).items():
                if dotted in values:
                    found = values[dotted]
        if found != want:
            mismatches.append(f"{dotted}: dvc.lock records {found!r}, flow asked for {want!r}")

    if mismatches:
        raise RuntimeError(
            "The pipeline never saw your parameters, so `train` was probably "
            "skipped and the model is stale:\n  "
            + "\n  ".join(mismatches)
            + "\n\nDid `write_params` run before `run_pipeline`?"
        )
    _log().info("dvc.lock confirms %s", requested)
    return requested


# ── Retries: the network edges, and nowhere else ────────────────────────────


@task(**NETWORK_RETRIES)
def pull_data(settings: Settings) -> bool:
    """`dvc pull` from Silo. Retried, because the call is idempotent."""
    _run_dvc(settings, "pull")
    return True


@task(**NETWORK_RETRIES)
def push_data(settings: Settings) -> bool:
    """`dvc push` to Silo. Retried, because the call is idempotent."""
    _run_dvc(settings, "push")
    return True


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def register_model(settings: Settings) -> str | None:
    """Register the run's model in MLflow. Not idempotent: each call creates a new version.

    So it first looks for a version from this run and returns it. That narrows the duplicate
    risk on retry, but does not remove it.
    """
    logger = _log()
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        logger.warning("no MLflow run recorded — skipping registration")
        return None

    from mlflow.tracking import MlflowClient

    client = MlflowClient(settings.mlflow_tracking_uri)
    existing = [
        v
        for v in client.search_model_versions(f"name='{settings.registered_model_name}'")
        if v.run_id == run_id
    ]
    if existing:
        version = existing[0].version
        logger.info("run %s is already registered as version %s — not registering again",
                    run_id[:8], version)
        return str(version)

    model_version = registry.register_best_model(settings, run_id)
    return str(model_version.version)


# ── No retries: reporting ───────────────────────────────────────────────────


@task
def notify(settings: Settings, verdict: dict, error: str | None = None) -> Path:
    """Write a one-line record of how the run ended, on the failure path too."""
    path = settings.project_root / "reports" / "last_run.txt"
    path.parent.mkdir(parents=True, exist_ok=True)

    if error:
        line = f"FAILED — {error}"
    elif verdict:
        summary = verdict.get("summary", {})
        line = (
            f"{verdict.get('verdict', '?')} — "
            f"{summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, "
            f"{summary.get('skipped', 0)} skipped "
            f"(criteria {verdict.get('criteria_version', '?')})"
        )
    else:
        line = "no verdict recorded"

    path.write_text(line + "\n")
    _log().info("notify: %s", line)
    return path


@task
def restore_params(settings: Settings, backup: Path | None) -> None:
    """Put `params.yaml` back. Used only by the demonstration targets."""
    if backup and backup.exists():
        shutil.move(str(backup), settings.project_root / "params.yaml")
        _log().info("params.yaml restored")
