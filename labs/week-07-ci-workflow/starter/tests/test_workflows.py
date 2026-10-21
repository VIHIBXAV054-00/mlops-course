"""The lab's workflows, read as YAML: triggers, job graph, make targets, pins.

They check structure, never formatting or comments, so they run in milliseconds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from week_07_ci_workflow.workflows import (
    load_workflow,
    make_targets,
    pin_status,
    triggers,
    uses_refs,
)

# TODO(student) Exercise 3: mark this module's layer with `pytestmark`:
# unit, data, eval or integration.

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


@pytest.fixture(scope="module")
def ci() -> dict:
    path = WORKFLOW_DIR / "ci.yml"
    if not path.exists():
        pytest.skip("ci.yml is missing.")
    return load_workflow(path)


@pytest.fixture(scope="module")
def ct() -> dict:
    path = WORKFLOW_DIR / "ct.yml"
    if not path.exists():
        pytest.skip("ct.yml is missing.")
    return load_workflow(path)


# ── Where the workflows live ─────────────────────────────────────────────────


def test_workflows_live_in_a_github_workflows_directory():
    """The lab keeps its workflows under `.github/workflows/`, like the repository root."""
    assert WORKFLOW_DIR.is_dir(), (
        f"expected {WORKFLOW_DIR}: write the workflows there; "
        "`make install-ci` copies them to the repository root, where GitHub runs them."
    )


# ── Triggers ─────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_ci_is_triggered_by_code_changing(ci):
    fired_by = triggers(ci)
    assert "push" in fired_by
    assert "pull_request" in fired_by


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_ct_is_triggered_by_time_or_a_human_not_by_code(ct):
    """CT runs on a clock or by hand, never on a push."""
    fired_by = triggers(ct)
    assert "schedule" in fired_by, "CT needs a clock"
    assert "workflow_dispatch" in fired_by, "CT needs a human override"
    assert "push" not in fired_by, (
        "ct.yml runs on push, so it is a slower copy of ci.yml. CT runs when no code changed."
    )


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_ct_schedule_declares_a_cron(ct):
    schedule = triggers(ct)["schedule"]
    assert isinstance(schedule, list) and schedule, "schedule: needs at least one entry"
    assert all("cron" in entry for entry in schedule)


# ── The job graph ────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_ci_has_the_three_jobs(ci):
    assert set(ci["jobs"]) >= {"lint", "test", "pipeline"}


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_pipeline_waits_for_lint_and_tests(ci):
    """The pipeline job runs only after lint and the tests pass."""
    needs = ci["jobs"]["pipeline"]["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    assert set(needs) == {"lint", "test"}


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_the_test_job_fans_out_over_the_pyramid_layers(ci):
    """One test job per layer."""
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]
    assert set(matrix["layer"]) == {"unit", "data", "eval"}


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_the_matrix_does_not_fail_fast(ci):
    """One failing layer does not cancel the others."""
    assert ci["jobs"]["test"]["strategy"]["fail-fast"] is False


# ── One definition of the build ──────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_both_workflows_invoke_the_project_makefile(ci, ct):
    assert make_targets(ci), "ci.yml runs no make target — is it re-listing commands?"
    assert make_targets(ct), "ct.yml runs no make target — is it re-listing commands?"


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_ci_and_ct_share_a_gate_summary_step(ci, ct):
    """Both workflows write the verdict with the same target."""
    assert "gate-summary" in make_targets(ci)
    assert "gate-summary" in make_targets(ct)


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_neither_workflow_reimplements_the_pipeline(ci, ct):
    """Workflows call make targets, never the pipeline commands themselves."""
    from week_07_ci_workflow.workflows import run_commands

    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for command in run_commands(workflow):
            assert "src/main.py" not in command, (
                f"{name} calls the pipeline directly:\n    {command.strip()}\n"
                "Call a make target instead — one definition of the build, many callers."
            )


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_every_make_target_a_workflow_calls_actually_exists(ci, ct):
    """Every make target a workflow calls is defined in the Makefile."""
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    declared = {
        line.split(":", 1)[0].strip()
        for line in makefile.splitlines()
        if line and not line.startswith(("\t", " ", "#")) and ":" in line and "=" not in line.split(":", 1)[0]
    }
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for target in make_targets(workflow):
            # `make test-${{ matrix.layer }}` becomes one of the three layer targets.
            candidates = (
                [f"test-{layer}" for layer in ("unit", "data", "eval")]
                if "${{" in target or target == "test-"
                else [target]
            )
            assert any(c in declared for c in candidates), (
                f"{name} calls `make {target}`, which the Makefile does not define"
            )


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_ci_runs_one_target_per_pyramid_layer(ci):
    """The matrix calls the per-layer test targets."""
    targets = make_targets(ci)
    assert any(t.startswith("test-") for t in targets), (
        "no per-layer test target invoked; the matrix should call "
        "`make test-${{ matrix.layer }}`"
    )


# ── Pins ─────────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_every_action_is_pinned_to_a_version_not_a_branch(ci, ct):
    """No action is pinned to a branch."""
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            assert status != "floating", (
                f"{name}: {action}@{ref} tracks a branch — {detail}"
            )


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_the_labs_own_actions_are_not_stale(ci, ct):
    """No action pin is older than the snapshot in workflows.py."""
    stale = []
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            if status == "stale":
                stale.append(f"{name}: {action}@{ref} — {detail}")
    assert not stale, "stale action pins:\n  " + "\n  ".join(stale)


# ── Working directory ────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 5: delete this marker when the workflow is written.")
def test_workflows_run_inside_this_lab(ci, ct):
    """Every `run:` starts in this lab's folder, not at the repository root."""
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        working = workflow.get("defaults", {}).get("run", {}).get("working-directory")
        assert working and "week-07-ci-workflow" in working, (
            f"{name}: expected defaults.run.working-directory inside the lab, got {working!r}"
        )


@pytest.mark.skip(reason="Exercise 4: delete this marker when the workflow is written.")
def test_the_evidence_is_uploaded_even_when_the_gate_refuses(ci):
    """The artifacts are uploaded even when the gate fails."""
    steps = ci["jobs"]["pipeline"]["steps"]
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "pipeline uploads no artifacts"
    assert any("always()" in str(s.get("if", "")) for s in uploads), (
        "the upload step is not conditioned on always(), so a NO-GO discards its own evidence"
    )


# ── The setup-uv tag ─────────────────────────────────────────────────────────


def test_a_major_tag_that_does_not_exist_is_reported_as_unresolvable():
    """`setup-uv@v9` names a tag that does not exist; `@v9.0.0` resolves."""
    status, detail = pin_status("astral-sh/setup-uv", "v9")
    assert status == "unresolvable"
    assert "v7" in detail

    status, _ = pin_status("astral-sh/setup-uv", "v9.0.0")
    assert status == "exact", "the exact release tag does resolve, and is the right pin here"


def test_a_stale_pin_is_still_reported_as_stale():
    """An old major tag is reported as stale."""
    status, detail = pin_status("astral-sh/setup-uv", "v5")
    assert status == "stale"
    assert "v7" in detail
