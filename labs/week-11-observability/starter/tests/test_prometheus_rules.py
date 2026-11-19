"""The alerting configuration, checked without a Prometheus server.

TWO KINDS OF CHECK, AND THE README SAYS WHICH IS WHICH — because claiming more
than you verify is exactly the failure this course keeps naming:

  * **`make alerts-test`** runs Prometheus's own `promtool test rules` against
    synthetic time series and proves the alerts FIRE WHEN THEY SHOULD. That is
    the real test, and it needs the Prometheus image.
  * **This file** proves the configuration is well-formed and CONSISTENT WITH
    `slo.yaml`. It needs nothing at all, so it runs in the autograder, on a
    laptop with Docker off, and on a fresh clone.

Neither subsumes the other. A rule can be perfectly well-formed and never fire;
a rule can fire correctly against a threshold that no longer matches the promise
the team made.

THE STAR ASSERTION IS `test_every_threshold_is_derived_from_slo_yaml`. The SLO
is written down twice — once as a document humans argue about, once as a number
inside a PromQL expression — because a rule engine cannot read a YAML document
that is not a rule file. Duplication you cannot detect is a bug. Duplication a
test watches is a translation.
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
    """Every metric name this application actually exposes.

    Read from a LIVE REGISTRY rather than a hard-coded list, which is the whole
    point: a hard-coded list is a third copy that would need maintaining, and it
    would keep agreeing with the rules long after the code stopped agreeing with
    both.

    Histogram and counter suffixes are added because that is how the series are
    named on the wire, and it is the wire that PromQL queries.
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
    # Synthesised by Prometheus on every scrape rather than by us. It is the one
    # metric you get without instrumenting anything, and ServiceDown needs it.
    names.add("up")
    return names


# The identifiers that appear in a PromQL expression and are NOT metric names:
# functions, operators and aggregation keywords. Anything else that looks like a
# bare identifier is being read as a series.
PROMQL_KEYWORDS = {
    "rate", "irate", "increase", "sum", "avg", "min", "max", "count", "by", "without",
    "and", "or", "unless", "on", "ignoring", "group_left", "group_right", "offset",
    "histogram_quantile", "clamp_min", "clamp_max", "absent", "vector", "scalar",
    "le", "job", "route", "status", "instance", "check", "outcome", "service",
}


def metric_names_in(expr: str) -> set[str]:
    """Series names referenced by an expression.

    Deliberately crude — a regex, not a parser — and honest about it. It finds
    identifiers that are followed by `{`, `[`, `)` or whitespace and are not
    PromQL keywords, which is enough to catch the failure this guards against: a
    metric renamed in the code and not in the rules.

    A real PromQL parser would be better. It would also be a dependency, and the
    thing being defended here is a rename, which this catches.
    """
    # Strip label matchers first, so label VALUES are never mistaken for metrics.
    without_labels = re.sub(r"\{[^}]*\}", " ", expr)
    without_durations = re.sub(r"\[[^\]]*\]", " ", without_labels)
    candidates = set(re.findall(r"\b[a-zA-Z_:][a-zA-Z0-9_:]*\b", without_durations))
    return {name for name in candidates if name not in PROMQL_KEYWORDS}


# ── The configuration ────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 2 — add the diabetes-api scrape job to prometheus.yml")
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
    """Deliberately absent, and asserted so it stays that way on purpose.

    Routing, grouping, silences and on-call are about what happens to a HUMAN
    after an alert fires, which is Week 13's subject. Prometheus shows
    pending/firing on its own /alerts page, which is enough to watch the
    machinery work.
    """
    assert "alerting" not in load(CONFIG)


