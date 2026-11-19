# Week 11 — Observability — Study Notes

These notes go with the Week 11 lecture and lab. In Week 10 we replaced a model step by step and could take it back. Every check so far runs at one moment: the gate at training time, CI at every commit, the smoke test before any traffic. Each runs because somebody typed a command. This week the service reports on itself all the time, and we decide which few numbers may wake a person.

## Why this matters

**Hospital alarms (The Joint Commission, 2013).** The Joint Commission accredits hospitals in the US. On 8 April 2013 it published Sentinel Event Alert 50, *Medical device alarm safety in hospitals*. Bedside devices measure each patient around the clock, and a value over its threshold sounds an alarm. On one unit, devices can produce **several hundred alarm signals per patient per day**; across a hospital, tens of thousands. The alert reports an estimate that **85% to 99%** of alarm signals need no clinical action. It records **80 alarm-related deaths** in The Joint Commission's own database between January 2009 and June 2012, and **566** in an FDA database between January 2005 and June 2010. These are two databases and two periods, so do not add them up. The source says "alarm-related"; it does not say that the alarms caused the deaths.

Every one of these alarms detected a real threshold crossing. The staff could not respond to all of them and stopped responding: the alert calls this **desensitisation**, or alarm fatigue. Its remedy is fewer alarms: review which signals are actionable, set thresholds for each patient group, and make somebody own the alarm policy.

Lecture: "Monitoring in hospitals", "Alarm fatigue", "Fewer alarms"

### Another case the teacher may use

- **Knight Capital (2012).** Knight Capital was a US trading firm. On 1 August 2012, one of its eight servers ran old code after a deployment. Between 8:01 and 9:30, before the market opened, its order system sent **97 e-mails** naming the fault ("Power Peg disabled") to a group of staff. Knight "did not design these types of messages to be system alerts", and staff generally did not review them (US SEC, Release No. 34-70694, 16 Oct 2013, ¶19). After the open, Knight lost more than $460 million. The SEC adds that a procedure bringing these messages into Knight's monitoring could have prevented the events (¶41). A message goes to a mailbox that nobody owns. An alert goes to one named person, says what is broken, and expects an action.

### Why watch at all

Week 6's gate checks the model at training time, Week 7's CI at every commit, Week 10's smoke test before any traffic. A model spends nearly all of its life in the months of serving between these checks, and nobody looks. Speed cameras work the same way: a driver slows down at each camera and speeds again between them. Our checks look at fixed moments; monitoring measures the whole road, all the time. Collecting numbers is easy. The hard part is choosing, before the incident, which few numbers may wake a person.

Lecture: "Who is watching between the checks?", "Where we are: monitoring the service"

## Core concepts

### The four golden signals

Google's SRE book names four signals for any service that users call. They are **traffic** (how many requests arrive), **errors** (how many fail), **latency** (how long an answer takes) and **saturation** (how full the service is). The book: "If you can only measure four metrics of your user-facing system, focus on these four." The lab's dashboard shows the first three.

Lecture: "Your API is running." · Lab: Exercise 3

### What a model service adds

The four signals would be the same for a service that returns the weather. Our service also serves a model, so it reports more:

| Metric | Kind | Answers |
| --- | --- | --- |
| `http_requests_total{method, route, status}` | counter | traffic and errors |
| `http_request_duration_seconds{method, route}` | histogram | latency |
| `http_requests_in_flight` | gauge | how busy it is now |
| `model_predictions_total{outcome}` | counter | how many patients were flagged |
| `model_prediction_score` | histogram | the spread of the scores |
| `model_contract_violations_total{check}` | counter | which rule callers break |
| `model_info{model_version, …}` | gauge, always 1 | which model is serving |

Say a caller's new release sends `glucose = 0`. The contract rejects the request with a 422, and the model is never called. Traffic does not move: the same number of requests arrive. Errors (5xx) do not move: a 422 is the contract working. Latency does not move: a rejection is fast. Saturation does not move: a rejection costs almost nothing. None of the four golden signals moves; only `model_contract_violations_total` goes up. The service is healthy, and the caller's patients get no prediction. A caller who sends glucose in mmol/L instead of mg/dL passes the contract, because the values are above 0, and nothing on this week's dashboard moves. Week 12 watches the inputs themselves, and compares `model_prediction_score` with the training data.

Lecture: "Which signal moves?", "Metric types" · Lab: Exercise 1

### Metric types

A **metric** is a number sampled over time.

- A **counter** only goes up, and starts again at 0 when the process restarts. Its raw value means little, because it depends on when the process started. Examples: `http_requests_total`, `model_predictions_total`, `model_contract_violations_total`.
- A **gauge** goes up and down; it is a value right now. Examples: `http_requests_in_flight`, `process_resident_memory_bytes` (added by the client library, on Linux only).
- A **histogram** counts values into **buckets**, such as ≤ 50 ms, ≤ 100 ms and ≤ 250 ms. Examples: `http_request_duration_seconds`, `model_prediction_score`. The buckets are **cumulative**: `le="0.25"` counts every request up to 250 ms, including the ones in the smaller buckets.

