"""A traffic generator: a steady, seeded mix of requests so the dashboards and alerts have data.

It is not a load test (`loadtest.py` is). It sends requests at a modest rate with a known mix:

    valid       POST /predict, fills latency, request rate and the prediction histogram
    violation   glucose = 0, a 422 that counts as a contract violation, not a 5xx
    v1          the same patient through the V1 route
    notfound    a 404 on a different path every time, to test the route label
    health      GET /health

The same `--seed` and `--mix` send the same sequence of request kinds.
"""

from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

from .loadtest import PROBE_PATIENT

# fails one contract check: glucose 0 is a missing value, so the API returns 422
ILLEGAL_PATIENT = {**PROBE_PATIENT, "glucose": 0.0}


@dataclass
class TrafficResult:
    """What was sent, and what came back."""

    requests: int = 0
    wall_seconds: float = 0.0
    statuses: Counter = field(default_factory=Counter)
    kinds: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.requests / self.wall_seconds if self.wall_seconds else 0.0

    def summary(self) -> str:
        lines = [
            f"  sent      : {self.requests} requests in {self.wall_seconds:.1f}s "
            f"({self.rate:.1f}/s)",
            "  by kind   : "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(self.kinds.items())),
            "  by status : "
            + ", ".join(f"{status}={count}" for status, count in sorted(self.statuses.items())),
        ]
        if self.errors:
            lines.append(f"  transport : {len(self.errors)} failed to send, e.g. {self.errors[0]}")
        return "\n".join(lines)


def plan(count: int, mix: dict[str, float], seed: int = 42) -> list[str]:
    """Decide the kind of every request before sending any. Weights need not sum to 1."""
    if count <= 0:
        return []
    kinds = sorted(mix)
    weights = [max(0.0, float(mix[kind])) for kind in kinds]
    total = sum(weights)
    if total <= 0:
        raise ValueError("traffic mix must give at least one kind a positive weight.")
    rng = random.Random(seed)
    return rng.choices(kinds, weights=weights, k=count)


def _request_for(kind: str, index: int) -> tuple[str, str, dict[str, Any] | None]:
    """(method, path, json body) for one request of the given kind."""
    if kind == "valid":
        return "POST", "/predict", PROBE_PATIENT
    if kind == "violation":
        return "POST", "/predict", ILLEGAL_PATIENT
    if kind == "v1":
        return "POST", "/v1/models/diabetes:predict", {"instances": [PROBE_PATIENT]}
    if kind == "notfound":
        # A different path every time. With `route_label` returning the route
        # template these collapse to one series. With the raw path as a label
        # they are `index` separate series.
        return "GET", f"/does-not-exist/{index}", None
    if kind == "health":
        return "GET", "/health", None
    raise ValueError(
        f"unknown traffic kind {kind!r}; expected one of "
        "valid, violation, v1, notfound, health."
    )


def generate(
    url: str,
    count: int = 300,
    mix: dict[str, float] | None = None,
    rate: float = 20.0,
    seed: int = 42,
    timeout: float = 10.0,
) -> TrafficResult:
    """Send `count` requests at roughly `rate` per second and report the mix.

    Paced, not as fast as possible, so the requests spread over many scrapes.
    """
    mix = mix or {"valid": 0.9, "violation": 0.1}
    kinds = plan(count, mix, seed=seed)
    result = TrafficResult()
    interval = 1.0 / rate if rate > 0 else 0.0

    started = time.perf_counter()
    with httpx.Client(base_url=url.rstrip("/"), timeout=timeout) as client:
        for index, kind in enumerate(kinds):
            slot_started = time.perf_counter()
            method, path, body = _request_for(kind, index)
            try:
                response = client.request(method, path, json=body)
                result.statuses[response.status_code] += 1
            except httpx.HTTPError as exc:
                # a transport failure is not a status code, so it is counted separately
                result.errors.append(f"{type(exc).__name__}: {exc}")
                result.statuses["transport-error"] += 1
            result.kinds[kind] += 1
            result.requests += 1
            elapsed = time.perf_counter() - slot_started
            if interval > elapsed:
                time.sleep(interval - elapsed)
    result.wall_seconds = time.perf_counter() - started
    return result


def parse_mix(text: str) -> dict[str, float]:
    """`"valid=9,violation=1"` -> `{"valid": 9.0, "violation": 1.0}`."""
    mix: dict[str, float] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(
                f"cannot parse traffic mix {text!r}: expected `kind=weight` pairs, "
                "e.g. 'valid=9,violation=1'."
            )
        kind, _, weight = part.partition("=")
        if not kind.strip():
            raise ValueError(
                f"cannot parse traffic mix {text!r}: {part!r} has no kind before the `=`."
            )
        mix[kind.strip()] = float(weight)
    if not mix:
        raise ValueError(f"traffic mix {text!r} is empty.")
    return mix
