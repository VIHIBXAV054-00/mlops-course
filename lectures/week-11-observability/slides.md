---
theme: default
title: Week 11 — Observability
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers metrics, logs and traces, Prometheus and Grafana, SLIs, SLOs and error
  budgets, burn-rate alerting, and alert fatigue.
class: text-left
transition: slide-left
mdc: true
# hash routing + relative base (built with --base ./) so the SPA works in a
# GitHub Pages subdirectory: slides live after the # and assets load relatively.
routerMode: hash
# Shared course components (Lifecycle, ImageSlot, DataBatch). The path is resolved
# from lectures/, so './_shared' means lectures/_shared.
addons:
  - ./_shared
duration: 80min
---

# Week 11: Observability

<carbon-activity class="icon-corner" />

<div class="middle">

**Lifecycle of Artificial Intelligence Systems**

- Metrics, logs and traces
- Prometheus and Grafana
- SLIs, SLOs and error budgets
- Alerting

</div>

<!--
Last week we could replace the model safely. Today the running service reports how it is doing, and a person is called only when it matters.
-->

---

# Recap: latency percentiles

<carbon-chart-histogram class="icon-corner" />

<div class="middle">

Hypothetical: 20 requests, sorted by latency in ms

<div class="flex justify-center gap-1 font-mono" style="margin:1rem 0">
  <span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">4</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">4</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">5</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">5</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">5</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">5</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">6</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">6</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">6</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center; background:#dcfce7; border-color:#16a34a">6</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">7</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">7</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">7</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">8</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">8</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">9</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">9</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center">10</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center; background:#fef3c7; border-color:#d97706">12</span><span style="display:inline-block; min-width:2rem; padding:0.25rem 0.4rem; border:1px solid #94a3b8; border-radius:0.3rem; text-align:center; background:#ffe4e6; border-color:#e11d48">240</span>
</div>

| **Statistic** | **Value** |
| --- | --- |
| p50 | <span v-click="1">6 ms</span> |
| p95 | <span v-click="1">12 ms</span> |
| p99 | <span v-click="1">240 ms</span> |
| mean | <span v-click="2">18.5 ms: slower than 19 of the 20 requests</span> |

</div>

<!--
Week 10's load test terms: p50, p95, p99 are the latencies under which 50, 95 and 99% of requests finished. Nearest-rank percentiles on 20 values. One slow request moves the mean and leaves the median alone, which is why latency targets are percentiles. Today Prometheus stores latency as buckets, and the latency SLO is a percentile.
-->

---

# Recap: HTTP status codes

<carbon-http class="icon-corner" />

<div class="middle">

<div v-click="1" class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div :class="$clicks >= 3 ? 'card faded' : 'card'"><ph-check-circle class="ic" /><b>2xx · success</b>200: a prediction</div>
  <div :class="$clicks >= 3 ? 'card faded' : 'card'"><ph-user class="ic" /><b>4xx · the caller's mistake</b>422: the contract rejected the input<br>404: no such route</div>
  <div class="card" :style="$clicks >= 3 ? 'border:3px solid #e11d48; background:#fff1f2' : ''"><ph-warning class="ic" /><b>5xx · the service's fault</b>500: the model crashed<br>503: not ready yet</div>
</div>

<v-click at="2">

Which of them should count against our service?

</v-click>

<v-click at="3">

**5xx.** A 4xx means the contract did its job.

</v-click>

</div>

<!--
Week 5's contract runs in the API since Week 9: FastAPI answers 422 and names the failed check. Week 9's readiness: 503 until the model is loaded. Today the SLI counts 5xx against us and leaves 4xx out, because a caller who sends bad data must not spend our error budget.
-->

---

# Recap: the rollout plan

<carbon-document class="icon-corner" />

<div class="middle">

<div v-click="1" class="text-sm">
<table>
  <thead><tr><th>Item</th><th>Example</th></tr></thead>
  <tbody>
    <tr><td>before any traffic</td><td>the smoke test passes on v2</td></tr>
    <tr :style="$clicks >= 3 ? 'background:#ffe4e6' : ''"><td>promote when</td><td>24 hours with errors under 1%</td></tr>
    <tr :style="$clicks >= 3 ? 'background:#ffe4e6' : ''"><td>roll back when</td><td>errors above 1% for 5 minutes</td></tr>
    <tr><td>expected load</td><td>20 requests per second, p95 under 300 ms</td></tr>
  </tbody>
</table>
</div>

<v-click at="2">

Which of these can we not check today?

</v-click>

<v-click at="3">

Nothing measures the error rate over minutes or hours yet.

</v-click>

</div>

<!--
Week 10's rollout plan (`release.yaml` in the lab). Each "when" line names a signal, a threshold and a duration: that is an alert rule. In Week 10 every number came from a command somebody typed. Today the service reports these numbers itself, and a rule checks them.
-->

---

# Who is watching between the checks?

<carbon-time class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div v-click="1" class="node green no-shrink" style="width:9rem"><ph-seal-check class="ic" /><b>Gate</b><br><small>in the training pipeline</small></div>
  <div v-click="2" class="node green no-shrink" style="width:9rem"><ph-git-commit class="ic" /><b>CI</b><br><small>at every commit</small></div>
  <div v-click="3" class="node green no-shrink" style="width:9rem"><ph-rocket-launch class="ic" /><b>Smoke test</b><br><small>before any traffic</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node rose no-shrink" style="width:20rem; border-style:dashed"><ph-moon class="ic" /><b>In production</b><br><small>months of requests, nobody looks</small></div>
</div>

<div v-click="5">

<svg viewBox="0 0 640 195" style="width:100%; max-width:40rem; height:auto; display:block; margin:0.5rem auto 0">
  <line x1="50" y1="140" x2="620" y2="140" stroke="#94a3b8"/>
  <line x1="50" y1="15" x2="50" y2="140" stroke="#94a3b8"/>
  <text x="40" y="80" font-size="12" fill="#475569" text-anchor="middle" transform="rotate(-90 40 80)">speed</text>
  <text x="620" y="134" font-size="12" fill="#475569" text-anchor="end">road</text>
  <line x1="50" y1="92" x2="620" y2="92" stroke="#16a34a" stroke-width="2" stroke-dasharray="6 5"/>
  <text x="615" y="86" font-size="12" fill="#16a34a" text-anchor="end">speed limit</text>
  <g transform="translate(216,150)"><rect x="0" y="4" width="22" height="14" rx="3" fill="#475569"/><circle cx="11" cy="11" r="4.5" fill="#e2e8f0"/><rect x="22" y="8" width="6" height="6" fill="#475569"/></g><text x="230" y="186" text-anchor="middle" font-size="12" fill="#475569">speed camera</text><line x1="230" y1="20" x2="230" y2="148" stroke="#94a3b8" stroke-dasharray="2 4"/>
  <g transform="translate(436,150)"><rect x="0" y="4" width="22" height="14" rx="3" fill="#475569"/><circle cx="11" cy="11" r="4.5" fill="#e2e8f0"/><rect x="22" y="8" width="6" height="6" fill="#475569"/></g><text x="450" y="186" text-anchor="middle" font-size="12" fill="#475569">speed camera</text><line x1="450" y1="20" x2="450" y2="148" stroke="#94a3b8" stroke-dasharray="2 4"/>
  <path d="M50,40 L185,40 C205,40 210,96 230,96 C250,96 255,40 275,40 L405,40 C425,40 430,96 450,96 C470,96 475,40 495,40 L620,40" fill="none" stroke="#e11d48" stroke-width="3"/>
  <text x="120" y="32" font-size="12" fill="#e11d48">car</text>
</svg>

</div>

</div>

<!--
Every check so far runs at one moment, because somebody typed a command or pushed a commit. The model spends nearly all of its life in the last box.
Speed cameras work the same way: a driver slows down at each camera and speeds again between them. Our checks look at fixed moments; monitoring measures the whole road, all the time.
Collecting numbers is easy. The hard part is choosing, before the incident, which few numbers may wake a person.
-->

---
layout: section
---

# 1 · Metrics, logs and traces

<!--
About 20 minutes. No tool in this section: Prometheus comes in Section 2. The metric names are the ones the lab's API exports.
-->

---