Lecture: "Metric types" · Lab: Exercise 1

### Which model drew this graph?

`model_info` is an **info metric**: a gauge whose value is always 1, and whose labels carry the model's identity.

```text
model_info{model_version="7", store_version="v1", gate_verdict="GO", schema_version="1.0.0"} 1
```

With it, a graph leads back along the chain the course has built. The graph (Week 11) leads to the revision that served it (Week 10), then to the model version (Weeks 3 and 9), the training run and its data (Weeks 3–4), and the gate verdict (Weeks 5–6). `make trace` still resolves the version to a run, a dataset hash and a gate verdict. Why not put `model_version` on `http_requests_total` instead? Every deploy would start new series at 0, and the busiest metric would multiply by every version ever served.

Lab: Exercise 1

### Labels and cardinality

A **label** is a name and a value attached to a metric, such as `status="422"`. You can filter by it, or add over it. Each combination of label values is its own **time series**, and Prometheus stores every one of them. A series appears the first time its combination happens. Every request lands in one series, so the series always add up to the total. After 300 requests from the lab's traffic generator, `http_requests_total` had, among others, 233 for `route="/predict", status="200"`, 33 for `status="422"`, and 34 for `route="__unmatched__", status="404"`. The lab API's labels have these values: `method` `GET`, `POST`; `route` `/health`, `/predict`, `/v1/models/{model_name}:predict`, `__unmatched__` (`/metrics` is not counted); `status` `200`, `404`, `422`, `500`, `503`. So the metric has at most 2 × 4 × 5 = 40 series, which Prometheus handles for years. In practice it has fewer, because some combinations, such as `GET /predict`, never happen.

The number of series (the **cardinality**) is the product of the number of values of every label, so one bad label multiplies the whole metric. A label `outcome` multiplies it by 2 (80 series); `model_version` by the number of versions ever served; `patient_age` by 52, the number of different ages in our data; `request_id` by every request, ever. The cost is paid in the memory of the collector, which other teams share, and each series stays for the whole retention period.

Measured with `prometheus_client` 0.26.0: 1,000 requests to `GET /forecast/<lat>,<lon>`, each for a different place, give **1** series when the `route` label is the template `/forecast/{lat},{lon}`, and **1,000** series when it is the raw path. The count with the template stays 1 however many requests arrive. On a public endpoint, a scanner trying `/wp-admin`, `/.env` and so on creates one series per path, so a stranger chooses your cardinality. The lab collapses every unmatched path into `__unmatched__`, and Exercise 3 measures the effect on our own API.

A label's values come from a short list you can write down. Put anything else, such as an ID, an e-mail address or a raw path, in a log line. Label requests with the route template, and give every unknown path one value, such as `__unmatched__`.

Lecture: "Labels", "How many time series?", "Choosing labels" · Lab: Exercise 1

### Metrics, logs and traces

One request, `POST /predict` that took 6.4 ms and returned 422, leaves two records:

- a **metric**: `http_requests_total{…, status="422"}` grows by 1. There is one number per label combination, and the request itself is gone. A metric costs the same for 300 requests or 3 million, so teams keep it for a year.
- a **log line**: `{"request_id": "9f2c…", "status": 422, "duration_ms": 6.4, …}`, with every field of this request. Log lines grow with traffic, and adding them up means reading every one.

A `request_id` costs nothing in a log line. As a metric label, it creates a new series for every request.

| | Metric | Log line |
| --- | --- | --- |
| Saved data | one count per label combination | every field of one request |
| Stored in | a metrics database that scrapes the service | stdout, then a log store |
| Read by | dashboards, alert rules, the on-call engineer | the engineer debugging one failure |
| Answers | Is something wrong, and since when? | What happened to this request? |

An alert fires on a metric; the engineer then searches the logs for the failing requests, by `request_id`.

A **trace** is the path of one request through several services: a list of spans. A **span** is one step: the service, its start time, its duration, and the trace ID that all spans of the trace share. Each service sends its spans to a tracing backend, which draws them as a waterfall. OpenTelemetry produces spans; Jaeger or Grafana Tempo store and show them. With several services, "the request took 900 ms" is not enough; the trace shows where the time went. In the lecture's illustration, 720 ms went to a feature store, most of it in its database, and 18 ms to the model. Our service is one process, so a log line already holds what a span would, and the `request_id` is where a trace ID would go. No tracing tool is installed in this course.

| Question | Answer from |
| --- | --- |
| Is p95 latency higher since Tuesday's deploy? | a metric |
| Why did user 812's forecast fail at 09:14? | a log |
| Which of five services made checkout slow? | a trace |
| How many requests failed last month? | a metric |

Lecture: "Metrics and logs", "Traces", "Quiz · Metric, log or trace?" · Lab: Exercise 2

