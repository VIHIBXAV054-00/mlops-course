"""Prefect tasks: the pipeline's steps, with a retry policy that is mostly absent.

Read the `retries=` arguments in this file as a **map of where this pipeline
touches the network**, because that is exactly what they are. Three tasks have
them. Everything else has none, deliberately, and Exercise 3 is about why.

The rule, stated once:

    A retry is only useful when the SAME call, run again, might succeed. That
    means the failure has to be transient, and the operation has to be safe to
    repeat. Retrying anything else burns time and hides a real bug behind a
    delay.

`train` is deterministic and local. If it raised once it will raise three
times, and the only thing `retries=3` buys you is that the traceback you needed
arrives ninety seconds later.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import yaml  # noqa: F401 -- you need it in Exercise 4
from prefect import get_run_logger, task
from prefect.tasks import exponential_backoff

from . import pipeline, registry
from .config import Settings
from .datasets import build_measurements

def _log():
    """The run logger inside a flow, an ordinary logger outside one.

    `get_run_logger()` raises `MissingContextError` when there is no active
    run — which would make `task.fn(...)` unusable outside Prefect, and that is
    the cheap unit-test path this lab's test suite is built on (0.000s per
    call, against ~1.1s for a real flow run).

    The general rule this encodes: **a function that can only execute inside
    its framework is a function you cannot unit-test.** Keep the framework at
    the edges.
    """
    try:
        return get_run_logger()
    except Exception:  # noqa: BLE001 -- MissingContextError and friends
        return logging.getLogger(__name__)


def _dvc_env() -> dict:
    """The environment `dvc` needs to reach Silo.

    DVC talks to the object store directly and reads the standard `AWS_*`
    names, while this project keeps one credential block under `S3_*` in
    `.env`. The Makefile maps one onto the other for interactive use; a task
    that shells out has to do the same, or `dvc pull` fails to authenticate and
    reports it as an ordinary failure -- which a retry then patiently repeats
    three times.

    Worth knowing as a general shape: **a subprocess does not inherit your
    intentions, only your environment.** Anything the shell wrapper was doing
    for you has to be done again here.
    """
    env = dict(os.environ)
    if "S3_ACCESS_KEY" in env:
        env.setdefault("AWS_ACCESS_KEY_ID", env["S3_ACCESS_KEY"])
    if "S3_SECRET_KEY" in env:
        env.setdefault("AWS_SECRET_ACCESS_KEY", env["S3_SECRET_KEY"])
    return env


def _run_dvc(settings: Settings, *args: str) -> str:
    """Run a dvc subcommand, and report its failure in a way you can act on."""
    result = subprocess.run(
        ["uv", "run", "dvc", *args],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
        env=_dvc_env(),
    )
    if result.returncode != 0:
        # NOT `--quiet`: a retry policy is only as useful as the message it
        # eventually gives up with, and "dvc pull failed:" with nothing after
        # the colon costs more time than the retries save.
        detail = ((result.stderr or "") + (result.stdout or "")).strip()
        tail = "\n  ".join(detail.splitlines()[-4:]) or "no output"
        raise RuntimeError(f"dvc {' '.join(args)} failed (exit {result.returncode}):\n  {tail}")
    return result.stdout


# One place to say "this is a flaky network call", so the policy is visible
# rather than scattered across decorators.
# TODO(student) Exercise 3 — decide the retry policy, and where it applies.
#
# A retry is only useful when the SAME call, run again, might succeed. That
# needs two things: the failure has to be TRANSIENT, and the operation has to
# be SAFE TO REPEAT.
#
# Set `retries`, `retry_delay_seconds` (try `exponential_backoff`) and
# `retry_jitter_factor` here, then decide which tasks below get them.
# `tests/test_flows.py` asserts your answer — and asserts that the local,
# deterministic tasks did NOT get them.
NETWORK_RETRIES = {
    "retries": 0,
    # Doubling, so a service that is restarting gets a chance to finish.
    # "retry_delay_seconds": exponential_backoff(backoff_factor=2),
    # Jitter matters more than it looks. Without it, every task that failed at
    # the same moment retries at the same moment, and a service that fell over
    # because of load gets hit by the identical burst that felled it.
    # "retry_jitter_factor": 0.5,
}


# ── No retries: local, deterministic work ───────────────────────────────────


@task
def build_dataset(settings: Settings, version: int = 2) -> str:
    """Rebuild the DVC-tracked dataset from the git-committed raw batches.

    No retries: this reads files that are either there or not. A missing batch
    is a broken checkout, and running it again does not fix a checkout.
    """
    rows = build_measurements(
        version=version,
        raw_dir=settings.project_root / "data" / "raw",
        out_path=settings.measurements_path,
    )
    _log().info("built %s rows -> %s", rows, settings.measurements_path.name)
    return str(settings.measurements_path)


@task
def params_committed(settings: Settings) -> bool:
    """True when `params.yaml` has no uncommitted changes in Git."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "params.yaml"],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        _log().warning("cannot check params.yaml in Git: %s", result.stderr.strip())
        return False
    return result.stdout.strip() == ""


