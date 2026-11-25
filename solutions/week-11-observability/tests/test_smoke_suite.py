"""The smoke suite, tested — including the case where it must FAIL.

A check that has never failed is not known to work. Week 4 shipped a
`check_locks.sh` that exited 0 having checked nothing; Week 7 shipped a
`ci-fail` target that reported success while planting no fault. Both were
believed for a while. A smoke test is the same shape of risk with higher stakes,
because it is the last thing between a bad model and real traffic.

So this file does two things:

  * asserts the suite PASSES against the shipped logistic regression;
  * asserts it FAILS against the `C: 0.001` model — the one Week 6 built to
    break the gate, which predicts the negative class for **all 192** test
    patients and still scores ROC-AUC 0.8407, higher than the model we ship.
    That model loads fine, answers `/health` with a 200, and passes every probe
    Week 9 wrote.

Both run in-process against a `TestClient`. No cluster, no Docker, no server, no
network — so the autograder runs them, and so does a student on a train.
"""

from __future__ import annotations

import json
import os

import joblib
import pytest
from fastapi.testclient import TestClient

from week_11_observability.api import create_app
from week_11_observability.config import load_settings
from week_11_observability.data import build_dataset
from week_11_observability.model import build_model
from week_11_observability.pipeline import _hyperparams
from week_11_observability.smoke import (
    check_behaviour,
    check_contract,
    check_identity,
    run_smoke,
)

pytestmark = pytest.mark.eval


def _published_client(tmp_path, *, C: float, verdict: str, version: str) -> TestClient:
    """A store version, on disk, served by the app — the deployed shape.

    Writing `provenance.json` beside the model is not test scaffolding; it is
    exactly what `make model-publish` does, and it is what lets `/health` report
    an identity at all. The app is then pointed at that directory, which is what
    KServe's mount does in the cluster.
    """
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
    """Week 6's exhibit: over-regularised until it flags nobody."""
    return _published_client(
        tmp_path_factory.mktemp("store-bad"), C=0.001, verdict="NO-GO", version="v3"
    )


def test_the_suite_passes_against_the_model_we_actually_ship(good_client):
    report = run_smoke(good_client, expect_version="v1")
    assert report["verdict"] == "PASS", report["checks"]
    assert report["failed"] == 0


def test_the_suite_fails_against_a_healthy_pod_serving_a_broken_model(broken_client):
    """**The most important test in the lab.**

    Everything the platform can see is fine: the model deserialised, `/health`
    returns 200, the readiness probe passes, every request gets an HTTP 200. A
    rollout that watched only the platform would promote this.

    What fails is behaviour — the model says "no diabetes" to a patient with a
    glucose of 183 and a BMI of 40.5 — and identity, because the gate refused it
    and `provenance.json` says so.
    """
    report = run_smoke(broken_client, expect_version="v3")
    failed = {check["name"] for check in report["checks"] if not check["passed"]}

    assert report["verdict"] == "FAIL"
    assert failed == {"behaviour.positive_is_positive", "identity.gate"}, failed

    # Read that set carefully, because it is the honest result rather than the
    # tidy one. TWO checks caught this model: the golden positive came back
    # negative, and the recorded gate verdict was a NO-GO. The probability
    # SPREAD check did not catch it (measured: 0.1754, above the 0.10 floor), and
    # neither did the contract, the protocol or `/health`. Every check catches a
    # different failure; a suite is a set of partial checks, and the ones that
    # passed here are exactly why you need more than one.


def test_the_health_check_alone_cannot_tell_the_two_apart(good_client, broken_client):
    """Week 9's honest limitation, as an assertion.

    Both endpoints answer `/health` with a 200 and a loaded model. That is the
    entire basis on which Kubernetes decides to send them traffic.
    """
    for client in (good_client, broken_client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_identity_checks_the_version_the_rollout_meant_to_deploy(good_client):
    """"Something is serving" is a ping. "v1 is serving" is a test."""
    checks = {c.name: c for c in check_identity(good_client, expect_version="v2")}
    assert not checks["identity.version"].passed
    assert "serving v1" in checks["identity.version"].detail


def test_the_contract_check_names_the_failing_rule(good_client):
    (check,) = check_contract(good_client)
    assert check.passed
    assert "greater_than" in check.detail, (
        "a 422 that does not name the check teaches a caller nothing"
    )


def test_the_behaviour_check_reports_the_probabilities_it_saw(good_client):
    """A check that only says pass/fail is hard to act on at 3 a.m."""
    details = " ".join(check.detail for check in check_behaviour(good_client))
    assert "p=" in details
    assert "spread" in details
