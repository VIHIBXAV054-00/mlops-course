"""The flow, its retry policy, and the assertion that keeps it honest.

Two testing strategies, and the choice between them is measured rather than
assumed (numbers from this lab, prefect 3.8.2):

    task.fn(...)                      0.000s   — the undecorated function
    prefect_test_harness() setup      ~4.3s    — once, session-scoped
    a flow run inside the harness     ~1.1s    — each

So: `task.fn()` for anything that is really about the function's logic, and a
small number of real flow runs for the things that are about Prefect actually
doing something — retries actually retrying, state actually recorded.

A bare flow call with no harness also works, because Prefect starts a temporary
server; it costs ~8s of process startup. That is fine once and ruinous fifty
times, and it fails by being SLOW rather than by failing, which is the worst
shape for a time budget.
"""

from __future__ import annotations

import pytest
import yaml

from week_10_kserve_rollout import tasks

pytestmark = pytest.mark.unit


# ── Retry policy: where it is, and where it deliberately is not ─────────────


def test_only_the_network_tasks_carry_retries():
    """The retry map IS the map of where this pipeline touches the network.

    If a future edit adds `retries=` to a local, deterministic task, this fails
    — which is the point. The policy is an architectural claim, so it gets an
    assertion rather than a comment.
    """
    retrying = {
        name: getattr(tasks, name).retries
        for name in dir(tasks)
        if hasattr(getattr(tasks, name), "retries")
        and getattr(getattr(tasks, name), "retries", 0)
    }
    assert set(retrying) == {"pull_data", "push_data", "register_model"}, (
        f"unexpected retry policy: {retrying}. Retries belong on calls that "
        "cross a network and are safe to repeat — nowhere else."
    )


def test_train_and_repro_have_no_retries():
    """Exercise 3's first question, as an assertion.

    `run_pipeline` is deterministic and local. If it raised once it will raise
    three times, and `retries=3` buys only a traceback that arrives ninety
    seconds later with the real bug buried under two retry lines.
    """
    assert not tasks.run_pipeline.retries
    assert not tasks.build_dataset.retries
    assert not tasks.write_params.retries


def test_the_network_retries_use_backoff_and_jitter():
    """A fixed delay makes every failed task retry in lockstep.

    Which means a service that fell over under load gets hit by the identical
    burst that felled it. Jitter is not decoration.
    """
    assert tasks.pull_data.retry_jitter_factor
    assert tasks.pull_data.retry_delay_seconds


# ── The parameter trap (Exercise 4) ────────────────────────────────────────


def test_write_params_edits_the_file_dvc_actually_hashes(tmp_path, settings):
    """A Prefect parameter that never reaches params.yaml is invisible to DVC."""
    import dataclasses

    params = tmp_path / "params.yaml"
    params.write_text(yaml.safe_dump({"train": {"C": 1.0, "family": "logreg"}}))
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    applied = tasks.write_params.fn(sandbox, {"train.C": 0.01})

    assert applied == {"train.C": 0.01}
    assert yaml.safe_load(params.read_text())["train"]["C"] == 0.01
    # untouched keys survive
    assert yaml.safe_load(params.read_text())["train"]["family"] == "logreg"


def test_verify_params_applied_accepts_a_lock_that_agrees(tmp_path, settings):
    import dataclasses

    (tmp_path / "dvc.lock").write_text(
        yaml.safe_dump({"stages": {"train": {"params": {"params.yaml": {"train.C": 0.01}}}}})
    )
    sandbox = dataclasses.replace(settings, project_root=tmp_path)
    assert tasks.verify_params_applied.fn(sandbox, {"train.C": 0.01}) == {"train.C": 0.01}


def test_verify_params_applied_catches_a_pipeline_that_never_saw_the_override(
    tmp_path, settings
):
    """The load-bearing test of the week.

    Without this, forgetting `write_params` produces a run that reports success
    and ships the PREVIOUS model — correct caching, wrong result, exactly the
    Week 4 undeclared-dependency failure wearing a different hat.
    """
    import dataclasses

    (tmp_path / "dvc.lock").write_text(
        yaml.safe_dump({"stages": {"train": {"params": {"params.yaml": {"train.C": 1.0}}}}})
    )
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    with pytest.raises(RuntimeError, match="never saw your parameters"):
        tasks.verify_params_applied.fn(sandbox, {"train.C": 0.01})


def test_verify_params_is_a_no_op_when_nothing_was_overridden(tmp_path, settings):
    """An ordinary run passes no parameters and must not need a lock at all."""
    import dataclasses

    sandbox = dataclasses.replace(settings, project_root=tmp_path)
    assert tasks.verify_params_applied.fn(sandbox, {}) == {}


# ── Retries actually retry (needs the harness) ─────────────────────────────


def test_a_transient_failure_is_retried_and_then_succeeds(prefect_harness):
    """Proves the policy is real, not decorative.

    A retry policy that has never been observed retrying is a comment.
    """
    from prefect import task

    calls = {"n": 0}

    @task(retries=2, retry_delay_seconds=0, retry_jitter_factor=0)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"transient #{calls['n']}")
        return "ok"

    from prefect import flow

    @flow
    def wrapper() -> str:
        return flaky()

    assert wrapper() == "ok"
    assert calls["n"] == 3, "the task did not retry the expected number of times"


def test_a_permanent_failure_still_fails_after_its_retries(prefect_harness):
    """Retries delay a real failure; they do not remove it."""
    from prefect import flow, task

    calls = {"n": 0}

    @task(retries=2, retry_delay_seconds=0, retry_jitter_factor=0)
    def broken() -> None:
        calls["n"] += 1
        raise RuntimeError("permanent")

    @flow
    def wrapper() -> None:
        broken()

    with pytest.raises(Exception):
        wrapper()
    assert calls["n"] == 3, "should have tried once and retried twice"


# ── Partial failure (Exercise 5) ───────────────────────────────────────────


def test_a_failing_task_stops_the_tasks_after_it(prefect_harness):
    """What a partial failure leaves behind.

    The tasks downstream of a failure never start. Which means the workspace is
    in a state that is neither the old one nor the new one — and nothing in the
    filesystem records which. That is what a run history is for, and it is
    Exercise 5's written question.
    """
    from prefect import flow, task

    ran: list[str] = []

    @task
    def first() -> None:
        ran.append("first")

    @task
    def second() -> None:
        ran.append("second")
        raise RuntimeError("boom")

    @task
    def third() -> None:
        ran.append("third")

    @flow
    def wrapper() -> None:
        first()
        second()
        third()

    with pytest.raises(Exception):
        wrapper()

    assert ran == ["first", "second"], "third should never have started"


# ── notify runs on both paths ──────────────────────────────────────────────


def test_notify_records_a_verdict(tmp_path, settings):
    import dataclasses

    sandbox = dataclasses.replace(settings, project_root=tmp_path)
    path = tasks.notify.fn(
        sandbox,
        {"verdict": "GO", "criteria_version": "1.0.0",
         "summary": {"passed": 13, "failed": 0, "skipped": 4}},
    )
    assert "GO" in path.read_text()


def test_notify_records_a_failure_too(tmp_path, settings):
    """A flow that only reports its successes is the Toy Story 2 backup."""
    import dataclasses

    sandbox = dataclasses.replace(settings, project_root=tmp_path)
    path = tasks.notify.fn(sandbox, {}, error="dvc repro failed")
    assert "FAILED" in path.read_text()