@task
def run_pipeline(settings: Settings) -> dict:
    """`dvc repro` -- the whole content-hashed core, as ONE task.

    Not five tasks shelling out to `dvc repro -s <stage>`. DVC already owns the
    graph inside here: which stages are stale, in what order, and what to skip.
    Splitting it up would put two schedulers in charge of one graph, and the
    one with less information would be making the decisions.

    The division of labour for the whole week, in one line:

        DVC decides what is out of date. Prefect decides what happens, when,
        how many times, and what to do when it fails.

    No retries. If `prepare` raised, it will raise again; if the gate refused,
    it will refuse again. A refusal is an answer, not a glitch.
    """
    logger = _log()
    result = subprocess.run(
        ["uv", "run", "dvc", "repro"],
        cwd=settings.project_root,
        capture_output=True,
        text=True,
        check=False,
        env=_dvc_env(),
    )
    for line in (result.stdout or "").splitlines():
        if line.strip():
            logger.info(line.rstrip())

    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError(
            "dvc repro failed (exit %s):\n  %s" % (result.returncode, "\n  ".join(tail))
        )
    return pipeline.read_gate(settings)


@task
def read_params_used(settings: Settings, stage: str = "train") -> dict:
    """The parameter values `stage` used in its last run, as `dvc.lock` records them.

    `dvc.lock` stores the values, not only a hash:

        train:
          params:
            params.yaml:
              train.C: 1.0
    """
    # TODO(student) Exercise 4: read dvc.lock and return the parameters of
    # `stage` as one dictionary of name -> value, for example
    # {"train.C": 1.0, "train.family": "logreg"}. Read the file, not
    # params.yaml: the record must say what the stage used.
    return {}


# ── Retries: the network edges, and nowhere else ────────────────────────────


@task(**NETWORK_RETRIES)
def pull_data(settings: Settings) -> bool:
    """`dvc pull` from Silo.

    RETRIES, because this is a socket. A restarting object store, a DNS blip
    and a connection reset are all things that succeed on the second attempt.

    IDEMPOTENT: pulling the same content hash twice produces the same bytes.
    That is what makes the retry safe, and it is not an accident -- Week 4's
    content addressing is what bought it.
    """
    _run_dvc(settings, "pull")
    return True


@task(**NETWORK_RETRIES)
def push_data(settings: Settings) -> bool:
    """`dvc push` to Silo. Retries for the same reason, idempotent for the same reason."""
    _run_dvc(settings, "push")
    return True


@task(retries=2, retry_delay_seconds=exponential_backoff(backoff_factor=2))
def register_model(settings: Settings) -> str | None:
    """Register the run's model in MLflow -- **and this one is NOT idempotent.**

    Exercise 3's second question, and the reason it is worth asking: every
    other retry in this file is free because the operation is content-addressed
    or read-only. This one creates a NEW MODEL VERSION on every call.

    So consider the failure that retries are for: the request reaches MLflow,
    MLflow commits the version, and the RESPONSE is lost. From here that is
    indistinguishable from "it never arrived" -- and the retry registers a
    second, identical version. Nothing errors. You simply have version 4 and
    version 5 pointing at the same run, and a registry that has quietly started
    lying about how many models you have.

    The mitigation here is the cheap one: ask first. Before registering, look
    for an existing version for this run id and return it if present. That
    narrows the window rather than closing it -- a true fix needs an
    idempotency key, which the MLflow registry does not offer.

    The general rule worth taking away:

        **Idempotency is a PRECONDITION for a retry, not a consequence of one.**
        Adding `retries=` to a task that creates things converts a visible
        failure into an invisible duplicate.
    """
    logger = _log()
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        logger.warning("no MLflow run recorded — skipping registration")
        return None

    from mlflow.tracking import MlflowClient

    client = MlflowClient(settings.mlflow_tracking_uri)
    existing = [
        v
        for v in client.search_model_versions(f"name='{settings.registered_model_name}'")
        if v.run_id == run_id
    ]
    if existing:
        version = existing[0].version
        logger.info("run %s is already registered as version %s — not registering again",
                    run_id[:8], version)
        return str(version)

    model_version = registry.register_best_model(settings, run_id)
    return str(model_version.version)


# ── No retries: reporting ───────────────────────────────────────────────────


@task
def notify(
    settings: Settings,
    verdict: dict,
    error: str | None = None,
    params: dict | None = None,
    committed: bool | None = None,
) -> Path:
    """Write a one-line record of how the run ended.

    A file, not an email. Where a notification is DELIVERED is a Week 11
    question; that it exists at all is this week's. What matters here is that
    it runs on the failure path too -- a flow that only reports its successes
    is the Toy Story 2 backup with extra steps.
    """
    path = settings.project_root / "reports" / "last_run.txt"
    path.parent.mkdir(parents=True, exist_ok=True)

    if error:
        line = f"FAILED — {error}"
    elif verdict:
        summary = verdict.get("summary", {})
        line = (
            f"{verdict.get('verdict', '?')} — "
            f"{summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed, "
            f"{summary.get('skipped', 0)} skipped "
            f"(criteria {verdict.get('criteria_version', '?')})"
        )
    else:
        line = "no verdict recorded"

    if params and not error:
        values = ", ".join(f"{name}={value}" for name, value in sorted(params.items()))
        state = "committed" if committed else "uncommitted"
        line += f" | {values} | params.yaml {state}"

    path.write_text(line + "\n")
    _log().info("notify: %s", line)
    return path
