"""Tests for the SLO arithmetic, against numbers worked out by hand and the published table."""

from __future__ import annotations

import math

import pytest
import yaml

from week_12_drift_monitoring.slo import (
    SECONDS_PER_DAY,
    Objective,
    budget_remaining,
    burn_rate,
    format_duration,
    load_slo,
    parse_duration,
    time_to_exhaustion,
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def doc():
    return load_slo()


# ── The document ─────────────────────────────────────────────────────────────


def test_slo_yaml_declares_both_objectives(doc):
    assert set(doc.objectives) == {"availability", "latency"}
    assert doc.window_days == 30
    assert doc.service == "diabetes-api"


def test_no_objective_promises_perfection(doc):
    """A 100% target forbids every deploy, so no shipped objective has one."""
    for objective in doc.objectives.values():
        assert 0.0 < objective.target < 1.0


def test_every_burn_alert_has_a_shorter_short_window(doc):
    """The short window checks that the problem is still happening."""
    for alert in doc.burn_alerts:
        assert parse_duration(alert.short_window) < parse_duration(alert.long_window)


# ── The budget, computed by hand ─────────────────────────────────────────────


def test_a_99_percent_target_is_seven_hours_twelve_minutes_a_month():
    """0.01 * 30 days = 0.3 days = 7.2 hours = 7h 12m."""
    objective = Objective("availability", "", target=0.99, window_days=30)
    assert objective.error_budget == pytest.approx(0.01)
    assert objective.budget_seconds == pytest.approx(0.01 * 30 * SECONDS_PER_DAY)
    assert objective.budget_seconds == pytest.approx(25_920.0)
    assert format_duration(objective.budget_seconds) == "7h 12m"


def test_each_extra_nine_costs_a_factor_of_ten():
    minutes = []
    for target in (0.99, 0.999, 0.9999):
        objective = Objective("a", "", target=target, window_days=30)
        minutes.append(objective.budget_seconds / 60)
    assert minutes[0] / minutes[1] == pytest.approx(10, rel=1e-6)
    assert minutes[1] / minutes[2] == pytest.approx(10, rel=1e-6)
    assert minutes[2] == pytest.approx(4.32, abs=0.01), "four and a bit minutes a MONTH"


def test_burn_rate_is_a_multiple_of_on_plan():
    """1.0 = the budget runs out exactly at the end of the window."""
    objective = Objective("availability", "", target=0.99, window_days=30)
    assert burn_rate(1, 100, objective) == pytest.approx(1.0)
    assert burn_rate(144, 1000, objective) == pytest.approx(14.4)
    assert burn_rate(0, 1000, objective) == 0.0


def test_no_traffic_burns_nothing_and_that_is_a_real_hole():
    """Zero events burn nothing, so a dead service looks healthy here. `ServiceDown` covers it."""
    objective = Objective("availability", "", target=0.99, window_days=30)
    assert burn_rate(0, 0, objective) == 0.0
    assert budget_remaining(0, 0, objective) == 1.0


def test_budget_remaining_is_clamped_not_negative():
    objective = Objective("availability", "", target=0.99, window_days=30)
    # Exactly on budget: 1 bad in 100 allowed at 99%.
    assert budget_remaining(1, 100, objective) == pytest.approx(0.0)
    assert budget_remaining(0.5, 100, objective) == pytest.approx(0.5)
    # well over budget: clamped to 0, not negative
    assert budget_remaining(5, 100, objective) == 0.0


def test_time_to_exhaustion():
    objective = Objective("availability", "", target=0.99, window_days=30)
    # A full budget burning at exactly 1x lasts exactly one window.
    assert time_to_exhaustion(1.0, 1.0, objective) == pytest.approx(30 * SECONDS_PER_DAY)
    # Half a budget at 14.4x: 15 days / 14.4 ~= 25 hours.
    assert time_to_exhaustion(0.5, 14.4, objective) == pytest.approx(
        0.5 * 30 * SECONDS_PER_DAY / 14.4
    )
    assert time_to_exhaustion(1.0, 0.0, objective) == math.inf


# ── The published table ──────────────────────────────────────────────────────


def test_the_burn_rate_table_matches_the_sre_workbook(doc):
    """Google SRE Workbook, "Alerting on SLOs", Table 5-8, checked against the source."""
    expected = {
        "fast": (14.4, "1h", "5m", 0.02, "page"),
        "medium": (6.0, "6h", "30m", 0.05, "page"),
        "slow": (1.0, "3d", "6h", 0.10, "ticket"),
    }
    assert {alert.name for alert in doc.burn_alerts} == set(expected)
    for alert in doc.burn_alerts:
        rate, long_window, short_window, consumed, severity = expected[alert.name]
        assert alert.burn_rate == pytest.approx(rate)
        assert alert.long_window == long_window
        assert alert.short_window == short_window
        assert alert.budget_consumed == pytest.approx(consumed)
        assert alert.severity == severity


def test_the_declared_budget_consumption_follows_from_the_arithmetic(doc):
    """`burn_rate * long_window / window` gives the published column: 14.4x for 1h is 2%."""
    for alert in doc.burn_alerts:
        computed = alert.consumed_by_end_of_long_window(doc.window_days)
        assert computed == pytest.approx(alert.budget_consumed, rel=0.02), (
            f"{alert.name}: {alert.burn_rate} x {alert.long_window} over "
            f"{doc.window_days}d is {computed:.4f}, but the document claims "
            f"{alert.budget_consumed}"
        )


def test_alert_thresholds_scale_with_the_budget(doc):
    """Latency (95%) has five times the budget of availability (99%), so 5x the threshold."""
    availability = doc.objective("availability")
    latency = doc.objective("latency")
    fast = next(alert for alert in doc.burn_alerts if alert.name == "fast")

    assert fast.threshold(availability) == pytest.approx(0.144)
    assert fast.threshold(latency) == pytest.approx(0.72)
    assert fast.threshold(latency) / fast.threshold(availability) == pytest.approx(5.0)


def test_fast_burn_exhausts_a_month_in_about_two_days(doc):
    availability = doc.objective("availability")
    fast = next(alert for alert in doc.burn_alerts if alert.name == "fast")
    hours = fast.time_to_exhaustion(availability) / 3600
    assert 49 < hours < 51, f"expected ~50 hours, got {hours:.1f}"


# ── Parsing ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("30s", 30), ("5m", 300), ("1h", 3600), ("6h", 21_600), ("3d", 259_200)],
)
def test_durations_parse(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("bad", ["5min", "h", "", "-1h", "0m", "1w", "five minutes"])
def test_a_duration_we_do_not_understand_is_refused_not_guessed(bad):
    """`"5min"` must not silently become 5 seconds."""
    with pytest.raises(ValueError):
        parse_duration(bad)


# ── The validator ────────────────────────────────────────────────────────────


def write_slo(tmp_path, **overrides):
    """A minimal valid slo.yaml, with one field replaced."""
    document = {
        "service": "diabetes-api",
        "window_days": 30,
        "objectives": {"availability": {"description": "d", "target": 0.99}},
        "burn_rate_alerts": [
            {
                "name": "fast",
                "burn_rate": 14.4,
                "long_window": "1h",
                "short_window": "5m",
                "budget_consumed": 0.02,
                "severity": "page",
            }
        ],
    }
    document.update(overrides)
    path = tmp_path / "slo.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def test_a_short_window_that_is_not_shorter_is_refused(tmp_path):
    path = write_slo(
        tmp_path,
        burn_rate_alerts=[
            {
                "name": "backwards",
                "burn_rate": 14.4,
                "long_window": "5m",
                "short_window": "1h",
                "budget_consumed": 0.02,
                "severity": "page",
            }
        ],
    )
    with pytest.raises(ValueError, match="shorter"):
        load_slo(path)


def test_a_perfect_target_is_refused(tmp_path):
    path = write_slo(tmp_path, objectives={"availability": {"target": 1.0}})
    with pytest.raises(ValueError, match="incoherent"):
        load_slo(path)


def test_a_severity_that_is_neither_page_nor_ticket_is_refused(tmp_path):
    path = write_slo(
        tmp_path,
        burn_rate_alerts=[
            {
                "name": "fast",
                "burn_rate": 14.4,
                "long_window": "1h",
                "short_window": "5m",
                "budget_consumed": 0.02,
                "severity": "urgent-ish",
            }
        ],
    )
    with pytest.raises(ValueError, match="page"):
        load_slo(path)


def test_an_slo_nobody_watches_is_refused(tmp_path):
    """A document with objectives and no alerts is prose."""
    path = write_slo(tmp_path, burn_rate_alerts=[])
    with pytest.raises(ValueError, match="prose"):
        load_slo(path)
