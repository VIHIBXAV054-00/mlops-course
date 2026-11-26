"""Tests for the traffic generator's plan, which is a pure function of (count, mix, seed)."""

from __future__ import annotations

from collections import Counter

import pytest

from week_11_observability.traffic import (
    ILLEGAL_PATIENT,
    _request_for,
    parse_mix,
    plan,
)

pytestmark = pytest.mark.unit


def test_the_mix_is_respected_within_sampling_error():
    """900 valid and 100 violations, within sampling error."""
    kinds = Counter(plan(1000, {"valid": 0.9, "violation": 0.1}, seed=7))
    assert set(kinds) == {"valid", "violation"}
    # the binomial standard error at n=1000, p=0.1 is about 0.95 points, so +/-4 points never flakes
    assert 0.06 < kinds["violation"] / 1000 < 0.14


def test_the_same_seed_gives_the_same_plan():
    assert plan(200, {"valid": 3, "violation": 1}, seed=1) == plan(
        200, {"valid": 3, "violation": 1}, seed=1
    )
    assert plan(200, {"valid": 3, "violation": 1}, seed=1) != plan(
        200, {"valid": 3, "violation": 1}, seed=2
    )


def test_weights_do_not_have_to_sum_to_one():
    """`--mix valid=9,violation=1` means 90/10."""
    kinds = Counter(plan(1000, {"valid": 9, "violation": 1}, seed=7))
    assert 0.06 < kinds["violation"] / 1000 < 0.14


def test_a_mix_with_no_positive_weight_is_refused():
    with pytest.raises(ValueError, match="positive weight"):
        plan(10, {"valid": 0, "violation": 0})


def test_zero_requests_is_not_an_error():
    assert plan(0, {"valid": 1}) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("valid=9,violation=1", {"valid": 9.0, "violation": 1.0}),
        (" valid = 1 , notfound = 2 ", {"valid": 1.0, "notfound": 2.0}),
    ],
)
def test_parse_mix(text, expected):
    assert parse_mix(text) == expected


@pytest.mark.parametrize("bad", ["", "valid", "valid=", "=1"])
def test_an_unparseable_mix_is_refused_not_guessed(bad):
    with pytest.raises(ValueError):
        parse_mix(bad)


# ── What each kind actually sends ────────────────────────────────────────────


def test_the_violation_payload_breaks_the_contract_in_exactly_one_way():
    """Only glucose is 0, so the violation counter always has the same `check` label."""
    assert ILLEGAL_PATIENT["glucose"] == 0.0
    other_fields = {k: v for k, v in ILLEGAL_PATIENT.items() if k != "glucose"}
    assert all(value > 0 for value in other_fields.values())


def test_every_not_found_request_has_a_different_path():
    """Different paths, so the cardinality test has something to collapse."""
    paths = {_request_for("notfound", index)[1] for index in range(20)}
    assert len(paths) == 20


def test_an_unknown_kind_names_the_ones_that_exist():
    with pytest.raises(ValueError, match="valid, violation, v1, notfound, health"):
        _request_for("nonsense", 0)
