"""Checks the Grafana dashboard as JSON data, with no Grafana running.

A renamed metric does not break a panel: the panel goes empty. These tests catch that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from prometheus_client import CollectorRegistry

from week_12_drift_monitoring.drift_metrics import DriftCollector
from week_12_drift_monitoring.metrics import build_metrics, render
from week_12_drift_monitoring.slo import load_slo

pytestmark = pytest.mark.unit

LAB = Path(__file__).resolve().parents[1]
GRAFANA = LAB / "grafana"
DASHBOARD_DIR = GRAFANA / "dashboards"
DATASOURCE_FILE = GRAFANA / "provisioning" / "datasources" / "prometheus.yml"
PROVIDER_FILE = GRAFANA / "provisioning" / "dashboards" / "provider.yml"


def dashboards() -> list[Path]:
    return sorted(DASHBOARD_DIR.glob("*.json"))


def load_dashboard(path: Path) -> dict:
    return json.loads(path.read_text())


def panels(dashboard: dict) -> list[dict]:
    """Flattened, because a `row` panel nests its children."""
    found = []
    for panel in dashboard.get("panels", []):
        found.append(panel)
        found.extend(panel.get("panels", []))
    return [panel for panel in found if panel.get("type") != "row"]


def expressions(dashboard: dict) -> list[tuple[str, str]]:
    """(panel title, PromQL) for every target on every panel."""
    return [
        (panel.get("title", "<untitled>"), target["expr"])
        for panel in panels(dashboard)
        for target in panel.get("targets", [])
        if target.get("expr")
    ]


def exported_metric_names() -> set[str]:
    """Every metric name the application exports, read from a live registry."""
    registry = CollectorRegistry()
    build_metrics(registry)
    # The drift metrics come from a collector that reads a drift report.
    registry.register(DriftCollector(LAB / "tests/fixtures/drift-report.json"))
    names: set[str] = set()
    for line in render(registry).splitlines():
        if line.startswith("# TYPE "):
            _, _, name, kind = line.split(maxsplit=3)
            names.add(name)
            if kind == "counter":
                names.add(f"{name}_total")
            elif kind == "histogram":
                names |= {f"{name}_bucket", f"{name}_sum", f"{name}_count"}
    names.add("up")  # Synthesised by Prometheus, not by us.
    return names


PROMQL_KEYWORDS = {
    "rate", "irate", "increase", "sum", "avg", "min", "max", "count", "by", "without",
    "and", "or", "unless", "on", "ignoring", "group_left", "group_right", "offset",
    "histogram_quantile", "clamp_min", "clamp_max", "absent", "vector", "scalar",
    "le", "job", "route", "status", "instance", "check", "outcome", "service",
    "time", "abs", "feature", "method", "verdict", "signal",
}


def metric_names_in(expr: str) -> set[str]:
    without_labels = re.sub(r"\{[^}]*\}", " ", expr)
    without_durations = re.sub(r"\[[^\]]*\]", " ", without_labels)
    candidates = set(re.findall(r"\b[a-zA-Z_:][a-zA-Z0-9_:]*\b", without_durations))
    return {name for name in candidates if name not in PROMQL_KEYWORDS}


# ── Panels query exported metrics ────────────────────────────────────────────


def test_every_panel_queries_a_metric_we_actually_export():
    """A renamed metric fails here instead of leaving a panel empty."""
    exported = exported_metric_names()
    problems = []
    for path in dashboards():
        for title, expr in expressions(load_dashboard(path)):
            unknown = metric_names_in(expr) - exported
            if unknown:
                problems.append(f"{path.name} / '{title}': {sorted(unknown)}")
    assert not problems, (
        "dashboard panels query metrics the application does not export:\n  "
        + "\n  ".join(problems)
        + f"\nexported: {sorted(exported)}"
    )


def test_every_panel_uses_the_provisioned_datasource_uid():
    """A datasource uid that does not match the provisioned one leaves every panel empty."""
    declared = yaml.safe_load(DATASOURCE_FILE.read_text())["datasources"][0]["uid"]
    for path in dashboards():
        dashboard = load_dashboard(path)
        for panel in panels(dashboard):
            for source in [panel.get("datasource"), *[t.get("datasource") for t in panel.get("targets", [])]]:
                if source is None:
                    continue
                assert source.get("uid") == declared, (
                    f"{path.name} / '{panel.get('title')}' points at datasource uid "
                    f"{source.get('uid')!r}, but provisioning declares {declared!r}"
                )


def test_the_provider_points_at_the_directory_the_dashboards_are_mounted_in():
    provider = yaml.safe_load(PROVIDER_FILE.read_text())["providers"][0]
    assert provider["options"]["path"] == "/etc/grafana/dashboards"
    assert provider["allowUiUpdates"] is False, (
        "with UI updates allowed, an edit is saved and then overwritten on the "
        "next rescan — a change that appears to work and then vanishes, which is "
        "the worst possible way to discover where the source of truth is"
    )


# ── What the dashboard has to cover ──────────────────────────────────────────


def test_the_syllabus_panels_exist():
    """Request rate, error rate, latency and predictions by outcome each have a panel."""
    titles = " ".join(
        panel.get("title", "").lower()
        for path in dashboards()
        for panel in panels(load_dashboard(path))
    )
    for expected in ("request rate", "error rate", "latency", "predictions by outcome"):
        assert expected in titles, f"no panel about {expected}"


def test_latency_percentiles_are_computed_from_summed_bucket_rates():
    """`histogram_quantile(q, sum by (le) (rate(..._bucket[...])))`: percentiles cannot be averaged."""
    found = False
    for path in dashboards():
        for title, expr in expressions(load_dashboard(path)):
            if "histogram_quantile" not in expr:
                continue
            found = True
            collapsed = " ".join(expr.split())
            assert re.search(r"sum\s*by\s*\(le\)\s*\(\s*rate\(", collapsed), (
                f"{path.name} / '{title}': histogram_quantile must be applied to "
                f"`sum by (le) (rate(..._bucket[...]))`. Got: {collapsed}"
            )
            assert "_bucket" in expr
    assert found, "no panel computes a latency percentile"


def test_counters_are_never_graphed_raw():
    """A raw counter depends on when the process started, so graph it through rate()."""
    for path in dashboards():
        for title, expr in expressions(load_dashboard(path)):
            for name in metric_names_in(expr):
                if not name.endswith("_total"):
                    continue
                assert re.search(rf"(rate|irate|increase)\(\s*{re.escape(name)}", expr), (
                    f"{path.name} / '{title}' graphs the counter {name} without "
                    "rate()/increase()"
                )


def test_the_error_budget_panel_uses_the_budget_from_slo_yaml():
    """The 0.01 in the budget panel is `1 - target` from slo.yaml."""
    budget = load_slo().objective("availability").error_budget
    budget_panels = [
        (title, expr)
        for path in dashboards()
        for title, expr in expressions(load_dashboard(path))
        if "budget" in title.lower()
    ]
    assert budget_panels, "no error-budget panel"
    for title, expr in budget_panels:
        assert f"{budget}" in expr, (
            f"'{title}' does not use the {budget} error budget slo.yaml declares"
        )


def test_the_latency_threshold_line_matches_the_slo():
    """The red line on the latency panel is the threshold from slo.yaml."""
    threshold = load_slo().objective("latency").threshold_seconds
    steps = [
        step
        for path in dashboards()
        for panel in panels(load_dashboard(path))
        if "latency" in panel.get("title", "").lower()
        for step in panel.get("fieldConfig", {}).get("defaults", {}).get("thresholds", {}).get("steps", [])
    ]
    values = {step.get("value") for step in steps}
    assert threshold in values, (
        f"the latency panel's threshold line is at {values}, but slo.yaml promises "
        f"{threshold}s"
    )


# ── Hygiene ──────────────────────────────────────────────────────────────────


def test_dashboards_are_valid_json_with_stable_uids():
    """A dashboard without a uid gets a new one on every import, so links rot."""
    assert dashboards(), "no dashboard JSON in grafana/dashboards/"
    for path in dashboards():
        dashboard = load_dashboard(path)
        assert dashboard.get("uid"), f"{path.name} has no uid"
        assert dashboard.get("title")
        assert panels(dashboard), f"{path.name} has no panels"


def test_every_panel_explains_itself():
    """JSON has no comments, so each panel explains itself in `description`."""
    for path in dashboards():
        for panel in panels(load_dashboard(path)):
            description = panel.get("description", "")
            assert len(description) > 60, (
                f"{path.name} / '{panel.get('title')}' has no useful description"
            )