# Where we are: monitoring the service

<div class="middle">

<Lifecycle stage="monitor" width="70%" />

Today: watch the running service, and call a person only when it matters.

</div>

<!--
Why monitor: the model is deployed (Weeks 9–10) and in operation. This week watches the service; Week 12 watches the data and the predictions, in the same stage.
-->

---
layout: center
---

# Your API is running.
# What do you keep an eye on?

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-traffic-signal class="ic" /><b>Traffic</b>how many requests arrive</div>
  <div v-click class="card"><ph-x-circle class="ic" style="color:#dc2626" /><b>Errors</b>how many fail</div>
  <div v-click class="card"><ph-clock class="ic" /><b>Latency</b>how long an answer takes</div>
  <div v-click class="card"><ph-gauge class="ic" /><b>Saturation</b>how full the service is</div>
</div>

<div v-click class="mt-4">

Google's SRE book calls them the **four golden signals**[^1][].

</div>

[^1]: Ewaschuk, "Monitoring Distributed Systems", in *Site Reliability Engineering*, Google, 2017. https://sre.google/sre-book/monitoring-distributed-systems/

<!--
The book: "If you can only measure four metrics of your user-facing system, focus on these four." The lab's dashboard shows the first three: requests per second, error rate, latency.
-->

---

# Which signal moves?

<carbon-chart-line class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:11rem"><ph-globe class="ic" /><b>A caller</b><br><small>sends <span class="mono">glucose = 0</span></small></div>
  <div class="arrow">→</div>
  <div style="border:2px solid #0284c7; border-radius:0.8rem; padding:0.4rem 0.8rem 0.8rem">
    <div class="text-center text-sm mono" style="color:#0284c7; margin-bottom:0.4rem">POST /predict</div>
    <div class="flow" style="margin:0">
      <div class="node green" style="width:10rem"><ph-seal-check class="ic" /><b>Contract</b><br><small>rejects it: 422</small></div>
      <div class="arrow fail">✗</div>
      <div class="node sky" style="width:9rem; opacity:0.6"><ph-cube class="ic" /><b>Model</b><br><small>never called</small></div>
    </div>
  </div>
</div>

<div class="text-sm">

| **Signal** | **Moves?** |
| --- | --- |
| Traffic | <span v-click="1"><b style="color:#dc2626">✗</b> the same number of requests</span> |
| Errors (5xx) | <span v-click="2"><b style="color:#dc2626">✗</b> a 422 is the contract working</span> |
| Latency | <span v-click="3"><b style="color:#dc2626">✗</b> a rejection is fast</span> |
| Saturation | <span v-click="4"><b style="color:#dc2626">✗</b> a rejection costs almost nothing</span> |
| <span v-click="5">**Contract violations**</span> | <span v-click="6"><b style="color:#d97706"><ph-trend-up /> goes up</b> a signal about the model's input</span> |

</div>

</div>

<!--
The request reaches our endpoint, the contract runs first and rejects it, so the model is never called. None of the four golden signals moves: the service is healthy, and the caller's patients get no prediction. A model service needs signals of its own, such as contract violations.
A caller who sends glucose in mmol/L instead of mg/dL passes the contract (the values are above 0) and moves nothing at all: Week 12.
-->

---

# Metric types

<carbon-meter class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-trend-up class="ic" /><b>Counter</b>only goes up<br>starts again at 0 when the process restarts<hr style="margin:0.6rem 0"><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">http_requests_total</span><br><small>requests served</small><br><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">model_predictions_total</span><br><small>predictions, by outcome</small><br><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">model_contract_violations_total</span><br><small>rejected requests, by failed check</small><br></div>
  <div v-click class="card"><ph-gauge class="ic" /><b>Gauge</b>goes up and down<br>a value right now<hr style="margin:0.6rem 0"><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">http_requests_in_flight</span><br><small>requests in progress</small><br><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">process_resident_memory_bytes</span><br><small>memory in use</small><br></div>
  <div v-click class="card"><ph-chart-bar class="ic" /><b>Histogram</b>counts values into buckets<br><span class="mono">≤ 50 ms · ≤ 100 ms · ≤ 250 ms</span><hr style="margin:0.6rem 0"><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">http_request_duration_seconds</span><br><small>how long requests took</small><br><span class="mono" style="font-size:0.85rem; color:#0f172a; background:#ffffff; padding:0 0.3rem; border-radius:0.25rem; font-weight:600">model_prediction_score</span><br><small>the spread of the scores</small><br></div>
</div>

</div>

<!--
A metric is a number sampled over time. A counter's raw value means little (it depends on when the process started); Section 2 shows how to read it.
The names are the ones the lab's API exports. The `http_` metrics would be the same for a service that returned the weather; the `model_` ones exist because this one serves a model: Week 10's "What do you watch in the first hour?" as metrics. Week 12 compares `model_prediction_score` with the training data. `process_resident_memory_bytes` comes free from the client's default registry, on Linux only, so it appears in the container and not on a Mac.
-->

---

# Labels

<carbon-tag class="icon-corner" />

<div class="middle">

<div class="flow" style="align-items:center">
  <div class="node" style="width:14rem"><span class="mono">http_requests_total</span><br><b>300</b> requests</div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" style="display:flex; flex-direction:column; gap:0.5rem; font-size:0.85rem">
    <div class="node green" style="width:24rem; display:flex; justify-content:space-between; text-align:left"><span class="mono">route="/predict", status="200"</span><b>233</b></div>
    <div class="node amber" style="width:24rem; display:flex; justify-content:space-between; text-align:left"><span class="mono">route="/predict", status="422"</span><b>33</b></div>
    <div class="node rose" style="width:24rem; display:flex; justify-content:space-between; text-align:left"><span class="mono">route="__unmatched__", status="404"</span><b>34</b></div>
  </div>
</div>

<v-click at="2">

A **label** is a name and a value attached to a metric, such as `status="422"`. You can filter by it, or add over it.

</v-click>

<v-click at="3">

Each combination of label values is its own **time series**.

</v-click>

</div>

<!--
Real numbers after 300 requests from the lab's traffic generator (lab README, Exercise 2). A series appears the first time its combination happens: the first 500 would add a fourth row with `status="500"`. Every request lands in exactly one series, so the rows always add up to the total. Only the route has a catch-all, `__unmatched__`, for paths that match no route.
-->
---

# How many time series?

<carbon-calculator class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **Label** | **Values** |
| --- | --- |
| `method` | `GET`, `POST` |
| `route` | `/health`, `/predict`, `/v1/models/{model_name}:predict`, `__unmatched__` |
| `status` | `200`, `404`, `422`, `500`, `503` |

</div>

<v-click at="1">

At most 2 × 4 × 5 = **40** series for `http_requests_total`.

</v-click>

<div class="cards" style="grid-template-columns:repeat(2,1fr); margin-top:1rem">
  <div v-click="2" class="card"><b>Add <code>outcome</code></b><span class="mono" style="font-size:0.85rem">"positive", "negative"</span><span v-click="3"><b>× 2 = 80</b></span></div>
  <div v-click="4" class="card"><b>Add <code>model_version</code></b><span class="mono" style="font-size:0.85rem">"6", "7", "8", …</span><span v-click="5" style="color:#dc2626"><b>× every version ever served</b></span></div>
</div>

</div>

<!--
The lab API's routes and status codes; `/metrics` is not counted. The product is an upper bound: a series exists only once its combination has happened, and GET /predict never does. The number of series is the product of the number of values of every label, so one more label multiplies the whole metric. The cost is paid in the collector's memory, which other teams share, and each series stays for the whole retention period.
-->

---

# Choosing labels

<carbon-chart-multitype class="icon-corner" />

<div class="middle">

- A label's values come from a short list you can write down: methods, routes, status codes.
- An ID, an e-mail address or a raw path goes into a log line, not a label[^1][].

