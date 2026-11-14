"""The training flow.

Week 4 gave this project a DAG runner already, so the first question the week
has to answer is why there is now a second one:

    `dvc repro` answers **is this stale?**  Its graph is about CONTENT.
    Prefect answers **did it run, when, how many times, and what then?**
    Its graph is about EXECUTION.

They are not competitors and this module does not stage them as one. The flow
calls `dvc repro` as a single task for the content-hashed core, and owns the
things DVC has no opinion about: the network edges, the retries, the run
options, the schedule, and the record that any of it happened.

    DVC tells you what is out of date. Prefect tells you what happened.
"""

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
    # NOT `register`: Prefect builds a pydantic model from the flow's
    # signature, and `register` shadows an attribute on its base class,
    # which produces a UserWarning on every run. Flow parameter names are
    # part of a public API here — they appear in the UI and in
    # `run_deployment` calls — so pick ones that do not collide.
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

    NOTE WHAT IS ABSENT FROM THIS SIGNATURE: a `settings` parameter.
    Prefect builds a pydantic model from a flow's signature so that runs can be
    scheduled, re-run from the UI and triggered by API — which means **every
    flow parameter has to be serialisable**. Passing a dataclass here looks
    harmless and works when you call the function directly; it then fails only
    when a SCHEDULED run tries to validate its parameters:

        Validation of flow parameters failed with error: PydanticUserError:
        `Scheduled_FlowModel` is not fully defined; you should define
        `Settings`, then call `Scheduled_FlowModel.model_rebuild()`

    Measured, on a real scheduled run, while building this lab. A flow
    signature is a public API. Keep it to strings, numbers and booleans.
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
            # The gate is the only thing between a schedule and a released
            # model, and this is the line where it says no.
            logger.warning("verdict is %s — not registering", verdict.get("verdict"))

        notify(settings, verdict, params=params, committed=committed)
        return verdict

    except Exception as error:  # noqa: BLE001 -- we re-raise below
        # Report on the failure path too. A flow that only records its
        # successes is the Toy Story 2 backup with extra steps.
        notify(settings, verdict, error=str(error)[:300])
        raise


@flow(name="diabetes-training-with-pull", log_prints=True)
def scheduled_flow() -> dict:
    """What a cron actually runs: fetch the current data, then train and gate.

    It differs from a run from the terminal in two ways. `pull_data` comes
    first, because a scheduled run cannot assume the workspace is up to date.
    And the training flow refuses an uncommitted `params.yaml`, because nobody
    is there to say which values built the model.

    Note what it does NOT do: register or promote. Two reasons, and the second
    is the one worth arguing about.

      1. The registry needs infrastructure a scheduled run may not have.
      2. Nobody has decided that a model trained at 03:00, seen by no one,
         should reach users because a threshold said GO. A gate is a NECESSARY
         condition for a release, not a sufficient one. Week 10 decides what
         else is required.
    """
    pull_data(load_settings())
    return training_flow(require_committed_params=True)
