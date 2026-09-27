"""Tests for the model registry: versions, aliases, traceability (Exercises 5-6).

All `live` — see test_tracking.py for how the skip works.
"""

import pytest
from mlflow.tracking import MlflowClient

from week_03_mlflow_integration.registry import load_aliased_model, trace_alias

pytestmark = pytest.mark.live


def test_registration_creates_version_with_run_id(live_settings, staging_version) -> None:
    """Exercise 5: the version exists AND links back to its source run.

    The run_id assertion is the important half. `mlflow.register_model` only
    records run_id when the model URI is the `runs:/<run_id>/model` form —
    registering from `model_info.model_uri` (`models:/<model_id>` in MLflow 3)
    leaves it empty against the open-source registry and silently breaks the
    traceability chain below. If someone "simplifies" registry.py, this fails.
    """
    assert int(staging_version.version) >= 1
    assert staging_version.run_id, "ModelVersion.run_id is empty — register from runs:/"


def test_alias_resolves_to_version(live_settings, staging_version) -> None:
    """Exercise 6: the alias points at the promoted version.

    Two aliases coexist on one version — something a fixed stage could never do.
    """
    client = MlflowClient(live_settings.mlflow_tracking_uri)
    resolved = client.get_model_version_by_alias(
        live_settings.registered_model_name, live_settings.model_alias
    )
    assert resolved.version == staging_version.version
    assert live_settings.model_alias in staging_version.aliases
    assert "champion" in staging_version.aliases


def test_alias_traceability_chain(live_settings, staging_version) -> None:
    """Exercise 6: alias -> version -> run -> the params that produced it."""
    chain = trace_alias(live_settings)

    assert chain["version"] == staging_version.version
    assert chain["run_id"]

    # Params come back as STRINGS, not the types you logged. Classic trip-up.
    assert chain["params"]["random_seed"] == "42"
    assert chain["git_commit"]

    # The promotion evidence on the version matches the source run's metric,
    # so the tag cannot drift away from what was actually measured.
    assert chain["version_tags"]["validation_f1"] == f"{chain['metrics']['f1']:.4f}"
    assert chain["version_tags"]["promoted_by"] == live_settings.model_owner


def test_aliased_model_loads_and_predicts(live_settings, staging_version) -> None:
    """Exercise 6: models:/<name>@<alias> loads with NO object-store credentials.

    This is the only test that exercises the artifact proxy end to end, and it
    is what proves Week 2's credential story: the client holds the tracking URI
    and nothing else, while the server holds the MinIO keys.
    """
    from week_03_mlflow_integration.data import build_dataset

    model = load_aliased_model(live_settings)
    _, x_test, _, _ = build_dataset(live_settings)
    predictions = model.predict(x_test.head(5))
    assert len(predictions) == 5
