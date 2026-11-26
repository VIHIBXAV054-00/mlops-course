# Week 11 Lab — Reference Solution

**Observability**: instrumentation, the exposition format, Prometheus, PromQL, dashboards as code,
SLIs, SLOs, error budgets, burn-rate alerting, and alert fatigue.

Canonical tutorials followed:

- Prometheus getting started — https://prometheus.io/docs/prometheus/latest/getting_started/
- Instrumentation, naming/labels, histograms —
  https://prometheus.io/docs/practices/instrumentation/ ·
  https://prometheus.io/docs/practices/naming/ · https://prometheus.io/docs/practices/histograms/
- Rule unit testing (`promtool test rules`) —
  https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/
- `prometheus_client` (Python) — https://prometheus.github.io/client_python/
- Grafana provisioning — https://grafana.com/docs/grafana/latest/administration/provisioning/
- Google SRE Workbook, *Implementing SLOs* / *Alerting on SLOs* —
  https://sre.google/workbook/implementing-slos/ · https://sre.google/workbook/alerting-on-slos/

**Required deviations, one line each:**

1. **Hand-written middleware instead of `prometheus-fastapi-instrumentator`.** The package would
   produce these metrics in two lines and teach nothing about label choice, which is the part of
   instrumentation that is actually a decision.
2. **A plain `/metrics` route instead of the documented `make_asgi_app()` mount** — measured below;
   the mount makes a bare `GET /metrics` a 307 redirect.
3. **Alertmanager is not installed.** Prometheus evaluates the rules and shows pending/firing itself;
   routing an alert to a human is Week 13's subject.
4. **Grafana is provisioned from files**, with anonymous Editor access as a classroom convenience, so
   students can edit a panel in the UI and copy the dashboard JSON into the file. `grafana/grafana.ini`
   turns off Grafana 13's new dashboard layouts, so the JSON offered on save is in the classic format
   of the provisioned file.
5. **`promtool` is run from inside the Prometheus image**, so this week adds no host tool.

## Changes from starter

| Area | What the starter leaves as `TODO(student)` |
| :--- | :--- |
| `src/…/metrics.py` | `route_label`, and the two metric updates in the middleware (Ex. 1) |
| `src/…/api.py` | the contract-violation count and the two model-level observations (Ex. 1) |
| `prometheus/prometheus.yml` | the `diabetes-api` scrape job (Ex. 2) |
| `grafana/dashboards/*.json` | the "Predictions by outcome" panel, added in the Grafana UI (Ex. 3) |
| `prometheus/rules/service.yml` | the "not alerted on" list |
| `tests/` | the Week 11 test bodies are intact; the starter skips them per exercise |

Everything from Weeks 4–10 is carried forward unchanged: the DVC pipeline, both contracts, the
release gate, MLflow linkage, `ruff`, the marker axes, both workflows, the Prefect flow, the API,
`serve.Dockerfile`, the model store, the KServe manifests, `smoke.py` and `loadtest.py`.

## Prerequisites

**Stop the Week 10 cluster and bring the Compose stack back.** This is the reverse of last week, and
it is worth saying out loud because the Week 10 README says the opposite:

```bash
kind delete cluster --name mlops          # Istio + Knative + KServe were using ~2.3 GiB
cd ../../week-10-kserve-rollout/solution && make down
```

Nothing this week needs Kubernetes. The thing being observed is a container.

**No new host tool.** Prometheus and Grafana are containers; `promtool` ships inside the Prometheus
image and is invoked through `docker compose run`.

**One newly declared Python dependency, and zero newly installed ones.** `prometheus-client` has been
in `uv.lock` since Week 8 at **0.26.0** because Prefect depends on it. Declaring it moved the lock by
**exactly two lines** and added **no packages**:

```
4542a4543
>     { name = "prometheus-client" },
4569a4571
>     { name = "prometheus-client", specifier = ">=0.26.0" },
```

Check for yourself with `uv tree --package prometheus-client --invert`. For three weeks this project
has shipped a metrics library and exposed not one metric.

## Running the solution

```bash
cp .env.example .env
make up                 # postgres, s3, mlflow, prefect, prometheus, grafana
make repro && make register && make promote-champion   # the model, as usual
make image              # builds diabetes-api:local — REFUSES on a non-GO gate verdict
make api-up             # the service to observe (Compose profile `api`)
make traffic            # something to look at
```

