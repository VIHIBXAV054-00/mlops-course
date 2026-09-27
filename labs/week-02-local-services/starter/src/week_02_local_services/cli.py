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

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    print(f"MLflow tracking URI: {settings.mlflow_tracking_uri}")
    print(f"Experiment:          {settings.mlflow_experiment_name}")
    print()

    with mlflow.start_run():
        mlflow.log_param("random_seed", settings.random_seed)
        mlflow.log_param("test_size", settings.test_size)
        mlflow.log_param("max_iter", settings.max_iter)

        model = train_logistic_regression(x_train, y_train, settings)
        metrics = evaluate_model(model, x_test, y_test)

        for name, value in metrics.items():
            mlflow.log_metric(name, value)

        mlflow.sklearn.log_model(model, name="model")

        print("Logistic Regression metrics:")
        print(json.dumps(metrics, indent=2))
        print()
        print(f"Run logged to: {settings.mlflow_tracking_uri}")