<div class="flow" style="align-items:center">
  <div class="node amber" style="width:13rem"><ph-globe class="ic" /><b>1,000 requests</b><br><small>each for a different place<br><span class="mono">GET /forecast/47.91,17.83</span></small></div>
  <div style="display:flex; flex-direction:column; gap:0.6rem">
    <div class="flow" style="margin:0"><div class="arrow-l">route = the template<span class="arrow">→</span></div><div class="node green" style="width:15rem"><span class="mono">/forecast/{lat},{lon}</span><br><b>1</b> time series</div></div>
    <div class="flow" style="margin:0"><div class="arrow-l fail">route = the raw path<span class="arrow">→</span></div><div class="node rose" style="width:15rem"><span class="mono">/forecast/47.91,17.83</span> …<br><b>1,000</b> time series</div></div>
  </div>
</div>

> [!TIP]
> Label requests with the route template, and give every unknown path one value, such as `__unmatched__`.

</div>

[^1]: Prometheus docs, "Metric and label naming", Labels. https://prometheus.io/docs/practices/naming/#labels

<!--
Measured with prometheus_client 0.26.0 (the lab's version), counting the series in a fresh registry. The count with the template stays 1 however many requests arrive; the raw path adds one series per new place.
On a public endpoint a scanner trying `/wp-admin`, `/.env`, … creates one series per path, so a stranger chooses your cardinality. The lab collapses every unmatched path into `__unmatched__`.
-->

---

# Metrics and logs

<carbon-document class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:11rem"><ph-globe class="ic" /><b>One request</b><br><small>POST /predict, 6.4 ms, 422</small></div>
  <div style="display:flex; flex-direction:column; gap:0.6rem">
    <div class="flow" style="margin:0; justify-content:flex-start">
      <div class="arrow">→</div>
      <div class="node sky" style="width:24rem; text-align:left"><b>Metric</b> <span class="mono">http_requests_total{…,status="422"} += 1</span></div>
    </div>
    <div class="flow" style="margin:0; justify-content:flex-start">
      <div class="arrow">→</div>
      <div class="node violet" style="width:24rem; text-align:left"><b>Log line</b> <span class="mono">{"request_id": "9f2c…", "status": 422, "duration_ms": 6.4, …}</span></div>
    </div>
  </div>
</div>

<div class="text-sm">

| | **Metric** | **Log line** |
| --- | --- | --- |
| Saved data | <span v-click="1">one count per label combination</span> | <span v-click="1">every field of one request</span> |
| Stored in | <span v-click="2">a metrics database that scrapes the service</span> | <span v-click="2">stdout, then a log store</span> |
| Read by | <span v-click="3">dashboards, alert rules, the on-call engineer</span> | <span v-click="3">the engineer debugging one failure</span> |
| Answers | <span v-click="4">Is something wrong, and since when?</span> | <span v-click="4">What happened to this request?</span> |

</div>

</div>

<!--
The lab writes both from the same middleware; the log line goes to stdout as JSON, and the container runtime collects it. An alert fires on a metric; the engineer then searches the logs for the failing requests, by `request_id`. As a label, the `request_id` would add one series per request. A metric costs the same for 300 or 3 million requests; log lines grow with every request, so teams keep them for a shorter time than metrics.
-->

---

# Traces

<carbon-flow class="icon-corner" />

<div class="middle">

- A **trace** is the path of one request through several services: a list of spans.
- A **span** is one step: the service, its start time, its duration, and the trace ID.

<div style="margin:1rem auto 0; width:100%; max-width:40rem">
  <div class="text-sm mono" style="opacity:0.7; margin-bottom:0.3rem">trace ID 4bf92f35…</div>
  <div class="bar-row"><span>API</span><div class="bar-track"><div class="bar-fill sky" style="left:0%; width:100%"></div></div><span>900 ms</span></div>
  <div v-click="1" class="bar-row"><span>feature store</span><div class="bar-track"><div class="bar-fill amber" style="left:5%; width:80%"></div></div><span>720 ms</span></div>
  <div v-click="2" class="bar-row"><span>database</span><div class="bar-track"><div class="bar-fill" style="left:8%; width:74%"></div></div><span>666 ms</span></div>
  <div v-click="3" class="bar-row"><span>model</span><div class="bar-track"><div class="bar-fill green" style="left:88%; width:2%"></div></div><span>18 ms</span></div>
</div>

</div>

<!--
An illustration, not a measurement. With several services, "the request took 900 ms" is not enough; the trace shows where the time went: here the database, not the model. Each service sends its spans to a tracing backend, which draws them like this. OpenTelemetry produces spans; Jaeger or Grafana Tempo store and show them.
Our service is one process and calls no other service, so the course installs no tracing tool. The `request_id` in our log line is where a trace ID would go.
-->

---

# **Quiz** · Metric, log or trace?

<carbon-help class="icon-corner" />

<div class="middle">

| **Question** | **Answer from** |
| --- | --- |
| Is p95 latency higher since Tuesday's deploy? | <span v-click="1">a metric</span> |
| Why did user 812's forecast fail at 09:14? | <span v-click="2">a log</span> |
| Which of five services made checkout slow? | <span v-click="3">a trace</span> |

</div>

<!--
A metric answers about many requests over a long time; a log about one request; a trace about one request across services.
"How many requests failed last month?" is a metric: logs could count it too, but few teams keep a month of logs.
-->

---

# Monitoring and observability

<carbon-view class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click="1" class="card"><ph-gauge class="ic" /><b>Monitoring</b>answers the questions you planned<br><small>dashboards, thresholds, alerts</small></div>
  <div v-click="2" class="card"><ph-magnifying-glass class="ic" /><b>Observability</b>answers questions you did not plan,<br>from data you already have<br><small>logs with an ID, labels you can filter by</small></div>
</div>

</div>

<!--
The line between the two terms is disputed, partly by vendors. A useful test: the last time something broke, did you have the data, or did you add a log line and wait for it to happen again? Waiting is the sign of poor observability.
-->

---
layout: section
---

# 2 · Prometheus and Grafana

<!--
About 18 minutes. The code examples use a small forecast service, not our patients: the lab writes the diabetes API's instrumentation.
-->

---
class: fn-inline
---

# Tool options

<carbon-tool-box class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><div class="logo" style="background-image:url(/prometheus-logo.webp)"></div><b>Prometheus</b>collects and stores metrics, pulls them over HTTP</div>
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><div class="logo" style="background-image:url(/grafana-logo.webp)"></div><b>Grafana</b>dashboards over many data sources</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/opentelemetry-logo.png)"></div><b>OpenTelemetry</b>produces and exports traces, metrics and logs, stores nothing</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/victoriametrics-logo.webp)"></div><b>VictoriaMetrics</b>time-series storage that answers Prometheus queries</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/datadog-logo.webp)"></div><b>Datadog</b>an agent on each host sends data to Datadog</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/cloudwatch-logo.png)"></div><b>Amazon CloudWatch</b>metrics, logs and alarms for AWS</div>
</div>

<div class="text-sm opacity-70">

Prometheus[^1][] · Grafana[^2][] · OpenTelemetry[^3][] · VictoriaMetrics[^4][] · Datadog[^5][] · CloudWatch[^6][]

</div>

<v-click>

**We use Prometheus and Grafana:** open source, one container each, and the queries are plain text we can keep in Git.

</v-click>

[^1]: https://prometheus.io/docs/introduction/overview/
[^2]: https://grafana.com/docs/grafana/latest/fundamentals/dashboards-overview/
[^3]: https://opentelemetry.io/docs/what-is-opentelemetry/
[^4]: https://docs.victoriametrics.com/victoriametrics/
[^5]: https://docs.datadoghq.com/getting_started/agent/
[^6]: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html

<!--
Prometheus started at SoundCloud in 2012 and joined the CNCF in 2016, as its second project after Kubernetes. Its docs warn that it is the wrong tool where you need 100% accuracy, such as per-request billing.
OpenTelemetry is how many teams produce the data; it then sends it to a backend such as Prometheus.
-->

---

# How Prometheus works

<carbon-arrows-horizontal class="icon-corner" />

<div class="middle">

Prometheus collects metrics from services, stores them as time series, and checks alert rules on them.

<div class="flow">
  <div class="node sky" style="width:11rem"><ph-cube class="ic" /><b>API</b><br><span class="mono">api:8000/metrics</span></div>
  <div v-click="1" class="arrow-l on">GET every 5 s<span class="arrow">←</span></div>
  <div v-click="1" class="node violet" style="width:11rem"><ph-database class="ic" /><b>Prometheus</b><br><small>stores the time series</small></div>
  <div v-click="2" class="arrow-l">PromQL, when you look<span class="arrow">←</span></div>
  <div v-click="2" class="node green" style="width:10rem"><ph-chart-line class="ic" /><b>Grafana</b><br><small>stores no data</small></div>
