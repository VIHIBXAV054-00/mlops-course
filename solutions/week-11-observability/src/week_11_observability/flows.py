"""The Prefect training flow.

`dvc repro` decides what is stale and runs the pipeline. The flow adds retries, runtime
parameters, schedules and a record of every run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from prefect import flow, get_run_logger

from .config import Settings, load_settings  # noqa: F401
from .tasks import (
    build_dataset,
    notify,
    pull_data,
    push_data,
    register_model,
    run_pipeline,
    verify_params_applied,
    write_params,
)


@flow(name="diabetes-training", log_prints=True)
def training_flow(
    C: float | None = None,
    impute_strategy: str | None = None,
    family: str | None = None,
    push: bool = False,
    # not `register`, which clashes with an attribute of Prefect's parameter model
    register_model_version: bool = False,
) -> dict:
    """prepare -> validate -> train -> evaluate -> gate, with a run history.

    The overrides go into `params.yaml` before the pipeline runs. Every flow parameter must be
    serialisable (strings, numbers, booleans), or a scheduled run fails to validate it.
    `push` and `register_model_version` need the stack, so they default to False.
    """
    settings = load_settings()
    logger = get_run_logger()

    overrides = {
        key: value
        for key, value in (
            ("train.C", C),
            ("train.impute_strategy", impute_strategy),
            ("train.family", family),
        )
        if value is not None
    }

    verdict: dict = {}
    try:
        build_dataset(settings)
        applied = write_params(settings, overrides)
        verdict = run_pipeline(settings)
        # after the pipeline: did the stage that decides staleness see the override?
        verify_params_applied(settings, applied)

        if push:
            push_data(settings)
        if register_model_version and verdict.get("verdict") == "GO":
            version = register_model(settings)
            logger.info("registered version %s", version)
        elif register_model_version:
            logger.warning("verdict is %s — not registering", verdict.get("verdict"))

        notify(settings, verdict)
        return verdict

    except Exception as error:  # noqa: BLE001 -- we re-raise below
        # report failures too, not only successes
        notify(settings, verdict, error=str(error)[:300])
        raise


@flow(name="diabetes-training-with-pull", log_prints=True)
def scheduled_flow() -> dict:
    """What a scheduled run executes: pull the current data, then train and gate.

    It does not register or promote: a GO is needed for a release, but it is not enough.
    """
    pull_data(load_settings())
    return training_flow()


def demo_parameterised(settings: Settings, **overrides) -> dict:
    """Run the flow with overrides, then restore params.yaml.

    The restore keeps the lab's working tree clean. A real scheduled run keeps the change.
    """
    params = settings.project_root / "params.yaml"
    backup = Path(str(params) + ".flow-bak")
    shutil.copy(params, backup)
    try:
        return training_flow(**overrides)
    finally:
        shutil.move(str(backup), params)
