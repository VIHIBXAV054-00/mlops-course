# Week 11 Lab — Observability

Your model runs in a container, and you can release a new version safely. Between two releases,
nobody sees how the service behaves: how many requests fail, how slow they are, what the model
predicts. In this lab, you make the service report metrics and watch them with Prometheus and
Grafana:

1. Instrument the service.
2. Scrape it with Prometheus and query it.
3. Add a panel to the Grafana dashboard.
4. Read the SLO and watch an alert fire.

## What you already have

You already have the training pipeline, the data contracts, the quality gate, the FastAPI service
with `/health` and `/predict`, and the serving image. The model, metrics and thresholds stay the
same. The Kubernetes cluster is not used this week: the API runs as a Docker Compose service.

New in this lab:

- `metrics.py`: the service's metrics, and a middleware that measures every request and writes one
  JSON log line for it.
- `GET /metrics` on the API.
- `traffic.py`: sends requests with a known mix of valid requests, contract violations and unknown paths.
- `slo.yaml`: the availability and latency SLOs, and the burn-rate table.
- `slo.py`: the error budget and burn-rate arithmetic.
- `prometheus/`: the scrape configuration, the alert rules and their tests. The spec is in
  `prometheus/README.md`.
- `grafana/`: the Grafana settings, the data source, the dashboard provider and the dashboard JSON.
  The spec is in `grafana/README.md`.
- Three new Compose services: Prometheus on port 5560, Grafana on 5561 and the API on 5562.

## Based on (official tutorials)

- **Prometheus getting started:** https://prometheus.io/docs/prometheus/latest/getting_started/
- **prometheus_client:** https://prometheus.github.io/client_python/
- **Alerting rules:** https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- **Unit tests for rules:** https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/
- **Grafana provisioning:** https://grafana.com/docs/grafana/latest/administration/provisioning/
- **SRE Workbook, Alerting on SLOs:** https://sre.google/workbook/alerting-on-slos/

## Prerequisites

- Weeks 1–10 working, with Docker running.
- Delete the Week 10 cluster, which uses about 2.3 GiB: `kind delete cluster --name mlops`.
- Run the Setup before the lab session if you can. The first `make up` downloads the Prometheus
  and Grafana images.

## Setup

```bash
cp .env.example .env
make sync               # install all dependency groups
make data-v2            # rebuild the dataset from the committed raw batches
make repro              # train and check the gate; you should get a GO and models/model.pkl
make up                 # postgres, s3, mlflow, prefect, prometheus and grafana
```

Run `uv run pytest -q` before starting the exercises. With the stack down, the expected result is:

```
340 passed, 18 skipped
```

Eight of the skipped tests need the MLflow server. The other 10 belong to this lab.

## Exercises

Complete the four exercises in order. Exercises 1, 2 and 4 have questions. Write your answers in
`answers.md`, and commit the file with your code.

### Exercise 1 — Instrument the service (`make metrics-show`, `make cardinality`) — **written**

A metric is a number the service keeps up to date, such as the number of requests it has answered.
Prometheus reads metrics from `GET /metrics`.
Labels, such as `status="422"`, let you split a metric into groups.
Prometheus stores a separate time series for each combination of label values.
Some labels, such as a raw URL path, can have many different values, creating many time series.
When reviewing a new metric, a team needs to consider this cost.

In this exercise, you record requests in a counter and a latency histogram, count predictions and contract violations, and measure the cost of using a raw path as a label.

1. In `src/week_11_observability/metrics.py`, `make_middleware()`, fill in the TODO: count the request in `http_requests_total` and observe its duration in `http_request_duration_seconds`.
2. In `src/week_11_observability/api.py`, `predict()`, fill in the two TODOs: count contract violations by check name, and count predictions by outcome and observe the probability.
3. Run `make metrics-show`.
   It sends five requests to the app in-process and prints its metrics.
4. Run `make cardinality`.
   It sends the same requests twice: once using `route_label` and once using the raw path.
   It then counts the series.
   Both counts are 51 because `route_label` still returns the raw path.
5. In `metrics.py`, change `route_label()` to return the route template, or `__unmatched__` if the path matches no route.
   Run `make cardinality` again.

**Check:** delete the skip markers in `tests/test_metrics.py`, and the tests pass.
`make metrics-show` prints `route="/predict"` and `route="__unmatched__"`, and no raw path.
`make cardinality` prints `2 time series` for the route template and `51 time series` for the raw path.

Question:

1. A teammate opens a pull request that adds the patient's `age` as a label on `model_predictions_total` to show predictions by age.
   Would you approve it?
   Estimate how many series it would add and say where else this information could go.

### Exercise 2 — Scrape the service and query it (`make api-up`, `make traffic`, `make promql`) — **written**

