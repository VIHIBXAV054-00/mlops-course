# Week 12 Lab — Drift & Degradation

In Week 11, you built service monitoring: instrumentation, an SLO, an error budget, six alerting rules and a dashboard in Git. Those signals tell you whether the **service** is up, fast and free of HTTP errors.

This week, the service is healthy, but the world around it has changed.

A model can be up and error-free while giving wrong answers for the patients it scores, although they no longer look like the training set.

In this lab, you will work through three ideas:

1. **Week 11's metrics cannot answer drift questions.** If you ask `/metrics` whether incoming patients' glucose levels have shifted, it cannot answer because it never stored the inputs. To monitor drift, you first have to **keep the input rows**, which means storing patient data.
2. **A drift verdict is a policy.** The same live traffic can flip between "no drift" and "drift" depending on the reference, the window size or the statistic you pick. Choosing the test, threshold, window size and minimum sample size are engineering decisions that belong in a reviewable config file.
3. **Decide whether the drift matters.** Input drift tells you the data moved; degradation tells you the answers got worse, and only labels can show that. For diabetes diagnosis, labels arrive years later, so "drift detected → retrain" is not a realistic plan.

There are **four exercises**. The code ships finished: you run the monitor, change the reference and the values in `drift.yaml`, and see what happens. Exercises 3 and 4 have written questions. Put your answers in `answers.md` in this directory and commit it with your code.

---

## Prerequisites

Keep the Compose stack setup from Week 11, and make sure any earlier Kind cluster or Week 11 stack is stopped so the ports are free:

```bash
kind delete cluster --name mlops                              # if Week 10's cluster is still up
cd ../../week-11-observability/starter && make down            # frees ports 5500/5510/5511/5532/5560+
```

You do not need any new host tool, container or port this week. **The drift monitor is a batch job, not a server.** It compares a window of recent requests against a reference dataset on a schedule.

We add one new Python dependency: `evidently==0.7.21`. Look at where it lives in `pyproject.toml` (under `[dependency-groups] drift`) and see what `uv lock` pulled in with it. Evidently ships a web framework, plotting libraries and an NLP toolkit, so keeping it in a separate group ensures the serving image stays small.

## Setup

```bash
cp .env.example .env
make up
make repro && make register && make promote-champion
make image && make api-up
```

Confirm you are starting from a clean Week 11 baseline: `make ci` passes, the gate verdict is **GO**, and `make targets` shows `diabetes-api` as `UP`.

---

## Exercises

### 1. Log the requests

A drift check needs the inputs the model actually saw. To capture them, the service now writes two separate logs:

- The **request log** records one line per HTTP request with its request id, route and status code.
- The **prediction log** records one row per scored request with the same request id, the model's inputs and its prediction.

Requests that fail validation never reach the model, so they appear in the request log only.

In this exercise, you turn on the prediction log, send requests, and compare what each log records.

1. Turn the prediction log on and restart the API:
   ```bash
   make predictions-on
   make api-down api-up
   ```
2. Send one valid request and one with an impossible zero:
   ```bash
   make request
   make request ZERO=glucose
   ```
   The first returns `200` and the second `422`. Note both `x-request-id` headers.
3. Look up both ids in the request log with `make api-logs`, then search for them in the prediction log with `make predictions-head`. Only the `200` request appears in the prediction log, alongside its inputs, its prediction and the matching request id.
4. Send a mixed batch that includes invalid requests:
   ```bash
   make traffic N=200 MIX=valid=9,violation=1
   ```
   Count the `200` and `422` responses in the request log (`make api-logs N=300`) and compare them with the row count reported by `make predictions-head`.
5. Send a batch from the drifted cohort so you have data ready for the next exercises: `make traffic-drift`.

**Check:** every `200` on `/predict` has a matching row in the prediction log with the same request id, and no `422` has one.

### 2. Choose the reference

A drift check compares live traffic against a reference baseline. Because the reference defines what "normal" looks like, choosing the wrong baseline breaks the verdict. A reliable reference comes from the training data, pinned to the dataset version the model was trained on (`reference:` in `drift.yaml`), and filtered by the same input contract as live requests.