Ports: Prometheus **5560**, Grafana **5561**, the API **5562**. (MLflow 5500, Silo 5510/5511,
Prefect 5520, Postgres 5532 as before; Week 9 took 5540–5543 and Week 10 took 5550.)

**The scrape target is DOWN when you first run `make up`, and that is the point.** The `api` service
sits behind a Compose profile, so `up{job="diabetes-api"}` is 0 before you have instrumented
anything — the first metric, the first alert, and the cheapest possible demonstration that a
pull-based collector has an opinion about whether your service exists.

---

## Exercise 1 — instrument the service, and read the wire format

No Docker, no Prometheus, one second per iteration: `make serve-api` on the host, or `make
metrics-show` entirely in-process. Real output, five requests in (three valid, one contract
violation, one unmatched path):

```text
    # HELP http_requests_total Total HTTP requests, by method, route template and status code.
    # TYPE http_requests_total counter
    http_requests_total{method="GET",route="/health",status="200"} 1.0
    http_requests_total{method="POST",route="/predict",status="200"} 3.0
    http_requests_total{method="POST",route="/predict",status="422"} 1.0
    http_requests_total{method="GET",route="__unmatched__",status="404"} 1.0
    # HELP http_request_duration_seconds HTTP request latency in seconds.
    # TYPE http_request_duration_seconds histogram
    http_request_duration_seconds_bucket{le="0.0025",method="POST",route="/predict"} 0.0
    http_request_duration_seconds_bucket{le="0.005",method="POST",route="/predict"}  2.0
    http_request_duration_seconds_bucket{le="0.01",method="POST",route="/predict"}   3.0
    …
    http_request_duration_seconds_bucket{le="+Inf",method="POST",route="/predict"}   4.0
    http_request_duration_seconds_count{method="POST",route="/predict"}              4.0
    http_request_duration_seconds_sum{method="POST",route="/predict"}                0.0421
```

Three things to notice, and the third is the week:

- A histogram is **not one line**. One `_bucket` per boundary — **cumulative**, so `le="0.25"`
  already counts everything at or below 250 ms — plus `_sum` and `_count`. Eleven boundaries times
  two labels is not one time series but dozens, so bucket boundaries are a cost as well as a
  resolution.
- **`/metrics` does not appear.** It does not measure itself. Prometheus scrapes forever, so leaving
  it in adds a permanent floor to every RPS graph and puts the collector inside your own error budget.
- The `route` label is the **template**, and the unmatched path collapsed to a single constant.

### Two traps met while building this, both measured

**Mounting `/metrics` gives you a redirect.** `prometheus_client` documents
`app.mount("/metrics", make_asgi_app())`, and that is what this lab tried first:

```text
GET /metrics   -> 307  Location: http://testserver/metrics/
GET /metrics/  -> 200  text/plain; version=0.0.4; charset=utf-8
```

A Starlette `Mount` is a *directory*, so the router redirects the bare path. Prometheus follows
redirects, so it works — and pays a round trip every scrape forever, while `curl localhost:5562/metrics`
prints nothing at all without `-L`. Neither is a bug in the library. The lab serves the library's own
`generate_latest()` from a plain route instead, keeping the exposition format and losing only gzip
negotiation on a few kilobytes over a local network.

**`create_app()` twice raises `DuplicateTimeseries`,** because a registry is a namespace and the
default one is a process global. Found the direct way: 23 previously green tests went red the moment
the counters were added. `create_app` now takes a registry and defaults to a **private** one; the
served app at the bottom of `api.py` passes the global `REGISTRY` explicitly, which is also what
brings in `process_*`, `python_gc_*` and `python_info` for free:

```text
python_info{implementation="CPython",major="3",minor="12",patchlevel="13",version="3.12.13"} 1.0
process_resident_memory_bytes 2.39099904e+08
model_info{gate_verdict="GO",model_version="unknown",schema_version="1.0.0",store_version="unknown"} 1.0
```

The general shape is worth keeping: **process-global state is a decision, so make it something a
caller opts into rather than something they inherit.**

### The cardinality experiment

`make cardinality` sends the same requests twice, changing only the label expression. With the
default 50 requests of each kind:

