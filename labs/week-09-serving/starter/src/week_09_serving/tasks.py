"""Prefect tasks for the training flow. Only the tasks that call the network have `retries=`.

A retry helps only when the failure is temporary and the operation is safe to repeat.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import yaml
from prefect import get_run_logger, task
from prefect.tasks import exponential_backoff

from . import pipeline, registry
from .config import Settings
from .datasets import build_measurements

def _log():
    """The Prefect run logger inside a flow, a standard logger outside one, so `task.fn()` works."""
    try:
        return get_run_logger()
    except Exception:  # noqa: BLE001 -- MissingContextError and friends
        return logging.getLogger(__name__)


def _dvc_env() -> dict:
    """Copy the `S3_*` credentials from `.env` to the `AWS_*` names that `dvc` reads."""
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
        # Keep the last lines of output, so the final error says why dvc failed.
        detail = ((result.stderr or "") + (result.stdout or "")).strip()
        tail = "\n  ".join(detail.splitlines()[-4:]) or "no output"
        raise RuntimeError(f"dvc {' '.join(args)} failed (exit {result.returncode}):\n  {tail}")
    return result.stdout


# One place to say "this is a flaky network call", so the policy is visible
# rather than scattered across decorators.
NETWORK_RETRIES = {
    "retries": 3,
    # Doubling, so a service that is restarting gets a chance to finish.
    "retry_delay_seconds": exponential_backoff(backoff_factor=2),
    # Jitter spreads the retries, so tasks that failed together do not retry together.
    "retry_jitter_factor": 0.5,
}


# ── No retries: local, deterministic work ───────────────────────────────────


@task
def build_dataset(settings: Settings, version: int = 2) -> str:
    """Rebuild the DVC-tracked dataset from the raw batches in Git. No retries: files are local."""
    rows = build_measurements(
        version=version,
        raw_dir=settings.project_root / "data" / "raw",
        out_path=settings.measurements_path,
    )
    _log().info("built %s rows -> %s", rows, settings.measurements_path.name)
    return str(settings.measurements_path)


@task
def params_committed(settings: Settings) -> bool:
    """True when `params.yaml` has no uncommitted changes in Git."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "params.yaml"],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        _log().warning("cannot check params.yaml in Git: %s", result.stderr.strip())
        return False
    return result.stdout.strip() == ""


@task
def run_pipeline(settings: Settings) -> dict:
    """Run `dvc repro` as one task; DVC decides which stages are stale.

    No retries: a failed stage or a NO-GO fails the same way again.
    """
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
def read_params_used(settings: Settings, stage: str = "train") -> dict:
    """The parameter values `stage` used in its last run, as `dvc.lock` records them.

    `dvc.lock` stores the values, not only a hash:

        train:
          params:
            params.yaml:
              train.C: 1.0
    """
    lock = yaml.safe_load((settings.project_root / "dvc.lock").read_text())
    recorded = lock["stages"][stage].get("params") or {}
    return {name: value for values in recorded.values() for name, value in values.items()}


# ── Retries: the network edges, and nowhere else ────────────────────────────


@task(**NETWORK_RETRIES)
def pull_data(settings: Settings) -> bool:
    """`dvc pull` from Silo. Safe to retry: the same content hash always gives the same bytes."""
    _run_dvc(settings, "pull")
    return True


@task(**NETWORK_RETRIES)
def push_data(settings: Settings) -> bool:
    """`dvc push` to Silo. Retries for the same reason, idempotent for the same reason."""
    _run_dvc(settings, "push")
    return True


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def register_model(settings: Settings) -> str | None:
    """Register the run's model in MLflow. Not idempotent: each call creates a new version.

    So it first returns an existing version for this run id; a lost response can still duplicate.
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
def notify(
    settings: Settings,
    verdict: dict,
    error: str | None = None,
    params: dict | None = None,
    committed: bool | None = None,
) -> Path:
    """Write a one-line record of how the run ended to `reports/last_run.txt`."""
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

    if params and not error:
        values = ", ".join(f"{name}={value}" for name, value in sorted(params.items()))
        state = "committed" if committed else "uncommitted"
        line += f" | {values} | params.yaml {state}"

    path.write_text(line + "\n")
    _log().info("notify: %s", line)
    return path