Prometheus collects metrics by calling `GET /metrics` at regular intervals on each target listed in `prometheus.yml`.
It stores the time series with timestamps, and you can query them with PromQL.
A counter increases until the process restarts, when it starts again at 0.
To see how quickly it changes, query its rate rather than its value.

In this exercise, you add a scrape job, start the API container, send traffic and query the request rate and p95 latency.

1. In `prometheus/prometheus.yml`, add the `diabetes-api` scrape job.
   `prometheus/README.md` lists its fields.
   Run `make prom-reload`.
2. Build the image with your Exercise 1 code and start it.
   At http://127.0.0.1:5560/targets, the `diabetes-api` target goes from DOWN to UP.

   ```bash
   make image          # refuses on a non-GO gate verdict
   make api-up
   ```

3. Send 300 requests, 90% valid and 10% contract violations: `make traffic`.
4. Run `make promql` and paste queries 3, 4 and 6 into http://127.0.0.1:5560/graph.

**Check:** delete the "Exercise 2" skip marker in `tests/test_prometheus_rules.py`, and the test passes.
`make targets` shows `diabetes-api` as `up`.
Query 4 returns one series for status 200 and one for 422, and query 6 returns the p95 latency in seconds.

Question:

2. Next month the API runs as three replicas.
   A colleague wants the dashboard to show the mean of the three replicas' p95 latency.
   Would you accept it?
   Write the query you would use instead and say why it gives the right answer.

### Exercise 3 — Add a panel to the dashboard (`make grafana`, `make dashboard-check`)

Grafana displays Prometheus data in dashboards.
In this lab, the dashboard is a JSON file in Git that Grafana loads at start-up, a process called provisioning.
You can edit the dashboard in the Grafana UI, but Grafana cannot save your changes there.
Instead, you copy the dashboard JSON into the file.
The change can then be reviewed in a pull request, and a test checks that every panel's query names a metric the service exports.

In this exercise, you add a panel in the UI, copy the dashboard JSON into the file and see the test catch a renamed metric.

1. Run `make traffic` again so the panels have data.
   Run `make grafana` and open the dashboard URL it prints.
   You do not need to sign in: anonymous users have the Editor role in this lab.
2. Click **Make editable**, then **Add** → **Visualization**, and set:
   - **Title:** `Predictions by outcome`
   - **Description:** one or two sentences on what the panel shows, more than 60 characters
   - **Query:** switch the query editor from **Builder** to **Code**, enter `sum by (outcome) (rate(model_predictions_total[1m]))`, and click **Run queries**

   Try a few panel options, such as the unit or the legend.
3. Click **Save dashboard**.
   Grafana says it cannot save the dashboard from the UI because it was provisioned from a file.
   Open **Advanced options**, choose **Classic**, and click **Copy JSON to clipboard**.
4. Replace the contents of `grafana/dashboards/diabetes-service.json` with the copied JSON.
   Click **Exit edit**, discard the unsaved changes, and reload the page after 10 seconds.
   The dashboard now shows your panel loaded from the file.
5. Run `make dashboard-check`.
   In `metrics.py`, `build_metrics()`, rename `http_requests_total` to `http_requests_count_total` and run `make dashboard-check` again.
   In a running service, panels using that metric would become empty without showing an error.
   Undo the rename.

**Check:** delete the "Exercise 3" skip marker in `tests/test_dashboard.py`, and the tests pass.
With the rename, `make dashboard-check` fails and names `http_requests_total`.
`git diff` shows your panel in `grafana/dashboards/diabetes-service.json`.

### Exercise 4 — Read the SLO and watch an alert fire (`make slo-budget`, `make alerts-test`, `make alert-fire`) — **written**

An SLO sets a target for the proportion of good events among valid events over a time window.
In `slo.yaml`, the availability target is that 99% of prediction requests receive a response that is not a 5xx error over 30 days.
A 422 does not count against the target because the contract rejected the request.
The error budget is the amount of failure the SLO allows: here, 1% of requests.
The burn rate tells you how quickly the budget is being spent.
A burn-rate alert fires when the error ratio is high over both a long window and a short window.
The alert rules are kept in Git and tested with `promtool`.
At work, you might agree on an SLO with the product owner and receive alerts while on call.

In this exercise, you compare two targets, find the alerts in Prometheus, run the rule tests and stop the service to watch an alert fire.

1. Read the availability objective in `slo.yaml`.
   Run `make slo-budget`.
   It prints the error budget for each SLO and the threshold (error ratio) for each burn-rate alert.
2. In `slo.yaml`, change the availability `target` to `0.999` and run `make slo-budget` again.
   Note the availability budget and the error ratio of the `fast` row.
   Change the target back to `0.99`.
3. Open http://127.0.0.1:5560/rules and find `AvailabilityBudgetBurnFast`.
   Compare it with the rule in `prometheus/rules/slo.yml`.
4. Run `make alerts-test`.
   It runs the tests in `prometheus/tests/alerts_test.yml` against the rules.