```text
  route = the route TEMPLATE  ->      2 time series
        http_requests_total{method="GET",route="__unmatched__",status="404"}
        http_requests_total{method="POST",route="/predict",status="200"}

  route = the RAW PATH        ->     51 time series
```

Before `route_label` is fixed, both runs print 51. The template count is **constant in the number of
requests**; the raw-path count **grows with it**. For a public endpoint the number of distinct paths
is chosen by whoever is scanning you. Cardinality is **multiplicative** across labels, it is paid in
the **collector's** memory rather than the application's, and each series is kept for the whole
retention period.

> **A label value must come from a small set you can write down.** If you cannot list it, it belongs
> in a log line.

---

## Exercise 2 — scrape it, and ask it questions

`make image` then `make api-up`, and watch `http://127.0.0.1:5560/targets` go from DOWN to UP.

**Two changes to `make image` this week, and the investigation behind them is worth more than either.**

Weeks 9 and 10 set `DOCKER_BUILDKIT=0` to keep the build log plain for a classroom. On **Docker
Engine 29.6.2** this target printed the legacy builder's deprecation banner and then produced nothing
at all for **26 minutes**.

**The first diagnosis was wrong, and that is the part worth keeping.** It looked exactly like a
deprecated flag hanging, and that is what got written down. Then the killed process's stderr arrived:

```text
Can't add file .../solution/.dvc to tar: io: read/write on closed pipe
```

It was never stuck. It was building the **context tarball**. `du -sh .` in this directory was
**783 MB, of which 780 MB was `.venv/`** — and there was no `.dockerignore`. `docker build` uploads
the entire context to the daemon *before* the first instruction runs, and the legacy builder does
that as one serial tar with no progress output until it completes.

Re-measured against an **empty** context, `DOCKER_BUILDKIT=0` builds `FROM alpine` + `RUN echo hi` in
**5.6 seconds**. It does not hang. And with the `.dockerignore` this week adds, the context is
**2.9 MB** and the *legacy* builder finishes this very image in **37 seconds**.

So: BuildKit is still the right default — the legacy builder's removal is announced, and
`--progress=plain` gives back the plain log the flag was being kept for. But note which of the two
changes was the actual fix. **BuildKit did not solve the oversized context; it hid it**, which is how
783 MB survived from Week 9 to Week 11 without anyone noticing. Week 9 wrote *"a build context is
exactly what you put in it"* when `README.md` was **missing** from it; this is the same sentence
arriving from the other end of the range, and the fast tool is the one that let it hide.

Then `make traffic` produces something to look at, with a **known composition** — which is the whole
point of it not being a load test:

```text
  target : http://127.0.0.1:5562
  mix    : {'valid': 8.0, 'violation': 1.0, 'notfound': 1.0}   rate ~25.0/s   seed 42

  sent      : 300 requests in 14.0s (21.4/s)
  by kind   : notfound=34, valid=233, violation=33
  by status : 200=233, 404=34, 422=33
```

When the error-rate panel reads what it reads, you can say *"yes, because I asked for that"* rather
than looking at a graph and hoping.

`make promql` prints seven queries, in order, with what each is for. The two that matter:

```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

`rate` the buckets, `sum by (le)`, **then** the quantile. Any other order produces a plausible number
that is wrong, because **percentiles do not average** — you cannot mean two replicas' p95, but you can
add their buckets.

### Latency, measured

From the histogram after the run above (266 `/predict` requests, host → container through Docker's
port mapping):

| | |
| :--- | :--- |
| p50 | **8.79 ms** |
| p95 | **22.97 ms** |
| p99 | **24.73 ms** |

Week 9 measured the same model **in process** at p50 3.95 ms / p95 7.17 ms. The difference is the
container boundary and the port mapping, not the model — which is the honest reason to say *where* a
latency number was measured every single time you quote one. (The mean is 10.01 ms. Do not quote it.)

### Logs and metrics

The same event, two shapes, side by side (`make logs-json`):

```text
=== the METRIC: 300 requests, aggregated into four numbers ===
http_requests_total{method="GET",route="/health",status="200"} 5.0
http_requests_total{method="POST",route="/predict",status="200"} 233.0
http_requests_total{method="GET",route="__unmatched__",status="404"} 34.0
http_requests_total{method="POST",route="/predict",status="422"} 33.0

=== the LOG: one line per request, with things a metric cannot hold ===
{"duration_ms": 0.296, "event": "http_request", "method": "GET",
 "path": "/does-not-exist/297", "request_id": "d1cddb04-…", "route": "__unmatched__", "status": 404}
```

**Thirty-four different URLs became one time series** — and every one of them is still in the log,
with its own path and its own id. That is the whole logs-versus-metrics story in one screen:
the `request_id` is free in a log line and catastrophic as a metric label.

---

## Exercise 3 — a dashboard that lives in Git

Everything under `grafana/` is provisioned from files: the datasource (with a **pinned uid**), the
dashboard provider (`allowUiUpdates: false`), and ten panels in `dashboards/diabetes-service.json`.
JSON has no comments, so each panel's teaching note is in its `description` and shows on the (i) icon.

Students add "Predictions by outcome" in the UI: **Make editable** → **Add** → **Visualization**,
title, description, and the query `sum by (outcome) (rate(model_predictions_total[1m]))` in **Code**
mode. **Save dashboard** is refused with "This dashboard cannot be saved from the Grafana UI because it
has been provisioned from another source." Under **Advanced options**, the model defaults to **V2
Resource**; students choose **Classic**, click **Copy JSON to clipboard**, and replace the file.
Grafana rescans it within 10 seconds. The panel in this solution was written by hand, so its JSON is
tidier than a UI copy; both pass `tests/test_dashboard.py`.

Two settings do the work:

- **A pinned datasource `uid`.** Grafana generates one when you add a datasource by hand, so a
  dashboard exported from your machine points at a uid that exists nowhere else and every panel comes
  up **silently empty** for everybody else.
- **`allowUiUpdates: false`.** With it true, a UI edit is saved and then overwritten at the next
  rescan — a change that appears to work and then vanishes, which is the worst possible way to find
  out where the source of truth is.

**Then break it on purpose.** Rename `http_requests_total` in `metrics.py`: in a running service the
panel does not error, does not warn, and goes **empty** — which is exactly what a healthy service with no traffic
looks like. `make dashboard-check` goes red immediately, because `tests/test_dashboard.py` cross-checks
every PromQL expression against the metrics the application actually exports, read from a **live
registry** rather than a hard-coded list. A hard-coded list would be a third copy, and it would keep
agreeing with the dashboard long after the code stopped agreeing with both.

---

## Exercise 4 — an SLO, an error budget, and an alert that fires

Since 16 November 2026, `slo.py` and `prometheus/rules/slo.yml` ship complete in the starter.
Students read `slo.yaml`, run `make slo-budget` at 99% and at 99.9%, find the alerts on
`/rules`, run `make alerts-test` and watch `ServiceDown` fire with `make alert-fire`.

`slo.yaml` is the declaration everything else is derived from. It is next to `params.yaml` and
deliberately not inside it: `params.yaml` is DVC-hashed, and tightening a latency target must not
invalidate a model.

```text
SLO document for `diabetes-api` — 30-day rolling window

  objective     target    error budget            over the window
  ------------------------------------------------------------------
  availability  0.9900    1.00% of requests  =  7h 12m
  latency       0.9500    5.00% of requests  =  1d 12h 0m       (good = faster than 0.25s)

  Burn-rate alerts (Google SRE Workbook, Alerting on SLOs, Table 5-8)
  measured against the `availability` objective:

  name    sev     burn   long   short   budget spent   error ratio   budget gone in
  ----------------------------------------------------------------------------
  fast    page     14.4x     1h      5m          2.0%        0.1440   2d 2h 0m
  medium  page      6.0x     6h     30m          5.0%        0.0600   5d 0h 0m
  slow    ticket    1.0x     3d      6h         10.0%        0.0100   30d 0h 0m