In this exercise, you run the same drift check with three flawed references and the pinned one, then compare the results.

1. Run the check on known-good traffic using the pinned reference, then repeat it with an unfiltered reference that keeps rows the API would reject:
   ```bash
   make drift-report COHORT=reference N=800
   make drift-report COHORT=reference N=800 REFERENCE=unfiltered
   ```
   Compare the `skin_thickness` row in both outputs. Nothing changed in the traffic; only the reference changed.
2. Run the check on known-good traffic using a tiny 50-row reference across two seeds, and watch how much the numbers jump:
   ```bash
   make drift-report COHORT=reference N=800 REFERENCE=small SEED=1
   make drift-report COHORT=reference N=800 REFERENCE=small SEED=2
   ```
3. Run the check on drifted traffic, first against the pinned reference, and then using the prediction log itself as the reference (a moving baseline that shifts with live data):
   ```bash
   make drift-report COHORT=drifted N=800
   make drift-report COHORT=drifted N=800 REFERENCE=log
   ```
4. Open the HTML report from the last run with `make drift-open`.

**Check:** for each of the three flawed references, you can explain what went wrong: whether it caused a false alarm or hid a real shift.

### 3. Set the threshold — written

A drift monitor reduces each feature to a single number and compares it against a threshold. However, that number can change even when the data has not shifted, depending on the window size and the statistical test you choose. In practice, a team calibrates both the threshold and the minimum sample size on its own data.

In this exercise, you explore two statistical traps, measure known-good and drifted windows, and set the policy values in `drift.yaml`.

1. **A p-value depends on the number of rows.** Run `make drift-sample-size`. It prints the K-S p-value and the PSI for glucose on the same drifted data at four window sizes. Notice which one keeps dropping as the window grows, even though the underlying shift is the same.
2. **Too few rows.** Run `make drift-report COHORT=reference N=50` with a few seeds (`SEED=1`, `SEED=2`, `SEED=3`) on known-good traffic to see how wide the PSI values swing on small windows.
3. **Calibrate.** Run `make drift-report` on both `COHORT=reference` and `COHORT=drifted` at a few window sizes (for example `N=100`, `N=300`, `N=800`) across three seeds. Record the glucose PSI each time.
4. Set glucose's `threshold` and `min_samples` in `drift.yaml` based on your measurements. Verify your config with `make drift-policy` and `make drift-insufficient`.

**Check:** `make test-drift` passes, `make drift-report COHORT=drifted N=800` reports `DRIFT`, and `make drift-report COHORT=reference N=800` reports `NO_DRIFT`.

**Written (`answers.md`):**
1. Your calibration table: glucose PSI for both cohorts at each window size and seed.
2. The threshold and `min_samples` you chose, along with the rows in your table that support them.
3. In one sentence: what is the difference between `INSUFFICIENT` and `NO_DRIFT`?

### 4. Check for degradation — written

Input drift tells you the data moved; degradation tells you the model's predictions got worse, which you can only measure once true outcomes arrive. In production those labels may take months or years, but this lab includes them for both cohorts so you can score the model directly.

In this exercise, you score the model on both labelled windows, pick the degradation metric in `drift.yaml`, and map out what each outcome means.

1. Run `make drift-impact` and compare F1 and ROC-AUC on the known-good and drifted cohorts.
2. Set `degradation.primary_metric` and `min_drop` in `drift.yaml` using the metric that gets both cohorts right.
3. Run `make drift-vs-contract`. Week 5's data contract still passes on the drifted batch, because every shifted value remains a valid number.

**Check:** `make test-drift` passes, and `make drift-report COHORT=drifted N=800 IMPACT=1` reports drift together with degradation.

**Written (`answers.md`):**
1. Which metric did you choose, and why does the other one get a cohort wrong?
2. Fill in the table with your measured numbers and the action you would take:

   | Case | Your numbers | What you would do |
   | :--- | :--- | :--- |
   | drift **and** degradation | | |
   | drift, **no** degradation | | |
   | degradation, **no** drift | | |

### Already wired for you: drift alerts and the reaction policy

