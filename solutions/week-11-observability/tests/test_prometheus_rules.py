"""Checks the Prometheus configuration and alerting rules, with no Prometheus running.

`make alerts-test` checks that the alerts fire. These tests check that the rules
are complete, use exported metrics and agree with slo.yaml.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from prometheus_client import CollectorRegistry

from week_11_observability.metrics import build_metrics, render
from week_11_observability.slo import load_slo

pytestmark = pytest.mark.unit

LAB = Path(__file__).resolve().parents[1]
PROM = LAB / "prometheus"
CONFIG = PROM / "prometheus.yml"
RULES_DIR = PROM / "rules"
TESTS_DIR = PROM / "tests"


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def rule_files() -> list[Path]:
    return sorted(RULES_DIR.glob("*.yml"))


def all_rules() -> list[tuple[Path, dict]]:
    """Every rule in every file, with the file it came from (for error messages)."""
    found = []
    for path in rule_files():
        for group in load(path).get("groups", []):
            for rule in group.get("rules", []):
                found.append((path, rule))
    return found


def alerts() -> list[tuple[Path, dict]]:
    return [(path, rule) for path, rule in all_rules() if "alert" in rule]


def recordings() -> list[tuple[Path, dict]]:
    return [(path, rule) for path, rule in all_rules() if "record" in rule]


def exported_metric_names() -> set[str]:
    """Every metric name the application exports, read from a live registry.

    Counter and histogram suffixes are added, because PromQL queries those names.
    """
    registry = CollectorRegistry()
    build_metrics(registry)
    names: set[str] = set()
    for line in render(registry).splitlines():
        if line.startswith("# TYPE "):
            _, _, name, kind = line.split(maxsplit=3)
            names.add(name)
            if kind == "counter":
                names.add(f"{name}_total")
            elif kind == "histogram":
                names |= {f"{name}_bucket", f"{name}_sum", f"{name}_count"}
    # Added by Prometheus on every scrape. ServiceDown uses it.
    names.add("up")
    return names


# Identifiers in PromQL that are not metric names: functions, operators and labels.
PROMQL_KEYWORDS = {
    "rate", "irate", "increase", "sum", "avg", "min", "max", "count", "by", "without",
    "and", "or", "unless", "on", "ignoring", "group_left", "group_right", "offset",
    "histogram_quantile", "clamp_min", "clamp_max", "absent", "vector", "scalar",
    "le", "job", "route", "status", "instance", "check", "outcome", "service",
}


def metric_names_in(expr: str) -> set[str]:
    """Series names referenced by an expression. A regex, not a parser: enough to catch a rename."""
    # Strip label matchers first, so label values are never read as metrics.
    without_labels = re.sub(r"\{[^}]*\}", " ", expr)
    without_durations = re.sub(r"\[[^\]]*\]", " ", without_labels)
    candidates = set(re.findall(r"\b[a-zA-Z_:][a-zA-Z0-9_:]*\b", without_durations))
    return {name for name in candidates if name not in PROMQL_KEYWORDS}


# ── The configuration ────────────────────────────────────────────────────────


def test_prometheus_config_parses_and_scrapes_our_service():
    config = load(CONFIG)
    jobs = {job["job_name"] for job in config["scrape_configs"]}
    assert "diabetes-api" in jobs
    assert "prometheus" in jobs, (
        "the getting-started guide scrapes Prometheus itself, and it earns its "
        "place: there is always a live target to practise PromQL against"
    )

    api = next(j for j in config["scrape_configs"] if j["job_name"] == "diabetes-api")
    targets = [t for sc in api["static_configs"] for t in sc["targets"]]
    assert targets == ["api:8000"], (
        "the target must be the COMPOSE DNS NAME. Prometheus pulls, so it has to "
        "reach the service over the Docker network — `localhost` here would be "
        "the Prometheus container itself."
    )


def test_no_alertmanager_is_configured():
    """Prometheus shows pending and firing alerts on its own /alerts page."""
    assert "alerting" not in load(CONFIG)


def test_the_rule_glob_cannot_pick_up_a_test_file():
    """Prometheus does not start if `rules/*.yml` matches a promtool test file."""
    assert TESTS_DIR.exists()
    assert not list(RULES_DIR.glob("*_test.yml"))
    assert list(TESTS_DIR.glob("*_test.yml")), "the promtool test file is missing"


# ── Every alert is a complete alert ──────────────────────────────────────────


@pytest.mark.parametrize("path,rule", alerts(), ids=lambda v: getattr(v, "name", None))
def test_every_alert_is_actionable(path, rule):
    """Every alert has a `for:`, a severity, a summary and a useful description."""
    name = rule["alert"]
    where = f"{path.name}:{name}"

    assert "for" in rule, (
        f"{where} has no `for:`. It will fire on one bad scrape — a deploy, a "
        "restart, a two-second hiccup — which is how an alert becomes furniture."
    )
    labels = rule.get("labels") or {}
    assert labels.get("severity") in {"page", "ticket"}, (
        f"{where}: severity must say whether this is worth waking somebody for."
    )
    annotations = rule.get("annotations") or {}
    assert annotations.get("summary"), f"{where} has no summary"
    assert len(annotations.get("description", "")) > 80, (
        f"{where}'s description is too short to be useful at 3 a.m. Say what is "
        "happening, what it costs, and what to look at."
    )


@pytest.mark.parametrize("path,rule", all_rules(), ids=lambda v: getattr(v, "name", None))
def test_every_expression_references_a_metric_we_actually_export(path, rule):
    """A rule that queries a renamed metric selects nothing and never fires.

    Recording-rule outputs (the `slo:` prefix) are allowed as inputs.
    """
    exported = exported_metric_names() | {r["record"] for _, r in recordings()}
    referenced = metric_names_in(rule.get("expr", ""))
    unknown = {name for name in referenced if name not in exported}
    assert not unknown, (
        f"{path.name}:{rule.get('alert') or rule.get('record')} references "
        f"{sorted(unknown)}, which the application does not export. Exported: "
        f"{sorted(exported)}"
    )


# ── The seam with slo.yaml ───────────────────────────────────────────────────


def test_every_threshold_is_derived_from_slo_yaml():
    """Each alert threshold equals `burn_rate x error_budget` from slo.yaml."""
    doc = load_slo()
    by_rate = {alert.name: alert for alert in doc.burn_alerts}

    # alert name -> (objective, burn-rate row)
    expected = {
        "AvailabilityBudgetBurnFast": ("availability", "fast"),
        "AvailabilityBudgetBurnMedium": ("availability", "medium"),
        "AvailabilityBudgetBurnSlow": ("availability", "slow"),
        "LatencyBudgetBurnFast": ("latency", "fast"),
    }

    seen = set()
    for path, rule in alerts():
        name = rule["alert"]
        if name not in expected:
            continue
        seen.add(name)
        objective_name, rate_name = expected[name]
        threshold = by_rate[rate_name].threshold(doc.objective(objective_name))

        literals = {float(match) for match in re.findall(r">\s*([0-9.]+)", rule["expr"])}
        assert literals, f"{path.name}:{name} has no numeric threshold in its expr"
        assert all(
            abs(literal - threshold) < 1e-9 for literal in literals
        ), (
            f"{name} compares against {sorted(literals)}, but slo.yaml's "
            f"{objective_name} target ({doc.objective(objective_name).target}) at a "
            f"{by_rate[rate_name].burn_rate}x burn rate is {threshold}."
        )

        assert rule["labels"]["severity"] == by_rate[rate_name].severity
        assert rule["labels"]["objective"] == objective_name

    assert seen == set(expected), f"missing burn-rate alerts: {set(expected) - seen}"


def test_both_windows_appear_in_every_burn_rate_alert():
    """Each burn-rate alert checks both the long and the short window from slo.yaml."""
    doc = load_slo()
    by_rate = {alert.name: alert for alert in doc.burn_alerts}
    mapping = {
        "AvailabilityBudgetBurnFast": "fast",
        "AvailabilityBudgetBurnMedium": "medium",
        "AvailabilityBudgetBurnSlow": "slow",
        "LatencyBudgetBurnFast": "fast",
    }
    for path, rule in alerts():
        rate_name = mapping.get(rule["alert"])
        if not rate_name:
            continue
        alert = by_rate[rate_name]
        expr = rule["expr"]
        assert "\nand\n" in expr or " and " in expr, f"{rule['alert']} is single-window"
        for window in (alert.long_window, alert.short_window):
            assert f"_{window}" in expr, (
                f"{rule['alert']} does not use the {window} window slo.yaml declares"
            )


def test_the_latency_rule_selects_the_declared_bucket_boundary():
    """`le="0.25"` is the slo.yaml threshold. Label values match as strings."""
    threshold = load_slo().objective("latency").threshold_seconds
    text = (RULES_DIR / "slo.yml").read_text()
    assert f'le="{threshold}"' in text, (
        f'the latency SLI must select le="{threshold}" to match slo.yaml'
    )


# ── Every alert has a unit test ──────────────────────────────────────────────


def test_every_alert_is_covered_by_a_promtool_test():
    """Every alert is named in the promtool suite. `make alerts-test` checks that it fires."""
    covered = set()
    for path in TESTS_DIR.glob("*_test.yml"):
        document = load(path)
        for test in document.get("tests", []):
            for case in test.get("alert_rule_test", []):
                covered.add(case["alertname"])

    declared = {rule["alert"] for _, rule in alerts()}
    assert declared <= covered, (
        f"these alerts have no promtool test: {sorted(declared - covered)}. "
        "An alert nobody has ever seen fire is a hypothesis."
    )
    assert covered <= declared, (
        f"the test suite asserts on alerts that do not exist: {sorted(covered - declared)}"
    )


def test_the_promtool_suite_points_at_the_real_rule_files():
    """`rule_files` resolve relative to the test file. A wrong path loads no rules and still passes."""
    for path in TESTS_DIR.glob("*_test.yml"):
        referenced = load(path).get("rule_files", [])
        assert referenced, f"{path.name} loads no rule files, so it tests nothing"
        for relative in referenced:
            resolved = (path.parent / relative).resolve()
            assert resolved.exists(), f"{path.name} references {relative}, which does not exist"
            assert resolved.parent == RULES_DIR.resolve()


def test_the_rule_set_is_deliberately_small():
    """At most six alerts and at most four pages."""
    declared = {rule["alert"] for _, rule in alerts()}
    assert len(declared) <= 6, (
        f"{len(declared)} alerts: {sorted(declared)}. Every one of them is an "
        "interrupt aimed at a person. Which would you delete?"
    )
    pages = {
        rule["alert"] for _, rule in alerts() if (rule.get("labels") or {}).get("severity") == "page"
    }
    assert pages, "an alerting configuration where nothing pages is a dashboard"
    assert len(pages) <= 4, "more than four things worth waking somebody for is a smell"