```

Three things this file settles:

- **An SLI is a ratio of good events to valid events**, not uptime. Uptime is a property of a process,
  and nobody is a user of a process.
- **The latency threshold must be a bucket boundary.** `histogram_quantile` interpolates inside a
  bucket, and `prometheus/rules/slo.yml` selects the SLI with `le="0.25"` — a string match. If the two
  drift, the expression selects **no series**, the ratio is empty, and the alert can never fire.
  `tests/test_metrics.py` and `tests/test_prometheus_rules.py` check it from opposite ends.
- **Thresholds follow from the promise.** `0.144` is `14.4 × 0.01`; the same burn rate against the
  looser 95% latency target is `0.72`. `tests/test_prometheus_rules.py` recomputes every one of them
  from `slo.yaml` and fails if they disagree. That is what makes writing the SLO twice acceptable:
  duplication you cannot detect is a bug, duplication a test watches is a translation.

**A 422 does not consume the error budget.** The SLI's numerator is `5..` only, because a contract
rejection is the service working exactly as Week 5 designed it — and counting it against ourselves
would let any caller exhaust our budget by sending rubbish. The cost of that decision is that a flood
of 422s is invisible to the availability objective, which is precisely why
`ContractViolationSpike` exists.

### Testing the rules

An alerting rule describes a situation nobody has seen yet, and when it is wrong it stays silent.
`promtool` tests it against synthetic series:

```bash
make alerts-check       # promtool check config
make alerts-test        # promtool test rules — 10 cases over all 6 alerts
make alerts-test-fail   # plant `for: 5m` on ServiceDown; the suite MUST go red
make alert-fire         # stop the container, watch pending -> firing -> resolved
```

`prometheus/tests/alerts_test.yml` lives in `tests/` and **not** in `rules/`, because
`rule_files: /etc/prometheus/rules/*.yml` would otherwise try to load a test file as a rule file — and
Prometheus refuses to start on an unparseable rule file. Directory layout is interface here.

The assertion worth copying is the one that checks what does **not** fire:

```yaml
- eval_time: 1m                # down, but not for long enough
  alertname: ServiceDown
  exp_alerts: []               # PENDING, not firing — this is the `for:` clause under test
- eval_time: 2m
  alertname: ServiceDown
  exp_alerts: [ … ]
```

Anyone can test that an alert fires. Testing that it stays quiet through a deploy is the test that
saves the rotation.

---

## Not an exercise: alert fatigue

Six alerts is the whole configuration. The list at the bottom of `prometheus/rules/service.yml` says
what was deliberately **not** alerted on, and that list is the more interesting half.

`make alert-noise` replays one simulated day — ordinary noise plus one genuine 90-minute incident —
past two rules that claim to watch the same thing:

```text
    naive   : p95 miss rate > 5% right now
              -> fired 40 times

    burn    : 1h AND 5m miss rate > 72% (14.4x budget)
              -> fired 1 time(s)
```

Both caught the incident. One of them also caught every hiccup the service has ever had, at three in
the morning, with no action available. The naive rule is not a straw man — "p95 above the SLO
threshold" is exactly what almost everybody writes first.

The trade is honest and worth stating: the burn-rate rule is **slower**. You are buying trust with
detection latency, and for a 99% target that is clearly the right purchase.

---

## Not an exercise: the multi-worker trap

`make workers-trap` — 4 uvicorn workers, N requests, then thirty scrapes of one counter:

```text
  200 requests sent. Thirty scrapes of ONE counter:
    value 45.0     seen  5 times
    value 155.0    seen 24 times

  120 requests sent. Thirty scrapes of ONE counter:
    value 17.0     seen  2 times
    value 103.0    seen 28 times
```

The values add up to the true total, and **not one of them is it**. `prometheus_client`'s default
registry lives in process memory, so each scrape is answered by whichever worker took the connection.
Prometheus records a counter that repeatedly falls, and `rate()` reads every fall as a process
restart — then counts the climb back as requests that never happened.

Repeated **with HTTP keep-alive**, every scrape reused one connection and returned a stable **35**
against a true total of **40**.

One worker per container; scale with containers. The library's `multiprocess` mode is the other
answer, and it costs a shared directory and an explicit aggregation mode for every gauge.

---

## What is NOT here

Deliberately out of scope, each with its home:

- **Drift** — a prediction-score histogram is emitted and never interpreted. Comparing it against a
  reference window is Week 12, and so are proxy metrics and retraining triggers.
- **Alertmanager** — routing, grouping, silences, on-call. Week 13 (incident management).
- **Tracing** — no OpenTelemetry, no Jaeger. The `request_id` in the log line is the seam where a
  trace id would go; a single-process service does not yet have the problem tracing solves.
- **A logging backend** — no Loki, no ELK. `docker compose logs | jq` is enough to make the point.
- **Exporters** — no node-exporter, no cAdvisor, no postgres-exporter. We scrape our own service and
  Prometheus itself, exactly as the getting-started guide does.
- **Kubernetes monitoring** — no `ServiceMonitor`, no kube-prometheus-stack, and no scraping of
  Knative or Istio.
- **Federation, remote write, Thanos, long-term storage.**
- **Autoscaling on metrics**, and any new modelling at all.

## Tests

**375 collected, 367 passed, 8 skipped** (the skips need the live stack). Layers: unit **186**,
data **90**, eval **91**, integration **8**; **unmarked: 0**.

New this week, all offline:

| File | What it defends |
| :--- | :--- |
| `tests/test_metrics.py` | the route label is the template (three URLs → one series); unmatched paths collapse; `/metrics` does not count itself; the SLO threshold is a bucket boundary; `le="0.25"` renders exactly; a 422 is a contract violation and not a 5xx; `model_info` agrees with `/health`; **no existing response changed** |
| `tests/test_slo.py` | budget arithmetic against hand-computed values; the SRE-workbook table against the published source; the validator refusing a 1.0 target, a backwards window, and an SLO with no alerts |
| `tests/test_prometheus_rules.py` | every alert has `for`/severity/summary/description; **every metric named in every expression is exported by the app**, read from a live registry; every threshold recomputed from `slo.yaml`; both windows present; every alert covered by a promtool test; the rule set is ≤ 6 |
| `tests/test_dashboard.py` | every panel queries an exported metric; the datasource uid matches provisioning; `histogram_quantile` over `sum by (le) (rate(…))`; no counter graphed raw; the budget panel uses `slo.yaml`'s budget |
| `tests/test_traffic.py` | the mix, the seed determinism, and that every not-found path is distinct |

`tests/test_scope.py` does **two** things this week: `prometheus_client` **graduates** out of
`FUTURE_WEEK_MODULES`, and `grafana_client` moves *into* `PLATFORM_SDKS_WE_DO_NOT_IMPORT` alongside
`kserve` and `kubernetes` — for their reason, one week later. A dashboard belongs in Git, not in a
POST. `evidently`, `alibi_detect` and `river` stay forbidden until Week 12.

## Make targets

| Target | What it does |
| :--- | :--- |
| `make metrics-show` | the exposition format, in-process, with five requests already sent |
| `make api-up` / `api-down` | start/stop the observed container (Compose profile `api`) |
| `make traffic` | `N`, `RATE`, `MIX`, `SEED` — a controlled request mix |
| `make promql` | the seven queries, with what each is for |
| `make logs-json` | the same requests as a metric and as log lines, side by side |
| `make cardinality` | template vs raw path, counted |
| `make workers-trap` | the multi-worker counter, reproduced |
| `make grafana` / `prometheus-ui` / `targets` | the URLs, and who is being scraped |
| `make dashboard-check` | the drift guard on its own |
| `make slo-budget` | the promise, the budget, the burn-rate table |
| `make alerts-check` / `alerts-test` / `alerts-test-fail` | promtool: config, rules, and the negative test |
| `make alert-fire` | stop the service and time pending → firing → resolved |
| `make alert-noise` | the naive rule vs the burn rate, over one simulated day |
| `make prom-reload` | apply a rule change in about a second |
| `make test-observability` | just this week's tests. No Docker, no services, no network. |

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Target permanently DOWN | scraping `localhost:8000` — inside the Prometheus container, that *is* Prometheus | use the Compose DNS name `api:8000` |
| Target DOWN and you have not started the API | it is behind the `api` profile, on purpose | `make api-up` |
| `curl /metrics` prints nothing | you mounted `make_asgi_app()`; it is a 307 to `/metrics/` | serve `generate_latest()` from a route, or `curl -L` |
| `DuplicateTimeseries` on a second `create_app()` | the default registry is a process global | pass a `CollectorRegistry()` |
| Counter values jump around | several uvicorn workers | one worker per container |
| Prometheus will not start | a `*_test.yml` matched by `rules/*.yml` | keep promtool tests in `prometheus/tests/` |
| Every Grafana panel empty, no error | datasource uid mismatch, or a renamed metric | `make dashboard-check`, then check the uid |
| Panels empty in the browser only | `access: direct` — your browser cannot resolve `prometheus` | `access: proxy` |
| An alert never fires | `le=` in the rule is not a bucket boundary, so it selects nothing | `make test-observability` |
| `make image` prints nothing for minutes before the first step | Docker is uploading a large build context, such as `.venv/` | keep `.venv/` in `.dockerignore` |

## Where to look, in order

1. `http://127.0.0.1:5560/targets` — is it being scraped at all, and what was the last error?
2. `http://127.0.0.1:5560/graph` — does the raw metric exist? Type its name and nothing else.
3. `http://127.0.0.1:5560/rules` — is the rule loaded, and when did it last evaluate?
4. `http://127.0.0.1:5560/alerts` — inactive, pending, or firing?
5. `http://127.0.0.1:5561` — only now is it Grafana's fault.

---

## Two defects `promtool` found that no amount of reading would have

The rule files pass `tests/test_prometheus_rules.py` — every threshold recomputed from `slo.yaml`,
every metric cross-checked against a live registry, every alert covered by a test case. They were
still wrong in two ways, and both were found by *running* them. This is the week's own lesson
applied to the week's own work.

**1. `sum()` over no matching series returns an EMPTY vector, not zero.**

```text
    expr: "slo:availability:error_ratio_1h", time: 1h10m,
        exp: {__name__="slo:availability:error_ratio_1h"} 0E+00
        got: nil
```

On a healthy service with no 5xx at all, the numerator selects nothing, so the whole division is
empty and the recording rule produces **no series**. The alerts still behave — a comparison against
an absent series is false — but the dashboard panel reads **"No data"**, which is indistinguishable
from a broken panel. Fixed by wrapping the **numerator** in `(… or vector(0))`, and only the
numerator: an empty *denominator* means there genuinely is no traffic, and the honest answer to
"what fraction failed" is then nothing rather than a reassuring zero. That gap is what `ServiceDown`
covers. Verified live after the fix: `slo:availability:error_ratio_5m` = **0.0000**, not empty.

**2. A promtool suite's `evaluation_interval` silently coarsens every `for:` it is testing.**

The suite had `evaluation_interval: 1m` while both rule groups run at `interval: 15s`. Rules are
then evaluated on a 1-minute grid, so a `for: 1m` alert whose condition became true at t=75s does
not fire at t=135s as the arithmetic says — it fires at the next evaluation, t=180s. Nothing warns
you. The rule is right, the input is right, the assertion is right, and the test fails on an
off-by-one-evaluation that is invisible in all three. Which is a fair description of most alerting
bugs, and the best possible argument for testing alerting rules at all.

(A third, smaller one: the expanded `1x4` notation is ambiguous about whether it is four samples or
five, which moves every assertion by one interval. When the exact sample times *are* what you are
testing, write the values out.)

## Verification — measured live

Prometheus **v3.13.2**, Grafana **13.1.3**, Docker Engine **29.6.2**, 10-CPU MacBook, Docker limited
to 8 GiB.

```text
make alerts-check   SUCCESS: prometheus.yml valid · service.yml 2 rules · slo.yml 11 rules
make alerts-test    SUCCESS  (10 cases, all 6 alerts covered)
make alerts-test-fail   promtool exit 2, service.yml restored   <- the suite CAN go red
```

| | |
| :--- | :--- |
| On a fresh `make up`, before `api-up` | `up{job="diabetes-api"}` = **0**, `ServiceDown` already **pending** |
| Scrape error while down | `dial tcp: lookup api on 127.0.0.11:53: no such host` |
| Rules loaded | **4 groups, 13 rules** — 7 recording, 6 alerting |
| `ServiceDown` after `make api-down` | inactive → **pending at +5s** → **firing at +67s** (`for: 1m`, 5s scrape) |
| `slo:availability:error_ratio_5m` under healthy traffic | **0.0000** (empty before the `or vector(0)` fix) |
| RPS by status after `make traffic N=400` | 200 = **5.83/s** · 404 = **0.68/s** · 422 = **0.82/s** |
| …and the 422s in the availability SLI | **none** — exactly as the objective declares |
| p95 via `histogram_quantile` in Prometheus | **22.3 ms** (matches the 22.97 ms computed from the raw histogram) |
| Grafana | datasource `uid=prometheus`, dashboard `diabetes-service` in folder "MLOps course", **10 panels**, queries answered through the server proxy |
| New services' footprint | Prometheus **44 MiB**, Grafana **189 MiB** |
| Whole seven-service stack | ~2.8 GiB, of which MLflow is **1.9 GiB** |
| `docker compose up -d --wait` | **17 s** with images present |
