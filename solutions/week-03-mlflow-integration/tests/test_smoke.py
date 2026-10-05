"""Smoke tests for the Week 3 pipeline.

These tests do NOT require a running Docker stack. They verify the pipeline
logic in isolation: data loading, model building, and metric shapes. Anything
needing the tracking server lives in test_tracking.py / test_registry.py behind
the `live` marker.
"""

import pytest

from week_03_mlflow_integration.config import load_settings
from week_03_mlflow_integration.data import build_dataset, load_dataframe
from week_03_mlflow_integration.model import (
    build_model,
    evaluate_model,
    train_logistic_regression,
)


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
    """evaluate_model returns a dict with the expected metric keys.

    roc_auc is new in Week 3 — it gives the sweep a second, threshold-independent
    way to rank models.
    """
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1", "roc_auc"}


def test_seed_42_metrics() -> None:
    """Seed 42 reproduces the Week 1 baseline metrics (LR F1 ≈ 0.5785)."""
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    # These must match Week 1 and Week 2 exactly — if they change, the dataset
    # or the pipeline was modified unintentionally.
    assert metrics["f1"] == pytest.approx(0.5785, abs=0.001)
    assert metrics["accuracy"] == pytest.approx(0.7344, abs=0.001)


def test_build_model_reproduces_pinned_baselines() -> None:
    """build_model at sklearn's defaults reproduces both locked baselines.

    This is what makes sweep cells 3 and 5 load-bearing: the regression lock
    lives inside the sweep rather than beside it.
    """
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)

    logreg = build_model("logreg", {"C": 1.0}, settings)
    logreg.fit(x_train, y_train)
    assert evaluate_model(logreg, x_test, y_test)["f1"] == pytest.approx(
        0.5785, abs=0.001
    )

    forest = build_model("rf", {"n_estimators": 100}, settings)
    forest.fit(x_train, y_train)
    assert evaluate_model(forest, x_test, y_test)["f1"] == pytest.approx(
        0.6066, abs=0.001
    )


def test_build_model_rejects_unknown_family() -> None:
    """build_model fails loudly on a typo rather than silently guessing."""
    settings = load_settings()
    with pytest.raises(ValueError):
        build_model("xgboost", {}, settings)
