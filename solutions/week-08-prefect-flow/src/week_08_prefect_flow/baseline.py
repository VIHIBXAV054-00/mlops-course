"""The recorded champion — what "worse than what we have" is measured against.

New in Week 6, and the design decision here is worth more than the code.

"Is this model worse than the one already deployed?" needs a number for *the one
already deployed*, and there are three places to get it:

**A. A committed file** (`metrics/baseline.json`). Hermetic, hashable by DVC,
readable in a diff, works with no network. Its failure mode is that it is a
*claim*: nothing stops someone editing it until the gate passes.

**B. A live registry query** — the run behind `diabetes-classifier@champion`.
Always true. Its failure modes are worse than A's: the `gate` stage stops being
reproducible from its declared inputs, `dvc.lock` starts lying, and the gate
breaks whenever the stack is down, including in CI.

**C. Nothing** — absolute floors only. Cheapest, and it cannot answer the
question at all.

This lab ships **A as the pipeline's source of truth, with B as a human-invoked
sync.** `make baseline-sync` reads the champion alias, loads that version,
scores it on today's test split, and rewrites the file — so raising the bar is a deliberate
act that lands in a commit, next to the data pointer, the lock file, the metrics
and the validation verdict. A live test asserts the two agree.

Say the reason out loud, because it generalises past this lab: **a pipeline
stage whose result depends on a database in another container is not
reproducible.** The whole value of `dvc.lock` is that you can believe it. Reading
the champion at gate time would trade that away for freshness nobody asked for —
the champion changes when a human promotes something, not between two runs of
the same pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .data import load_measurements
from .model import evaluate_model

# What the baseline file is allowed to contain. Deliberately small: the metrics,
# and enough provenance to find out where they came from. Note what is NOT here
# — a timestamp. This file is a `cache: false` DVC dependency of the gate stage,
# so a value that changed on every write would make `gate` permanently stale and
# the working tree permanently dirty. See the same rule in pipeline.py.
BASELINE_KEYS = ("source", "model_name", "model_version", "run_id", "metrics")


def read_baseline(path: Path) -> dict:
    """The recorded champion, or {} if none has ever been recorded.

    Returning {} rather than raising is deliberate: "there is no baseline" is an
    ordinary state (it is true for the first model any project ever trains), and
    the gate's job is to report it as a SKIPPED regression check rather than to
    crash — or, far worse, to treat the absence as a pass.
    """
    if not path.exists():
        return {}
    payload = json.loads(path.read_text() or "{}")
    return payload if payload.get("metrics") else {}


def write_baseline(payload: dict, path: Path) -> Path:
    """Persist the champion's scores. Keys are written in a fixed order.

    Fixed order and 4-decimal rounding, both for the same reason: this file is
    committed, and a file whose byte content depends on dict iteration order
    produces diffs that say nothing.
    """
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
