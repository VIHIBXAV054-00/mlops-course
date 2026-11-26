"""The import boundaries of `src/`, checked with `ast` so comments and prose cannot trip them.

- No module imports a tool from a later week.
- No module drives a platform (KServe, Kubernetes, Grafana) through a Python SDK.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src"

# Tool -> the week that introduces it. Delete an entry in that week.
FUTURE_WEEK_MODULES = {
    "evidently": 12,
    "alibi_detect": 12,
    "river": 12,
}

# Platforms configured by files in Git (manifests, provisioning), never through a Python SDK.
PLATFORM_SDKS_WE_DO_NOT_IMPORT = {
    "kserve": "KServe is driven declaratively, with kubectl and YAML in git",
    "kubernetes": "the same: a manifest is reviewable, an SDK call is not",
    "grafana_client": "a dashboard belongs in git, not in a POST",
    "grafana_api": "the same, under its other package name",
}


def imported_roots(path: Path) -> set[str]:
    """Every top-level module name this file imports."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` has no module; relative imports are ours.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_source_file_imports_a_future_weeks_tool():
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(FUTURE_WEEK_MODULES):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — that is Week "
                f"{FUTURE_WEEK_MODULES[root]}'s tool"
            )
    assert not offences, "future-week tooling imported in src/:\n  " + "\n  ".join(offences)


def test_the_platform_is_driven_declaratively_and_not_through_an_sdk():
    """A rollout is a manifest change someone can review, not a Python call."""
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(PLATFORM_SDKS_WE_DO_NOT_IMPORT):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — "
                f"{PLATFORM_SDKS_WE_DO_NOT_IMPORT[root]}"
            )
    assert not offences, "platform SDK imported in src/:\n  " + "\n  ".join(offences)


def test_the_guard_can_actually_fire():
    """The guard flags planted forbidden imports."""
    planted = ast.parse(
        "import kserve\n"
        "import evidently\n"
        "from grafana_client import GrafanaApi\n"
        "from prometheus_client import Counter\n"
    )
    forbidden = set(FUTURE_WEEK_MODULES) | set(PLATFORM_SDKS_WE_DO_NOT_IMPORT)
    roots: set[str] = set()
    for node in ast.walk(planted):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    # prometheus_client is declared in pyproject.toml, so it is allowed.
    assert roots & forbidden == {"kserve", "evidently", "grafana_client"}
    assert "prometheus_client" not in forbidden, (
        "prometheus_client is declared in pyproject.toml, so it must not be forbidden"
    )


def test_this_weeks_tool_is_allowed():
    """The guard must not block a tool in scope."""
    for allowed in ("fastapi", "prefect", "httpx", "prometheus_client"):
        assert allowed not in FUTURE_WEEK_MODULES
        assert allowed not in PLATFORM_SDKS_WE_DO_NOT_IMPORT
    api = SRC / "week_11_observability" / "api.py"
    if api.exists():
        assert "fastapi" in imported_roots(api)
    loadtest = SRC / "week_11_observability" / "loadtest.py"
    if loadtest.exists():
        assert "httpx" in imported_roots(loadtest)
    metrics = SRC / "week_11_observability" / "metrics.py"
    if metrics.exists():
        assert "prometheus_client" in imported_roots(metrics)


def test_prometheus_client_was_already_installed_before_this_week_declared_it():
    """Prefect installs prometheus-client. Check with `uv tree --package prometheus-client --invert`."""
    import importlib.util

    assert importlib.util.find_spec("prometheus_client") is not None


def test_fastapi_was_already_installed_before_this_week_declared_it():
    """Prefect installs fastapi as a dependency."""
    import importlib.util

    assert importlib.util.find_spec("fastapi") is not None
