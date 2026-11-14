"""release.yaml, the rollout plan: complete, and consistent with the rest of the lab."""

from __future__ import annotations

import pytest

from week_10_kserve_rollout.release import load_release, problems, value

pytestmark = pytest.mark.unit

COMPLETE = {
    "model": {"candidate": "v2", "replaces": "v1"},
    "strategy": "canary",
    "canary": {"percent": 10},
    "smoke": {"min_probability_spread": 0.1},
    "load": {"expected_rps": 20, "max_p95_ms": 300, "max_error_rate": 0.01},
    "promote": {"when": ["24 hours without a failed check"]},
    "rollback": {"when": ["any smoke check fails"]},
}


# ── Shipped: the checks in release.py ─────────────────────────────────────────


def test_a_complete_request_has_no_problems():
    assert problems(COMPLETE) == []


def test_every_placeholder_is_named():
    request = {**COMPLETE, "canary": {"percent": "<fill in>"}}
    assert problems(request) == ["`canary.percent` is still `<fill in>`"]


def test_the_candidate_must_differ_from_the_running_version():
    request = {**COMPLETE, "model": {"candidate": "v1", "replaces": "v1"}}
    assert any("same version" in problem for problem in problems(request))


def test_a_canary_share_above_half_is_not_a_canary():
    request = {**COMPLETE, "canary": {"percent": 80}}
    assert any("canary.percent" in problem for problem in problems(request))


def test_an_error_rate_is_a_share_not_a_percentage():
    request = {**COMPLETE, "load": {**COMPLETE["load"], "max_error_rate": 5}}
    assert any("max_error_rate" in problem for problem in problems(request))


def test_a_request_without_promotion_criteria_is_not_ready():
    request = {**COMPLETE, "promote": {"when": []}}
    assert any("promote.when" in problem for problem in problems(request))


def test_a_dotted_key_reads_a_nested_value():
    assert value(COMPLETE, "smoke.min_probability_spread") == 0.1


# ── Exercise 2: your release.yaml ─────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 2: fill in release.yaml")
def test_your_rollout_plan_is_complete():
    found = problems(load_release())
    assert found == [], "release.yaml is not ready:\n  " + "\n  ".join(found)


@pytest.mark.skip(reason="Exercise 2: fill in release.yaml")
def test_your_request_releases_a_version_from_the_store():
    release = load_release()
    assert release["model"]["candidate"] != release["model"]["replaces"]
    assert release["strategy"] == "canary"