</div>

<div v-click="3" class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><b>Target</b>a service on Prometheus' list<br>DOWN if it cannot be reached</div>
  <div class="card"><b>Scrape</b>a GET to the target's <code>/metrics</code>, on a schedule</div>
  <div class="card"><b><code>up</code></b>added for every target<br>1 if the scrape worked, 0 if not</div>
</div>

</div>

<!--
Prometheus **pulls**: the service only answers a GET. Most logging systems students know push. A push gateway exists for short jobs. The lab scrapes every 5 s from a static list of targets.
Inside the Prometheus container, `localhost` is Prometheus itself, so the target is `api:8000`, the Compose service name.
-->
---

# Prometheus setup

<carbon-settings class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem">
<div style="border:2px solid #0284c7; border-radius:0.8rem; padding:0.4rem 1rem">

**<ph-cube /> In our service**

- define each metric: name, type, labels
- update it in the request handler
- serve all metrics at `GET /metrics`

</div>
<div v-click="1" style="border:2px solid #7c3aed; border-radius:0.8rem; padding:0.4rem 1rem">

**<ph-database /> In Prometheus**

- the targets to scrape, and how often

```yaml
scrape_configs:
  - job_name: forecast
    scrape_interval: 5s
    static_configs:
      - targets: ["forecast:8000"]
```

</div>
</div>

</div>

<!--
The service only answers GET /metrics; it does not know Prometheus exists. Prometheus reads `prometheus.yml` at start-up. In Kubernetes, service discovery can find pods by label instead of a static list, but that is also written in this file. Grafana needs one more file: a data source that points at Prometheus ("Dashboards live in Git").
https://prometheus.io/docs/prometheus/latest/configuration/configuration/
-->
---

# `prometheus_client` quick start

<carbon-terminal class="icon-corner" />

<div class="middle">

```python {1-4|6-9|11-17|19-21|all}
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

</div>

<!--
Define the metrics once, update them in the handler, and serve them at `/metrics`. `generate_latest()` renders every metric as the text a scrape receives. Install with `uv add prometheus-client`.
Adapted from the client's documentation, https://prometheus.github.io/client_python/.
-->

---

# What Prometheus reads

<carbon-document-view class="icon-corner" />

<div class="middle">

`GET /metrics` after three forecasts:

```text {all|1|2-5|6-7}
forecast_requests_total{status="200"} 3.0
forecast_duration_seconds_bucket{le="0.05"} 1.0
forecast_duration_seconds_bucket{le="0.1"} 2.0
forecast_duration_seconds_bucket{le="0.25"} 2.0
forecast_duration_seconds_bucket{le="+Inf"} 3.0
forecast_duration_seconds_count 3.0
forecast_duration_seconds_sum 0.437
```

<v-clicks at="1">

- One scrape reads the whole page: every line of every metric.
- The buckets are **cumulative**: `le="0.1"` counts every request up to 100 ms.
- `_count` and `_sum` come with every histogram.

</v-clicks>

</div>

<!--
Real output of the app on "`prometheus_client` quick start" (prometheus_client 0.26.0, FastAPI 0.141.1, through `TestClient`), with a stand-in model that took 42, 80 and 300 ms. The `# HELP` and `# TYPE` lines, the `_created` timestamps and the default `python_*` metrics are cut here; the sum is rounded.
`_sum / _count` gives the mean latency, the one number not to quote: a mean hides the slow tail.
-->

---

# PromQL

<carbon-query class="icon-corner" />

<div class="middle">

<div class="flow" style="margin:0 0 0.5rem">
  <div class="node green no-shrink" style="width:13rem"><b>Grafana, alert rules</b></div>
  <div class="arrow-l on">PromQL<span class="arrow">→</span></div>
  <div class="node violet no-shrink" style="width:9rem"><b>Prometheus</b></div>
  <div class="arrow-l">GET /metrics<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:8rem"><b>API</b></div>
</div>

PromQL is how we ask Prometheus for data: select series by name and labels, then compute over them[^1][].

<div class="text-sm">

| **Query** | **Returns** |
| --- | --- |
| `forecast_requests_total` | <span v-click="1">every series of the counter</span> |
| `forecast_requests_total{status="500"}` | <span v-click="2">only the series with status 500</span> |
| `sum(forecast_requests_total)` | <span v-click="3">the series added together</span> |
| `rate(forecast_requests_total[1m])` | <span v-click="4">requests per second, over the last minute</span> |

</div>

</div>

[^1]: Prometheus docs, "Querying basics". https://prometheus.io/docs/prometheus/latest/querying/basics/

<!--
Every Grafana panel and every alert rule is a PromQL query. Prometheus reads our service with a plain GET, not with PromQL. `{status="500"}` filters by a label, `sum` adds over labels, and `[1m]` asks for the last minute of samples. The next slides show why a counter is read with `rate()`, and how a percentile is computed from buckets.
-->

---
layout: center
---

# A counter fell from 1,500 to 120. What happened?

<div class="text-sm" style="margin:1rem auto; max-width:34rem">

| Time | `forecast_requests_total` | `rate(…[1m])` |
| --- | --- | --- |
| 10:00 | 1,200 | |
| 10:01 | 1,500 | 5.0 per second |
| 10:02 | **120** | <span v-click="2">2.0 per second</span> |
| 10:03 | 420 | 5.0 per second |

</div>

<v-click at="1">

- The process restarted, and the counter started again at 0.

</v-click>

<v-click at="3">

- `rate()` reads a fall as a restart. Graph `rate()`, never the raw counter.

</v-click>

<!--
Prometheus documents it: "Breaks in monotonicity (such as counter resets due to target restarts) are automatically adjusted for." After the reset it counts the 120 as new requests.
https://prometheus.io/docs/prometheus/latest/querying/functions/#rate
Simplified: `rate()` needs at least two samples in its range, so use a range of about four scrape intervals (the lab scrapes every 5 s).
-->

---
class: fn-inline
---

# Several workers in one container

<carbon-copy class="icon-corner" />

<div class="middle">

With `--workers 4`, the server runs four **worker** processes in one container. Each keeps its own counters.

<div class="flow" style="align-items:center">
  <div class="node amber no-shrink" style="width:8rem"><ph-globe class="ic" /><b>200 requests</b></div>
  <div class="arrow">→</div>
  <div style="border:2px solid #0284c7; border-radius:0.8rem; padding:0.4rem 0.6rem 0.6rem">
    <div class="text-center text-sm" style="color:#0284c7; margin-bottom:0.3rem">one container, one port<br>each worker has its own counter</div>
    <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:0.4rem">
      <div class="node sky" style="width:7rem; margin:0; padding:0.3rem"><b>worker 1</b></div>
      <div class="node sky" style="width:7rem; margin:0; padding:0.3rem"><b>worker 2</b></div>
      <div class="node sky" style="width:7rem; margin:0; padding:0.3rem"><b>worker 3</b></div>
      <div class="node sky" style="width:7rem; margin:0; padding:0.3rem"><b>worker 4</b></div>
    </div>
  </div>
  <div v-click="1" class="arrow-l">GET /metrics<br>one worker answers<span class="arrow">←</span></div>
  <div v-click="1" class="node violet no-shrink" style="width:9rem"><ph-database class="ic" /><b>Prometheus</b><br><small>30 scrapes</small></div>
</div>

<div v-click="2" class="flow" style="margin:0.4rem 0">
  <div class="node no-shrink" style="width:9rem"><b>45</b><br><small>in 5 scrapes</small></div>
  <div class="node no-shrink" style="width:9rem"><b>155</b><br><small>in 24 scrapes</small></div>
  <div class="node rose no-shrink" style="width:13rem"><b>200</b><br><small>the true total, never seen</small></div>
</div>

<v-click at="3">

> [!TIP]
> Run one worker per container and add replicas[^1][]. If you need workers, use multiprocess mode[^2][].

</v-click>

</div>

