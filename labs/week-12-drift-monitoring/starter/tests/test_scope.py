"""The import boundaries of `src/`, checked with `ast` so comments and prose cannot trip them.

- No module imports a tool from a later week, a declined drift library or a platform SDK.
- The serving modules cannot reach `evidently`, which the serving image does not install.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src"

# Tool -> the week that introduces it. Empty: no later week adds a Python tool.
FUTURE_WEEK_MODULES: dict[str, int] = {}

# Drift libraries this lab does not use: drift.yaml declares the statistic, threshold and window.
DRIFT_LIBRARIES_WE_DO_NOT_USE = {
    "alibi_detect": "choosing the statistic, threshold and window IS the lesson",
    "river": "online learning is a different course; this one ships models deliberately",
}

# Module -> import roots it must not reach, directly or through first-party imports.
# The serving image (`uv sync --locked --no-dev`) does not install the `drift` group.
SERVING_PATH_MUST_NOT_REACH = {
    "api.py": {"evidently"},
    "inference.py": {"evidently"},
    "metrics.py": {"evidently"},
    "drift_metrics.py": {"evidently"},
    "drift_policy.py": {"evidently"},
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


def first_party_imports(path: Path) -> set[str]:
    """Relative imports from this package, such as `from .drift import x`."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def reachable_roots(start: Path) -> set[str]:
    """Every import root reachable from `start`, following first-party imports."""
    package = start.parent
    seen: set[str] = set()
    queue = [start]
    roots: set[str] = set()
    while queue:
        current = queue.pop()
        if current.name in seen or not current.exists():
            continue
        seen.add(current.name)
        roots |= imported_roots(current)
        for module in first_party_imports(current):
            queue.append(package / f"{module}.py")
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


def test_the_drift_libraries_this_course_declined_stay_declined():
    """drift.yaml declares the statistic, the threshold and the window, not a library."""
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(DRIFT_LIBRARIES_WE_DO_NOT_USE):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — "
                f"{DRIFT_LIBRARIES_WE_DO_NOT_USE[root]}"
            )
    assert not offences, "declined drift library imported in src/:\n  " + "\n  ".join(offences)


def test_the_serving_path_cannot_reach_the_drift_library():
    """The serving image has no `evidently`, so an import would crash the container at startup."""
    package = SRC / "week_12_drift_monitoring"
    offences = []
    for module, forbidden in sorted(SERVING_PATH_MUST_NOT_REACH.items()):
        path = package / module
        if not path.exists():
            continue
        reached = reachable_roots(path) & forbidden
        for root in sorted(reached):
            offences.append(
                f"{module} can reach `{root}` (directly or through a first-party "
                f"import). The serving image does not install it — "
                f"`uv sync --no-dev` skips the `drift` group — so this is an "
                f"ImportError at container startup, not a style preference."
            )
    assert not offences, "the serving path reaches a job-only library:\n  " + "\n  ".join(
        offences
    )


def test_the_directional_guard_can_actually_fire():
    """The walk finds `evidently` where it is imported, directly and through first-party imports."""
    package = SRC / "week_12_drift_monitoring"
    assert "evidently" in reachable_roots(package / "drift.py"), (
        "drift.py should import evidently. If it does not, the guard checks nothing."
    )
    # cli.py imports drift.py inside functions, and the ast walk still sees it.
    assert "evidently" in reachable_roots(package / "cli.py")


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


def test_the_week_module_guard_can_actually_fire():
    """The guard flags planted forbidden imports."""
    planted = ast.parse(
        "import kserve\n"
        "import alibi_detect\n"
        "from grafana_client import GrafanaApi\n"
        "from prometheus_client import Counter\n"
        "import evidently\n"
    )
    forbidden = (
        set(FUTURE_WEEK_MODULES)
        | set(PLATFORM_SDKS_WE_DO_NOT_IMPORT)
        | set(DRIFT_LIBRARIES_WE_DO_NOT_USE)
    )
    roots: set[str] = set()
    for node in ast.walk(planted):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    # prometheus_client and evidently are declared in pyproject.toml, so they are allowed.
    assert roots & forbidden == {"kserve", "grafana_client", "alibi_detect"}
    for graduated in ("prometheus_client", "evidently"):
        assert graduated not in forbidden, (
            f"{graduated} is declared in pyproject.toml, so it must not be in a forbidden set."
        )


def test_this_weeks_tool_is_allowed():
    """The guard must not block a tool in scope."""
    for allowed in ("fastapi", "prefect", "httpx", "prometheus_client", "evidently"):
        assert allowed not in FUTURE_WEEK_MODULES
        assert allowed not in PLATFORM_SDKS_WE_DO_NOT_IMPORT
    api = SRC / "week_12_drift_monitoring" / "api.py"
    if api.exists():
        assert "fastapi" in imported_roots(api)
    loadtest = SRC / "week_12_drift_monitoring" / "loadtest.py"
    if loadtest.exists():
        assert "httpx" in imported_roots(loadtest)
    metrics = SRC / "week_12_drift_monitoring" / "metrics.py"
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


def test_evidently_is_declared_in_a_group_and_not_in_the_runtime_dependencies():
    """The serving-path guard relies on `evidently` staying out of the runtime dependencies."""
    import tomllib

    pyproject = tomllib.loads((SRC.parent / "pyproject.toml").read_text())
    runtime = " ".join(pyproject["project"]["dependencies"])
    assert "evidently" not in runtime, (
        "move evidently back to the `drift` dependency group: the serving image "
        "(`uv sync --locked --no-dev`) must not install it"
    )
    groups = pyproject["dependency-groups"]
    assert "drift" in groups
    assert any("evidently" in spec for spec in groups["drift"])


def test_evidently_is_actually_installed_so_the_drift_tests_run_rather_than_skip():
    """`uv sync --all-groups` installs the `drift` group, so the drift tests call Evidently for real."""
    import importlib.util

    assert importlib.util.find_spec("evidently") is not None, (
        "evidently is not installed. The drift tests need it; run "
        "`uv sync --all-groups` (or `--group drift`)."
    )
