# `prometheus/` — the specification

Three files, and a directory layout that is itself an interface.

```text
prometheus/
  prometheus.yml          global config, rule_files, scrape_configs   (Exercise 2)
  rules/
    slo.yml               recording rules + burn-rate alerts                       (given, Exercise 4)
    service.yml           ServiceDown, ContractViolationSpike                      (given)
  tests/
    alerts_test.yml       promtool tests for every alert                            (given)
```

**`tests/` is beside `rules/`, never inside it.** `prometheus.yml` loads
`rule_files: /etc/prometheus/rules/*.yml`, and that glob would happily pick up a `*_test.yml` and
try to parse it as a rule file — at which point **Prometheus refuses to start**.

---

## `prometheus.yml` — Exercise 2

The `prometheus` self-scrape job is given (it is straight out of the getting-started guide, and it
earns its place: there is always a live target to practise PromQL against). Add one more:

| field | value | why |
| :--- | :--- | :--- |
| `job_name` | `diabetes-api` | every rule and every dashboard query matches on it |
| `static_configs.targets` | `["api:8000"]` | **a Compose DNS name.** Prometheus pulls; it has to reach you |
| `metrics_path` | `/metrics` | stated, not inherited |
| `scrape_interval` | `5s` | faster than the global default, so the DOWN → UP transition is watchable |
| `static_configs.labels` | `service: diabetes-api` | a label *you* attach, on every series from this job |

`localhost:8000` is the single most common mistake here, and its symptom is a target that is
permanently DOWN — because inside the Prometheus container, `localhost` *is* Prometheus.

---

## `rules/slo.yml` — given, read in Exercise 4

Every threshold in this file comes from `slo.yaml`. `tests/test_prometheus_rules.py` recomputes each
one from that file and fails if the two disagree.

The file starts with **recording rules**. A recording rule computes an expression on every
evaluation and stores the result as a new series, such as `slo:availability:error_ratio_1h`. The
alerts then compare these series with a threshold. The names follow Prometheus's
`level:metric:operation` convention (https://prometheus.io/docs/practices/rules/).

- The availability error ratio counts only `5..` responses as bad. A 422 from the contract is the
  service working, so it does not spend the error budget. `ContractViolationSpike` in `service.yml`
  watches the 422s instead.
- The numerator is wrapped in `(... or vector(0))`, because `sum()` over no matching series returns
  no result rather than 0.
- The latency error ratio selects the bucket `le="0.25"`. The value must match a bucket boundary in
  `metrics.py`, written the same way, or the expression selects nothing and the alert never fires.

Then come **the alerts**. Each burn-rate alert has two conditions joined with `and`: the error ratio
over the long window and over the short window are both above the threshold. The threshold is
`burn_rate × error_budget`; `make slo-budget` prints it for every row.

`AvailabilityBudgetBurnFast` is the fast-burn alert: it pages when more than 14.4% of prediction
requests fail over the last hour and over the last 5 minutes.

## `rules/service.yml` — given

- **`ServiceDown`** fires when `up{job="diabetes-api"} == 0` for one minute. Prometheus sets `up` to 0
  when a scrape fails.
- **`ContractViolationSpike`** opens a ticket when the rate of rejected requests stays above 0.2 per
  second for five minutes.

## `tests/alerts_test.yml` — given

`make alerts-test` runs `promtool test rules` on this file. It feeds synthetic series to the real
rules and checks which alerts fire at which time, and which stay quiet. Reference:
https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/

In `values`, `0+10x130` is a counter that starts at 0 and grows by 10 per interval, 130 times.
`10x130` is the flat value 10, whose rate is zero.