[^1]: FastAPI docs, "FastAPI in Containers - Docker", Replication. https://fastapi.tiangolo.com/deployment/docker/
[^2]: prometheus_client docs, "Multiprocess Mode". https://prometheus.github.io/client_python/multiprocess/

<!--
Nobody gets this by accident: uvicorn runs one worker unless told otherwise, and the course's images say `--workers 1`. A team adds workers deliberately, for more CPU, and then the metrics go wrong without an error. FastAPI's docs recommend one process per container in Kubernetes and replication at the cluster level; multiprocess mode works, but loses custom collectors such as CPU and memory, and Info metrics. Measured with the lab's `make workers-trap` (uvicorn, 4 workers). Each scrape is answered by whichever worker gets the connection, so Prometheus sees one worker's count, and `rate()` reads every fall from 155 to 45 as a restart. With HTTP keep-alive it was worse: every scrape reused one connection and returned a stable 35 against a true 40. A wrong number that looks stable gets used.
The Week 9 and 10 images already run one worker, so nothing changes there.
-->
---

# Scraping replicas

<carbon-network-3 class="icon-corner" />

<div class="middle">

<div class="flow" style="align-items:center">
  <div class="node amber no-shrink" style="width:7rem"><ph-globe class="ic" /><b>Requests</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:8rem"><b>Load balancer</b></div>
  <div class="arrow">→</div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node sky" style="width:10rem; margin:0"><b>replica 1</b> <span class="mono text-xs">/metrics</span></div>
    <div class="node sky" style="width:10rem; margin:0"><b>replica 2</b> <span class="mono text-xs">/metrics</span></div>
    <div class="node sky" style="width:10rem; margin:0"><b>replica 3</b> <span class="mono text-xs">/metrics</span></div>
  </div>
  <div v-click="1" class="arrow-l on">scrapes each one<span class="arrow">←</span></div>
  <div v-click="1" class="node violet no-shrink" style="width:9rem"><ph-database class="ic" /><b>Prometheus</b></div>
</div>

<v-click at="2">

Each replica is its own target. Prometheus adds an `instance` label to every series[^1][]:

<div class="text-sm">

```text
forecast_requests_total{instance="10.0.0.11:8000", status="200"} 412
forecast_requests_total{instance="10.0.0.12:8000", status="200"} 398
```

</div>

</v-click>

<v-click at="3">

The total is a PromQL sum over the instances.

</v-click>

</div>

[^1]: Prometheus docs, "Jobs and instances". https://prometheus.io/docs/concepts/jobs_instances/

<!--
Hypothetical counts. Prometheus scrapes the replicas directly, not through the load balancer: through it, each scrape would reach a random replica, the workers problem again. In Kubernetes the target list comes from service discovery, which finds the pods by label, so a new replica is scraped without editing the config. KServe's annotation `serving.kserve.io/enable-prometheus-scraping` exposes the metrics port, but Prometheus must still be configured to scrape the pods (KServe docs, "Prometheus metrics").
-->
---
layout: center
---

# Three replicas of our API report their p95 latency: 49, 81 and 241 ms.
# What is the p95 of all their requests?

<div class="text-sm" style="margin-top:0.5rem">

A replica is one copy of the service. A load balancer spreads the requests over the copies (Week 9).

</div>

<div v-click>

- The mean, 124 ms? Wrong.
- The largest, 241 ms? Also wrong.
- **These three numbers cannot tell you.**

</div>

<!--
Percentiles do not average. The numbers come from the bucket counts on "Percentiles from buckets" (100 requests per replica), computed with Prometheus' interpolation rule.
-->

---

# Percentiles from buckets

<carbon-chart-histogram class="icon-corner" />

<div class="middle">

Hypothetical: three replicas, 100 requests each

<div class="text-sm">

| **Requests up to** | **50 ms** | **100 ms** | **250 ms** | **all** |
| --- | --- | --- | --- | --- |
| replica A | 97 | 100 | 100 | 100 |
| replica B | 90 | 98 | 100 | 100 |
| replica C | 50 | 80 | 96 | 100 |
| <span v-click="1">**sum**</span> | <span v-click="1">237</span> | <span v-click="1">278</span> | <span v-click="1">**296**</span> | <span v-click="1">300</span> |

</div>

<v-click at="2">

The 285th of 300 requests falls between 100 and 250 ms: p95 ≈ **158 ms**.

</v-click>

<v-click at="3">

Add the replicas' bucket counts first, then take the percentile of the sum[^1][].

</v-click>

</div>

[^1]: Prometheus docs, "Histograms and summaries". https://prometheus.io/docs/practices/histograms/

<!--
A constructed example. Inside a bucket Prometheus assumes the requests are spread evenly ("linear interpolation"), so p95 = 100 + (285 − 278) / (296 − 278) × 150 ms.
A quantile is only as precise as its buckets. That is why the lab's latency target, 250 ms, is itself a bucket boundary.
-->

---

# Grafana

<carbon-dashboard class="icon-corner" />

<div class="middle">

Grafana draws dashboards from data sources. It stores the dashboards, not the data[^1][].

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click="1" class="card"><ph-database class="ic" /><b>Data source</b>where the data lives: Prometheus, a log store, a SQL database</div>
  <div v-click="2" class="card"><ph-squares-four class="ic" /><b>Dashboard</b>one page of panels</div>
  <div v-click="3" class="card"><ph-chart-line class="ic" /><b>Panel</b>one query, drawn as a graph, a number or a table</div>
</div>

<div v-click="4" class="flow" style="margin-top:1rem">
  <div class="node green" style="width:11rem"><ph-chart-line class="ic" /><b>Panel</b><br><small>p95 latency</small></div>
  <div class="arrow-l">PromQL<span class="arrow">→</span></div>
  <div class="node violet" style="width:10rem"><ph-database class="ic" /><b>Prometheus</b></div>
  <div class="arrow-l">scrape<span class="arrow">→</span></div>
  <div class="node sky" style="width:9rem"><ph-cube class="ic" /><b>API</b></div>
</div>

</div>

[^1]: Grafana docs, "Dashboards overview". https://grafana.com/docs/grafana/latest/fundamentals/dashboards-overview/

<!--
Grafana asks the data source again every time the page refreshes, so a dashboard is always as fresh as Prometheus. Grafana also has its own alerting; this course keeps the alert rules in Prometheus.
-->

---

# Grafana dashboard

<img src="/grafana-dashboard.png" style="max-height:440px; max-width:100%; margin:0 auto; border-radius:0.4rem" />

<!--
The lab's dashboard, `diabetes-service`, during `make traffic`. Every panel is one PromQL query: request rate by status, error rate, latency percentiles, requests in flight, predictions by outcome, contract violations by check, and four more. It is loaded from files when Grafana starts, with no clicking.
-->

---

# A panel and its query

<carbon-query class="icon-corner" />

<div class="middle">

<img src="/grafana-latency.png" style="max-height:330px; margin:0 auto; border-radius:0.4rem" />

</div>

<!--
Open any panel with "Edit" to see its query. The latency panel uses the percentile-from-buckets query: add the buckets over the replicas, then take the 95th percentile.
-->

---

# Grafana configuration

<carbon-document class="icon-corner" />

<div class="middle">

At start-up, YAML files tell Grafana the data source and where the dashboards are. A dashboard is a JSON file:

<div class="text-sm">

```json
{
  "title": "Forecast service",
  "panels": [
    {
      "type": "timeseries",
      "title": "Requests per second",
      "targets": [{ "expr": "sum(rate(forecast_requests_total[5m]))" }]
    }
  ]
}
```

</div>

> [!TIP]
> Keep dashboards as JSON files in Git, next to the code that exports the metrics.

</div>

<!--
In Git, a dashboard change is reviewed in a pull request like code. A test can check that every query names a metric the service still exports; a renamed metric otherwise leaves an empty panel, and from the panel alone you cannot tell "no traffic" from "no metric". Grafana calls this the dashboard JSON model; "Export" in the UI produces the same file. Loading files at start-up is called provisioning. The lab's files are `grafana/provisioning/datasources/prometheus.yml`, `grafana/provisioning/dashboards/provider.yml` and `grafana/dashboards/diabetes-service.json`.
https://grafana.com/docs/grafana/latest/administration/provisioning/
-->
---
layout: section
---

# 3 · SLIs, SLOs and error budgets

<!--
About 10 minutes. No new tool: the SRE Workbook's SLO chapters play the role of the tutorial this week. The lab writes the numbers in `slo.yaml`.
-->

---

# SLI, SLO and SLA

<carbon-rule class="icon-corner" />

<div class="middle">

| **Term** | **Stands for** | **Means** |
| --- | --- | --- |
| SLI | service level indicator | <span v-click="1">a measurement: good events ÷ valid events</span> |
| SLO | service level objective | <span v-click="2">a target for an SLI, over a time window</span> |
| SLA | service level agreement | <span v-click="3">an SLO in a contract, with a penalty if it is missed</span> |
| Error budget | | <span v-click="4">the failure an SLO allows: 1 − target</span> |

</div>

<div class="text-sm opacity-70">

Google, *Site Reliability Engineering*, "Service Level Objectives"[^1][]

</div>

[^1]: https://sre.google/sre-book/service-level-objectives/

<!--
"The service must be fast and reliable" cannot be checked. "We may be down for seven hours a month" can, and a product owner will have an opinion about it. The Workbook: an SLA is "a business contract that comes into effect when your users are so unhappy you have to compensate them". The SLO is stricter than the SLA, so that the team hears about trouble before the contract does.
-->
---

# SLI: good events ÷ valid events

<carbon-chart-pie class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:12rem"><ph-globe class="ic" /><b>40 requests</b><br><DataBatch cells="gggg.ggg ggggrggg gg.ggggg ggggg.gg gggggggg" :cols="8" /></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:20rem; text-align:left; font-size:0.9rem"><DataBatch cells="g" /> 36 answered (200)<br><DataBatch cells="r" /> 1 failed (500)<br><DataBatch cells="." /> 3 rejected by the contract (422)</div>
</div>

Should a 422 count against us?

<v-click>

No: the contract did its job. Availability = 36 ÷ 37 = **97.3%**.

</v-click>

</div>

<!--
The SRE Workbook writes the SLI as "the number of good events divided by the total number of events". We leave 422s out of both, so a caller cannot spend our budget by sending bad data; `model_contract_violations_total` watches them instead.
A ratio of events adds up across replicas; "uptime" of a process does not, and no user is a user of a process.
-->

---

# Example SLOs

<carbon-rule class="icon-corner" />

<div class="middle">

| **Term** | **Example: our service** |
| --- | --- |
| Availability SLI | non-5xx answers ÷ requests that passed the contract |
| Availability SLO | 99% over 30 days |
| Latency SLO | 95% of requests faster than 250 ms\*, over 30 days |
| SLA | none |
| Error budget | 1% of requests |

<v-click>

\* measured where? The same model: p95 7.67 ms in the process, 22.97 ms from the host into the container.

</v-click>

<v-click>

> [!TIP]
> Agree each SLO before the first incident: what counts as good, the target, and the window.

</v-click>

</div>

<!--
The star: a latency means nothing without the place it was measured from. In the process (Week 9, through `TestClient`): p50 4.48 ms, p95 7.67 ms. From the host into the container (Week 11): p50 8.79 ms, p95 22.97 ms; the mean of that run, 10.01 ms, hides the slow tail. Quote a latency with its percentile and where it was measured, never the mean.
The lab writes these in `slo.yaml`. When the budget is spent, reliability work comes first and risky releases wait: the SRE Workbook calls this an error budget policy. A budget that is never touched may mean the target is too loose. https://sre.google/workbook/implementing-slos/
-->
---

# The nines of availability

<carbon-hourglass class="icon-corner" />

<div class="middle">

| **Availability** | **Name** | **Error budget in 30 days** |
| --- | --- | --- |
| 99% | two nines | <span v-click="1">**7 h 12 min**</span> |
| 99.9% | three nines | <span v-click="2">43 min 12 s</span> |
| 99.99% | four nines | <span v-click="3">4 min 19 s</span> |
| 99.999% | five nines | <span v-click="4">26 s</span> |
| 100% | | <span v-click="5">0: no deploy may ever fail</span> |

</div>

<!--
30 days are 43,200 minutes; each budget is that times 1 − target. The lab's `make slo-budget` prints 7h 12m for 99%, checked in `tests/test_slo.py`. At four nines and above, the budget is shorter than the time to notice and act, so it needs redundancy in the design, not a faster on-call engineer.
-->
---
layout: section
---

# 4 · Alerting

<!--
About 20 minutes. It opens with one case, alarm fatigue in hospitals; Option B (Knight Capital's e-mails) is hidden after the hospital slides. Then the same effect on our service, and burn-rate alerts. The lab's Exercise 4 reads the SLO and fires an alert. Alertmanager, which routes an alert to a person, is Week 13: this week Prometheus only marks an alert as pending or firing.
-->

---
layout: two-cols
---

# Monitoring in hospitals

Bedside devices measure each patient around the clock.

- A value over its threshold sounds an **alarm**.
- A nurse hears it and comes to the bed.

In 2013, The Joint Commission (US) published an alert about these alarms[^1][].

::right::

<div style="margin-top:3rem">
<img src="/bedside-patient-monitor.png" style="max-height:300px; margin:0 auto; border-radius:0.5rem" />
</div>

[^1]: The Joint Commission, Sentinel Event Alert 50, "Medical device alarm safety in hospitals", 8 Apr 2013. https://www.jointcommission.org/en-us/knowledge-library/newsletters/sentinel-event-alert/issue-50

<!--
This is our own domain: patients, measured by machines. The alert is a first-party document; quote it by number and date.
-->

---
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div style="width:20rem"><div class="text-5xl font-bold">several hundred</div><div>alarm signals per patient per day, on one unit</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:20rem"><div class="text-5xl font-bold" style="color:#dc2626">85–99%</div><div>need no clinical action</div></div></div>
</div>

<br>

The Joint Commission, Sentinel Event Alert 50[^1][]

[^1]: The Joint Commission, Sentinel Event Alert 50, 8 Apr 2013.

<!--
Across a hospital this is tens of thousands of alarm signals a day. The 85–99% is an estimate, and the alert calls it one.
-->

---

# Alarm fatigue

<carbon-warning-alt class="icon-corner" />

<div class="middle">

<div class="flow">
  <div style="display:flex; flex-direction:column; gap:0.6rem">
    <div class="node amber" style="width:12rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem"><span style="white-space:nowrap"><ph-heartbeat /> Bed 1</span><DataBatch cells="..r. ...." /></div>
    <div class="node amber" style="width:12rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem"><span style="white-space:nowrap"><ph-heartbeat /> Bed 2</span><DataBatch cells=".... ...." /></div>
    <div class="node amber" style="width:12rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem"><span style="white-space:nowrap"><ph-heartbeat /> Bed 3</span><DataBatch cells=".... ..r." /></div>
  </div>
  <div class="arrow-l">every threshold crossing<span class="arrow">→</span></div>
  <div class="node" style="width:10rem"><ph-bell-ringing class="ic" /><b>Alarm signals</b><br><DataBatch cells="..r..... ........ ......r." :cols="8" /></div>
  <div class="arrow-l fail">too many to hear<span class="arrow">→</span></div>
  <div class="node rose" style="width:10rem"><ph-bell-slash class="ic" /><b>Staff</b><br><small>stop responding</small></div>
</div>

<div v-click class="flex justify-center gap-6 text-center" style="margin-top:0.5rem">
  <div style="width:17rem"><div class="text-4xl font-bold" style="color:#dc2626">80</div><div class="text-sm">alarm-related deaths, Jan 2009 – Jun 2012<br><small>The Joint Commission's database</small></div></div>
  <div style="width:17rem"><div class="text-4xl font-bold" style="color:#dc2626">566</div><div class="text-sm">alarm-related deaths, Jan 2005 – Jun 2010<br><small>an FDA database</small></div></div>
</div>

</div>

<div class="text-sm opacity-70">

The Joint Commission, Sentinel Event Alert 50[^1][]

</div>

[^1]: The Joint Commission, Sentinel Event Alert 50, 8 Apr 2013.

<!--
The alert's name for it: desensitisation, or alarm fatigue. Every alarm detected a real threshold crossing; the staff could not respond to all of them. The squares are an illustration, not the hospitals' data: red is an alarm that needed action, dashed is one that did not.
Two different databases and two different periods: do not add them up. The source says "alarm-related"; it does not say that the alarms caused the deaths.
-->

---

# Fewer alarms

<carbon-filter class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node" style="width:10rem"><ph-bell-ringing class="ic" /><b>Alarm signals</b><br><DataBatch cells="..r..... ........ ......r." :cols="8" /></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green" style="width:15rem"><ph-funnel class="ic" /><b>Review every alarm</b><br><small>Is it actionable?<br>Right threshold for this patient group?<br>Who owns it?</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node" style="width:8rem"><ph-bell-ringing class="ic" /><b>Fewer signals</b><br><DataBatch cells="r.r." /></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node sky" style="width:7rem"><ph-first-aid class="ic" /><b>Staff</b><br><small>respond</small></div>
</div>

<v-click at="3">

> [!TIP]
> Before you add an alarm, decide who acts on it and what they do. Delete the alarms nobody acts on.

</v-click>

</div>

<!--
The alert's remedy is fewer alarms: review which signals are actionable, set thresholds for the context, and make somebody own the alarm policy.
Deleting an alarm feels like removing a safety net, which is why teams rarely do it. Later in this section we measure the same effect on our service.
-->

---
hide: true
---

# Option B · 97 e-mails before the market opened

<carbon-email class="icon-corner" />

<div class="middle">

Knight Capital, a US trading firm, 1 August 2012. After a deployment, one of eight servers ran old code.

<div class="flow">
  <div class="node amber" style="width:12rem"><ph-cpu class="ic" /><b>Order system</b><br><small>"Power Peg disabled"</small></div>
  <div class="arrow-l">8:01 to 9:30<span class="arrow">→</span></div>
  <div v-click class="node" style="width:12rem"><ph-envelope-simple class="ic" /><b>97 e-mails</b><br><small>to a group of staff</small></div>
  <div v-click class="arrow-l fail">not read<span class="arrow">→</span></div>
  <div v-click class="node rose" style="width:12rem"><ph-currency-dollar class="ic" /><b>Market opens</b><br><small>a loss of more than $460 million</small></div>
</div>

<v-click>

Knight "did not design these types of messages to be system alerts"[^1][].

</v-click>

</div>

[^1]: US SEC, Order Instituting Proceedings, Knight Capital Americas LLC, Release No. 34-70694, 16 Oct 2013, ¶19. https://www.sec.gov/litigation/admin/2013/34-70694.pdf

<!--
Option B: use it instead of the hospital alarms (switch `hide` on the five hospital slides and on these two). The hospital alarms also appear in the notes of "One simulated day" and "Delete alerts nobody acts on", and in the study notes' "Why this matters"; change them too.
The SEC: staff "generally did not review them", although the messages were sent in real time and "provided Knight with a potential opportunity" to fix the problem before the open.
-->

---
hide: true
---

# Option B · A message or an alert?

<carbon-notification class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr); ">
  <div class="card"><ph-envelope-simple class="ic" /><b>A message</b>goes to a mailbox<br>nobody owns it<br>nobody has to act</div>
  <div v-click class="card"><ph-siren class="ic" /><b>An alert</b>goes to one named person<br>says what is broken<br>expects an action</div>