### Monitoring and observability

**Monitoring** answers the questions you planned: dashboards, thresholds, alerts. **Observability** means you can answer questions you did not plan, from data you already have: logs with an ID, labels you can filter by. The line between the two terms is disputed, partly by vendors. A useful test: the last time something broke, did you have the data, or did you add a log line and wait for it to happen again?

Lecture: "Monitoring and observability"

### Tool options

| Tool | What it does |
| --- | --- |
| **Prometheus** | collects and stores metrics; pulls them over HTTP |
| **Grafana** | dashboards over many data sources |
| **OpenTelemetry** | produces and exports traces, metrics and logs; stores nothing |
| **VictoriaMetrics** | time-series storage; answers Prometheus queries |
| **Datadog** | an agent on each host sends data to Datadog's service |
| **Amazon CloudWatch** | metrics, logs and alarms for AWS |

The course uses Prometheus and Grafana: they are open source, each runs in one container, and the queries are plain text we can keep in Git. Prometheus started at SoundCloud in 2012 and joined the CNCF in 2016, as its second project after Kubernetes. Its documentation warns that it is the wrong tool when you need 100% accuracy, such as per-request billing. Many teams produce their data with OpenTelemetry and send it to a backend such as Prometheus.

Lecture: "Tool options"

### Prometheus pulls

Nobody sends numbers to Prometheus. Every few seconds (5 s in the lab), it sends an HTTP GET to `/metrics` on every **target** it knows; this is a **scrape**. Grafana stores no data: each panel sends a PromQL query to Prometheus when you look. Three things follow from the pull model:

- Prometheus must reach you, so a target that is DOWN is often a network problem. Inside the Prometheus container, `localhost` is Prometheus itself, so the lab's target is `api:8000`, the Compose service name.
- Prometheus must know you: it has a list of targets, which is a static list in the lab.
- You get `up` for free: 1 if the scrape worked, 0 if not.

Most logging systems push. For short jobs that end before a scrape, Prometheus has a push gateway.

So the setup has two sides. In our service, we define each metric (name, type, labels), update it in the request handler, and serve all metrics at `GET /metrics`. The service does not know that Prometheus exists. In Prometheus, a config file, `prometheus.yml`, lists the targets and how often to scrape them:

```yaml
scrape_configs:
  - job_name: forecast
    scrape_interval: 5s
    static_configs:
      - targets: ["forecast:8000"]
```

One scrape reads the whole `/metrics` page, every line of every metric at once.

Lecture: "How Prometheus works" · Lab: Exercise 2

### `prometheus_client` quick start

The Python client defines the metrics and produces the text that a scrape receives. The lecture's example is a small forecast service, so that the lab's code stays yours to write:

```python
import time

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI()
REQUESTS = Counter("forecast_requests_total", "Forecasts served.", ["status"])
LATENCY = Histogram("forecast_duration_seconds", "Time to answer.",
                    buckets=[0.05, 0.1, 0.25])

@app.get("/forecast/{lat},{lon}")
def forecast(lat: float, lon: float):
    began = time.perf_counter()
    temperature = predict_temperature(lat, lon)  # the model
    LATENCY.observe(time.perf_counter() - began)
    REQUESTS.labels(status="200").inc()
    return {"temperature": temperature}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

After three forecasts that took 42, 80 and 300 ms, `GET /metrics` returns (with `prometheus_client` 0.26.0, without the `# HELP` and `# TYPE` lines, the `_created` timestamps and the default `python_*` metrics):

```text
forecast_requests_total{status="200"} 3.0
forecast_duration_seconds_bucket{le="0.05"} 1.0
forecast_duration_seconds_bucket{le="0.1"} 2.0
forecast_duration_seconds_bucket{le="0.25"} 2.0
forecast_duration_seconds_bucket{le="+Inf"} 3.0
forecast_duration_seconds_count 3.0
forecast_duration_seconds_sum 0.437
```

There is one line per label value. The histogram is not one line: one `_bucket` per boundary, plus `_count` and `_sum`. `_sum / _count` gives the mean latency, which hides the slow tail.

### PromQL

**PromQL** is Prometheus' query language: Grafana, alert rules and people use it to ask Prometheus for data. It is not how Prometheus reads our service; that is a plain `GET /metrics`. A query selects time series by name and labels, then computes over them:

| Query | Returns |
| --- | --- |
| `forecast_requests_total` | every series of the counter |
| `forecast_requests_total{status="500"}` | only the series with status 500 |
| `sum(forecast_requests_total)` | the series added together |
| `rate(forecast_requests_total[1m])` | requests per second, over the last minute |

Lecture: "Prometheus setup", "`prometheus_client` quick start", "What Prometheus reads", "PromQL" · Lab: Exercise 1

### Read a counter with `rate()`

