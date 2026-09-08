from __future__ import annotations

import json

from .config import load_settings
from .data import build_dataset, load_dataframe
from .model import evaluate_model, train_logistic_regression


def main() -> None:
    settings = load_settings()
    frame = load_dataframe(settings)
    x_train, x_test, y_train, y_test = build_dataset(settings)

    print("Week 1 — Diabetes prediction baseline")
    print("=" * 37)
    print(f"Dataset:        {settings.data_path.name} ({len(frame)} patients)")
    print(f"Diabetes rate:  {frame['outcome'].mean():.1%}")
    print(f"Random seed:    {settings.random_seed}")
    print(f"Training rows:  {len(x_train)}")
    print(f"Test rows:      {len(x_test)}")
    print()
    print("Logistic Regression metrics:")
    model = train_logistic_regression(x_train, y_train, settings)
    print(json.dumps(evaluate_model(model, x_test, y_test), indent=2))
