"""Shared fixtures. Each guard skips only while its file or service is absent,
so the suite also runs in CI."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from week_09_serving.config import load_params, load_settings
from week_09_serving.tracking import mlflow_available


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def settings():
    """Settings. Needs only data/diabetes.csv and params.yaml, both committed."""
    return load_settings()


@pytest.fixture(scope="session")
def params(project_root) -> dict:
    return load_params(project_root)


@pytest.fixture(scope="session")
def raw_batches(project_root) -> Path:
    """The git-committed measurement batches the dataset is built from."""
    raw_dir = project_root / "data" / "raw"
    if not (raw_dir / "batch_01_baseline.csv").exists():
        pytest.skip(
            "data/raw batches missing — run scripts/sync_datasets.sh from the "
            "repository root."
        )
    return raw_dir


# ── Committed data ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def broken_batch(project_root) -> Path:
    """The corrupted batch in data/quality/, committed to Git."""
    path = project_root / "data" / "quality" / "broken_batch.csv"
    if not path.is_file():
        pytest.skip(
            "data/quality/broken_batch.csv missing — run scripts/sync_datasets.sh "
            "from the repository root."
        )
    return path


# ── Files that the pipeline writes or Git restores ──────────────────────────


@pytest.fixture(scope="session")
def validation_report(settings) -> Path:
    if not settings.validation_report_path.is_file():
        pytest.skip("No validation report yet: run `make validate`.")
    return settings.validation_report_path


@pytest.fixture(scope="session")
def dvc_repo(project_root) -> Path:
    if not (project_root / ".dvc" / "config").is_file():
        pytest.skip("No DVC repo: .dvc/config is committed, so restore it with `git checkout .dvc/config`.")
    return project_root


@pytest.fixture(scope="session")
def measurements_pointer(project_root) -> Path:
    pointer = project_root / "data" / "measurements.csv.dvc"
    if not pointer.is_file():
        pytest.skip("No DVC pointer: restore it with `git checkout data/measurements.csv.dvc`.")
    return pointer


@pytest.fixture(scope="session")
def dvc_lock(project_root) -> Path:
    lock = project_root / "dvc.lock"
    if not lock.is_file():
        pytest.skip("No dvc.lock yet — run `make repro`.")
    return lock


@pytest.fixture(scope="session")
def live_settings(settings):
    """Skip unless MLflow answers; use `-tests` names so test runs leave your real
    experiment and registered model alone."""
    if not mlflow_available(settings):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )


# ── Prefect ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def prefect_harness():
    """A temporary Prefect database, shared by the whole session because each setup is slow."""
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield
