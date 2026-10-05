"""Shared fixtures for the Week 3 tests.

Week 2 put a reachability guard inside each server-dependent test. Week 3 has
eight of them, so the guard is lifted into a session-scoped fixture: one check,
one sweep, and one registration for the whole suite instead of eight.

The fixtures redirect to a `-tests` experiment and registered model, so running
the test suite never pollutes the artifacts you are graded on and never inflates
your model version numbers.
"""

from __future__ import annotations

import dataclasses
import urllib.error
import urllib.request

import pytest

from week_03_mlflow_integration import registry, tracking
from week_03_mlflow_integration.config import load_settings


@pytest.fixture(scope="session")
def settings():
    """Offline settings — no server required."""
    return load_settings()


@pytest.fixture(scope="session")
def live_settings(settings):
    """Skip every dependent test when the tracking server is unreachable."""
    try:
        urllib.request.urlopen(settings.mlflow_tracking_uri + "/health", timeout=2)
    except (urllib.error.URLError, OSError):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")

    # Settings is frozen, so replace() rather than mutate.
    return dataclasses.replace(
        settings,
        mlflow_experiment_name=settings.mlflow_experiment_name + "-tests",
        registered_model_name=settings.registered_model_name + "-tests",
    )


@pytest.fixture(scope="session")
def sweep_results(live_settings):
    """Run the sweep exactly once for every test that needs it."""
    return tracking.run_sweep(live_settings)


@pytest.fixture(scope="session")
def staging_version(live_settings, sweep_results):
    """Register the best run and promote it, once per session."""
    best_run_id = tracking.find_best_run(live_settings)
    version = registry.register_best_model(live_settings, best_run_id)
    return registry.promote_to_staging(
        live_settings, version.version, reason="pytest session"
    )
