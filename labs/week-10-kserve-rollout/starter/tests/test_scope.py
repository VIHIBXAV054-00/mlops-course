"""The course boundary, enforced rather than documented.

From Week 8 on, "a future week's tool is not installed" stops being true.
Prefect depends on **fastapi** (Week 9's subject) and **prometheus-client**
(Week 11's), so both arrive in `uv.lock` whether anyone likes it or not.

Installed is fine. Imported is a defect, and prose cannot stop an import.

This test walks `src/` with `ast`, collects the root module of every import,
and asserts the set is disjoint from the tools later weeks introduce. It is
offline, deterministic, and immune to false positives from comments and prose —
which a grep over the same directory is not.

**Carry this file forward into Weeks 10-13**, deleting each entry from
`FUTURE_WEEK_MODULES` in the week that legitimately introduces it. It gets
stronger every week, because every week adds more transitive tooling that a
student could reach for by accident.

Week 10 is the first week that does NOT delete an entry for its own tool, and
the reason is a teaching point rather than an oversight — see
`PLATFORM_SDKS_WE_DO_NOT_IMPORT` below.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[1] / "src"

# Tool -> the week that introduces it. Delete an entry in that week.
# Week 9 introduced FastAPI, so fastapi/starlette/uvicorn GRADUATED out of this
# set. That is the intended lifecycle: each week deletes the entries it
# legitimately introduces, and the guard keeps protecting everything else.
FUTURE_WEEK_MODULES = {
    "prometheus_client": 11,
    "grafana_client": 11,
    "evidently": 12,
}

# WEEK 10 DOES SOMETHING DIFFERENT, and it is worth a paragraph.
#
# Every previous week deleted the entry for the tool it introduced. Week 10
# introduces KServe — and `kserve` and `kubernetes` stay forbidden, permanently,
# because **not every tool a week introduces is a package you import**.
#
# KServe is a CONTROL PLANE. It is driven by applying YAML: an InferenceService
# is a Kubernetes object, and `kubectl` is the client. Both projects also publish
# Python SDKs that can create those objects imperatively, and reaching for one
# here would give this lab two ways to do the same thing — one of them
# reviewable as a manifest in git, the other buried in a script. The manifest is
# the artifact a rollout should be argued about, so the SDK is not a convenience
# this course wants.
#
# So this set is not a waiting room. Nothing graduates out of it later.
PLATFORM_SDKS_WE_DO_NOT_IMPORT = {
    "kserve": "KServe is driven declaratively, with kubectl and YAML in git",
    "kubernetes": "the same: a manifest is reviewable, an SDK call is not",
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
    """Week 10 may import fastapi. It may not import Prometheus or Evidently."""
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(FUTURE_WEEK_MODULES):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — that is Week "
                f"{FUTURE_WEEK_MODULES[root]}'s tool"
            )
    assert not offences, "future-week tooling imported in src/:\n  " + "\n  ".join(offences)


def test_the_platform_is_driven_declaratively_and_not_through_an_sdk():
    """This week's own tool, still forbidden as an import, on purpose.

    A rollout is a change to a manifest in git that someone can review before it
    reaches patients. The moment it becomes a Python call, the reviewable
    artifact disappears — and the thing this week is teaching is precisely that a
    rollout should be a declaration, not a procedure.
    """
    offences = []
    for path in sorted(SRC.rglob("*.py")):
        for root in imported_roots(path) & set(PLATFORM_SDKS_WE_DO_NOT_IMPORT):
            offences.append(
                f"{path.relative_to(SRC)} imports `{root}` — "
                f"{PLATFORM_SDKS_WE_DO_NOT_IMPORT[root]}"
            )
    assert not offences, "platform SDK imported in src/:\n  " + "\n  ".join(offences)


def test_the_guard_can_actually_fire():
    """A guard whose failure mode is a green tick is worse than no guard.

    Week 4 shipped a `check_locks.sh` that exited 0 having checked nothing, and
    Week 7 shipped a `ci-fail` target that reported success while doing
    nothing. Both were believed. This asserts the detector detects.
    """
    planted = ast.parse("import kserve\nfrom prometheus_client import Counter\n")
    forbidden = set(FUTURE_WEEK_MODULES) | set(PLATFORM_SDKS_WE_DO_NOT_IMPORT)
    roots: set[str] = set()
    for node in ast.walk(planted):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots & forbidden == {"kserve", "prometheus_client"}


def test_this_weeks_tool_is_allowed():
    """The complement of the rule: the guard must not block a tool in scope."""
    for allowed in ("fastapi", "prefect", "httpx"):
        assert allowed not in FUTURE_WEEK_MODULES
        assert allowed not in PLATFORM_SDKS_WE_DO_NOT_IMPORT
    api = SRC / "week_10_kserve_rollout" / "api.py"
    if api.exists():
        assert "fastapi" in imported_roots(api)
    loadtest = SRC / "week_10_kserve_rollout" / "loadtest.py"
    if loadtest.exists():
        assert "httpx" in imported_roots(loadtest), (
            "Week 10's load generator uses httpx, which Week 9 declared — no new "
            "dependency was needed to measure a rollout"
        )


def test_fastapi_was_already_installed_before_this_week_declared_it():
    """Documents the situation rather than hiding it.

    If this ever fails, Prefect dropped a dependency and Week 9's "it has been
    installed since Week 8" slide needs rewriting.
    """
    import importlib.util

    assert importlib.util.find_spec("fastapi") is not None, (
        "fastapi is no longer installed — Week 9's opening slide claims Prefect "
        "brings it in transitively. Re-measure before teaching it."
    )