5. Run `make alert-fire`.
   It stops the API, prints the state of `ServiceDown` every 5 seconds and starts the API again.
   It takes about two minutes.

**Check:** `make slo-budget` prints `7h 12m` for availability, and `git diff slo.yaml` shows no change.
`make alerts-test` prints `SUCCESS`.
`make alert-fire` shows `ServiceDown` as `inactive`, then `pending`, then `firing` about one minute later.

Question:

3. The product owner asks for 99.9% availability instead of 99%.
   Would you accept it for this service?
   Give the error budget in minutes per 30 days from your run and explain your decision.

### Finish — commit your work

```bash
git status          # include answers.md
git add .
git commit -m "week11: metrics, scrape job, dashboard panel and written answers"
```

`.env` and `.venv/` are not committed. If `git status` shows the renamed metric in `metrics.py` or a
changed target in `slo.yaml`, undo the change first.

## Make targets

| Target | What it does |
| --- | --- |
| `make metrics-show` | the metrics after five in-process requests (Exercise 1) |
| `make cardinality` | the series count with the route template and with the raw path (Exercise 1) |
| `make prom-reload` | reload `prometheus.yml` and the rules without a restart (Exercise 2) |
| `make image` | build the API image with this week's code (Exercise 2) |
| `make api-up` / `make api-down` | start or stop the API container (Exercise 2) |
| `make traffic` | send requests with a known mix; set `N`, `RATE`, `MIX`, `SEED` (Exercise 2) |
| `make promql` | the PromQL queries to try, with what each one returns (Exercise 2) |
| `make logs-json` | the same requests as a metric and as log lines |
| `make targets` | every scrape target and its state |
| `make grafana` / `make prometheus-ui` | the URLs of the two UIs (Exercise 3) |
| `make dashboard-check` | the dashboard tests (Exercise 3) |
| `make slo-budget` | the error budgets and the burn-rate table (Exercise 4) |
| `make alerts-check` | check the Prometheus configuration and the rule files |
| `make alerts-test` | run the rule tests (Exercise 4) |
| `make alert-fire` | stop the API and watch `ServiceDown` fire (Exercise 4) |
| `make alert-noise` | a simple alert and a burn-rate alert over one simulated day (not an exercise) |
| `make workers-trap` | four uvicorn workers in one container, scraped 30 times |
| `make test-observability` | this week's tests only |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| the `diabetes-api` target stays DOWN after `make api-up` | the target is `localhost:8000`, which inside the Prometheus container is Prometheus itself | use the Compose service name, `api:8000` |
| the `diabetes-api` target is DOWN | the API runs only after `make api-up` | `make api-up` |
| `make api-up` refuses | the image `diabetes-api:local` does not exist | `make image` |
| `/metrics` on port 5562 does not show a change you made in `metrics.py` | the container still runs the old image | `make image && make api-up` |
| Save dashboard says the dashboard cannot be saved | it is provisioned from a file | copy the JSON into `grafana/dashboards/diabetes-service.json` (Exercise 3) |
| the copied JSON starts with `"apiVersion": "dashboard.grafana.app/v2"` | **V2 Resource** is selected in the save dialog | **Advanced options** → **Classic**, then copy again |
| tests in `test_slo.py`, `test_prometheus_rules.py` and `test_dashboard.py` fail | the availability target in `slo.yaml` is still `0.999` | set it back to `0.99` |
| a rule is missing from http://127.0.0.1:5560/rules after `make prom-reload` | the rule file has an error, and Prometheus keeps the old rules | `make alerts-check` |
| every Grafana panel is empty, with no error | a renamed metric, or a data source `uid` that does not match | `make dashboard-check` |
| `make image` prints nothing for minutes | Docker is uploading a large build context, such as `.venv/` | keep `.venv/` in `.dockerignore` |

## Submission

Submit the commit from Finish. It contains your code, `prometheus/prometheus.yml`, the dashboard
JSON and `answers.md`. Do not include `.env` or `.venv/`.
Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`), and upload
that URL to Moodle.

## Deviations from the tutorials

1. **A hand-written middleware instead of `prometheus-fastapi-instrumentator`.** The package
   chooses the labels for you, and choosing labels is what this lab teaches.
2. **A plain `/metrics` route instead of mounting `make_asgi_app()`.** The mount answers a bare
   `GET /metrics` with a redirect to `/metrics/`.
3. **No Alertmanager.** Prometheus shows pending and firing alerts on its own `/alerts` page.
   Sending an alert to a person is Week 13.
4. **Grafana is provisioned from files**, with anonymous Editor access, so the lab does not start
   with a login and you can edit panels. Never give anonymous users the Editor role on a real server.
   `grafana/grafana.ini` turns off Grafana 13's new dashboard layouts, so the JSON that Grafana offers
   on save has the same classic format as the provisioned file.
5. **`promtool` runs inside the Prometheus image**, so this week needs no new host tool.
