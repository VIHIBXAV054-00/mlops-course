"""Instrumentation: what this service tells the outside world about itself.

For ten weeks this project has been checked AT MOMENTS. The gate checks at
training time, CI at commit time, the smoke test at deploy time. In between —
which is where the model spends essentially all of its life — nothing was
looking.

This module is the other half. It is about forty lines of actual measurement,
and the reason it is not two lines of `prometheus-fastapi-instrumentator` is
that the interesting decisions are all in the label choices, and a package that
makes them for you is a package that hides the week's subject.

THREE IDEAS, and everything here is one of them.

1. **A metric is a number with dimensions.** `http_requests_total` is not one
   number; it is one number per combination of `method`, `route` and `status`.
   Those labels are the questions you will be able to ask later. Labels you did
   not add are questions you cannot ask, and labels you added carelessly are a
   bill you did not know you were signing (see CARDINALITY below).

2. **Counters only go up, and are never read raw.** A counter's value is
   meaningless — it depends on when the process started. `rate(x[5m])` is what
   you graph, and it is defined precisely so that a process restart (the counter
   going back to 0) is handled as a reset rather than as a gigantic negative
   spike.

3. **A histogram is buckets, not percentiles.** The service counts how many
   requests fell into `<=5ms`, `<=10ms`, `<=25ms` and so on, and Prometheus
   computes the percentile from those counts at query time. This looks like a
   detour and it is the only thing that works: **percentiles do not average.**
   You cannot take the mean of three replicas' p95 and get the fleet's p95, but
   you can add up their buckets and get exactly the right answer.

CARDINALITY — the one that bites, and `make cardinality` measures it.

The number of time series is the PRODUCT of the number of distinct values of
every label. `method` has ~2 values here, `route` has ~5, `status` maybe 4: at
most a few dozen series, and Prometheus is happy for years. Add one label whose
value is the patient's age and you have multiplied by ~50. Add a request id and
you have multiplied by the number of requests you will ever serve — every one of
them a series held in the collector's memory, forever, and none of them ever
observed twice.

The rule that follows: **a label value must come from a small, bounded set you
can write down.** If you cannot enumerate it, it belongs in a log line, where
unbounded cardinality is free. That sentence is the entire logs-vs-metrics
distinction, and it is worth more than the three-pillars diagram.

MULTIPLE PROCESSES — stated here because the failure is silent.

`prometheus_client`'s default registry lives in this process's memory. Run four
uvicorn workers behind one port and each has its own counters; a scrape is
answered by whichever worker accepted the connection, so the value Prometheus
records hops between four unrelated series and appears to go DOWN — which
`rate()` reads as a restart. The library has a `multiprocess` mode for it. This
lab does not use it: **one worker per container, scale with containers.**
`make workers-trap` reproduces the symptom in about a minute.
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

# ── Bucket boundaries ────────────────────────────────────────────────────────
#
# EXPLICIT, not the library default, and the two reasons are different.
#
# The default buckets (.005 … 10 seconds) are tuned for a generic web service.
# This one answers in single-digit milliseconds (Week 9 measured p50 3.95 ms,
# p95 7.17 ms in-process), so half the default buckets are above anything we
# will ever see and the interesting region has almost no resolution.
#
# The second reason is the one that matters more: `slo.yaml` declares a latency
# threshold of 0.25 s, and an SLI defined as "the fraction of requests faster
# than the threshold" is only EXACT if the threshold is a bucket boundary. Ask
# for a boundary that does not exist and `histogram_quantile` interpolates
# linearly inside whichever bucket contains it — a straight-line guess about a
# distribution that is not a straight line.
#
# tests/test_metrics.py asserts 0.25 is in this tuple and that it matches
# slo.yaml. Change one without the other and the suite goes red rather than the
# dashboard going subtly wrong.
LATENCY_BUCKETS = (
    0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
)

# The prediction score is a probability, so its buckets are just the unit
# interval in tenths. Week 11 only ever describes this as "the shape of what we
# predict" — comparing that shape against a reference window is drift, and drift
# is Week 12.
SCORE_BUCKETS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Requests to the metrics endpoint itself are NOT counted. Prometheus scrapes
# every 15 seconds forever, so leaving it in adds a permanent 0.067 rps floor to
# every RPS graph and puts the collector in its own error budget. Observing a
# system perturbs it; the least you can do is not measure the thermometer.
EXCLUDED_ROUTES = frozenset({"/metrics"})

# The label value used when a request matched no route at all (a 404). Without
# this, the raw path of every scan and typo becomes its own time series — which
# is unbounded cardinality arriving through the back door, sourced from the
# public internet, chosen by strangers.
UNMATCHED_ROUTE = "__unmatched__"


def build_metrics(registry: CollectorRegistry | None = None) -> dict[str, Any]:
    """Create this service's metric objects.

    Takes a registry so tests can build a FRESH one per test. The default
    registry is global and a `Counter` registered twice under the same name
    raises `Duplicated timeseries in CollectorRegistry` — which is the correct
    behaviour for a process and a nuisance for a test suite, so the seam exists.
    """
    reg = registry if registry is not None else DEFAULT_REGISTRY

    return {
        # ── The three that any HTTP service should have ───────────────────────
        #
        # `_total` is the convention for a counter, and prometheus_client appends
        # it for you: declare `http_requests` and the exposed name is
        # `http_requests_total`. Declaring it WITH the suffix (as here) is also
        # accepted and is clearer, because the name in the code then matches the
        # name in the PromQL.
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
        # A GAUGE, because it goes both ways. This is the number a counter
        # structurally cannot give you: how many requests are in flight right
        # now. It is also the one that identifies a saturated service — Week
        # 10's load test showed throughput flat while latency grew, and this is
        # the metric that says the requests are queued rather than lost.
        "in_flight": Gauge(
            "http_requests_in_flight",
            "Requests currently being served.",
            registry=reg,
        ),
        # ── The three that make this an ML service ────────────────────────────
        #
        # Everything above would be identical for a service that returned the
        # weather. These three are why "monitor your model" is not the same
        # instruction as "monitor your server".
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
        # Week 5's contract, aggregated. A 422 is the service working correctly
        # — it refused an impossible patient — so it is deliberately NOT counted
        # against the availability SLO. But a RISE in this number means a caller
        # started sending different data, which is a genuine incident that no
        # generic web dashboard would ever surface. It gets its own alert.
        "violations": Counter(
            "model_contract_violations_total",
            "Requests rejected by the model-input contract, by failing check.",
            ["check"],
            registry=reg,
        ),
        # THE INFO-METRIC PATTERN: a gauge that is always 1, carrying identity
        # in its labels.
        #
        # Why not put `model_version` on http_requests_total instead? Because it
        # would multiply the cardinality of the busiest metric in the system by
        # the number of versions you will ever deploy, and because it would
        # change what the counter MEANS — a deploy would look like a traffic
        # drop, since the old series stops and a new one starts at zero.
        #
        # This is link ten of the traceability chain. The dashboard can now name
        # the model behind the graph, so a latency step change can be attributed
        # to a deployment without leaving the browser.
        "info": Gauge(
            "model_info",
            "Always 1. The labels are the identity of the loaded model.",
            ["model_version", "store_version", "gate_verdict", "schema_version"],
            registry=reg,
        ),
    }


def route_label(request: Any) -> str:
    """The label value for a request's path.

    TODO(student) Exercise 1: return the route template instead of the raw
    path. Starlette leaves the matched route in `request.scope["route"]`, and
    its `path` attribute is the pattern from the decorator, such as
    `/v1/models/{model_name}:predict`. A request that matched no route has no
    `route` in its scope: return UNMATCHED_ROUTE for it.
    Reference: https://www.starlette.io/routing/
    """
    return request.url.path


def make_middleware(
    metrics: dict[str, Any],
    logger: logging.Logger,
) -> Callable[[Any, Callable[[Any], Awaitable[Any]]], Awaitable[Any]]:
    """The measurement itself: one function, wrapped around every request.

    It emits TWO THINGS for the same event, and the pair is the whole
    logs-vs-metrics slide made concrete:

      * metric observations — aggregate, bounded, cheap, and unable to tell you
        anything about ONE request;
      * one structured JSON log line — per request, carrying a `request_id`,
        which as a metric label would be a catastrophe and as a log field is
        free.

    Neither is a substitute for the other, and noticing that is most of what
    "the three pillars" is trying to say.
    """

    async def instrument(request: Any, call_next: Callable[[Any], Awaitable[Any]]) -> Any:
        # The metrics endpoint does not measure itself. See EXCLUDED_ROUTES.
        if request.url.path in EXCLUDED_ROUTES:
            return await call_next(request)

        request_id = str(uuid.uuid4())
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

            # TODO(student) Exercise 1: record the request in two metrics.
            # Increment `metrics["requests"]` with its labels method, route and
            # status (as a string). Observe `elapsed` on `metrics["latency"]`
            # with its labels method and route. The declarations in
            # build_metrics() above list the label names.
            # Reference: https://prometheus.github.io/client_python/instrumenting/labels/

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
    """A logger that writes ONE JSON OBJECT PER LINE to stdout, and nothing else.

    Three decisions, all conventional and all worth knowing:

      * **JSON, not a formatted sentence.** `docker compose logs api | jq` works
        on this; a grep for `status=5..` works on a sentence right up until
        somebody reorders the fields.
      * **stdout, not a file.** The container writes to stdout and the platform
        decides where logs go. A process that manages its own log files has
        made a decision that belongs to whoever is running it (and will fill a
        disk on a machine it has never met).
      * **`propagate = False`.** Otherwise every line is emitted twice — once by
        this handler and once by the root logger uvicorn configures. Duplicated
        log lines are the sort of thing everyone learns to live with, which is
        worse than fixing it.
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

    Called once at startup. The value is always 1; the labels carry the
    identity. `or "unknown"` keeps a missing value from becoming the label
    "None".
    """
    metrics["info"].labels(
        model_version=str(provenance.get("model_version") or "unknown"),
        store_version=str(provenance.get("store_version") or "unknown"),
        gate_verdict=str(provenance.get("gate_verdict") or "unknown"),
        schema_version=schema_version,
    ).set(1)


def render(registry: CollectorRegistry | None = None) -> str:
    """The exposition format, as text. Used by tests and by `make metrics-show`.

    Worth reading once rather than taking on trust — it is a text format, one
    sample per line, and everything Prometheus knows about your service arrived
    through it:

        # HELP http_requests_total Total HTTP requests, by ...
        # TYPE http_requests_total counter
        http_requests_total{method="POST",route="/predict",status="200"} 42.0

    A histogram is not one line but many: one `_bucket` per boundary (cumulative
    — `le="0.25"` counts everything at or below 250 ms, not just that bucket),
    plus `_sum` and `_count`. That is why a histogram with eleven buckets and
    two labels is not one time series but dozens, and why bucket boundaries are
    a cost as well as a resolution.
    """
    return generate_latest(registry if registry is not None else DEFAULT_REGISTRY).decode()