| Time | `forecast_requests_total` | `rate(…[1m])` |
| --- | --- | --- |
| 10:00 | 1,200 | |
| 10:01 | 1,500 | 5.0 per second |
| 10:02 | **120** | 2.0 per second |
| 10:03 | 420 | 5.0 per second |

The counter fell because the process restarted and the counter started again at 0. `rate()` gives the per-second increase over a window, and it reads a fall as a restart. The Prometheus documentation: "Breaks in monotonicity (such as counter resets due to target restarts) are automatically adjusted for." So after the reset, `rate()` counts the 120 as new requests. Graph `rate()`, never the raw counter: plotted raw, a restart looks like a disaster.

The table is simplified. `rate()` needs at least two samples in its range, so use a range of about four scrape intervals or more (the lab scrapes every 5 s and uses `[5m]`).

Lecture: "A counter fell from 1,500 to 120. What happened?" · Lab: Exercise 2

### Scraping replicas

A **replica** is one copy of the service; a load balancer spreads the requests over the copies. Prometheus does not scrape through the load balancer: each scrape would reach a random replica. It scrapes every replica directly, as its own target. It adds an `instance` label to every series ("an endpoint you can scrape is called an instance", Prometheus docs, *Jobs and instances*). A PromQL `sum` over the instances gives the total. In Kubernetes the target list comes from service discovery, which finds the pods by label, so a new replica is scraped without editing the config. KServe's annotation `serving.kserve.io/enable-prometheus-scraping` exposes the metrics port, but Prometheus must still be configured to scrape the pods.

### Percentiles from buckets

Three replicas report their p95 latency: 49, 81 and 241 ms. The p95 of all their requests is not the mean (124 ms) and not the largest (241 ms); these three numbers cannot tell you. **Percentiles do not average.** Bucket counts do. Here are the replicas' bucket counts, 100 requests each:

| Requests up to | 50 ms | 100 ms | 250 ms | all |
| --- | --- | --- | --- | --- |
| replica A | 97 | 100 | 100 | 100 |
| replica B | 90 | 98 | 100 | 100 |
| replica C | 50 | 80 | 96 | 100 |
| **sum** | 237 | 278 | 296 | 300 |

The 285th of 300 requests falls between 100 and 250 ms. Inside a bucket, Prometheus assumes that the requests are spread evenly (**linear interpolation**), so p95 = 100 + (285 − 278) / (296 − 278) × 150 ms ≈ **158 ms**. In PromQL the order is: `rate` each bucket, then `sum by (le)` over the replicas, then `histogram_quantile`:

```text
histogram_quantile(0.95, sum by (le) (rate(forecast_duration_seconds_bucket[5m])))
```

Any other order gives a number that looks plausible and is wrong. A quantile is only as precise as its buckets. That is why the lab's latency target, 250 ms, is itself a bucket boundary.

Lecture: "Three replicas of our API report their p95 latency: 49, 81 and 241 ms.", "Percentiles from buckets" · Lab: Exercise 2

### Grafana

**Grafana** draws dashboards from data sources. It stores the dashboards, not the data. A **data source** is where the data lives: Prometheus, a log store, a SQL database. A **dashboard** is one page of panels. A **panel** is one query, drawn as a graph, a number or a table. Each panel sends its PromQL query to Prometheus every time the page refreshes. The three signals as PromQL:

```text
# traffic: requests per second
sum(rate(forecast_requests_total[5m]))
# errors: the share of requests that failed with a 5xx
  sum(rate(forecast_requests_total{status=~"5.."}[5m]))
/ sum(rate(forecast_requests_total[5m]))
# latency: the 95th percentile
histogram_quantile(0.95, sum by (le) (rate(forecast_duration_seconds_bucket[5m])))
```

`[5m]` is the window: each point on the graph averages the last five minutes, and a shorter window shows more noise. Saturation comes from a gauge, such as requests in flight, read as it is. Every Grafana panel is one query like these. Grafana keeps no metric data; it asks a data source each time the page refreshes. The lab's dashboard has ten panels and is loaded from files when Grafana starts.

Lecture: "Grafana", "Grafana dashboard", "A panel and its query" · Lab: Exercises 2 and 3

### Grafana configuration

