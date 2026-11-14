"""The flow, its retry policy, and the record of which parameters built the model.

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

from week_08_prefect_flow import tasks

pytestmark = pytest.mark.unit


# ── Retry policy: where it is, and where it deliberately is not ─────────────


@pytest.mark.skip(reason="Exercise 3 — set the retry policy, then delete this skip marker.")
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


@pytest.mark.skip(reason="Exercise 3 — set the retry policy, then delete this skip marker.")
def test_train_and_repro_have_no_retries():
    """Exercise 3's first question, as an assertion.

    `run_pipeline` is deterministic and local. If it raised once it will raise
    three times, and `retries=3` buys only a traceback that arrives ninety
    seconds later with the real bug buried under two retry lines.
    """
    assert not tasks.run_pipeline.retries
    assert not tasks.build_dataset.retries
    assert not tasks.params_committed.retries
    assert not tasks.read_params_used.retries


@pytest.mark.skip(reason="Exercise 3 — set the retry policy, then delete this skip marker.")
def test_the_network_retries_use_backoff_and_jitter():
    """A fixed delay makes every failed task retry in lockstep.

    Which means a service that fell over under load gets hit by the identical
    burst that felled it. Jitter is not decoration.
    """
    for network_task in (tasks.pull_data, tasks.push_data):
        delays = network_task.retry_delay_seconds
        assert network_task.retries >= 2, "give the network tasks at least two retries"
        assert isinstance(delays, list) and len(delays) == network_task.retries, (
            f"{network_task.name}: use exponential_backoff, got {delays!r}"
        )
        assert all(a < b for a, b in zip(delays, delays[1:])), f"delays do not grow: {delays}"
        assert network_task.retry_jitter_factor and network_task.retry_jitter_factor > 0


# ── The training flow (Exercise 1) ──────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 1 — wire training_flow, then delete this skip marker.")
def test_training_flow_runs_the_pipeline_then_notifies(
    prefect_harness, monkeypatch, tmp_path, settings
):
    from week_08_prefect_flow import flows

    calls = _stub_flow_tasks(monkeypatch, tmp_path, settings)

    assert flows.training_flow()["verdict"] == "GO"

    exercise_1 = [name for name in calls["order"]
                  if name in {"build_dataset", "run_pipeline", "notify"}]
    assert exercise_1 == ["build_dataset", "run_pipeline", "notify"]
    assert calls["notify"][-1]["error"] is None


@pytest.mark.skip(reason="Exercise 1 — wire training_flow, then delete this skip marker.")
def test_training_flow_notifies_and_reraises_when_the_pipeline_fails(
    prefect_harness, monkeypatch, tmp_path, settings
):
    """The failure path reports too, and the run still ends Failed."""
    from week_08_prefect_flow import flows

    calls = _stub_flow_tasks(monkeypatch, tmp_path, settings, pipeline_error="dvc repro failed")

    with pytest.raises(RuntimeError, match="dvc repro failed"):
        flows.training_flow()

    assert calls["notify"], "notify did not run on the failure path"
    assert "dvc repro failed" in calls["notify"][-1]["error"]


# ── Parameters in a commit (Exercise 4) ─────────────────────────────────────


def _lock(path, stages: dict) -> None:
    stages = {name: {"params": {"params.yaml": values}} for name, values in stages.items()}
    (path / "dvc.lock").write_text(yaml.safe_dump({"stages": stages}))


@pytest.mark.skip(reason="Exercise 4 — record the parameters, then delete this skip marker.")
def test_read_params_used_returns_the_train_stage_values(tmp_path, settings):
    import dataclasses

    _lock(tmp_path, {
        "train": {"train.C": 0.01, "train.family": "logreg"},
        "gate": {"gate.min_f1": 0.5},
    })
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    assert tasks.read_params_used.fn(sandbox) == {"train.C": 0.01, "train.family": "logreg"}


@pytest.mark.skip(reason="Exercise 4 — record the parameters, then delete this skip marker.")
def test_read_params_used_reads_the_lock_not_params_yaml(tmp_path, settings):
    """The record says what train used, not what someone typed afterwards."""
    import dataclasses

    _lock(tmp_path, {"train": {"train.C": 1.0}})
    (tmp_path / "params.yaml").write_text(yaml.safe_dump({"train": {"C": 0.5}}))
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    assert tasks.read_params_used.fn(sandbox) == {"train.C": 1.0}


def test_params_committed_sees_an_uncommitted_change(tmp_path, settings):
    import dataclasses
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    params = tmp_path / "params.yaml"
    params.write_text(yaml.safe_dump({"train": {"C": 1.0}}))
    git("init", "-q")
    git("add", "params.yaml")
    git("-c", "user.name=lab", "-c", "user.email=lab@example.com", "commit", "-q", "-m", "params")
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    assert tasks.params_committed.fn(sandbox) is True
    params.write_text(yaml.safe_dump({"train": {"C": 0.01}}))
    assert tasks.params_committed.fn(sandbox) is False


def _stub_flow_tasks(
    monkeypatch, tmp_path, settings, committed: bool = True, pipeline_error: str | None = None
) -> dict:
    """Replace the flow's tasks with stubs that record what was called, in order."""
    import dataclasses

    from week_08_prefect_flow import flows

    calls: dict = {"order": [], "pipeline": 0, "notify": []}
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    def record(name, result=None):
        def stub(*_args, **_kwargs):
            calls["order"].append(name)
            return result
        return stub

    def run_pipeline(_settings):
        calls["order"].append("run_pipeline")
        calls["pipeline"] += 1
        if pipeline_error:
            raise RuntimeError(pipeline_error)
        return {"verdict": "GO", "summary": {}}

    def notify(_settings, verdict, error=None, params=None, committed=None):
        calls["order"].append("notify")
        calls["notify"].append({"error": error, "params": params, "committed": committed})

    monkeypatch.setattr(flows, "load_settings", lambda: sandbox)
    monkeypatch.setattr(flows, "params_committed", record("params_committed", committed))
    monkeypatch.setattr(flows, "build_dataset", record("build_dataset"))
    monkeypatch.setattr(flows, "run_pipeline", run_pipeline)
    monkeypatch.setattr(flows, "read_params_used", record("read_params_used", {"train.C": 0.01}))
    monkeypatch.setattr(flows, "notify", notify)
    return calls


