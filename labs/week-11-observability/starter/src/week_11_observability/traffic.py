"""A traffic generator, so there is something to observe.

A dashboard with no data on it teaches nothing, and neither does an alert that
cannot be made to fire. This module produces a controlled, reproducible mix of
requests against the running service so that every panel has a shape and every
rule has something to evaluate.

IT IS NOT A LOAD TEST. `loadtest.py` (Week 10) answers "how fast, at what
concurrency, before it falls over"; it drives the service as hard as it can and
reports percentiles. This one deliberately drives it at a MODEST, STEADY RATE
and controls the MIX — some fraction of requests violating Week 5's contract,
some fraction hitting a route that does not exist — because what the observability
half of the week needs is not throughput but a signal with known composition.

Knowing the composition is the whole point. When the error-rate panel reads 5%
you want to be able to say "yes, because I asked for 5%" — otherwise you are
looking at a graph and hoping, which is the state this week exists to end.

WHY THE MIX MATTERS, one line each:

  * **valid** requests populate latency, RPS and the prediction histogram.
  * **contract violations** (glucose = 0, the sentinel Week 5 outlawed) produce
    422s. They are NOT 5xx, so they must leave the availability SLI untouched
    while lighting up `model_contract_violations_total` — the clearest possible
    demonstration that "error rate" is a decision about what counts, not a fact.
  * **not-found** requests produce 404s on an unmatched route. They are the
    cardinality experiment's ammunition: every one of them has a different path,
    and `route_label` collapses them all to one series. Turn that off and watch
    what happens.

Determinism: one seeded `random.Random`, so the same `--seed` and `--mix`
produce the same sequence of request kinds. A demonstration you cannot repeat is
an anecdote.
"""

from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

from .loadtest import PROBE_PATIENT

# A patient that fails the model-input contract in exactly one way: `glucose: 0`
# is the sentinel Week 5 identified as "missing, in disguise" and declared
# illegal with `pa.Field(gt=0, nullable=True)`. The 422 names the check
# (`greater_than(0)`), which becomes the `check` label on the violation counter.
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
    """Decide the kind of every request before sending any of them.

    Separated from the sending on purpose: it makes the composition a pure
    function of `(count, mix, seed)`, so `tests/test_traffic.py` can assert the
    proportions exactly without a server, a socket or a clock. The same split
    `loadtest.percentile` uses, and for the same reason — arithmetic that a test
    can reach is arithmetic you can trust.

    The mix is normalised rather than required to sum to 1, because a student
    typing `--mix valid=9,violation=1` should get 90/10 and not an error about
    fractions.
    """
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
        # template these collapse to one series; with the raw path as a label
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

    SYNCHRONOUS AND PACED, which is the opposite of `loadtest.py` and is the
    right choice here. A load test wants to saturate; this wants a steady,
    boring stream that makes a graph legible and a rate-based alerting rule
    evaluate against something realistic. Firing 300 requests as fast as
    possible would put them all inside one scrape interval, and Prometheus would
    show a single spike rather than a rate.

    The pacing is deliberately naive — sleep out whatever is left of each
    request's slot. It drifts under load and that is fine: the target is
    "roughly 20 a second for fifteen seconds", not a benchmark.
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
                # A transport failure is NOT a status code, and conflating the
                # two is how a load generator reports 100% availability for a
                # service that is not running. Counted separately and printed.
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