At start-up, YAML files tell Grafana the data source and where the dashboards are; this is called **provisioning**. A dashboard is a JSON file (Grafana's dashboard JSON model), with one entry per panel: its type, its title and its query. "Export" in the UI produces the same file. The lab's files:

```text
grafana/
  provisioning/datasources/prometheus.yml   # uid: prometheus, written down
  provisioning/dashboards/provider.yml      # allowUiUpdates: false
  dashboards/diabetes-service.json          # the ten panels
```

Someone renames a metric in the code. The panel does not show an error or a warning; it goes empty, which is also what a healthy service with no traffic looks like. From the panel alone you cannot tell the two apart. So keep dashboards as files in Git, next to the code that feeds them, and test that every query names a metric the service exports. It is the same argument as for `dvc.yaml` and the `InferenceService` manifest: what should be argued about in a pull request has to be a file. A datasource added by hand gets a random uid, so a dashboard exported from your machine stays empty on everyone else's. `allowUiUpdates: false` stops a change in the UI that would disappear at the next reload.

Lecture: "Grafana configuration" · Lab: Exercise 3

### SLI, SLO, SLA and error budget

"The service must be fast and reliable" cannot fail, because nobody can say when it has failed. Reliability needs a number.

| Term | Stands for | Means |
| --- | --- | --- |
| **SLI** | service level indicator | a measurement: good events ÷ valid events |
| **SLO** | service level objective | a target for an SLI, over a time window |
| **SLA** | service level agreement | an SLO in a contract, with a penalty if it is missed |
| **Error budget** | | the failure an SLO allows: 1 − target |

Example SLOs, for our service:

| Term | Example: our service |
| --- | --- |
| Availability SLI | non-5xx answers ÷ requests that passed the contract |
| Availability SLO | 99% over 30 days |
| Latency SLO | 95% of requests faster than 250 ms, over 30 days |
| SLA | none |
| Error budget | 1% of requests |

A latency target also needs the place it is measured from: see "Say where you measured latency" below.

An example: of 40 requests, 36 are answered (200), 1 fails (500) and 3 are rejected by the contract (422). A 422 means the contract did its job, so we leave 422s out of both the good and the valid events: availability = 36 ÷ 37 = **97.3%**. Then a caller cannot spend our budget by sending bad data; `model_contract_violations_total` watches those requests instead. A ratio of events adds up across replicas. The "uptime" of a process does not, and no user is a user of a process.

The SRE Workbook describes an SLA as "a business contract that comes into effect when your users are so unhappy you have to compensate them". The SLO is stricter, so that the team hears about trouble before the contract does. Agree each SLO before the first incident: what counts as good, the target, and the window.

Lecture: "SLI, SLO and SLA", "SLI: good events ÷ valid events", "Example SLOs" · Lab: Exercise 4

### The nines of availability

| Availability | Name | Error budget in 30 days |
| --- | --- | --- |
| 99% | two nines | 7 h 12 min |
| 99.9% | three nines | 43 min 12 s |
| 99.99% | four nines | 4 min 19 s |
| 99.999% | five nines | 26 s |
| 100% | | 0: no deploy may ever fail |

Each extra nine leaves a tenth of the budget. The lab's `make slo-budget` prints 7h 12m for 99%, and `tests/test_slo.py` checks the others. At 99.99%, the budget of four minutes a month is shorter than the time to notice and act, so the target needs redundancy in the design.

The budget is for decisions. If it is spent after two weeks, reliability work comes first and risky releases wait. The Workbook's error budget policy gives reliability bugs top priority, and a "production freeze halts certain changes" until there is budget again. Nobody argues, because the number was agreed in advance. If it is untouched after four months, the target may be too loose, or we pay for reliability nobody asked for. An unspent budget can buy speed: the Workbook suggests relaxing release processes, or spending the engineering time on services that need it.

Lecture: "The nines of availability" · Lab: Exercise 4

### Burn rate, in two windows

The **burn rate** tells how fast we spend the error budget. At 1×, the budget lasts for the whole SLO window. It is the error ratio now ÷ the error ratio the SLO allows. The Workbook: "Burn rate is how fast, relative to the SLO, the service consumes the error budget." With a 1% budget, 14.4% of requests failing is a burn rate of 14.4. At 1×, the budget lasts the 30 days. At 6×, it is gone in 5 days; at 14.4×, in 2 days 2 h. At 14.4×, one hour spends 14.4 × 1 h ÷ 720 h = **2%** of the month's budget.

The Workbook recommends alerting on the burn rate, each alert over a long and a short window (multiwindow, multi-burn-rate alerts). Its "recommended starting parameters" (*Alerting on SLOs*, Table 5-8):

| Severity | Long window | Short window | Burn rate | Budget spent |
| --- | --- | --- | --- | --- |
| page | 1 hour | 5 minutes | 14.4 | 2% |
| page | 6 hours | 30 minutes | 6 | 5% |
| ticket | 3 days | 6 hours | 1 | 10% |

An alert fires when **both** windows are over the burn rate. The threshold follows from the SLO: 14.4 × 1% = an error ratio of **0.144**. Against the latency SLO (5% budget), the same rule needs 14.4 × 5% = **0.72**, so 72% of requests too slow. The lab's tests compare the table with the source, so nobody rounds 14.4 to 14, and they recompute every threshold from `slo.yaml`.

Lecture: "Burn rate", "Alerting on SLOs" · Lab: Exercise 4

### One simulated day: noise and patience

The lab's `make alert-noise` (seed 42) simulates 1,440 minutes. About 3% of them have a one-minute latency spike (a garbage collection, a noisy neighbour), and one real incident runs from 10:00 to 11:30. Two rules watch the latency SLO:

- "p95 latency above 250 ms right now" fires **40 times**. Almost everybody writes this rule first, because the SLO allows 5% of requests above 250 ms.
- The burn-rate rule (1 h and 5 min windows, both over 0.72) fires **once**.

Both caught the incident. The other 39 pages were short spikes, over before anyone could act. Forty pages a day lead to the same loop as the hospital alarms.

The two windows do different jobs. On the simulated day, the 5-minute window is over the threshold from 10:05 to 11:31, and the 1-hour window from 10:50 to 11:40. The alert needs both, so it fires from 10:50 to 11:31. The 1-hour window says the incident is serious; the 5-minute window says it is still happening, and so decides when the alert stops. With the 1-hour window alone it keeps firing until 11:40, because the last hour still contains the incident. With the 5-minute window as well it stops at 11:31. The Workbook's own example: the short window makes the alert stop "five minutes later, rather than one hour later". An alert that keeps firing after the fix teaches people to silence it.

The price is speed: the naive rule fires at 10:00, the burn-rate rule at 10:50, **50 minutes** later. It waits until 2% of the month's budget is gone, and that wait removes the 39 false pages. For a 99% target this is worth it. A service where ten minutes of failure is a disaster needs a different SLO, written before the incident.

Lecture: "An alert on p95 latency", "Long and short windows" · Lab: `make alert-noise`

### Page, ticket or nothing?

Google's SRE book separates "what's broken" (the symptom) from "why" (the cause). Page on symptoms, and keep causes on the dashboard for whoever investigates. Page a person only when users feel the problem now and someone can act now; send the rest to a ticket or a dashboard. Errors that burn the budget 14 times too fast for an hour are a page. A TLS certificate that expires in 14 days is a ticket: nobody feels it yet. A fall in the model's accuracy cannot be measured at all, because there are no labels at serving time. A diagnosis is the label, and it may arrive years later. Week 12 watches what can be seen without labels.

Lab: Exercise 4

### Alerting rules

Prometheus reads alerts from rule files. A rule group holds two kinds of rule:

```yaml
groups:
  - name: forecast-slo
    rules:
      - record: forecast:error_ratio:1h
        expr: |
          sum(rate(forecast_requests_total{status=~"5.."}[1h]))
          / sum(rate(forecast_requests_total[1h]))
      # forecast:error_ratio:5m is recorded the same way, over [5m]
      - alert: ForecastBudgetBurnFast
        expr: forecast:error_ratio:1h > 0.144 and forecast:error_ratio:5m > 0.144
        for: 2m
        labels:
          severity: page
```

- A **recording rule** (`record:`) computes a query at every evaluation and saves the result as a new time series, so alerts and dashboards do not recompute an hour of rates.
- An **alerting rule** (`alert:`) fires when its expression returns a result. `for:` is how long the expression must hold before the alert fires; until then the alert is **pending**. `labels` such as `severity: page` say how to treat it.

An alert moves from **inactive** to **pending** to **firing**. In the lab, `make api-down` stops the API container, and the rule `up == 0` with `for: 1m` goes pending at +5 s and firing at +67 s, both counted from `make api-down`; `make api-up` resolves it. `for: 1m` is a cheap guard against noise: a scrape that fails once does not page anyone. On a fresh `make up`, before the API starts, `up` is already 0 and the alert is already pending. This week Prometheus only marks an alert as firing. Alertmanager, which routes it to a person, is Week 13.

Lab: Exercise 4

### Test an alert before you need it

An alerting rule describes a situation nobody has seen yet, and when it is wrong, it stays silent. This course has already met three checks that reported success while checking nothing: Week 4's `check_locks.sh`, Week 7's `ci-fail` and Week 10's `make smoke`. `promtool test rules` is a unit test for rules: you feed made-up series in and state which alerts should fire at which times. It runs in seconds, with no server. The lab's `ServiceDown` test feeds `up` = 1 for one minute, then 0. At 1 minute it expects no alert, because the rule is only pending; at 2 minutes it expects the alert firing. The checks that an alert stays quiet are the ones most often wrong.

Two defects in the lab's own rules passed pytest and showed up only when the rules ran:

1. `sum()` over no matching series returns nothing, not 0. On a healthy service with no 5xx, the availability error ratio produced no series, and its dashboard panel read "No data", which looks like a broken panel. The fix is `(… or vector(0))` on the numerator only. An empty denominator means there is really no traffic, and then no answer is more honest than a zero.
2. A 1-minute `evaluation_interval` in the promtool suite, against rule groups evaluated every 15 s, made a correct `for: 1m` rule fail a correct test by one evaluation, and nothing said why.

A pytest suite can check that the rules are consistent with `slo.yaml`; only running them checks how they behave.

Lab: Exercise 4

### What this week does not catch

Availability is 100%, p95 latency is 23 ms against a target of 250 ms, and there are no contract violations. Is the model right? We do not know: no panel looks at whether the answers are right. The patients are not the users of this API, and they cannot report an error. Week 12 watches the inputs and the scores against the training data. Week 13 adds who receives an alert and what they do (incidents and kill-switches), and who answers for the people the model is about (Model Cards).

Lecture: "What this week does not solve"

## Red flags and good practices

### Delete alerts nobody acts on

Noisy alerts are ignored ("that one always fires"), so nobody reacts to a real incident. The postmortem then says "add an alert for it", which brings more noise. The hospital alarms were the same loop. After a missed incident, ask first which alert you can delete. Three ways out are decisions (fewer alerts, alerts on symptoms, an owner for each alert); one is a line of configuration (`for:`).

Lecture: "Fewer alarms"

### Several workers in one container

Started with `--workers 4`, a web server runs four **worker** processes in one container, to use more CPU cores. Nobody gets this by accident: uvicorn runs one worker unless told otherwise, and the course's images say `--workers 1`. `prometheus_client` keeps its counters in the memory of one process. Measured with the lab's `make workers-trap`: 200 requests to one container with 4 uvicorn workers, then 30 scrapes of one counter. The scrapes returned **45** five times and **155** 24 times; the true total, 200, never appeared. A scrape gets whichever worker answers, and `rate()` reads every fall from 155 to 45 as a restart. With HTTP keep-alive it was worse: every scrape reused one connection and returned a stable **35** against a true **40**, a wrong number with no visible sign. Run one worker per container and add replicas: FastAPI's documentation recommends a single process per container in Kubernetes, with replication at the cluster level. If you need workers, use the client's multiprocess mode; it works, but loses custom collectors such as CPU and memory, and Info metrics.

Lecture: "Several workers in one container" · Lab: `make workers-trap`

### Say where you measured latency

| Where | p50 | p95 |
| --- | --- | --- |
| in the process, through `TestClient` (Week 9) | 4.48 ms | 7.67 ms |
| from the host, into the container (Week 11) | 8.79 ms | 22.97 ms |

It is the same model. The difference is the container boundary and Docker's port mapping. The mean of the Week 11 run was 10.01 ms, which hides the slow tail that users feel. Quote a latency with its percentile and the place it was measured from.

Lecture: "Example SLOs"

## Commands

| Command | What it does |
| --- | --- |
| `uv add prometheus-client` | installs the Python client (already in the lab's `uv.lock`, through Prefect) |
| `Counter(…)` · `Histogram(…, buckets=[…])` · `Gauge(…)` | defines a metric; `.labels(…).inc()`, `.observe(x)`, `.set(x)` record values |
| `generate_latest(registry)` | the text a scrape receives |
| `rate(x[5m])` | per-second increase of a counter over 5 minutes |
| `histogram_quantile(0.95, sum by (le) (rate(x_bucket[5m])))` | p95 over all replicas |
| `make metrics-show` · `make serve-api` | the exposition format, in-process / the API on port 5541 without Docker |
| `make api-up` / `make api-down` | starts / stops the observed container (API on port 5562) |
| `make traffic` · `make promql` | a controlled request mix / the eight queries, with what each is for |
| `make logs-json` · `make cardinality` · `make workers-trap` | logs and metrics (Exercise 2), series counted (Exercise 1), workers (not an exercise) |
| `make grafana` · `make dashboard-check` | prints the Grafana URLs (port 5561) / runs `tests/test_dashboard.py`, which checks the panels' queries |
| `make slo-budget` | the SLO, the budget in time, the burn-rate table |
| `make alerts-check` · `make alerts-test` · `make alerts-test-fail` | `promtool check config` / `promtool test rules` / a broken rule that the suite must catch |
| `make alert-fire` | stops the container and shows pending → firing → resolved |
| `make alert-noise` | one simulated day: the naive rule against the burn rate |
| `make test-observability` | this week's tests; no Docker, no services |

## Key terms

- **PromQL**: Prometheus' query language, used by Grafana, alert rules and people; not by the scrape.
- **Instance / job**: one scraped endpoint, such as one replica / all instances with the same purpose.
- **Worker**: one of several server processes in one container; each has its own counters.
- **Data source / dashboard / panel**: where Grafana reads data / a page of panels / one query drawn as a graph, a number or a table.
- **Provisioning**: loading Grafana's data sources and dashboards from files at start-up.
- **The nines**: availability written as nines, such as 99.9% ("three nines").
- **Pull / push**: Prometheus fetches data from a service on a schedule; in a push system the service sends it.
- **Scrape / target / `up`**: one HTTP GET to `/metrics`; the service that is fetched; 1 if the scrape worked, 0 if not.
- **Exposition format**: the text a scrape returns; one sample per line, with `# HELP` and `# TYPE` lines.
- **Counter / gauge / histogram**: only goes up / goes up and down / counts values into cumulative buckets.
- **`rate()`**: the per-second increase of a counter over a window; it handles a counter reset.
- **`histogram_quantile`**: a percentile computed from bucket counts at query time; `sum by (le)` first.
- **Label / time series / cardinality**: a dimension of a metric / one combination of label values / the number of series, the product of every label's number of values.
- **Info metric**: a gauge that is always 1, with identity in its labels (`model_info`).
- **Log line / trace / span**: a record of one request / one request across services / one step of a trace.
- **Four golden signals**: traffic, errors, latency, saturation.
- **SLI / SLO / SLA**: good events ÷ valid events / a target for it over a window / an SLO in a contract, with a penalty.
- **Error budget**: 1 − target, as time or as requests; the failure the SLO allows.
- **Burn rate**: how fast the budget is spent; 1 means the budget lasts the whole window.
- **Multi-window alert**: fires only when a long and a short window are both over the burn rate.
- **Recording rule**: a query that Prometheus computes at every evaluation and stores under a new name.
- **Alerting rule / `for:`**: a condition / how long it must hold before the alert fires. Inactive → pending → firing.
- **Alert fatigue**: alerts are correct and so many that people no longer respond to them.
- **On-call** (*ügyelet*): the person who must respond to a page outside working hours.

## How this connects to the lab

The lab adds monitoring to the diabetes API from Weeks 9 and 10, in four exercises. You:

1. record every request in a counter and a latency histogram, count the model's predictions and contract violations, and fix `route_label` so that `make cardinality` drops from 51 series to 2: no Docker, no Prometheus;
2. add the scrape job and start the API container, and watch its target go from DOWN to UP. Then send traffic with a known mix, and read the request rate and p95 with PromQL;
3. add a panel in the Grafana UI, copy the dashboard JSON that Grafana offers into the file in Git, and see `make dashboard-check` fail when a query names a metric the service does not export;
4. read the SLO, print the error budget at 99% and at 99.9%, run the `promtool` tests, and fire `ServiceDown` for real by stopping the container.

Exercises 1, 2 and 4 have one written question each; the answers go in `answers.md`. Prometheus and Grafana use about 44 MiB and 189 MiB of memory. Stop the Week 10 cluster first: this week runs on Docker Compose. Traps you will meet:

- The scrape target `localhost:8000` stays DOWN: inside Prometheus, `localhost` is Prometheus. Use `api:8000`.
- `app.mount("/metrics", make_asgi_app())`, as documented, answers with a 307 redirect to `/metrics/`. Prometheus follows it, but `curl` without `-L` prints nothing.
- A second `create_app()` raises `DuplicateTimeseries`: the default registry is global, so pass a registry.
- A latency target that is not a bucket boundary: the latency alert never fires.
- A `*_test.yml` file inside `rules/` stops Prometheus from starting; keep the promtool tests beside `rules/`.
- A datasource added by hand: every panel is empty for everyone else; pin the datasource `uid`.

## Recommended reading

- **Prometheus: instrumentation and naming practices** (https://prometheus.io/docs/practices/instrumentation/ · https://prometheus.io/docs/practices/naming/). *Focus on:* the advice on labels and cardinality.
- **Prometheus: histograms and summaries** (https://prometheus.io/docs/practices/histograms/). *Focus on:* why buckets, and what `histogram_quantile` really computes.
- **Prometheus: unit testing for rules** (https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/). *Focus on:* `input_series` and `alert_rule_test`.
- **Google, *The Site Reliability Workbook*, "Implementing SLOs" and "Alerting on SLOs"** (https://sre.google/workbook/implementing-slos/ · https://sre.google/workbook/alerting-on-slos/). *Focus on:* the error budget policy and Table 5-8.
- **Grafana: provisioning** (https://grafana.com/docs/grafana/latest/administration/provisioning/). *Focus on:* dashboards and datasources as files.
- **The Joint Commission, Sentinel Event Alert 50** (https://www.jointcommission.org/en-us/knowledge-library/newsletters/sentinel-event-alert/issue-50). *Focus on:* the recommended actions on alarm safety.
- **Designing Machine Learning Systems (Huyen), Ch. 8.** *Focus on:* the monitoring section, on what to monitor for an ML system.

## Check yourself

1. Your service handles **12 requests a minute**. A colleague proposes a 99.9% availability SLO over 30 days. Compute the error budget in requests. Then say how long a 1-hour burn-rate window takes to collect enough events to tell a real 14.4× burn from noise. What would you propose instead?
2. A dashboard panel that read 40 requests per second yesterday reads nothing at all today, with no error. Give three different causes, and for each one say which single command or page would tell it apart from the other two.
3. Your availability SLI is 100% and your p95 latency is 23 ms against a 250 ms threshold. Name three things that could still be badly wrong with the model. For each one, say whether anything in this week's material would catch it, and if not, what would.
4. You are asked to add a label so that an on-call engineer can filter a graph by customer. There are 200,000 customers. Explain what happens if you do it, and describe two things you would offer instead: one that answers the same question, and one that answers a different question well.
