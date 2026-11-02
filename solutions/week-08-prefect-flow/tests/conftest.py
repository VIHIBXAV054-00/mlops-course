"""Shared fixtures.

The design goal, carried over from Week 4, is that ONE test file is green everywhere: on a
student's finished machine, on a fresh clone, and in the course autograder —
which runs `uv sync --all-groups && uv run pytest -q` with no Docker, no Silo,
no DVC remote and no `dvc pull`.

That is why the infrastructure guards below are FIXTURES rather than
`@pytest.mark.skip` decorators. A fixture skips only when its prerequisite is
genuinely absent, so the same test runs for real the moment the prerequisite
appears. Static skips would stay skipped forever.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from week_08_prefect_flow.config import load_params, load_settings
from week_08_prefect_flow.tracking import mlflow_available


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


# ── Week 5: git-committed teaching material, so no guard needed for the data ──


@pytest.fixture(scope="session")
def broken_batch(project_root) -> Path:
    """The deliberately corrupted batch. Committed, so it is always available.

    That is a deliberate property of the week: the whole validation half of this
    lab runs with no Docker, no Silo and no `dvc pull`, because every input it
    needs is in Git.
    """
    path = project_root / "data" / "quality" / "broken_batch.csv"
    if not path.is_file():
        pytest.skip(
            "data/quality/broken_batch.csv missing — run scripts/sync_datasets.sh "
            "from the repository root."
        )
    return path


# ── Guards for state the student creates during the lab ──────────────────────
# All four are absent in the starter and in CI, and present after the DVC setup
# carried over from Week 4 and after `make repro`.


@pytest.fixture(scope="session")
def validation_report(settings) -> Path:
    if not settings.validation_report_path.is_file():
        pytest.skip("No validation report yet — run `make validate` (Exercise 1).")
    return settings.validation_report_path


@pytest.fixture(scope="session")
def dvc_repo(project_root) -> Path:
    if not (project_root / ".dvc" / "config").is_file():
        pytest.skip("No DVC repo yet — run `make dvc-init` (Week 4 setup).")
    return project_root


@pytest.fixture(scope="session")
def measurements_pointer(project_root) -> Path:
    pointer = project_root / "data" / "measurements.csv.dvc"
    if not pointer.is_file():
        pytest.skip("No DVC pointer yet — run `make dvc-add` (Week 4 setup).")
    return pointer


@pytest.fixture(scope="session")
def dvc_lock(project_root) -> Path:
    lock = project_root / "dvc.lock"
    if not lock.is_file():
        pytest.skip("No dvc.lock yet — run `make repro` (Exercise 4).")
    return lock


@pytest.fixture(scope="session")
def live_settings(settings):
    """Skip unless the tracking server answers.

    Redirects to a `-tests` experiment and registered model so running the suite
    never pollutes the artifacts you are graded on or inflates version numbers.
    `Settings` is frozen, hence `dataclasses.replace`.
    """
    if not mlflow_available(settings):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )


# ── Week 8: Prefect ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def prefect_harness():
    """A temporary Prefect database for the whole session.

    SESSION-scoped, and the scope is a measured decision rather than a habit
    (prefect 3.8.2, this machine):

        harness setup      ~4.3s   once
        a flow run inside  ~1.1s   each
        task.fn(...)        0.000s  — no harness needed at all

    Per-test would pay the 4.3s every time. And note the failure mode if you
    skip the harness entirely: Prefect quietly starts a TEMPORARY server per
    process (~8s), so a careless suite gets slower rather than failing, which
    is the worst possible shape for a time budget.

    Most tests here use `task.fn()` and never touch this.
    """
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield
