"""Load testing, and counting a traffic split.

`split-measure` sends requests and counts which store version and revision answered each one.
`loadtest` sends them at rising concurrency and reports throughput, error rate and
p50/p95/p99. Both run inside the cluster as a Job, so the requests take the same route as real
traffic.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np

# A legal, ordinary patient: a load test measures the service, not the model.
PROBE_PATIENT = {
    "pregnancies": 6.0,
    "glucose": 148.0,
    "blood_pressure": 72.0,
    "skin_thickness": 35.0,
    "insulin": 125.0,
    "bmi": 33.6,
    "diabetes_pedigree": 0.627,
    "age": 50.0,
}


@dataclass
class LoadResult:
    concurrency: int
    requests: int
    wall_seconds: float
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter = field(default_factory=Counter)
    # (store_version, revision) -> count
    served_by: Counter = field(default_factory=Counter)

    @property
    def errors(self) -> int:
        return sum(count for status, count in self.statuses.items() if status != 200)

    @property
    def throughput(self) -> float:
        return self.requests / self.wall_seconds if self.wall_seconds else 0.0


def percentile(values: list[float], p: float) -> float:
    """The p-th percentile by nearest rank: always a latency some request really had."""
    if not values:
        return 0.0
    return float(np.percentile(values, p, method="inverted_cdf"))


async def _one_request(client: httpx.AsyncClient, result: LoadResult) -> None:
    started = time.perf_counter()
    try:
        response = await client.post("/predict", json=PROBE_PATIENT)
        status = response.status_code
        if status == 200:
            body = response.json()
            result.served_by[(body.get("store_version"), body.get("revision"))] += 1
    except httpx.HTTPError:
        # a refused connection counts as an error (status 0) instead of stopping the run
        status = 0
    result.latencies_ms.append((time.perf_counter() - started) * 1000)
    result.statuses[status] += 1


async def _run_async(
    base_url: str, host: str | None, requests: int, concurrency: int, timeout: float
) -> LoadResult:
    result = LoadResult(concurrency=concurrency, requests=requests, wall_seconds=0.0)
    headers = {"Host": host} if host else None
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        base_url=base_url, headers=headers, timeout=timeout, limits=limits
    ) as client:

        async def guarded() -> None:
            async with semaphore:
                await _one_request(client, result)

        started = time.perf_counter()
        await asyncio.gather(*(guarded() for _ in range(requests)))
        result.wall_seconds = time.perf_counter() - started
    return result


def run_load(
    base_url: str,
    *,
    host: str | None = None,
    requests: int = 200,
    concurrency: int = 1,
    timeout: float = 10.0,
) -> LoadResult:
    """Fire `requests` requests, at most `concurrency` in flight."""
    return asyncio.run(_run_async(base_url, host, requests, concurrency, timeout))


def summarise(result: LoadResult) -> dict[str, Any]:
    return {
        "concurrency": result.concurrency,
        "requests": result.requests,
        "wall_seconds": round(result.wall_seconds, 4),
        "throughput_rps": round(result.throughput, 1),
        "errors": result.errors,
        "error_rate": round(result.errors / result.requests, 4) if result.requests else 0.0,
        "p50_ms": round(percentile(result.latencies_ms, 50), 2),
        "p95_ms": round(percentile(result.latencies_ms, 95), 2),
        "p99_ms": round(percentile(result.latencies_ms, 99), 2),
        "statuses": dict(result.statuses),
        "served_by": {f"{v or '?'}/{r or '?'}": n for (v, r), n in result.served_by.items()},
    }


def format_load_table(rows: list[dict[str, Any]]) -> str:
    header = (
        f"  {'conc':>4} {'reqs':>5} {'wall':>8} {'rps':>8} {'errors':>7} "
        f"{'p50':>8} {'p95':>8} {'p99':>8}"
    )
    lines = ["", header, "  " + "-" * (len(header) - 2)]
    for row in rows:
        lines.append(
            f"  {row['concurrency']:>4} {row['requests']:>5} {row['wall_seconds']:>7.3f}s "
            f"{row['throughput_rps']:>8.1f} {row['errors']:>7} "
            f"{row['p50_ms']:>7.2f}ms {row['p95_ms']:>7.2f}ms {row['p99_ms']:>7.2f}ms"
        )
    return "\n".join(lines)


def format_split(summary: dict[str, Any], declared: int | None = None) -> str:
    """The measured split, beside the declared one and its sampling spread."""
    total = sum(summary["served_by"].values()) or 1
    lines = ["", f"  {total} responses, by store version / revision:", ""]
    for key, count in sorted(summary["served_by"].items(), key=lambda kv: -kv[1]):
        share = 100.0 * count / total
        lines.append(f"    {key:44} {count:>5}  {share:5.1f}%")
    if declared is not None:
        # standard error of a proportion: sqrt(p(1-p)/n)
        p = declared / 100.0
        se = (p * (1 - p) / total) ** 0.5 * 100
        lines += [
            "",
            f"  declared canary percentage: {declared}%   "
            f"expected sampling spread at n={total}: ±{se:.1f}% (1 s.e.)",
        ]
    if summary["errors"]:
        lines.append(f"  errors: {summary['errors']} of {summary['requests']}")
    return "\n".join(lines)


def format_against_release(rows: list[dict[str, Any]], max_p95_ms: float, max_error_rate: float) -> str:
    """Each concurrency level against the limits in release.yaml."""
    lines = ["", f"  against release.yaml: p95 under {max_p95_ms:g} ms, error rate at most {max_error_rate:g}"]
    for row in rows:
        ok = row["p95_ms"] <= max_p95_ms and row["error_rate"] <= max_error_rate
        lines.append(
            f"    concurrency {row['concurrency']:>3}: {row['throughput_rps']:>7.1f} rps, "
            f"p95 {row['p95_ms']:>8.2f} ms, errors {row['error_rate']:.2%}  "
            f"{'within' if ok else 'OVER'}"
        )
    return "\n".join(lines)
