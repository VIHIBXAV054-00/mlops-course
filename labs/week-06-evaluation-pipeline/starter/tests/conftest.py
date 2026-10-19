"""Shared fixtures. Infrastructure guards are fixtures that skip when the stack, a DVC file or a report is absent."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from week_06_evaluation_pipeline.config import load_params, load_settings
from week_06_evaluation_pipeline.tracking import mlflow_available


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
    """The committed measurement batches."""
    raw_dir = project_root / "data" / "raw"
    if not (raw_dir / "batch_01_baseline.csv").exists():
        pytest.skip(
            "data/raw batches missing — run scripts/sync_datasets.sh from the "
            "repository root."
        )
    return raw_dir


@pytest.fixture(scope="session")
def broken_batch(project_root) -> Path:
    """The corrupted batch. It is committed, so it is always available."""
    path = project_root / "data" / "quality" / "broken_batch.csv"
    if not path.is_file():
        pytest.skip(
            "data/quality/broken_batch.csv missing — run scripts/sync_datasets.sh "
            "from the repository root."
        )
    return path


# ── Guards for files that exist only after the lab commands have run ──


@pytest.fixture(scope="session")
def validation_report(settings) -> Path:
    if not settings.validation_report_path.is_file():
        pytest.skip("No validation report yet — run `make validate`.")
    return settings.validation_report_path


@pytest.fixture(scope="session")
def dvc_repo(project_root) -> Path:
    if not (project_root / ".dvc" / "config").is_file():
        pytest.skip("No DVC repo: .dvc/config is missing.")
    return project_root


@pytest.fixture(scope="session")
def measurements_pointer(project_root) -> Path:
    pointer = project_root / "data" / "measurements.csv.dvc"
    if not pointer.is_file():
        pytest.skip("No DVC pointer: data/measurements.csv.dvc is missing.")
    return pointer


@pytest.fixture(scope="session")
def dvc_lock(project_root) -> Path:
    lock = project_root / "dvc.lock"
    if not lock.is_file():
        pytest.skip("No dvc.lock yet — run `make repro`.")
    return lock


@pytest.fixture(scope="session")
def live_settings(settings):
    """Skip unless the tracking server answers. Uses a `-tests` experiment and model name."""
    if not mlflow_available(settings):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )
