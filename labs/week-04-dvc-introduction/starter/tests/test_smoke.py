"""Regression lock for the canonical Week 1-3 dataset.

These tests operate on `data/diabetes.csv`, NOT on the DVC-tracked dataset, and
they are unchanged in substance from Week 3. Their job is to prove that adding
data versioning did not disturb the baseline the course has been quoting since
Week 1. Nothing here needs Docker, Silo or DVC.
"""

import pytest

from week_04_dvc_introduction.data import build_dataset, load_dataframe
from week_04_dvc_introduction.model import (
    build_model,
    evaluate_model,
    train_logistic_regression,
)


def test_dataframe_loads(settings) -> None:
    frame = load_dataframe(settings)
    assert len(frame) == 768
    assert "outcome" in frame.columns


def test_dataset_split_sizes(settings) -> None:
    frame = load_dataframe(settings)
    x_train, x_test, _, _ = build_dataset(settings)
    assert len(x_train) + len(x_test) == len(frame)


def test_logistic_regression_returns_model(settings) -> None:
    from sklearn.pipeline import Pipeline

    x_train, _, y_train, _ = build_dataset(settings)
    assert isinstance(train_logistic_regression(x_train, y_train, settings), Pipeline)


def test_evaluate_model_keys(settings) -> None:
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    assert set(metrics) == {"accuracy", "precision", "recall", "f1", "roc_auc"}


def test_seed_42_metrics(settings) -> None:
    """Seed 42 on diabetes.csv still reproduces the Week 1 baseline."""
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    assert metrics["f1"] == pytest.approx(0.5785, abs=0.001)
    assert metrics["accuracy"] == pytest.approx(0.7344, abs=0.001)


def test_build_model_reproduces_pinned_baselines(settings) -> None:
    """build_model at sklearn's defaults reproduces both locked baselines."""
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


def test_build_model_rejects_unknown_family(settings) -> None:
    with pytest.raises(ValueError):
        build_model("xgboost", {}, settings)
