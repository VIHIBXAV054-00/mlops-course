"""The GitHub Actions workflows, checked as YAML on your machine instead of after a push.

They check structure (triggers, `needs:`, pins), not formatting or key order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from week_12_drift_monitoring.workflows import (
    load_workflow,
    make_targets,
    pin_status,
    triggers,
    uses_refs,
)

pytestmark = pytest.mark.unit

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


@pytest.fixture(scope="module")
def ci() -> dict:
    path = WORKFLOW_DIR / "ci.yml"
    if not path.exists():
        pytest.skip("ci.yml is missing: restore it with `git checkout .github/workflows/ci.yml`.")
    return load_workflow(path)


@pytest.fixture(scope="module")
def ct() -> dict:
    path = WORKFLOW_DIR / "ct.yml"
    if not path.exists():
        pytest.skip("ct.yml is missing: restore it with `git checkout .github/workflows/ct.yml`.")
    return load_workflow(path)


# ── The files exist and are where GitHub can be told to find them ────────────


def test_workflows_live_in_a_github_workflows_directory():
    """The lab uses GitHub's own path, so `make install-ci` only copies the files."""
    assert WORKFLOW_DIR.is_dir(), (
        f"expected {WORKFLOW_DIR}: `make install-ci` copies the workflows from there "
        "to the repository root, where GitHub runs them."
    )


# ── Triggers: the CI/CT distinction, asserted ────────────────────────────────


def test_ci_is_triggered_by_code_changing(ci):
    fired_by = triggers(ci)
    assert "push" in fired_by
    assert "pull_request" in fired_by


def test_ct_is_triggered_by_time_or_a_human_not_by_code(ct):
    """CT runs on a schedule or by hand. On push it would only be a slower CI."""
    fired_by = triggers(ct)
    assert "schedule" in fired_by, "CT needs a schedule"
    assert "workflow_dispatch" in fired_by, "CT needs a human override"
    assert "push" not in fired_by, (
        "ct.yml fires on push, which makes it a duplicate of ci.yml. CT exists "
        "to model the path where NO code changed."
    )


def test_ct_schedule_declares_a_cron(ct):
    schedule = triggers(ct)["schedule"]
    assert isinstance(schedule, list) and schedule, "schedule: needs at least one entry"
    assert all("cron" in entry for entry in schedule)


# ── The job graph ────────────────────────────────────────────────────────────


def test_ci_has_the_three_jobs(ci):
    assert set(ci["jobs"]) >= {"lint", "test", "pipeline"}


def test_pipeline_waits_for_lint_and_tests(ci):
    """`needs:` is why the expensive job does not run on code that will not lint."""
    needs = ci["jobs"]["pipeline"]["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    assert set(needs) == {"lint", "test"}


def test_the_test_job_fans_out_over_the_pyramid_layers(ci):
    """One job per layer, so a red X names the layer rather than 'tests'."""
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]
    assert set(matrix["layer"]) == {"unit", "data", "eval"}


def test_the_matrix_does_not_fail_fast(ci):
    """You want to know whether eval is also broken, not only that data failed first."""
    assert ci["jobs"]["test"]["strategy"]["fail-fast"] is False


# ── One build definition, two callers ────────────────────────────────────────


def test_both_workflows_invoke_the_project_makefile(ci, ct):
    assert make_targets(ci), "ci.yml runs no make target — is it re-listing commands?"
    assert make_targets(ct), "ct.yml runs no make target — is it re-listing commands?"


def test_ci_and_ct_share_a_gate_summary_step(ci, ct):
    """Both report the verdict the same way, because it is the same target."""
    assert "gate-summary" in make_targets(ci)
    assert "gate-summary" in make_targets(ct)


def test_neither_workflow_reimplements_the_pipeline(ci, ct):
    """A workflow that calls `src/main.py` itself is a second copy of the build, and it drifts."""
    from week_12_drift_monitoring.workflows import run_commands

    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for command in run_commands(workflow):
            assert "src/main.py" not in command, (
                f"{name} calls the pipeline directly:\n    {command.strip()}\n"
                "Call a make target instead — one definition of the build, many callers."
            )


def test_every_make_target_a_workflow_calls_actually_exists(ci, ct):
    """Each `make` target a workflow calls is defined in the Makefile."""
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    declared = {
        line.split(":", 1)[0].strip()
        for line in makefile.splitlines()
        if line and not line.startswith(("\t", " ", "#")) and ":" in line and "=" not in line.split(":", 1)[0]
    }
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for target in make_targets(workflow):
            # `make test-${{ matrix.layer }}` expands at run time to one of three targets.
            candidates = (
                [f"test-{layer}" for layer in ("unit", "data", "eval")]
                if "${{" in target or target == "test-"
                else [target]
            )
            assert any(c in declared for c in candidates), (
                f"{name} calls `make {target}`, which the Makefile does not define"
            )


def test_ci_runs_one_target_per_pyramid_layer(ci):
    """The matrix and the Makefile agree on the layer names."""
    targets = make_targets(ci)
    assert any(t.startswith("test-") for t in targets), (
        "no per-layer test target invoked; the matrix should call "
        "`make test-${{ matrix.layer }}`"
    )


# ── Pins ─────────────────────────────────────────────────────────────────────


def test_every_action_is_pinned_to_a_version_not_a_branch(ci, ct):
    """`uses: someone/action@main` runs whatever they push, in your repo, with your token."""
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            assert status != "floating", (
                f"{name}: {action}@{ref} tracks a branch — {detail}"
            )


def test_the_labs_own_actions_are_not_stale(ci, ct):
    """Pins are checked against the release snapshot in workflows.py."""
    stale = []
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            if status == "stale":
                stale.append(f"{name}: {action}@{ref} — {detail}")
    assert not stale, "stale action pins:\n  " + "\n  ".join(stale)


# ── Working directory ────────────────────────────────────────────────────────


def test_workflows_run_inside_this_lab(ci, ct):
    """Without `working-directory`, a monorepo workflow runs at the root and finds no pyproject.toml."""
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        working = workflow.get("defaults", {}).get("run", {}).get("working-directory")
        assert working and "week-12-drift-monitoring" in working, (
            f"{name}: expected defaults.run.working-directory inside the lab, got {working!r}"
        )


def test_the_evidence_is_uploaded_even_when_the_gate_refuses(ci):
    """`if: always()` on the upload step keeps the report that names the failed check."""
    steps = ci["jobs"]["pipeline"]["steps"]
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "pipeline uploads no artifacts"
    assert any("always()" in str(s.get("if", "")) for s in uploads), (
        "the upload step is not conditioned on always(), so a NO-GO discards its own evidence"
    )


# ── Tags that do not exist ───────────────────────────────────────────────────


def test_a_major_tag_that_does_not_exist_is_reported_as_unresolvable():
    """setup-uv has a v9.0.0 release but no `v9` tag, so `@v9` fails at "Set up job"."""
    status, detail = pin_status("astral-sh/setup-uv", "v9")
    assert status == "unresolvable"
    assert "v7" in detail

    status, _ = pin_status("astral-sh/setup-uv", "v9.0.0")
    assert status == "exact", "the exact release tag does resolve, and is the right pin here"


def test_a_stale_pin_is_still_reported_as_stale():
    """A pin several majors behind the newest release is stale."""
    status, detail = pin_status("astral-sh/setup-uv", "v5")
    assert status == "stale"
    assert "v7" in detail
