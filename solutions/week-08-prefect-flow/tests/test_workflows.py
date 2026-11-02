"""The workflows, checked as data.

A workflow file is code that runs on a machine you do not own, and the usual
way to find out whether it is right is to push and wait. These tests move most
of that feedback to your laptop: they parse the YAML and assert its structure,
so a missing `needs:` or an unpinned action fails in milliseconds instead of
after a commit, a push and a two-minute queue.

What they deliberately do NOT do is assert on formatting, comments or key
order. A test that breaks when someone reflows a YAML block is exactly the kind
of test this course has spent six weeks arguing against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from week_08_prefect_flow.workflows import (
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
        pytest.skip("ci.yml not written yet — Exercise 4.")
    return load_workflow(path)


@pytest.fixture(scope="module")
def ct() -> dict:
    path = WORKFLOW_DIR / "ct.yml"
    if not path.exists():
        pytest.skip("ct.yml not written yet — Exercise 5.")
    return load_workflow(path)


# ── The files exist and are where GitHub can be told to find them ────────────


def test_workflows_live_in_a_github_workflows_directory():
    """Authored under `.github/workflows/`, even though that is not where they run.

    Keeping the lab's own path convention identical to the real one is what
    makes `make install-ci` a copy rather than a translation.
    """
    assert WORKFLOW_DIR.is_dir(), (
        f"expected {WORKFLOW_DIR} — Exercise 4 authors the workflows there, and "
        "`make install-ci` copies them to the repository root, which is the only "
        "place GitHub executes them from."
    )


# ── Triggers: the CI/CT distinction, asserted ────────────────────────────────


def test_ci_is_triggered_by_code_changing(ci):
    fired_by = triggers(ci)
    assert "push" in fired_by
    assert "pull_request" in fired_by


def test_ct_is_triggered_by_time_or_a_human_not_by_code(ct):
    """The whole distinction, in one assertion.

    CT must NOT fire on push. If it did it would just be a slower CI, and the
    lesson — that a model can reach production without a code change — would be
    invisible.
    """
    fired_by = triggers(ct)
    assert "schedule" in fired_by, "CT needs a clock"
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
    """You want to know whether eval is ALSO broken, not just that data failed first."""
    assert ci["jobs"]["test"]["strategy"]["fail-fast"] is False


# ── The anti-drift property: one build definition, two callers ───────────────


def test_both_workflows_invoke_the_project_makefile(ci, ct):
    assert make_targets(ci), "ci.yml runs no make target — is it re-listing commands?"
    assert make_targets(ct), "ct.yml runs no make target — is it re-listing commands?"


def test_ci_and_ct_share_a_gate_summary_step(ci, ct):
    """Both report the verdict the same way, because it is the same target."""
    assert "gate-summary" in make_targets(ci)
    assert "gate-summary" in make_targets(ct)


def test_neither_workflow_reimplements_the_pipeline(ci, ct):
    """The load-bearing assertion of Exercise 2.

    A workflow that spells out `uv run python src/main.py prepare && ... train
    && ... evaluate` is a second copy of the build. It drifts from the Makefile
    silently, and you discover it when CI and your laptop disagree about
    whether the code works.
    """
    from week_08_prefect_flow.workflows import run_commands

    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for command in run_commands(workflow):
            assert "src/main.py" not in command, (
                f"{name} calls the pipeline directly:\n    {command.strip()}\n"
                "Call a make target instead — one definition of the build, many callers."
            )


def test_every_make_target_a_workflow_calls_actually_exists(ci, ct):
    """The gap that a green local suite still let through to a real runner.

    `test_ci_and_ct_share_a_gate_summary_step` asserts the workflows CALL
    `make gate-summary`. It passed while no such target existed, because it
    parses the workflow and never looks at the Makefile — so the build died at
    `make: *** No rule to make target 'gate-summary'` after four green jobs and
    two minutes of runner time.

    Checking one artifact against another is the whole idea here: an assertion
    about a file, made by reading only that file, is a spell-check.
    """
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    declared = {
        line.split(":", 1)[0].strip()
        for line in makefile.splitlines()
        if line and not line.startswith(("\t", " ", "#")) and ":" in line and "=" not in line.split(":", 1)[0]
    }
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for target in make_targets(workflow):
            # `make test-${{ matrix.layer }}` expands at runtime; check the
            # three real targets it can become.
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
    """Against the snapshot recorded in workflows.py.

    This is the test that will one day fail for a reason that is not your
    fault, and that is the point: the snapshot goes stale, somebody re-verifies
    it, and the pins move. A pin nobody revisits is how this repository ended
    up four majors behind on `astral-sh/setup-uv`.
    """
    stale = []
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            if status == "stale":
                stale.append(f"{name}: {action}@{ref} — {detail}")
    assert not stale, "stale action pins:\n  " + "\n  ".join(stale)


# ── Working directory ────────────────────────────────────────────────────────


def test_workflows_run_inside_this_lab(ci, ct):
    """A monorepo workflow that forgets `working-directory` runs at the root and
    fails with something unhelpful about a missing pyproject.toml."""
    for name, workflow in (("ci.yml", ci), ("ct.yml", ct)):
        working = workflow.get("defaults", {}).get("run", {}).get("working-directory")
        assert working and "week-08-prefect-flow" in working, (
            f"{name}: expected defaults.run.working-directory inside the lab, got {working!r}"
        )


def test_the_evidence_is_uploaded_even_when_the_gate_refuses(ci):
    """`if: always()` on the artifact step.

    A gate that blocks a release and leaves nothing behind is untriageable —
    the artifact naming which check failed is the whole reason the run was
    worth doing.
    """
    steps = ci["jobs"]["pipeline"]["steps"]
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "pipeline uploads no artifacts"
    assert any("always()" in str(s.get("if", "")) for s in uploads), (
        "the upload step is not conditioned on always(), so a NO-GO discards its own evidence"
    )


# ── The finding that cost this lab a red build ───────────────────────────────


def test_a_major_tag_that_does_not_exist_is_reported_as_unresolvable():
    """`astral-sh/setup-uv@v9` fails on a real runner, and the API will not tell you.

    Measured 2026-08-06: setup-uv's newest release is v9.0.0, and there is no
    `v8` or `v9` tag in the repository at all. `uses: astral-sh/setup-uv@v9`
    therefore dies at "Set up job" with

        Unable to resolve action `astral-sh/setup-uv@v9`, unable to find version `v9`

    before a single step runs. "What is the latest release" and "what can I pin
    to" are different questions, and only one of them has an API endpoint.
    """
    status, detail = pin_status("astral-sh/setup-uv", "v9")
    assert status == "unresolvable"
    assert "v7" in detail

    status, _ = pin_status("astral-sh/setup-uv", "v9.0.0")
    assert status == "exact", "the exact release tag does resolve, and is the right pin here"


def test_a_stale_pin_is_still_reported_as_stale():
    """The repo's own autograde.yml pinned this four majors back."""
    status, detail = pin_status("astral-sh/setup-uv", "v5")
    assert status == "stale"
    assert "v7" in detail
