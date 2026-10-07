"""Experiment tracking: structured logging, parameter sweeps, and run search.

New in Week 3. Week 2 proved the tracking server works by logging ONE run with
three loose `log_param` calls. This module is the engineering upgrade:

  - batched `log_params` / `log_metrics` (one REST round-trip, not N)
  - tags, which are how you find runs later
  - a signature + input example, which make the logged model self-describing
  - plots logged as artifacts
  - a sweep: one parent run with one child run per grid cell
  - server-side run search, so comparison is a query and not scrolling
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature

from .config import Settings
from .data import build_dataset
from .model import build_model, evaluate_model
from .plots import confusion_matrix_figure, roc_curve_figure

# Every child run of a sweep carries this tag. The parent does not, so a search
# filtered on it returns exactly the comparable rows — no metric-less parent
# polluting an "order by metrics.f1 DESC".
SWEEP_TAG = "week3-baseline"

# One sweep cell = (model family, the single hyperparameter under test).
#
# Two cells use scikit-learn's defaults (C=1.0, n_estimators=100), so the sweep
# reproduces the Week 1/2 baselines exactly (LR F1 0.5785 / acc 0.7344,
# RF F1 0.6066) rather than merely sitting next to them.
SWEEP_GRID: tuple[tuple[str, dict], ...] = (
    ("logreg", {"C": 0.01}),
    ("logreg", {"C": 0.1}),
    ("logreg", {"C": 1.0}),
    ("logreg", {"C": 10.0}),
    ("rf", {"n_estimators": 100}),
    ("rf", {"n_estimators": 300}),
)


@dataclass(frozen=True)
class RunResult:
    """What one logged run produced, for the CLI and the tests to inspect."""

    run_id: str
    run_name: str
    metrics: dict


def connect(settings: Settings) -> None:
    """Point the MLflow client at the tracking server and select the experiment.

    `set_experiment` creates the experiment on first use. Naming discipline
    matters: "diabetes-week3" is a question you are asking, "test2" is not.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)


def git_commit() -> str:
    """Return the current git commit, or "unknown" outside a git checkout.

    This is the single most valuable tag you can log: it is the link from a
    recorded metric back to the code — but only to committed code. See
    git_dirty() below, and Exercise 6.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def git_dirty() -> str:
    """Return "true" if this directory has uncommitted changes, else "false".

    `git_commit()` names the last commit, not the code that actually ran. With
    uncommitted edits the two differ, and `git checkout <git_commit>` hands you
    code that never produced the run. Tags are strings, hence "true"/"false";
    "unknown" outside a git checkout.

    `answers.md` is excluded: your written answers are committed with the lab,
    but editing them cannot change what a run computed.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":(exclude)answers.md"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return "true" if result.stdout.strip() else "false"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def log_training_run(
    settings: Settings,
    family: str,
    hyperparams: dict,
    *,
    sweep_tag: str | None = None,
    nested: bool = False,
) -> RunResult:
    """Train one model and record everything about it in a single MLflow run."""
    x_train, x_test, y_train, y_test = build_dataset(settings)
    run_name = f"{family}-" + "-".join(f"{k}={v}" for k, v in hyperparams.items())

    with mlflow.start_run(run_name=run_name, nested=nested) as run:
        # ── Params: the configuration that would let someone re-run this ─────
        # One batched call, not N separate ones. `max_iter` only affects logreg,
        # but logging it for every run keeps the UI's compare table rectangular.
        mlflow.log_params(
            {
                "model_family": family,
                "random_seed": settings.random_seed,
                "test_size": settings.test_size,
                "max_iter": settings.max_iter,
                "data_path": settings.data_path.name,
                "n_rows": len(x_train) + len(x_test),
                **hyperparams,
            }
        )

        # ── Tags: free-form labels, the thing you search on later ────────────
        # `git_dirty` is the Exercise 6 fix: without it, `git_commit` claims
        # code the run may never have seen.
        mlflow.set_tags(
            {
                "model_family": family,
                "git_commit": git_commit(),
                "git_dirty": git_dirty(),
                **({"sweep": sweep_tag} if sweep_tag else {}),
            }
        )

        model = build_model(family, hyperparams, settings)
        model.fit(x_train, y_train)
        metrics = evaluate_model(model, x_test, y_test)

        # ── Metrics: the measured outcome ─────────────────────────────────────
        mlflow.log_metrics(metrics)

        # ── Plots as artifacts ────────────────────────────────────────────────
        # log_figure writes the PNG straight to the artifact store — no local
        # temp file. Close each figure or matplotlib warns after 20 of them.
        figures = {
            "plots/roc_curve.png": roc_curve_figure(
                model, x_test, y_test, label=run_name
            ),
            "plots/confusion_matrix.png": confusion_matrix_figure(
                model, x_test, y_test
            ),
        }
        for artifact_file, figure in figures.items():
            mlflow.log_figure(figure, artifact_file)
            plt.close(figure)

        # ── The model itself ──────────────────────────────────────────────────
        # NOTE: `name=`, not the older `artifact_path=` that MLflow 3 deprecates
        # (and that every pre-MLflow-3 tutorial uses). The signature and input
        # example populate the UI's Schema tab and are what a serving runtime
        # reads to validate incoming requests.
        mlflow.sklearn.log_model(
            model,
            name="model",
            signature=infer_signature(x_train, model.predict(x_train)),
            input_example=x_train.head(3),
        )

        return RunResult(run_id=run.info.run_id, run_name=run_name, metrics=metrics)


