"""Shared fixtures.

A fixture below skips its tests while their prerequisite (a DVC repo, a pointer,
the MLflow server) is missing, and runs them as soon as it exists.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest

from week_04_dvc_introduction.config import load_params, load_settings
from week_04_dvc_introduction.tracking import mlflow_available


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
def incoming(project_root) -> Path:
    """The three batches in data/incoming/, committed to Git."""
    incoming_dir = project_root / "data" / "incoming"
    if not (incoming_dir / "batch_01.csv").exists():
        pytest.skip(
            "data/incoming batches missing — run scripts/sync_datasets.sh from the "
            "repository root."
        )
    return incoming_dir


def copy_batches(incoming_dir: Path, raw_dir: Path, count: int) -> Path:
    """Copy the first `count` batches into `raw_dir`, as if they had arrived."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(incoming_dir.glob("batch_*.csv"))[:count]:
        shutil.copyfile(source, raw_dir / source.name)
    return raw_dir


@pytest.fixture
def make_raw(incoming, tmp_path):
    """A function that returns a new data/raw/ folder holding the first n batches."""
    return lambda count: copy_batches(incoming, tmp_path / f"raw_{count}", count)


@pytest.fixture(scope="session")
def all_batches(incoming, tmp_path_factory) -> Path:
    """A data/raw/ folder in which all three batches have arrived."""
    return copy_batches(incoming, tmp_path_factory.mktemp("raw_all"), 3)


# ── Guards for files you create in Exercises 1, 2 and 5 ──────────────────────


@pytest.fixture(scope="session")
def dvc_repo(project_root) -> Path:
    if not (project_root / ".dvc" / "config").is_file():
        pytest.skip("No DVC repo yet — complete Exercise 1 (`make dvc-init`).")
    return project_root


@pytest.fixture(scope="session")
def measurements_pointer(project_root) -> Path:
    pointer = project_root / "data" / "measurements.csv.dvc"
    if not pointer.is_file():
        pytest.skip("No DVC pointer yet — complete Exercise 2 (`make dvc-add`).")
    return pointer


@pytest.fixture(scope="session")
def dvc_lock(project_root) -> Path:
    lock = project_root / "dvc.lock"
    if not lock.is_file():
        pytest.skip("No dvc.lock yet — complete Exercise 5 (`make repro`).")
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