The rest of the monitor ships finished so you can see how your verdict connects to alerting and operations. Read these files, run the commands, and leave them unchanged:

- `src/week_12_drift_monitoring/drift_metrics.py`: a custom Prometheus collector that exposes `reports/drift.json` on `/metrics`, including when the report was computed.
- `prometheus/rules/drift.yml`: four drift alerts, all tickets. Two of them watch clocks: a report that is too old, and a window with no new requests.
- `drift.yaml`'s `actions:` block: what each verdict means. `load_policy` refuses any policy that pages on input drift alone.

```bash
make drift-metrics          # the verdict as Prometheus sees it
make drift-alerts-test      # promtool runs the drift alert tests
make drift-stale            # age the report by 27 hours and watch DriftReportStale fire
make drift-protocol         # the reaction protocol
```

Week 13 builds on these files.

---

### Finish — commit your work

```bash
git status          # answers.md must appear; .env and .venv/ must NOT
git add labs/week-12-drift-monitoring/starter
git commit -m "week12: drift exercises and written answers"
```

## Where to look, in order

1. `reports/drift.json` — what was the verdict, and when was it computed?
2. `make drift-policy` — what does the policy say, including each test's direction?
3. `predictions/predictions.jsonl` — are there rows in the log, and how old is the newest one?
4. `http://127.0.0.1:5560/graph` — query `model_drift_report_timestamp_seconds`. Is it `0`?
5. `http://127.0.0.1:5560/alerts` — is the alert inactive, pending or firing?
6. `http://127.0.0.1:5561` — only check Grafana after the steps above pass.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `no prediction log at …` | logging is off by default | `make predictions-on`, then restart the service |
| Verdict is always `INSUFFICIENT` | fewer than `min_samples` rows | `make traffic-drift` sends 800 |
| `make api-logs` prints nothing | the API runs on the host, not in a container | use `make api-up`, or read the terminal of `make serve-api` |
| `REFERENCE=log` fails with "has no rows" | the prediction log is empty | `make predictions-on`, restart the API, `make traffic-drift` |
| The drift panels are empty | no report yet, or `DRIFT_REPORT_PATH` is wrong | `make drift-report` |
| `/metrics` returns 500 | `collect()` raised an exception | degrade to fewer series instead of raising |
| Permission denied writing `predictions/` | Docker created the bind mount as root | `predictions/.gitkeep` is committed for this |
| `ImportError: evidently is not installed` in the container | the `drift` group is excluded from the image | expected; run drift jobs outside the serving container |
| Drift numbers change when you re-run | PSI on a sampled window has sampling noise | pass `--seed`, and build the table in Exercise 3 |

## Make targets

| Target | What it does |
| :--- | :--- |
| `make predictions-on` / `predictions-off` | enable or disable the prediction log |
| `make request` | send one request to the API (`ZERO=glucose` sends an impossible zero) |
| `make api-logs` | print the last lines of the request log (`N=`) |
| `make predictions-head` | print the last rows of the prediction log and the row count |
| `make traffic-drift` | send 800 requests from a real cohort (`COHORT=reference\|drifted`) |
| `make drift-report` | compare two windows and output a verdict (`COHORT=`, `N=`, `SEED=`, `REFERENCE=`, `IMPACT=1`) |
| `make drift-insufficient` | run the report with too few rows on purpose |
| `make drift-open` | open Evidently's HTML report |
| `make drift-policy` | print the parsed policy, thresholds and test directions |
| `make drift-sample-size` | compare a p-value against an effect size across window sizes |
| `make drift-impact` | score the model on labelled windows |
| `make drift-vs-contract` | run Week 5's contract on drifted data |
| `make drift-metrics` | print the drift verdict as Prometheus sees it |
| `make drift-alerts-test` / `drift-alerts-test-fail` | run promtool alert tests, and the negative test |
| `make drift-stale` | age the report and watch `DriftReportStale` fire |
| `make drift-protocol` | print the reaction protocol |
| `make retrain-trigger` | run the retrain loop while the gate holds the door |
| `make test-drift` | run this week's tests (no Docker, services or network needed) |

