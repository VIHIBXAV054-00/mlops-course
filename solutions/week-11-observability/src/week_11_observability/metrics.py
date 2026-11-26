"""Instrumentation: the request metrics, the model metrics and the JSON access log.

A label value must come from a small set you can write down. Anything unbounded goes in the log.
Run one worker per container: each uvicorn worker keeps its own counters.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client import REGISTRY as DEFAULT_REGISTRY

# Explicit buckets: 0.25 must be a boundary so the latency SLI in slo.yaml is exact.
LATENCY_BUCKETS = (
    0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
)

# the score is a probability, so its buckets are tenths
SCORE_BUCKETS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Prometheus scrapes /metrics forever, so it is not counted.
EXCLUDED_ROUTES = frozenset({"/metrics"})

# the route label for a request that matched no route (a 404)
UNMATCHED_ROUTE = "__unmatched__"


def build_metrics(registry: CollectorRegistry | None = None) -> dict[str, Any]:
    """Create this service's metric objects on `registry` (a fresh one per test)."""
    reg = registry if registry is not None else DEFAULT_REGISTRY

    return {
        # request metrics, as for any HTTP service
        "requests": Counter(
            "http_requests_total",
            "Total HTTP requests, by method, route template and status code.",
            ["method", "route", "status"],
            registry=reg,
        ),
        "latency": Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ["method", "route"],
            buckets=LATENCY_BUCKETS,
            registry=reg,
        ),
        # a gauge, because requests in flight go up and down
        "in_flight": Gauge(
            "http_requests_in_flight",
            "Requests currently being served.",
            registry=reg,
        ),
        # model metrics
        "predictions": Counter(
            "model_predictions_total",
            "Predictions returned, by predicted outcome.",
            ["outcome"],
            registry=reg,
        ),
        "score": Histogram(
            "model_prediction_score",
            "Distribution of predicted probabilities.",
            buckets=SCORE_BUCKETS,
            registry=reg,
        ),
        # A 422 is not counted against the SLO, but a rise means a caller changed.
        "violations": Counter(
            "model_contract_violations_total",
            "Requests rejected by the model-input contract, by failing check.",
            ["check"],
            registry=reg,
        ),
        # An info metric: always 1, with the model's identity in its labels.
        # model_version on http_requests_total would multiply its series.
        "info": Gauge(
            "model_info",
            "Always 1. The labels are the identity of the loaded model.",
            ["model_version", "store_version", "gate_verdict", "schema_version"],
            registry=reg,
        ),
    }


def route_label(request: Any) -> str:
    """The label value for a request's path: the route template, never the raw path."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if not path:
        return UNMATCHED_ROUTE
    return str(path)


def make_middleware(
    metrics: dict[str, Any],
    logger: logging.Logger,
) -> Callable[[Any, Callable[[Any], Awaitable[Any]]], Awaitable[Any]]:
    """Measure every request as metrics, and write one JSON log line with its request id."""

    async def instrument(request: Any, call_next: Callable[[Any], Awaitable[Any]]) -> Any:
        route = route_label(request)

        # The metrics endpoint does not measure itself. See EXCLUDED_ROUTES.
        if request.url.path in EXCLUDED_ROUTES:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        # the route handler can log the same id, so log lines can be joined
        request.state.request_id = request_id

        metrics["in_flight"].inc()
        started = time.perf_counter()
        status = 500  # reported if call_next raises
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - started
            metrics["in_flight"].dec()
            # Read after call_next: Starlette sets scope["route"] during routing.
            route = route_label(request)
            metrics["requests"].labels(
                method=request.method, route=route, status=str(status)
            ).inc()
            metrics["latency"].labels(method=request.method, route=route).observe(elapsed)

            # the log line has what no metric has: the request id and the full path
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 3),
                    },
                    sort_keys=True,
                )
            )

    return instrument


def build_logger(name: str = "week11.access") -> logging.Logger:
    """A logger that writes one JSON object per line to stdout.

    `propagate = False` stops uvicorn's root logger from printing each line twice.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def set_model_info(metrics: dict[str, Any], provenance: dict[str, Any], schema_version: str) -> None:
    """Publish the loaded model's identity as labels on `model_info`.

    Called once at startup. The value is always 1, the labels carry the identity.
    `or "unknown"` keeps a missing value from becoming the label "None".
    """
    metrics["info"].labels(
        model_version=str(provenance.get("model_version") or "unknown"),
        store_version=str(provenance.get("store_version") or "unknown"),
        gate_verdict=str(provenance.get("gate_verdict") or "unknown"),
        schema_version=schema_version,
    ).set(1)


def render(registry: CollectorRegistry | None = None) -> str:
    """The exposition format as text, for tests and `make metrics-show`."""
    return generate_latest(registry if registry is not None else DEFAULT_REGISTRY).decode()
