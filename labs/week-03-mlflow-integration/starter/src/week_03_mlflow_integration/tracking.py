"""Experiment tracking: structured logging, parameter sweeps, and run search.

New in Week 3. Week 2 proved the tracking server works by logging ONE run with
three loose `log_param` calls. This module is the engineering upgrade:

  - batched `log_params` / `log_metrics` (one REST round-trip, not N)
  - tags, which are how you FIND runs later
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
# Two cells use scikit-learn's DEFAULTS (C=1.0, n_estimators=100), so the sweep
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
    recorded metric back to the exact code that produced it.
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


def log_training_run(
    settings: Settings,
    family: str,
    hyperparams: dict,
    *,
    sweep_tag: str | None = None,
    nested: bool = False,
) -> RunResult:
    """Train one model and record EVERYTHING about it in a single MLflow run.

    TODO(student) — Exercises 1 and 2. Fill in the five blanks below, in order.
    Week 2 logged three loose params and a model. This is the engineering
    version of the same idea: batched calls, tags, plots, and a signature.
    """
    x_train, x_test, y_train, y_test = build_dataset(settings)
    run_name = f"{family}-" + "-".join(f"{k}={v}" for k, v in hyperparams.items())

    with mlflow.start_run(run_name=run_name, nested=nested) as run:
        # ── Params: the configuration that would let someone re-run this ─────
        # TODO(student) — Exercise 1a:
        # Log all the params in ONE batched call with mlflow.log_params({...}).
        # One call is one REST round-trip; six log_param calls are six.
        # Include: model_family, random_seed, test_size, max_iter,
        #          data_path (use settings.data_path.name), n_rows,
        #          and **hyperparams so the swept value is recorded too.
        # Log max_iter even for the forest, which ignores it — it keeps the
        # UI's compare table rectangular.
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
        # TODO(student) — Exercise 1b:
        # mlflow.set_tags({...}) with:
        #   "model_family": family
        #   "git_commit":   git_commit()      <- the link back to the code
        #   "sweep":        sweep_tag          <- ONLY when sweep_tag is not None
        # Params are for reproducing a run; tags are for FINDING it later.
        tags = {"model_family": family, "git_commit": git_commit()}
        if sweep_tag is not None:
            tags["sweep"] = sweep_tag
        mlflow.set_tags(tags)

        model = build_model(family, hyperparams, settings)
        model.fit(x_train, y_train)
        metrics = evaluate_model(model, x_test, y_test)

        # ── Metrics: the measured outcome ─────────────────────────────────────
        # TODO(student) — Exercise 1c:
        # Log every metric in one call: mlflow.log_metrics(metrics)
        mlflow.log_metrics(metrics)

        # ── Plots as artifacts ────────────────────────────────────────────────
        # TODO(student) — Exercise 2:
        # Build both figures (see plots.py) and log each one with
        #   mlflow.log_figure(figure, "plots/roc_curve.png")
        #   mlflow.log_figure(figure, "plots/confusion_matrix.png")
        # log_figure writes straight to the artifact store — no local temp file.
        # Call plt.close(figure) after each one, or matplotlib warns once you
        # have opened more than 20 figures (the sweep opens 12).
        roc_figure = roc_curve_figure(model, x_test, y_test, label=family)
        mlflow.log_figure(roc_figure, "plots/roc_curve.png")
        plt.close(roc_figure)
        confusion_figure = confusion_matrix_figure(model, x_test, y_test)
        mlflow.log_figure(confusion_figure, "plots/confusion_matrix.png")
        plt.close(confusion_figure)

        # ── The model itself ──────────────────────────────────────────────────
        # TODO(student) — Exercise 1d:
        # mlflow.sklearn.log_model(
        #     model,
        #     name="model",          <- NOT artifact_path=, which MLflow 3
        #                               deprecates (older tutorials all use it).
        #     signature=infer_signature(x_train, model.predict(x_train)),
        #     input_example=x_train.head(3),
        # )
        # The signature is what populates the UI's Schema tab, and what a
        # serving runtime reads to validate incoming requests (Week 9).
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

    TODO(student) — Exercise 3:
    1. Loop over SWEEP_GRID and call log_training_run() once per cell, passing
       `sweep_tag=SWEEP_TAG` and `nested=True`. The `nested=True` is what makes
       each run a CHILD of the parent run opened below — without it you get
       seven unrelated top-level runs and the UI tree is flat.
    2. Append each RunResult to `results`.
    3. Run `make sweep`, then open the UI: you should see one "sweep" run with
       six children. Select all six -> Compare -> Parallel Coordinates.
    4. Delete the @pytest.mark.skip lines in tests/test_tracking.py.

    Note that every cell must reuse the SAME train/test split (log_training_run
    calls build_dataset with the same seed). If each cell re-randomised the
    split, the comparison would be meaningless.
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

        # TODO(student) — Exercise 3: run one nested child run per grid cell.
        for family, hyperparams in SWEEP_GRID:
            results.append(
                log_training_run(
                    settings,
                    family,
                    hyperparams,
                    sweep_tag=SWEEP_TAG,
                    nested=True,
                )
            )

        # Record the winner on the parent, so the sweep summarises itself.
        if results:
            best = max(results, key=lambda r: r.metrics["f1"])
            mlflow.set_tags(
                {"best_run_id": best.run_id, "best_run_name": best.run_name}
            )
            mlflow.log_metric("best_f1", best.metrics["f1"])
        _ = parent  # the context manager owns the parent run's lifecycle

    return results


def search_sweep_runs(settings: Settings, *, min_f1: float = 0.0) -> pd.DataFrame:
    """Query the tracking server for this sweep's child runs, best first.

    `filter_string` is evaluated by the tracking server against Postgres — this
    is not a full dump filtered in pandas. That is the whole payoff of Week 2's
    relational backend store.

    Watch the quoting: tag and param values need single quotes inside the Python
    string, metric comparisons are bare numbers, and the operator is `=` not `==`.

    TODO(student) — Exercise 4:
    Replace the empty DataFrame below with a real mlflow.search_runs() call:
        experiment_names=[settings.mlflow_experiment_name]
        filter_string=f"tags.sweep = '{SWEEP_TAG}' and metrics.f1 > {min_f1}"
        order_by=["metrics.f1 DESC", "attributes.start_time DESC"]
        max_results=50
        output_format="pandas"
    Only the CHILD runs carry the `sweep` tag, so this filter returns exactly
    the six comparable rows — the metric-less parent is excluded automatically.

    Then prove to yourself the filter runs server-side: call this with
    min_f1=0.99 and confirm you get ZERO rows back. If the filtering happened
    in pandas after downloading everything, you would still get six.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    try:
        return mlflow.search_runs(
            experiment_names=[settings.mlflow_experiment_name],
            filter_string=f"tags.sweep = '{SWEEP_TAG}' and metrics.f1 > {min_f1}",
            order_by=["metrics.f1 DESC", "attributes.start_time DESC"],
            max_results=50,
            output_format="pandas",
        )
    except MlflowException:
        # The experiment does not exist yet — a friendlier signal than a
        # raw REST traceback for a student who has not run the sweep.
        return pd.DataFrame()


def find_best_run(settings: Settings) -> str:
    """Return the run_id of the highest-F1 run in the sweep."""
    frame = search_sweep_runs(settings)
    if frame.empty:
        raise RuntimeError(
            "No sweep runs found. Run 'make sweep' first (Exercise 3)."
        )
    return str(frame.iloc[0]["run_id"])


def format_comparison_table(frame: pd.DataFrame) -> str:
    """Render the interesting columns of a search result for the terminal."""
    if frame.empty:
        return "(no runs)"
    columns = [
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
    return frame[present].to_string(index=False, na_rep="-")
