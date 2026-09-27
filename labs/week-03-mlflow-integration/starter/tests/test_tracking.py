"""Tests for structured logging, the sweep, and run search (Exercises 1-4).

Every test here is marked `live`: it needs the Docker Compose stack. The
`live_settings` fixture in conftest.py skips them automatically when the stack
is down, so this file is green either way.

    make test        # everything (live tests skip if the stack is down)
    make test-fast   # skip the live tests outright
"""

import pytest
from mlflow.tracking import MlflowClient

from week_03_mlflow_integration.tracking import (
    SWEEP_GRID,
    find_best_run,
    log_training_run,
    search_sweep_runs,
)

pytestmark = pytest.mark.live


def test_single_run_logged(live_settings) -> None:
    """Exercise 1-2: one run carries params, metrics, tags, and both plots."""
    from week_03_mlflow_integration.tracking import connect

    connect(live_settings)
    result = log_training_run(live_settings, "logreg", {"C": 1.0})

    client = MlflowClient(live_settings.mlflow_tracking_uri)
    run = client.get_run(result.run_id)

    # Params reproduce the run.
    assert run.data.params["model_family"] == "logreg"
    assert run.data.params["random_seed"] == "42"
    assert run.data.params["C"] == "1.0"

    # Metrics record the outcome, including Week 3's new roc_auc.
    assert "f1" in run.data.metrics
    assert "roc_auc" in run.data.metrics

    # Tags make the run findable.
    assert run.data.tags["model_family"] == "logreg"
    assert "git_commit" in run.data.tags

    # Both plots landed in the artifact store under plots/.
    plot_files = {item.path for item in client.list_artifacts(result.run_id, "plots")}
    assert "plots/roc_curve.png" in plot_files
    assert "plots/confusion_matrix.png" in plot_files


def test_sweep_creates_child_run_per_cell(live_settings, sweep_results) -> None:
    """Exercise 3: one child run per grid cell, all distinct, all tagged."""
    assert len(sweep_results) == len(SWEEP_GRID)
    assert len({result.run_id for result in sweep_results}) == len(SWEEP_GRID)

    client = MlflowClient(live_settings.mlflow_tracking_uri)
    for result in sweep_results:
        run = client.get_run(result.run_id)
        assert run.data.tags["sweep"] == "week3-baseline"
        # Children know their parent — this is what makes the UI tree work.
        assert "mlflow.parentRunId" in run.data.tags


def test_sweep_preserves_locked_baseline(live_settings, sweep_results) -> None:
    """Exercise 3: the two default cells still reproduce the course's pins.

    This is the regression lock enforced INSIDE the sweep. If it breaks, the
    dataset, the split, or the pipeline changed unintentionally.
    """
    by_name = {result.run_name: result for result in sweep_results}

    assert by_name["logreg-C=1.0"].metrics["f1"] == pytest.approx(0.5785, abs=0.001)
    assert by_name["logreg-C=1.0"].metrics["accuracy"] == pytest.approx(
        0.7344, abs=0.001
    )
    assert by_name["rf-n_estimators=100"].metrics["f1"] == pytest.approx(
        0.6066, abs=0.001
    )


def test_search_and_best_run(live_settings, sweep_results) -> None:
    """Exercise 4: the filter is a real server-side predicate, not pandas."""
    frame = search_sweep_runs(live_settings)
    assert len(frame) == len(SWEEP_GRID)

    # order_by=["metrics.f1 DESC"] means the server sorted this, not us.
    f1_values = list(frame["metrics.f1"])
    assert f1_values == sorted(f1_values, reverse=True)

    assert find_best_run(live_settings) == str(frame.iloc[0]["run_id"])

    # An impossible threshold returns zero rows. If the filter were applied in
    # pandas after a full dump, this would still return all six.
    assert search_sweep_runs(live_settings, min_f1=0.99).empty
