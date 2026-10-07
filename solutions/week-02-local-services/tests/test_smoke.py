"""Smoke tests for the Week 2 pipeline.

They check data loading, training and the metrics without the Docker stack.
`test_mlflow_run_logged` needs the stack, and skips itself when it is down.
"""
import pytest

from week_02_local_services.config import load_settings
from week_02_local_services.data import build_dataset, load_dataframe
from week_02_local_services.model import evaluate_model, train_logistic_regression


def test_dataframe_loads() -> None:
    """The diabetes CSV loads and has the expected shape."""
    settings = load_settings()
    frame = load_dataframe(settings)
    assert len(frame) == 768
    assert "outcome" in frame.columns


def test_dataset_split_sizes() -> None:
    """Train + test row counts sum to total rows."""
    settings = load_settings()
    frame = load_dataframe(settings)
    x_train, x_test, y_train, y_test = build_dataset(settings)
    assert len(x_train) + len(x_test) == len(frame)


def test_logistic_regression_returns_model() -> None:
    """train_logistic_regression returns a fitted scikit-learn Pipeline."""
    from sklearn.pipeline import Pipeline

    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    assert isinstance(model, Pipeline)


def test_evaluate_model_keys() -> None:
    """evaluate_model returns a dict with the expected metric keys."""
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1"}


def test_seed_42_metrics() -> None:
    """Seed 42 reproduces the Week 1 baseline metrics (LR F1 ≈ 0.5785)."""
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    # These must match Week 1 solution exactly.
    assert metrics["f1"] == pytest.approx(0.5785, abs=0.001)
    assert metrics["accuracy"] == pytest.approx(0.7344, abs=0.001)


def test_mlflow_run_logged() -> None:
    """The latest run in the experiment has the params, the metrics and the baseline F1."""
    import urllib.request
    import urllib.error

    settings = load_settings()

    try:
        urllib.request.urlopen(settings.mlflow_tracking_uri + "/health", timeout=2)
    except (urllib.error.URLError, OSError):
        pytest.skip("MLflow tracking server not reachable — start the stack first.")

    import mlflow

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    client = mlflow.tracking.MlflowClient(settings.mlflow_tracking_uri)

    exp = client.get_experiment_by_name(settings.mlflow_experiment_name)
    if exp is None:
        pytest.skip(
            "Experiment not found — run 'uv run python src/main.py' first."
        )

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        order_by=["start_time DESC"],
        max_results=1,
    )
    assert len(runs) > 0, "No runs found — run 'uv run python src/main.py' first."

    latest_run = runs[0]
    assert "random_seed" in latest_run.data.params, "random_seed param not logged"
    assert "f1" in latest_run.data.metrics, "f1 metric not logged"
    assert latest_run.data.metrics["f1"] == pytest.approx(0.5785, abs=0.001)
