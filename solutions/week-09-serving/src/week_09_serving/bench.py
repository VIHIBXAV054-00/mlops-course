"""Batch versus online scoring, measured on the same rows with the same model.

Run it with `make bench`. Plumbing for the output is at the bottom of the file.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

import pandas as pd

from .config import Settings
from .schemas import FEATURE_COLUMNS


def batch_score(model: Any, frame: pd.DataFrame) -> dict:
    """All rows in one call, as the evaluate stage does."""
    features = frame[list(FEATURE_COLUMNS)]
    start = time.perf_counter()
    model.predict_proba(features)
    elapsed = time.perf_counter() - start
    return {
        "mode": "batch",
        "rows": len(features),
        "wall_clock_s": round(elapsed, 4),
        "rows_per_second": round(len(features) / elapsed, 1),
    }


def to_payloads(frame: pd.DataFrame) -> list[dict]:
    """One request body per row. A missing value (NaN) becomes None, sent as JSON null."""
    rows = frame[list(FEATURE_COLUMNS)].to_dict(orient="records")
    return [{key: None if pd.isna(value) else value for key, value in row.items()} for row in rows]


def online_score(client: Any, frame: pd.DataFrame, url: str = "/predict") -> dict:
    """One request per row, each request timed on its own.

    `client` is anything with `.post(url, json=...)`: httpx, requests, or
    FastAPI's TestClient, which runs the app without a server.
    """
    payloads = to_payloads(frame)
    latencies: list[float] = []
    failed = 0

    start = time.perf_counter()
    for payload in payloads:
        request_start = time.perf_counter()
        response = client.post(url, json=payload)
        latencies.append((time.perf_counter() - request_start) * 1000)
        failed += response.status_code != 200
    elapsed = time.perf_counter() - start

    cuts = statistics.quantiles(latencies, n=100, method="inclusive")
    return {
        "mode": "online",
        "rows": len(payloads),
        "wall_clock_s": round(elapsed, 4),
        "rows_per_second": round(len(payloads) / elapsed, 1),
        "p50_ms": round(cuts[49], 2),
        "p95_ms": round(cuts[94], 2),
        "max_ms": round(max(latencies), 2),
        "failed": failed,
    }


def format_comparison(batch: dict, online: dict) -> str:
    ratio = online["wall_clock_s"] / batch["wall_clock_s"] if batch["wall_clock_s"] else 0
    return "\n".join(
        [
            f"  {'':<10} {'rows':>6} {'wall clock':>12} {'rows/s':>10} {'p50':>9} {'p95':>9}",
            f"  {'-' * 10} {'-' * 6} {'-' * 12} {'-' * 10} {'-' * 9} {'-' * 9}",
            f"  {'batch':<10} {batch['rows']:>6} {batch['wall_clock_s']:>11.4f}s "
            f"{batch['rows_per_second']:>10} {'—':>9} {'—':>9}",
            f"  {'online':<10} {online['rows']:>6} {online['wall_clock_s']:>11.4f}s "
            f"{online['rows_per_second']:>10} {online['p50_ms']:>8.2f}ms {online['p95_ms']:>8.2f}ms",
            "",
            f"  Online took {ratio:.0f}x the wall clock for the same {batch['rows']} rows.",
            *([f"  {online['failed']} online requests failed, so the two rows do not score "
               "the same patients."] if online.get("failed") else []),
        ]
    )


def run_bench(settings: Settings) -> dict:
    """Both modes, on the test rows and the model from `make repro`, in one process.

    The rows go through the same conversion as in training: a sentinel zero becomes
    a missing value, which batch passes as NaN and online sends as null.
    """
    import joblib
    from fastapi.testclient import TestClient

    from .api import create_app
    from .data import load_measurements
    from .pipeline import prepare_model_input

    frame, _, _ = prepare_model_input(load_measurements(settings.processed_dir / "test.csv"))
    model = joblib.load(settings.models_dir / "model.pkl")

    batch = batch_score(model, frame)
    online = online_score(TestClient(create_app()), frame)
    return {"batch": batch, "online": online}
