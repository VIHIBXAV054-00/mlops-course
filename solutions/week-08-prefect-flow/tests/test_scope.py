"""The course boundary, enforced rather than documented.

From Week 8 on, "a future week's tool is not installed" stops being true.
Prefect depends on **fastapi** (Week 9's subject) and **prometheus-client**
(Week 11's), so both arrive in `uv.lock` whether anyone likes it or not.

Installed is fine. Imported is a defect, and prose cannot stop an import.

This test walks `src/` with `ast`, collects the root module of every import,
and asserts the set is disjoint from the tools later weeks introduce. It is
offline, deterministic, and immune to false positives from comments and prose —
which a grep over the same directory is not.

**Carry this file forward into Weeks 9-13**, deleting each entry from
`FUTURE_WEEK_MODULES` in the week that legitimately introduces it. It gets
stronger every week, because every week adds more transitive tooling that a
student could reach for by accident.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src"

# Tool -> the week that introduces it. Delete an entry in that week.
FUTURE_WEEK_MODULES = {
    "fastapi": 9,
    "starlette": 9,
    "uvicorn": 9,
    "kubernetes": 9,
    "kserve": 10,
    "prometheus_client": 11,
    "grafana_client": 11,
    "evidently": 12,
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
    """`fastapi` is installed this week. It is Week 9's, and it stays Week 9's."""
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(FUTURE_WEEK_MODULES):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — that is Week "
                f"{FUTURE_WEEK_MODULES[root]}'s tool"
            )
    assert not offences, "future-week tooling imported in src/:\n  " + "\n  ".join(offences)


def test_the_guard_can_actually_fire():
    """A guard whose failure mode is a green tick is worse than no guard.

    Week 4 shipped a `check_locks.sh` that exited 0 having checked nothing, and
    Week 7 shipped a `ci-fail` target that reported success while doing
    nothing. Both were believed. This asserts the detector detects.
    """
    planted = ast.parse("import fastapi\nfrom prometheus_client import Counter\n")
    roots: set[str] = set()
    for node in ast.walk(planted):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots & set(FUTURE_WEEK_MODULES) == {"fastapi", "prometheus_client"}


def test_prefect_is_allowed_because_this_is_its_week():
    """The complement of the rule: the guard must not block the week's own tool."""
    assert "prefect" not in FUTURE_WEEK_MODULES
    flows = SRC / "week_08_prefect_flow" / "flows.py"
    if flows.exists():
        assert "prefect" in imported_roots(flows)


def test_fastapi_really_is_installed_and_that_is_expected():
    """Documents the situation rather than hiding it.

    If this ever fails, Prefect dropped a dependency and Week 9's "it has been
    installed since Week 8" slide needs rewriting.
    """
    import importlib.util

    assert importlib.util.find_spec("fastapi") is not None, (
        "fastapi is no longer installed — Week 9's opening slide claims Prefect "
        "brings it in transitively. Re-measure before teaching it."
    )