@pytest.mark.skip(reason="Exercise 4 — record the parameters, then delete this skip marker.")
def test_a_run_that_requires_committed_params_refuses_before_training(
    prefect_harness, monkeypatch, tmp_path, settings
):
    from week_08_prefect_flow import flows

    calls = _stub_flow_tasks(monkeypatch, tmp_path, settings, committed=False)

    with pytest.raises(RuntimeError, match="uncommitted"):
        flows.training_flow(require_committed_params=True)

    assert calls["pipeline"] == 0, "the pipeline ran from an uncommitted params.yaml"
    assert calls["notify"] and "uncommitted" in calls["notify"][-1]["error"]


@pytest.mark.skip(reason="Exercise 4 — record the parameters, then delete this skip marker.")
def test_an_experiment_run_records_uncommitted_params(
    prefect_harness, monkeypatch, tmp_path, settings
):
    """A run from the terminal may use an uncommitted value, and its record says so."""
    from week_08_prefect_flow import flows

    calls = _stub_flow_tasks(monkeypatch, tmp_path, settings, committed=False)

    flows.training_flow()

    assert calls["pipeline"] == 1
    assert calls["notify"][-1] == {"error": None, "params": {"train.C": 0.01}, "committed": False}


# ── The scheduled flow (Exercise 5) ─────────────────────────────────────────


@pytest.mark.skip(reason="Exercise 5 — implement scheduled_flow, then delete this skip marker.")
def test_scheduled_flow_pulls_first_and_refuses_uncommitted_params(
    prefect_harness, monkeypatch, tmp_path, settings
):
    import dataclasses

    from week_08_prefect_flow import flows

    order: list[str] = []
    training_kwargs: dict = {}
    sandbox = dataclasses.replace(settings, project_root=tmp_path)

    def training_flow(**kwargs):
        order.append("training_flow")
        training_kwargs.update(kwargs)
        return {"verdict": "GO"}

    def register_model(_settings):
        raise AssertionError("the scheduled flow must not register a model")

    monkeypatch.setattr(flows, "load_settings", lambda: sandbox)
    monkeypatch.setattr(flows, "pull_data", lambda _settings: order.append("pull_data"))
    monkeypatch.setattr(flows, "training_flow", training_flow)
    monkeypatch.setattr(flows, "register_model", register_model)

    flows.scheduled_flow()

    assert order == ["pull_data", "training_flow"]
    assert training_kwargs.get("require_committed_params") is True
    assert not training_kwargs.get("register_model_version")


# ── Retries actually retry (needs the harness) ─────────────────────────────


@pytest.mark.skip(reason="Exercise 3 — set the retry policy, then delete this skip marker.")
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


@pytest.mark.skip(reason="Exercise 3 — set the retry policy, then delete this skip marker.")
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


@pytest.mark.skip(reason="Exercise 4 — record the parameters, then delete this skip marker.")
def test_notify_records_the_params_and_whether_they_were_committed(tmp_path, settings):
    import dataclasses

    sandbox = dataclasses.replace(settings, project_root=tmp_path)
    path = tasks.notify.fn(
        sandbox,
        {"verdict": "GO", "summary": {}},
        params={"train.C": 0.01},
        committed=False,
    )
    line = path.read_text()
    assert "train.C=0.01" in line
    assert "params.yaml uncommitted" in line
