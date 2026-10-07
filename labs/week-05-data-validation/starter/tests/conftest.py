"""Shared fixtures.

A fixture below skips its tests while their prerequisite (the dataset, dvc.lock,
the MLflow server) is missing, and runs them as soon as it exists.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from week_05_data_validation.config import load_params, load_settings
from week_05_data_validation.tracking import mlflow_available


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
    """The two batches in data/raw/, committed to Git."""
    raw_dir = project_root / "data" / "raw"
    if len(list(raw_dir.glob("batch_*.csv"))) != 2:
        pytest.skip(
            "data/raw batches missing — run scripts/sync_datasets.sh from the "
            "repository root."
        )
    return raw_dir


@pytest.fixture(scope="session")
def broken_batch(project_root) -> Path:
    """The broken batch of Exercise 2, committed to Git."""
    path = project_root / "data" / "quality" / "broken_batch.csv"
    if not path.is_file():
        pytest.skip(
            "data/quality/broken_batch.csv missing — run scripts/sync_datasets.sh "
            "from the repository root."
        )
    return path


@pytest.fixture(scope="session")
def measurements_file(settings) -> Path:
    if not settings.measurements_path.is_file():
        pytest.skip("data/measurements.csv is missing — run `make build-data` (Setup).")
    return settings.measurements_path


# ── Guards for files that ship with the lab or that `make repro` writes ─────


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
    """Skip unless the tracking server answers.

    Uses a `-tests` experiment and model name, so tests do not add to your own runs.
    """
    if not mlflow_available(settings):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )
