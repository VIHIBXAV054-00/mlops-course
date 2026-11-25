"""Batch versus online, measured.

No load-testing tool. A `for` loop over the test set, timed, reporting p50 and
p95 — which is all Exercise 3 needs and all Week 9 is allowed. Load profiles,
saturation curves and concurrency are Week 10.

One statistics note worth more than it looks: **the mean is the wrong summary
for latency.** Latency distributions have a long right tail, so the average is
dragged around by outliers and describes nobody's experience. Percentiles say
something a user would recognise: half of requests were faster than p50, and
one in twenty was slower than p95.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

import pandas as pd

from .config import Settings
from .schemas import FEATURE_COLUMNS


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(int(len(ordered) * fraction), len(ordered) - 1)
    return ordered[index]


def batch_score(model: Any, frame: pd.DataFrame) -> dict:
    """All rows, one call. What `make predict` does."""
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


def online_score(client: Any, frame: pd.DataFrame, url: str = "/predict") -> dict:
    """One HTTP request per row, timed individually.

    `client` is anything with a `.post(url, json=...)` — httpx, requests, or
    FastAPI's TestClient, which is what makes this runnable with no server.
    """
    payloads = frame[list(FEATURE_COLUMNS)].to_dict(orient="records")
    latencies: list[float] = []

    start = time.perf_counter()
    for payload in payloads:
        request_start = time.perf_counter()
        client.post(url, json=payload)
        latencies.append((time.perf_counter() - request_start) * 1000)
    elapsed = time.perf_counter() - start

    return {
        "mode": "online",
        "rows": len(payloads),
        "wall_clock_s": round(elapsed, 4),
        "rows_per_second": round(len(payloads) / elapsed, 1),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "max_ms": round(max(latencies), 2),
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
            "",
            "  That is not overhead you can optimise away — it is the cost of asking",
            "  the question one row at a time, over a protocol, with validation on",
            "  every request. You buy it deliberately: batch cannot answer a question",
            "  nobody has asked yet, and online can.",
        ]
    )


def run_bench(settings: Settings) -> dict:
    """Both modes, against the same rows and the same model, in one process."""
    import joblib
    from fastapi.testclient import TestClient

    from .api import create_app
    from .data import load_measurements

    frame = load_measurements(settings.processed_dir / "test.csv")
    model = joblib.load(settings.models_dir / "model.pkl")

    batch = batch_score(model, frame)
    online = online_score(TestClient(create_app()), frame)
    return {"batch": batch, "online": online}