def run_sweep(settings: Settings) -> list[RunResult]:
    """Run the whole grid as one parent run with one child run per cell.

    The parent holds the sweep definition; each child holds one data point.
    This is the structure the official MLflow hyperparameter-tuning tutorial
    uses (it drives the grid with Optuna; a plain loop teaches the same thing
    with one less dependency).
    """
    connect(settings)

    results: list[RunResult] = []
    with mlflow.start_run(run_name="sweep") as parent:
        mlflow.set_tags({"sweep_parent": SWEEP_TAG, "git_commit": git_commit()})
        mlflow.log_params(
            {
                "grid_size": len(SWEEP_GRID),
                "families": ",".join(sorted({f for f, _ in SWEEP_GRID})),
                "random_seed": settings.random_seed,
            }
        )

        for family, hyperparams in SWEEP_GRID:
            results.append(
                log_training_run(
                    settings, family, hyperparams, sweep_tag=SWEEP_TAG, nested=True
                )
            )

        # Record the winner on the parent, so the sweep summarises itself.
        best = max(results, key=lambda r: r.metrics["f1"])
        mlflow.set_tags({"best_run_id": best.run_id, "best_run_name": best.run_name})
        mlflow.log_metric("best_f1", best.metrics["f1"])
        _ = parent  # the context manager owns the parent run's lifecycle

    return results


def latest_sweep_id(settings: Settings) -> str | None:
    """Return the run_id of the most recent sweep parent, or None if none exists.

    Every `make sweep` adds six more children to the experiment. Comparing runs
    from two different sweeps (say, one before and one after a code change) is
    exactly the mix-up a query should prevent, so searches scope to one sweep.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    try:
        parents = mlflow.search_runs(
            experiment_names=[settings.mlflow_experiment_name],
            filter_string=f"tags.sweep_parent = '{SWEEP_TAG}'",
            order_by=["attributes.start_time DESC"],
            max_results=1,
            output_format="list",
        )
    except MlflowException:
        # The experiment does not exist yet — nothing has been logged.
        return None
    return parents[0].info.run_id if parents else None


def search_sweep_runs(
    settings: Settings, *, metric: str = "f1", min_f1: float = 0.0
) -> pd.DataFrame:
    """Query the tracking server for the latest sweep's child runs, best first.

    The `filter_string` travels to the tracking server and becomes part of a SQL
    query against Postgres, so only matching rows come back over the network.
    That is the payoff of Week 2's relational backend store — it matters when
    the experiment holds ten thousand runs rather than a dozen.

    Watch the quoting: tag and param values need single quotes inside the Python
    string, metric comparisons are bare numbers, and the operator is `=` not `==`.
    """
    parent_id = latest_sweep_id(settings)
    if parent_id is None:
        return pd.DataFrame()
    # MLflow's own system tags (mlflow.parentRunId, mlflow.runName, ...) are
    # queryable exactly like the ones you set yourself.
    return mlflow.search_runs(
        experiment_names=[settings.mlflow_experiment_name],
        filter_string=(
            f"tags.mlflow.parentRunId = '{parent_id}' and metrics.f1 > {min_f1}"
        ),
        order_by=[f"metrics.{metric} DESC", "attributes.start_time DESC"],
        max_results=50,
        output_format="pandas",
    )


def find_best_run(settings: Settings, *, metric: str = "f1") -> str:
    """Return the run_id of the latest sweep's best run by `metric`."""
    frame = search_sweep_runs(settings, metric=metric)
    if frame.empty:
        raise RuntimeError(
            "No sweep runs found. Run 'make sweep' first (Exercise 3)."
        )
    return str(frame.iloc[0]["run_id"])


def query_runs(settings: Settings, filter_string: str, order_by: str | None) -> pd.DataFrame:
    """Run an arbitrary search across the whole experiment (the stretch exercise)."""
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return mlflow.search_runs(
        experiment_names=[settings.mlflow_experiment_name],
        filter_string=filter_string,
        order_by=[order_by] if order_by else None,
        max_results=50,
        output_format="pandas",
    )


def format_comparison_table(frame: pd.DataFrame) -> str:
    """Render the interesting columns of a search result for the terminal."""
    if frame.empty:
        return "(no runs)"
    columns = [
        "run_id",
        "tags.mlflow.runName",
        "params.model_family",
        "params.C",
        "params.n_estimators",
        "metrics.f1",
        "metrics.roc_auc",
        "metrics.accuracy",
        "metrics.recall",
    ]
    present = [column for column in columns if column in frame.columns]
    # A forest has no C and a logreg has no n_estimators: show "-", not "None".
    return frame[present].fillna("-").to_string(index=False)
