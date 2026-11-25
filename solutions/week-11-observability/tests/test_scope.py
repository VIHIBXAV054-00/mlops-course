"""The course boundary, enforced rather than documented.

From Week 8 on, "a future week's tool is not installed" stops being true.
Prefect depends on **fastapi** (Week 9's subject) and **prometheus-client**
(Week 11's), so both arrive in `uv.lock` whether anyone likes it or not.

Installed is fine. Imported is a defect, and prose cannot stop an import.

This test walks `src/` with `ast`, collects the root module of every import,
and asserts the set is disjoint from the tools later weeks introduce. It is
offline, deterministic, and immune to false positives from comments and prose —
which a grep over the same directory is not.

**Carry this file forward into Weeks 11-13**, deleting each entry from
`FUTURE_WEEK_MODULES` in the week that legitimately introduces it. It gets
stronger every week, because every week adds more transitive tooling that a
student could reach for by accident.

Week 10 was the first week that did NOT delete an entry for its own tool, and
the reason is a teaching point rather than an oversight — see
`PLATFORM_SDKS_WE_DO_NOT_IMPORT` below.

WEEK 11 DOES BOTH THINGS AT ONCE, which is why this file is worth re-reading
rather than skimming:

  * `prometheus_client` **graduates**. It has been installed since Week 8 as a
    Prefect dependency and forbidden ever since; this week declares it in
    pyproject.toml and imports it on purpose. Normal lifecycle.
  * `grafana_client` **moves the other way** — from "a future week's tool" to
    "a platform SDK we permanently do not import", joining `kserve` and
    `kubernetes` for exactly their reason. Grafana is configured by files in
    Git; a dashboard created through an API call is not reviewable, not
    diffable, and lives in a volume somebody will delete.
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
    # `prometheus_client` was here until Week 11 declared it. `grafana_client`
    # left too, but sideways — see PLATFORM_SDKS_WE_DO_NOT_IMPORT.
    "evidently": 12,
    # Drift detection is Week 12's subject, and these are the three ways a
    # student reaches for it early. `scipy.stats.ks_2samp` is one import away
    # from being a drift detector, and a hand-rolled one in Week 11 would make
    # next week's lecture a debate about statistics instead of about protocols.
    "alibi_detect": 12,
    "river": 12,
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
    # NEW IN WEEK 11, and it arrived here rather than graduating.
    #
    # Grafana has a perfectly good HTTP API and a Python client for it, and a
    # script that POSTs a dashboard would work. It would also put the definition
    # of what this team looks at inside a program, where it cannot be diffed,
    # reviewed or restored — and into a database inside a Docker volume, where
    # it survives exactly as long as nobody runs `down -v`.
    #
    # The provisioning files in grafana/ are the artifact. Same argument as the
    # InferenceService manifest, same argument as dvc.yaml, same argument as
    # params.yaml: the thing that should be argued about in a pull request has
    # to be a file.
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
    """Week 11 may import prometheus_client. It may not import Evidently."""
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
    # prometheus_client is deliberately NOT in the expected set any more: it
    # graduated this week. If it reappears here, somebody has un-declared it.
    assert roots & forbidden == {"kserve", "evidently", "grafana_client"}
    assert "prometheus_client" not in forbidden, (
        "prometheus_client graduated in Week 11 — this lab imports it on purpose"
    )


def test_this_weeks_tool_is_allowed():
    """The complement of the rule: the guard must not block a tool in scope."""
    for allowed in ("fastapi", "prefect", "httpx", "prometheus_client"):
        assert allowed not in FUTURE_WEEK_MODULES
        assert allowed not in PLATFORM_SDKS_WE_DO_NOT_IMPORT
    api = SRC / "week_11_observability" / "api.py"
    if api.exists():
        assert "fastapi" in imported_roots(api)
    loadtest = SRC / "week_11_observability" / "loadtest.py"
    if loadtest.exists():
        assert "httpx" in imported_roots(loadtest), (
            "Week 10's load generator uses httpx, which Week 9 declared — no new "
            "dependency was needed to measure a rollout"
        )
    metrics = SRC / "week_11_observability" / "metrics.py"
    if metrics.exists():
        assert "prometheus_client" in imported_roots(metrics), (
            "Week 11's instrumentation uses prometheus_client, which Prefect has "
            "been installing since Week 8 — newly DECLARED, not newly installed"
        )


def test_prometheus_client_was_already_installed_before_this_week_declared_it():
    """The same documentation trick Week 9 used for fastapi, one week later.

    If this ever fails, Prefect dropped a dependency and Week 11's opening slide
    ("you have been shipping a metrics library for three weeks and exposing not
    one metric") needs rewriting. Re-measure with:

        uv tree --package prometheus-client --invert
    """
    import importlib.util

    assert importlib.util.find_spec("prometheus_client") is not None


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
