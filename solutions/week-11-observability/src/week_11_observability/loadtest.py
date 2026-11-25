"""Load testing, and measuring a traffic split.

Two questions, one instrument, because they are the same measurement read two
ways:

  * **Where does the traffic go?** Send N requests and tally which revision
    answered. A `canaryTrafficPercent: 10` you cannot count is a comment.
  * **What does it do under concurrency?** Send N requests C at a time and
    report throughput, error rate and p50/p95/p99. Week 9 measured one request
    at a time and deliberately stopped there; concurrency is where a service
    finds out what it actually promised.

WHY NOT `hey`, `k6` OR `locust`. KServe's own docs reach for `hey`, and in
production you should too — they are better tools than this file. Three reasons
to write ~100 lines instead, and the third is the important one:

  1. No new host tool. The course already installed `kind` and `kubectl` this
     term, and `httpx` has been in the lock since Week 8.
  2. **It runs INSIDE the cluster, as a Job.** Week 9's most expensive lesson
     was that `kubectl port-forward` is not a load balancer — it forwards to one
     pod and holds a connection to it, so measuring a rollout through it
     measures the forward. Every number in this module is taken from a pod, over
     the cluster-local address, through the same route real traffic uses.
  3. **It attributes every response to a revision.** A generic load generator
     reports "200 OK" 500 times; this one reports which model version produced
     each of them, which is what makes a canary observable rather than
     declared.

ON THE ARITHMETIC. `percentile` is a pure function over a list, so the maths is
unit-tested offline against known inputs (`tests/test_loadtest.py`) rather than
trusted because the output looked plausible. Percentiles, never a mean: Week 9's
note holds, and it holds harder under concurrency, where the tail is the part
that moves.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

# The one patient every request in a load test sends. Deliberately a legal,
# unremarkable row: a load test measures the SERVICE, so the payload must not
# be the interesting variable. Contract rejection is the smoke test's job.
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
    # (store_version, revision) -> count. The canary tally.
    served_by: Counter = field(default_factory=Counter)

    @property
    def errors(self) -> int:
        return sum(count for status, count in self.statuses.items() if status != 200)

    @property
    def throughput(self) -> float:
        return self.requests / self.wall_seconds if self.wall_seconds else 0.0


def percentile(values: list[float], p: float) -> float:
    """The p-th percentile by nearest-rank, on a copy, sorted.

    Nearest-rank rather than interpolation: with a few hundred samples the
    difference is noise, and a percentile that is an ACTUAL OBSERVED REQUEST is
    easier to defend in a conversation than an interpolated one that nobody
    experienced. Say which definition you used — there are nine in common use.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    # Nearest-rank: the smallest value at or above which p% of the samples lie.
    rank = math.ceil(p / 100.0 * len(ordered))
    rank = min(max(rank, 1), len(ordered))
    return ordered[rank - 1]


async def _one_request(client: httpx.AsyncClient, result: LoadResult) -> None:
    started = time.perf_counter()
    try:
        response = await client.post("/predict", json=PROBE_PATIENT)
        status = response.status_code
        if status == 200:
            body = response.json()
            result.served_by[(body.get("store_version"), body.get("revision"))] += 1
    except httpx.HTTPError:
        # A connection refused during a rollout IS the measurement. Recording it
        # as status 0 keeps it in the error rate instead of crashing the run and
        # losing every sample taken so far.
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
    """The measured split, beside the declared one.

    Prints the arithmetic rather than a verdict, because the honest reading of a
    small sample is a range and not a number.
    """
    total = sum(summary["served_by"].values()) or 1
    lines = ["", f"  {total} responses, by store version / revision:", ""]
    for key, count in sorted(summary["served_by"].items(), key=lambda kv: -kv[1]):
        share = 100.0 * count / total
        lines.append(f"    {key:44} {count:>5}  {share:5.1f}%")
    if declared is not None:
        # Standard error of a proportion: sqrt(p(1-p)/n). Quoted so the "why is
        # it not exactly 10%" conversation has a number in it.
        p = declared / 100.0
        se = (p * (1 - p) / total) ** 0.5 * 100
        lines += [
            "",
            f"  declared canary share: {declared}%   "
            f"expected sampling spread at n={total}: ±{se:.1f}% (1 s.e.)",
        ]
    if summary["errors"]:
        lines.append(f"  errors: {summary['errors']} of {summary['requests']}")
    return "\n".join(lines)
