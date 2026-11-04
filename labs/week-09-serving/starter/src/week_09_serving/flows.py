"""The Prefect training flow: dvc repro as one task, plus push, register and notify around it."""

from __future__ import annotations

from prefect import flow, get_run_logger

from .config import Settings, load_settings  # noqa: F401
from .tasks import (
    build_dataset,
    notify,
    params_committed,
    pull_data,
    push_data,
    read_params_used,
    register_model,
    run_pipeline,
)


@flow(name="diabetes-training", log_prints=True)
def training_flow(
    push: bool = False,
    # Not "register": that name clashes with Prefect's parameter model.
    register_model_version: bool = False,
    require_committed_params: bool = False,
) -> dict:
    """prepare -> validate -> train -> evaluate -> gate, with a run history.

    The flow parameters choose what this run does. The hyperparameters stay in
    `params.yaml` and change with a commit. A run from the terminal may use an
    uncommitted `params.yaml`, for an experiment; with
    `require_committed_params=True` the run refuses it.

    `push` and `register_model_version` default to False because they need the
    stack. The flow is useful without them, which is what makes it testable.

    Flow parameters must be serialisable (strings, numbers, booleans); settings is loaded inside.
    """
    settings = load_settings()
    logger = get_run_logger()

    verdict: dict = {}
    try:
        committed = params_committed(settings)
        if require_committed_params and not committed:
            raise RuntimeError(
                "params.yaml has uncommitted changes. Commit them, or undo them with "
                "`git restore params.yaml`, before this run trains a model."
            )
        build_dataset(settings)
        verdict = run_pipeline(settings)
        params = read_params_used(settings)

        if push:
            push_data(settings)
        if register_model_version and verdict.get("verdict") == "GO":
            version = register_model(settings)
            logger.info("registered version %s", version)
        elif register_model_version:
            logger.warning("verdict is %s — not registering", verdict.get("verdict"))

        notify(settings, verdict, params=params, committed=committed)
        return verdict

    except Exception as error:  # noqa: BLE001 -- we re-raise below
        # Notify on failure too.
        notify(settings, verdict, error=str(error)[:300])
        raise


@flow(name="diabetes-training-with-pull", log_prints=True)
def scheduled_flow() -> dict:
    """What a cron actually runs: fetch the current data, then train and gate.

    It differs from a run from the terminal in two ways. `pull_data` comes
    first, because a scheduled run cannot assume the workspace is up to date.
    And the training flow refuses an uncommitted `params.yaml`, because nobody
    is there to say which values built the model.

    It does not register or promote: a GO verdict is not yet a release decision.
    """
    pull_data(load_settings())
    return training_flow(require_committed_params=True)
