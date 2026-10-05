"""Tests for the model registry: versions, aliases, traceability (Exercises 5-7).

All `live` — see test_tracking.py for how the skip works.
"""

import dataclasses

import pytest
from mlflow.tracking import MlflowClient

from week_03_mlflow_integration import registry, tracking
from week_03_mlflow_integration.registry import load_aliased_model, trace_alias

pytestmark = pytest.mark.live


def test_registration_creates_version_with_run_id(live_settings, staging_version) -> None:
    """Exercise 5: the version exists AND links back to its source run.

    The run_id assertion is the important half: it is hop 2 of the
    traceability chain. A version created from a bare artifact path (for
    example `client.create_model_version(source="s3://...")`) has no run, and
    every later hop is then a guess.
    """
    assert int(staging_version.version) >= 1
    assert staging_version.run_id, "ModelVersion.run_id is empty — register from a run"


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
    # The human half of the evidence: why this version.
    assert chain["version_tags"]["promotion_reason"] == "pytest session"


def test_aliased_model_loads_and_predicts(live_settings, staging_version) -> None:
    """Exercise 6: models:/<name>@<alias> loads with NO object-store credentials.

    This is the only test that exercises the artifact proxy end to end, and it
    is what proves Week 2's credential story: the client holds the tracking URI
    and nothing else, while the server holds the Silo keys.
    """
    from week_03_mlflow_integration.data import build_dataset

    model = load_aliased_model(live_settings)
    _, x_test, _, _ = build_dataset(live_settings)
    predictions = model.predict(x_test.head(5))
    assert len(predictions) == 5


@pytest.fixture(scope="module")
def rollback_registry(live_settings, sweep_results):
    """Three versions under their own name: two promoted in turn, one never."""
    settings = dataclasses.replace(
        live_settings,
        registered_model_name=live_settings.registered_model_name + "-rollback",
    )
    run_id = tracking.find_best_run(settings)
    first, second, unpromoted = (
        registry.register_best_model(settings, run_id).version for _ in range(3)
    )
    registry.promote_to_staging(settings, first, reason="first champion")
    registry.promote_to_staging(settings, second, reason="second champion")
    return settings, first, second, unpromoted


def test_rollback_refuses_unpromoted_target(rollback_registry) -> None:
    """Exercise 7: a version that never passed promotion is not a rollback target."""
    settings, _, _, unpromoted = rollback_registry
    client = MlflowClient(settings.mlflow_tracking_uri)
    before = client.get_model_version_by_alias(
        settings.registered_model_name, settings.model_alias
    ).version

    with pytest.raises(ValueError):
        registry.roll_back(settings, unpromoted, "should be refused")

    after = client.get_model_version_by_alias(
        settings.registered_model_name, settings.model_alias
    ).version
    assert after == before, "a refused rollback must not move the alias"


def test_rollback_moves_both_aliases_and_records_why(rollback_registry) -> None:
    """Exercise 7: both aliases move back, and the demoted version says why."""
    settings, first, second, _ = rollback_registry
    client = MlflowClient(settings.mlflow_tracking_uri)
    current = client.get_model_version_by_alias(
        settings.registered_model_name, settings.model_alias
    ).version
    if current == first:  # already rolled back by an earlier run of this test
        pytest.skip("rollback already exercised in this session")

    previous, restored = registry.roll_back(settings, first, "second one misbehaved")

    assert previous == second
    assert restored.version == first
    assert {settings.model_alias, "champion"} <= set(restored.aliases)

    # The registry keeps no alias history; this tag is the only record.
    demoted = client.get_model_version(settings.registered_model_name, second)
    assert demoted.tags["rollback_reason"] == "second one misbehaved"
    assert demoted.tags["rolled_back_to"] == first
