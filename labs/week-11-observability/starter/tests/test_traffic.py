"""The traffic generator's composition, tested without sending anything.

`plan()` is separated from `generate()` for exactly this reason: the decision
about WHAT to send is a pure function of `(count, mix, seed)`, so its
proportions can be asserted exactly with no server, no socket and no clock. It
is the same split `loadtest.percentile` uses — arithmetic a test can reach is
arithmetic you can trust.

Why this matters beyond tidiness: the observability half of this week depends on
knowing the composition of the traffic. When the error-rate panel reads 5% you
want to be able to say "yes, because I asked for 5%". A generator whose mix you
cannot verify turns every dashboard reading into a hope.
"""

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
    """900 valid, 100 violations, give or take the randomness we asked for."""
    kinds = Counter(plan(1000, {"valid": 0.9, "violation": 0.1}, seed=7))
    assert set(kinds) == {"valid", "violation"}
    # Binomial standard error at n=1000, p=0.1 is ~0.95 percentage points, so a
    # +/-4 point band is roughly four standard errors — wide enough never to
    # flake, narrow enough to catch a genuinely wrong mix. Week 10 made this
    # argument about a traffic split; it is the same argument.
    assert 0.06 < kinds["violation"] / 1000 < 0.14


def test_the_same_seed_gives_the_same_plan():
    """A demonstration you cannot repeat is an anecdote."""
    assert plan(200, {"valid": 3, "violation": 1}, seed=1) == plan(
        200, {"valid": 3, "violation": 1}, seed=1
    )
    assert plan(200, {"valid": 3, "violation": 1}, seed=1) != plan(
        200, {"valid": 3, "violation": 1}, seed=2
    )


def test_weights_do_not_have_to_sum_to_one():
    """`--mix valid=9,violation=1` should mean 90/10, not raise about fractions."""
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
    """`glucose: 0` is the sentinel Week 5 outlawed — missing, in disguise.

    One rule broken, deliberately, so the `check` label on
    `model_contract_violations_total` has a single predictable value and the
    dashboard panel is legible.
    """
    assert ILLEGAL_PATIENT["glucose"] == 0.0
    other_fields = {k: v for k, v in ILLEGAL_PATIENT.items() if k != "glucose"}
    assert all(value > 0 for value in other_fields.values())


def test_every_not_found_request_has_a_different_path():
    """This is the ammunition for the cardinality experiment.

    With `route_label` returning the route template they all collapse to one
    series; with the raw path as the label they are one series each — chosen by
    whoever is sending them.
    """
    paths = {_request_for("notfound", index)[1] for index in range(20)}
    assert len(paths) == 20


def test_an_unknown_kind_names_the_ones_that_exist():
    with pytest.raises(ValueError, match="valid, violation, v1, notfound, health"):
        _request_for("nonsense", 0)