def test_the_rule_glob_cannot_pick_up_a_test_file():
    """A layout constraint that would otherwise be found by a crash.

    `rule_files: /etc/prometheus/rules/*.yml` would happily try to load a
    promtool TEST file as a rule file, and Prometheus REFUSES TO START on an
    unparseable rule file. Hence tests/ next to rules/, not inside it.
    """
    assert TESTS_DIR.exists()
    assert not list(RULES_DIR.glob("*_test.yml"))
    assert list(TESTS_DIR.glob("*_test.yml")), "the promtool test file is missing"


# ── Every alert is a complete alert ──────────────────────────────────────────


@pytest.mark.parametrize("path,rule", alerts(), ids=lambda v: getattr(v, "name", None))
def test_every_alert_is_actionable(path, rule):
    """`for`, a severity, and prose a woken human can act on.

    None of this is bureaucracy. An alert without `for:` fires on a single
    scrape gap; an alert without a severity cannot be routed; an alert whose
    only text is its own name tells the person it woke nothing at all — and an
    alert nobody can act on is the mechanism by which every other alert stops
    being read.
    """
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
    """THE DRIFT GUARD.

    Rename a metric in `metrics.py` and every rule that mentions it stops
    matching anything. Prometheus does not complain — an expression that selects
    no series is a perfectly valid expression that evaluates to nothing — so the
    alert simply never fires again. That is a monitoring system that has silently
    stopped monitoring, and nothing about it looks wrong.

    Recording-rule outputs (the `slo:` prefix) are legitimate inputs to later
    rules, so they are added to the allowed set.
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
    """The alert thresholds must equal `burn_rate x error_budget`, recomputed.

    This is why writing the SLO twice is acceptable. The document is the source
    of truth; the rules are a translation of it; and this test is the compiler
    that checks the translation. Loosen a target in slo.yaml without touching
    the rules and the suite goes red, rather than the promise and the alerting
    quietly parting company.
    """
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
    """Long AND short, ANDed. Without the short window an alert that fires on a
    1-hour average stays firing for another hour after the incident ends — which
    is how a team learns that this alert means "something happened recently" and
    stops reading it."""
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
    """`le="0.25"` must be the threshold slo.yaml promises.

    Prometheus matches label values as STRINGS. If the two ever disagree the
    expression selects no series, the ratio is empty, and the alert can never
    fire — broken in the direction nobody investigates.
    """
    threshold = load_slo().objective("latency").threshold_seconds
    text = (RULES_DIR / "slo.yml").read_text()
    assert f'le="{threshold}"' in text, (
        f'the latency SLI must select le="{threshold}" to match slo.yaml'
    )


# ── Every alert has a unit test ──────────────────────────────────────────────


def test_every_alert_is_covered_by_a_promtool_test():
    """An alert that has never fired is not known to work.

    Week 4's `check_locks.sh`, Week 7's `ci-fail` and Week 10's `make smoke` all
    reported success while checking nothing, and all three were believed until
    somebody made them fail. An alerting rule is the purest case: its failure
    mode is silence.

    This asserts every alert is NAMED in the promtool suite. `make alerts-test`
    then asserts it actually fires.
    """
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
    """`rule_files` in a promtool test are resolved relative to the TEST file.

    Getting this wrong is the standard first-time failure, and it produces
    "0 rules loaded, all tests passed" — a green run that checked nothing.
    """
    for path in TESTS_DIR.glob("*_test.yml"):
        referenced = load(path).get("rule_files", [])
        assert referenced, f"{path.name} loads no rule files, so it tests nothing"
        for relative in referenced:
            resolved = (path.parent / relative).resolve()
            assert resolved.exists(), f"{path.name} references {relative}, which does not exist"
            assert resolved.parent == RULES_DIR.resolve()


def test_the_rule_set_is_deliberately_small():
    """Six alerts is not an accident and not an omission.

    The Joint Commission's estimate for hospital alarms is that 85-99% of them
    require no intervention, and the outcome is that people stop hearing them.
    The software version is the same. If this number ever climbs, the question
    to ask is not "is each new alert reasonable?" but "would I be willing to be
    woken by it?"
    """
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
