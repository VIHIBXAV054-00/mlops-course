"""Shared fixtures.

A guard fixture skips only while its prerequisite (a service, a file you create) is
missing, so the same tests pass on your machine, on a fresh clone and in CI.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from week_12_drift_monitoring.config import load_params, load_settings
from week_12_drift_monitoring.tracking import mlflow_available


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def settings():
    """Settings. Needs only data/diabetes.csv and params.yaml, both committed."""
    return load_settings()


@pytest.fixture(scope="session")
def served_model(tmp_path_factory) -> Path:
    """A model trained here on the committed data, for tests that need a working API."""
    import joblib

    from week_12_drift_monitoring.data import build_dataset
    from week_12_drift_monitoring.model import build_model
    from week_12_drift_monitoring.pipeline import _hyperparams

    settings = load_settings()
    x_train, _, y_train, _ = build_dataset(settings)
    model = build_model(settings.model_family, _hyperparams(settings), settings,
                        impute="median")
    model.fit(x_train, y_train)
    path = tmp_path_factory.mktemp("model") / "model.pkl"
    joblib.dump(model, path)
    return path


@pytest.fixture
def scoring_model(served_model, monkeypatch) -> Path:
    """Point the app at `served_model`, so `/predict` scores instead of returning 503."""
    monkeypatch.setenv("MODEL_PATH", str(served_model))
    return served_model


@pytest.fixture(scope="session")
def reference_root(tmp_path_factory, raw_batches, project_root, settings) -> Path:
    """A project root holding the drift reference window, rebuilt from the committed batches.

    It builds dataset version 2 like `make data-v2`, checks its md5 against drift.yaml
    and splits it like `prepare`. Pass the result to `load_reference`.
    """
    from week_12_drift_monitoring.data import load_measurements, split_measurements
    from week_12_drift_monitoring.datasets import build_measurements, file_md5
    from week_12_drift_monitoring.drift_policy import load_policy

    policy = load_policy(project_root / "drift.yaml")
    root = tmp_path_factory.mktemp("reference")
    measurements = root / "data" / "measurements.csv"
    build_measurements(2, raw_batches, measurements)
    assert file_md5(measurements) == policy.reference_md5, (
        "the rebuilt dataset version 2 does not match the md5 in drift.yaml"
    )
    train, _ = split_measurements(load_measurements(measurements), settings)
    out = root / policy.reference_path
    out.parent.mkdir(parents=True, exist_ok=True)
    train.to_csv(out, index=False, lineterminator="\n")
    return root


@pytest.fixture
def model_file(project_root) -> Path:
    """The project's own trained model. Skips until `make repro` has written it."""
    path = project_root / "models" / "model.pkl"
    if not path.exists():
        pytest.skip(
            "No trained model yet — run `make repro`. (model.pkl is git-ignored: "
            "it is a build artifact, so a fresh clone does not have one.)"
        )
    return path


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


# ── Committed data ───────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def broken_batch(project_root) -> Path:
    """The corrupted batch for the validation tests."""
    path = project_root / "data" / "quality" / "broken_batch.csv"
    if not path.is_file():
        pytest.skip(
            "data/quality/broken_batch.csv missing — run scripts/sync_datasets.sh "
            "from the repository root."
        )
    return path


# ── Guards for files you create during the lab ───────────────────────────────


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
    """Skip unless the tracking server answers.

    The tests write to a `-tests` experiment and registered model, so they never touch yours.
    """
    if not mlflow_available(settings):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )


# ── Prefect ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def prefect_harness():
    """A temporary Prefect database, set up once per session because setup takes seconds."""
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield
