"""The recorded champion: the scores that "worse than what we have" is measured against.

The pipeline reads `metrics/baseline.json`. `make baseline-sync` scores the champion
on today's test split and rewrites it, so raising the bar is a deliberate act that
lands in a commit.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .data import load_measurements
from .model import evaluate_model

# No timestamp in the file: it is a DVC dependency of `gate`, so it must not change on every write.
BASELINE_KEYS = ("source", "model_name", "model_version", "run_id", "metrics")


def read_baseline(path: Path) -> dict:
    """The recorded champion, or {} when none was recorded (the regression check is then skipped)."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text() or "{}")
    return payload if payload.get("metrics") else {}


def write_baseline(payload: dict, path: Path) -> Path:
    """Write the champion's scores in a fixed key order, rounded to 4 decimals."""
    ordered = {key: payload.get(key) for key in BASELINE_KEYS}
    ordered["metrics"] = {
        key: round(float(value), 4)
        for key, value in sorted((payload.get("metrics") or {}).items())
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, indent=2) + "\n")
    return path


def score_on_test_set(model, test_path: Path) -> dict:
    """Score `model` on the test split at `test_path`, the same way the `evaluate` stage does."""
    from .pipeline import prepare_model_input  # pipeline.py imports this module

    features, labels, _ = prepare_model_input(load_measurements(test_path))
    return evaluate_model(model, features, labels)


def baseline_from_registry(settings: Settings) -> dict:
    """Load the champion from the registry and score it on today's test split. Needs the MLflow stack.

    Only `make baseline-sync` calls it, never a pipeline stage.
    """
    import mlflow
    import mlflow.sklearn
    from mlflow.tracking import MlflowClient

    test_path = settings.processed_dir / "test.csv"
    if not test_path.exists():
        raise RuntimeError(f"{test_path} is missing. Run `make repro` first.")

    client = MlflowClient(settings.mlflow_tracking_uri)
    name = settings.registered_model_name
    version = client.get_model_version_by_alias(name, settings.champion_alias)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    model = mlflow.sklearn.load_model(f"models:/{name}@{settings.champion_alias}")
    metrics = score_on_test_set(model, test_path)

    return {
        "source": f"mlflow://{name}@{settings.champion_alias}",
        "model_name": name,
        "model_version": str(version.version),
        "run_id": version.run_id,
        "metrics": metrics,
    }


def format_baseline(baseline: dict) -> str:
    """The recorded champion, for the CLI."""
    if not baseline:
        return (
            "No baseline recorded.\n"
            "  The regression check will be SKIPPED — which is not the same as\n"
            "  passing it. Run `make baseline-sync` once a champion exists."
        )
    lines = [
        f"baseline source : {baseline.get('source')}",
        f"  model version : {baseline.get('model_version') or '—'}"
        f"   run: {baseline.get('run_id') or '—'}",
        "  metrics:",
    ]
    for key, value in (baseline.get("metrics") or {}).items():
        lines.append(f"    {key:<12} {value:.4f}")
    return "\n".join(lines)