</div>

US SEC, Release No. 34-70694[^1][]

<v-click>

> [!TIP]
> Before you add an alert, decide who acts on it and what they do. Delete the messages nobody acts on.

</v-click>

</div>

[^1]: US SEC, Release No. 34-70694, 16 Oct 2013, ¶41.

<!--
Option B: the second Knight Capital slide. The SEC: a procedure "that integrated the BNET Reject messages into Knight's monitoring of its systems likewise could have prevented the events of August 1" (¶41).
-->

---

# An alert on p95 latency

<carbon-calendar class="icon-corner" />

<div class="middle">

The rule: page when p95 latency is above 250 ms. One simulated day, with one real incident: 90 minutes when most requests were slower than 250 ms.

<div class="hours" style="margin-left:10.75rem; margin-right:7.75rem"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>

<div class="day-row"><b>The incident</b><div class="day"><div class="incident" style="left:41.67%; width:6.25%"></div></div><span>90 min</span></div>

<div v-click="1" class="day-row"><b>p95 &gt; 250 ms now</b><div class="day"><span class="tick" style="left:0.42%"></span><span class="tick" style="left:3.47%"></span><span class="tick" style="left:4.31%"></span><span class="tick" style="left:10.07%"></span><span class="tick" style="left:11.25%"></span><span class="tick" style="left:11.88%"></span><span class="tick" style="left:12.78%"></span><span class="tick" style="left:13.68%"></span><span class="tick" style="left:17.50%"></span><span class="tick" style="left:17.99%"></span><span class="tick" style="left:18.33%"></span><span class="tick" style="left:20.76%"></span><span class="tick" style="left:23.75%"></span><span class="tick" style="left:30.63%"></span><span class="tick" style="left:33.19%"></span><span class="tick" style="left:33.54%"></span><span class="tick" style="left:35.62%"></span><span class="tick" style="left:35.90%"></span><span class="tick" style="left:40.56%"></span><span class="tick" style="left:40.76%"></span><span class="tick" style="left:41.67%"></span><span class="tick" style="left:52.01%"></span><span class="tick" style="left:57.15%"></span><span class="tick" style="left:58.96%"></span><span class="tick" style="left:63.47%"></span><span class="tick" style="left:66.88%"></span><span class="tick" style="left:68.19%"></span><span class="tick" style="left:71.25%"></span><span class="tick" style="left:71.81%"></span><span class="tick" style="left:74.31%"></span><span class="tick" style="left:76.46%"></span><span class="tick" style="left:76.74%"></span><span class="tick" style="left:76.94%"></span><span class="tick" style="left:80.56%"></span><span class="tick" style="left:84.03%"></span><span class="tick" style="left:84.44%"></span><span class="tick" style="left:87.36%"></span><span class="tick" style="left:90.49%"></span><span class="tick" style="left:92.29%"></span><span class="tick" style="left:98.54%"></span></div><span class="count" style="color:#dc2626">40</span></div>


<v-click at="2">

39 of the 40 pages were short spikes, over before anyone could act. How do we page only for the incident?

</v-click>

</div>

<!--
The lab's `make alert-noise` (seed 42): 1,440 minutes, about 3% of them a one-minute spike (a garbage collection, a noisy neighbour), and one real incident from 10:00 to 11:30.
40 pages a day are 40 pages nobody reads by Thursday: the hospital alarms again.
-->

---

# Burn rate

<carbon-meter-alt class="icon-corner" />

<div class="middle">

The **burn rate** tells how fast we spend the error budget. At 1×, the budget lasts exactly the SLO window.

**Burn rate** = the error ratio now ÷ the error ratio the SLO allows[^1][]

<div style="margin:1.5rem auto 0; width:100%; max-width:42rem">
  <div class="bar-row"><b>1×</b><div class="bar-track"><div class="bar-fill amber" style="width:100%"></div></div><span>budget lasts 30 days</span></div>
  <div v-click="1" class="bar-row"><b>6×</b><div class="bar-track"><div class="bar-fill" style="width:16.67%"></div></div><span>gone in 5 days</span></div>
  <div v-click="2" class="bar-row"><b>14.4×</b><div class="bar-track"><div class="bar-fill" style="width:6.94%"></div></div><span>gone in 2 days 2 h</span></div>
</div>

<v-click at="3">

At 14.4×, one hour spends **2%** of the month's budget.

</v-click>

</div>

[^1]: Google, *The Site Reliability Workbook*, "Alerting on SLOs". https://sre.google/workbook/alerting-on-slos/

<!--
The Workbook: "Burn rate is how fast, relative to the SLO, the service consumes the error budget." With a 1% budget, 14.4% of requests failing is a burn rate of 14.4.
2% = 14.4 × 1 hour ÷ 720 hours. The bar lengths are from `make slo-budget`.
-->

---

# Alerting on SLOs

<carbon-alarm class="icon-corner" />

<div class="middle">

