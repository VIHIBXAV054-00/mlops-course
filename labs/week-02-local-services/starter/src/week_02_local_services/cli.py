from __future__ import annotations

import json

import mlflow
import mlflow.sklearn

from .config import load_settings
from .data import build_dataset, load_dataframe
from .model import evaluate_model, train_logistic_regression


def main() -> None:
    settings = load_settings()
    frame = load_dataframe(settings)
    x_train, x_test, y_train, y_test = build_dataset(settings)

    print("Week 2 — Diabetes prediction pipeline")
    print("=" * 38)
    print(f"Dataset:        {settings.data_path.name} ({len(frame)} patients)")
    print(f"Diabetes rate:  {frame['outcome'].mean():.1%}")
    print(f"Random seed:    {settings.random_seed}")
    print(f"Training rows:  {len(x_train)}")
    print(f"Test rows:      {len(x_test)}")
    print()

    # TODO(student) Exercise 3, part 1: point MLflow at the tracking server in
    # settings.mlflow_tracking_uri, and select the experiment
    # settings.mlflow_experiment_name (set_tracking_uri, set_experiment).

    # TODO(student) Exercise 3, part 2: put the training and evaluation below
    # inside an MLflow run (start_run, as a `with` block). In the run:
    #   - log the params random_seed, test_size and max_iter from `settings`;
    #   - log each metric that evaluate_model returns;
    #   - log the fitted pipeline as a model named "model" (mlflow.sklearn).
    # Then delete the last print line.
    # Tutorial: https://mlflow.org/docs/latest/ml/tracking/quickstart/
    model = train_logistic_regression(x_train, y_train, settings)
    metrics = evaluate_model(model, x_test, y_test)
    print("Logistic Regression metrics:")
    print(json.dumps(metrics, indent=2))
    print()
    print("This run is not tracked yet (Exercise 3).")
