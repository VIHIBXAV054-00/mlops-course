"""The smoke suite, in-process: it passes on the shipped model and fails on the C=0.001 model.

The C=0.001 model loads, answers /health with 200 and passes every probe, yet flags none of
the 192 test patients.
"""

from __future__ import annotations

import json
import os

import joblib
import pytest
from fastapi.testclient import TestClient

from week_10_kserve_rollout.api import create_app
from week_10_kserve_rollout.config import load_settings
from week_10_kserve_rollout.data import build_dataset
from week_10_kserve_rollout.model import build_model
from week_10_kserve_rollout.pipeline import _hyperparams
from week_10_kserve_rollout.release import load_release, problems
from week_10_kserve_rollout.smoke import (
    check_behaviour,
    check_contract,
    check_identity,
    check_protocol,
    run_smoke,
)

pytestmark = pytest.mark.eval


def _published_client(tmp_path, *, C: float, verdict: str, version: str) -> TestClient:
    """A store version on disk (model.pkl and provenance.json), served by the app."""
    settings = load_settings()
    hyperparams = {**_hyperparams(settings), "C": C}
    x_train, _, y_train, _ = build_dataset(settings)
    model = build_model(settings.model_family, hyperparams, settings, impute="median")
    model.fit(x_train, y_train)

    target = tmp_path / version
    target.mkdir()
    joblib.dump(model, target / "model.pkl")
    (target / "provenance.json").write_text(
        json.dumps(
            {
                "store_version": version,
                "model_version": "7",
                "run_id": "deadbeef",
                "gate_verdict": verdict,
                "family": settings.model_family,
                "params": {"C": C},
                "source": f"model store {version}",
            }
        )
    )

    os.environ["MODEL_PATH"] = str(target / "model.pkl")
    try:
        return TestClient(create_app(), raise_server_exceptions=False)
    finally:
        os.environ.pop("MODEL_PATH", None)


@pytest.fixture(scope="module")
def good_client(tmp_path_factory) -> TestClient:
    """The shipped model, published as v1 with a GO."""
    return _published_client(
        tmp_path_factory.mktemp("store-good"), C=1.0, verdict="GO", version="v1"
    )


@pytest.fixture(scope="module")
def broken_client(tmp_path_factory) -> TestClient:
    """The C=0.001 model, published by force with its NO-GO."""
    return _published_client(
        tmp_path_factory.mktemp("store-bad"), C=0.001, verdict="NO-GO", version="v3"
    )


# ── Shipped checks: identity, contract, protocol ─────────────────────────────


def test_the_health_check_alone_cannot_tell_the_two_models_apart(good_client, broken_client):
    for client in (good_client, broken_client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_identity_checks_the_version_the_rollout_meant_to_deploy(good_client):
    checks = {c.name: c for c in check_identity(good_client, expect_version="v2")}
    assert not checks["identity.version"].passed
    assert "serving v1" in checks["identity.version"].detail


def test_identity_fails_a_model_the_gate_refused(broken_client):
    checks = {c.name: c for c in check_identity(broken_client)}
    assert not checks["identity.gate"].passed


def test_the_contract_check_names_the_failing_rule(good_client):
    (check,) = check_contract(good_client)
    assert check.passed
    assert "greater_than" in check.detail


def test_both_routes_agree(good_client):
    (check,) = check_protocol(good_client)
    assert check.passed, check.detail


# ── Exercise 2: the behaviour check ───────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_behaviour_check_returns_three_named_checks(good_client):
    names = [check.name for check in check_behaviour(good_client)]
    assert names == [
        "behaviour.positive_is_positive",
        "behaviour.negative_is_negative",
        "behaviour.not_a_constant",
    ]


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_behaviour_check_reports_the_probabilities_it_saw(good_client):
    details = " ".join(check.detail for check in check_behaviour(good_client))
    assert "p=" in details
    assert "spread" in details


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_shipped_model_behaves(good_client):
    assert all(check.passed for check in check_behaviour(good_client, min_spread=0.1))


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_spread_check_uses_the_threshold_it_is_given(good_client):
    """A spread can never reach 1.0, so this threshold must fail."""
    checks = {c.name: c for c in check_behaviour(good_client, min_spread=1.0)}
    assert not checks["behaviour.not_a_constant"].passed


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_suite_passes_against_the_model_we_ship(good_client):
    report = run_smoke(good_client, expect_version="v1", min_spread=0.1)
    assert report["verdict"] == "PASS", report["checks"]


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_the_suite_fails_against_a_healthy_pod_serving_a_broken_model(broken_client):
    """The platform sees nothing wrong; the smoke test must."""
    report = run_smoke(broken_client, expect_version="v3", min_spread=0.1)
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert report["verdict"] == "FAIL"
    assert {"behaviour.positive_is_positive", "identity.gate"} <= failed, failed


@pytest.mark.skip(reason="Exercise 2: write check_behaviour() in smoke.py")
def test_your_release_spread_passes_the_shipped_model(good_client):
    """The threshold in release.yaml must not fail the model you ship today."""
    release = load_release()
    if problems(release):
        pytest.skip("release.yaml is not complete yet (Exercise 2)")
    spread = release["smoke"]["min_probability_spread"]
    checks = {c.name: c for c in check_behaviour(good_client, min_spread=spread)}
    assert checks["behaviour.not_a_constant"].passed, (
        f"min_probability_spread {spread} fails the model you ship: {checks['behaviour.not_a_constant'].detail}"
    )