The SRE Workbook recommends alerts on the burn rate, each over a long and a short window.

| **Severity** | **Long window** | **Short window** | **Burn rate** | **Budget spent** |
| --- | --- | --- | --- | --- |
| <b style="color:#dc2626">page</b> | 1 hour | 5 minutes | 14.4 | 2% |
| <b style="color:#dc2626">page</b> | 6 hours | 30 minutes | 6 | 5% |
| <b style="color:#d97706">ticket</b> | 3 days | 6 hours | 1 | 10% |

<v-click>

An alert fires when **both** windows are over the burn rate.

</v-click>

<v-click>

The threshold follows from the SLO: 14.4 × 1% = an error ratio of **0.144**.

</v-click>

</div>

<div class="text-sm opacity-70">

Google, The Site Reliability Workbook, "Alerting on SLOs", Table 5-8[^1][]

</div>

[^1]: https://sre.google/workbook/alerting-on-slos/

<!--
The Workbook calls these "recommended starting parameters"; we take them as they are. The lab's tests compare them with the source, so nobody rounds 14.4 to 14.
Against the latency SLO (5% budget) the same rule needs 14.4 × 5% = 72% of requests too slow. A test recomputes every threshold from `slo.yaml`.
-->

---

# Long and short windows

<carbon-time class="icon-corner" />

<div class="middle">

The alert fires only while **both** windows are over the threshold.

<div class="hours" style="margin-left:10.75rem; margin-right:7.75rem"><span>09:30</span><span>10:00</span><span>10:30</span><span>11:00</span><span>11:30</span><span>12:00</span></div>

<div class="day-row"><b>The incident</b><div class="day"><div class="incident" style="left:20%; width:60%"></div></div><span>10:00–11:30</span></div>
<div v-click="1" class="day-row"><b>5 min window</b><div class="day"><div class="incident" style="left:23.33%; width:58%; background:rgba(2,132,199,0.45)"></div></div><span>10:05–11:31</span></div>
<div v-click="2" class="day-row"><b>1 h window</b><div class="day"><div class="incident" style="left:53.33%; width:34%; background:rgba(217,119,6,0.55)"></div></div><span>10:50–11:40</span></div>
<div v-click="3" class="day-row"><b>Alert: both</b><div class="day"><div class="incident" style="left:53.33%; width:28%; background:rgba(225,29,72,0.6)"></div></div><span>10:50–11:31</span></div>

<div v-click="4">

- The 1 h window: the incident is serious.
- The 5 min window: it is still happening.
- The price: the page comes 50 minutes after the incident starts.

</div>

</div>

<!--
Computed from the lab's `make alert-noise` day (seed 42), threshold 72% slow requests (14.4 × the 5% latency budget). The 5-minute window crosses after five bad minutes but would also react to a short burst; the 1-hour window needs about 50 minutes of a 90-minute incident before 2% of the month's budget is gone. Without the short window, the page would keep firing until 11:40, after the fix. The Workbook: the short window makes the alert stop "five minutes later, rather than one hour later". For a 99% target the 50-minute wait is acceptable; a service where ten minutes of failure is a disaster needs a different SLO, written before the incident.
-->

---
layout: section
---

# 5 · Wrap-up

<!--
About 5 minutes: this week's service, takeaways, open questions, the lab, and the questions students can now answer.
-->

---

# This week's service

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.4rem; ">
  <div class="node sky no-shrink" style="width:9rem"><ph-cube class="ic" /><b>API</b><br><small><span class="mono">/metrics</span>, a log line per request</small></div>
  <div v-click="1" class="arrow-l">scrape, 5 s<span class="arrow">←</span></div>
  <div v-click="1" class="node violet no-shrink" style="width:10rem"><ph-database class="ic" /><b>Prometheus</b><br><small>time series and alerts</small></div>
  <div v-click="2" class="arrow-l">PromQL<span class="arrow">←</span></div>
  <div v-click="2" class="node green no-shrink" style="width:9rem"><ph-chart-line class="ic" /><b>Grafana</b><br><small>ten panels, from Git</small></div>
</div>

<div v-click="3" class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-file-text class="ic" /><b><span class="mono">slo.yaml</span></b><br><small>targets and window</small></div>
  <div class="arrow-l">thresholds<span class="arrow">→</span></div>
  <div class="node rose no-shrink" style="width:10rem"><ph-siren class="ic" /><b>Alerts</b><br><small>burn rate in two windows, <span class="mono">up</span></small></div>
  <div class="arrow-l">tested by<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:9rem"><ph-test-tube class="ic" /><b>promtool</b><br><small>and pytest</small></div>
</div>

</div>

<!--
`slo.yaml` sits next to `params.yaml`, not inside it: `params.yaml` is hashed by DVC, and a new latency target must not invalidate a model.
The cluster from Week 10 is down this week; the observed API is a Compose service.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><carbon-chart-line class="ic" /><b>Has the world changed?</b>Every panel stays green while the inputs drift.<br><br><b>→ Week 12:</b> drift monitoring</div>
  <div class="card"><carbon-notification class="ic" /><b>Who gets the alert, and what do they do?</b>Prometheus marks it firing. Nobody is called.<br><br><b>→ Week 13:</b> incidents and kill-switches</div>
  <div class="card"><carbon-user-multiple class="ic" /><b>Is it right for the patients?</b>No panel looks at the answers.<br><br><b>→ Week 13:</b> Model Cards</div>
</div>

</div>

<!--
`model_prediction_score` is already exported; Week 12 compares its shape with the training data. Alertmanager, routing and silences arrive in Week 13.
The last card has no tool. Observability shows whether the system does what we built it to do; whether we should have built it is Week 13's question.
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<div class="middle">

- Decide what to measure before the incident.
- Give a metric a label only if you can list all its values.
- Metrics count many requests, logs describe one, traces follow one across services.
- Write reliability as an SLO: good events over valid events, a target and a window.
- Page a person when the error budget burns fast, in both windows.

</div>

<!--
If time is short, ask which takeaway the room would drop for an internal tool used by five people, and why.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **#** | **Exercise** | **What you show** |
| --- | --- | --- |
| 1 | Instrument the service | `/metrics` with a counter and a latency histogram labelled by route template |
| 2 | Scrape the service and query it | the target goes from DOWN to UP, p95 from PromQL |
| 3 | Add a panel to the dashboard | a panel made in the Grafana UI, saved as JSON in Git |
| 4 | Read the SLO and watch an alert fire | the budget at 99% and 99.9%, `ServiceDown` goes pending, then firing |

</div>

Stop the Week 10 cluster first: this week runs on Docker Compose. Homework 4 is out this week: its Part B uses this lab.

</div>

<!--
Ports: Prometheus 5560, Grafana 5561, the API 5562. Exercise 1 needs no Docker: `make serve-api` and `curl`.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

<div class="middle">

- Which signals should a model service report, beyond those of any web service?
- Why can one label take down the monitoring, and where does the cost land?
- Which question does a metric answer, which a log, and which a trace?
- Why can you not average three replicas' p95 latency?
- What are an SLI, an SLO and an error budget for our service?
- Why does a burn-rate alert use two windows, and what does it cost?

</div>

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->

---
hide: true
---

# Traps you will meet in the lab

<carbon-debug class="icon-corner" />

<div class="middle">

<div class="text-sm">

| Trap | What you see | What is wrong |
| --- | --- | --- |
| target `localhost:8000` | the target stays DOWN | inside Prometheus, `localhost` is Prometheus: use `api:8000` |
| `app.mount("/metrics", make_asgi_app())` | `curl /metrics` prints nothing | a mount is a directory: 307 to `/metrics/` |
| `create_app()` twice | `DuplicateTimeseries` | the default registry is global: pass a registry |
| a latency target that is not a bucket | the latency alert never fires | `le="0.25"` must match a bucket boundary |
| `sum()` over no series | panel says "No data" | `(… or vector(0))` on the numerator |
| a `*_test.yml` in `rules/` | Prometheus will not start | keep promtool tests beside `rules/` |
| datasource added by hand | every panel empty, for others | pin the datasource `uid` |

</div>

</div>

<!--
Hidden: lab-specific. Show it at the start of the lab session instead.
All seven were met while building the lab; the README explains each.
-->
