# HW 4: Serving, Rollout and Monitoring

| | |
| --- | --- |
| **Released** | Week 11 |
| **Due** | 23:59 (Budapest) on Sunday of **Week 14** (13 December) |
| **Estimated effort** | 8–10 hours |
| **Builds on** | HW 1–HW 3 (your project repository), Labs 9 and 10 (Part A), Labs 11 and 12 (Part B) |

---

## Objective

Serve your model over HTTP, release a new model version to a small percentage of the requests, and
roll it back. Then make the running service measurable: count its requests, write down what it
promises, alert when it fails, and check whether its input data has moved.

This extends the repository you submitted for HW 3. Do not start a new project. This is the last
homework of the course.

The work has two parts:

- **Part A (R1–R5)** uses Labs 9 and 10. You can start it on the day of release.
- **Part B (R6–R8)** uses Lab 11 (in class on Wednesday 18 November) and Lab 12 (at home, in the
  week of 23 November). Start it after the lab it needs.

The written test is on Wednesday 2 December, so plan to finish Part A before it.

Use only the tools from Labs 1–12. You may copy the labs' code, Makefile targets, scripts and
manifests into your project and change the names. No Grafana dashboard is required.

---

## Requirements

The grader runs your tests and your image build, and reads the evidence in `docs/hw4.md` for the
rest. The grader does not start your cluster or your Compose stack. Your HW 1–3 work must keep
working: the pipeline reproduces, the contracts hold, the gate decides and the flow runs.

## Part A — Serve and roll out (Labs 9 and 10, about 5.5 hours)

### R1 — A prediction service (12 points)

Your HW 2 data contract decides which inputs the model may see. The service checks every request
against the same contract before the model runs, so a caller learns what was wrong with a request.

- Write a FastAPI app with `POST /predict` and `GET /health`, as in Lab 9.
- `/predict` checks one record against your HW 2 data contract. If a Pydantic request model lists
  the fields a second time, add a test that checks that the two lists agree.
- An invalid request gets a 422 that names the failed check, for example `greater_than(0)`.
- `/health` returns 503 until the model is loaded. After that it returns 200 with the version, run
  ID and gate verdict of the loaded model.
- Test both endpoints in `tests/` with FastAPI's `TestClient`. The tests pass with Docker stopped
  and no cluster.

### R2 — A serving image (6 points)

An image is a release, so the model in it must have passed the gate.

- Write a Dockerfile for the service and a `make` target that builds the image.
- The target refuses to build when the recorded gate verdict is not GO, and its message says why.

### R3 — Model versions and a rollout plan (10 points)

KServe loads a model version from a store when the pod starts, so a new version needs no new image.
Publishing to the store is a file copy, and it must check the gate like every other path to
production.

- Publish at least two versions of your own model to a model store, as in Lab 10, Exercise 1. Both
  have a GO verdict, and each version stores its run ID and gate verdict next to the model file.
- Publishing refuses a model whose gate verdict is not GO, unless you force it.
- Write the rollout plan for replacing your first version with the second: a `release.yaml` with
  the same keys as Lab 10's, filled in for your project. The `load` values may be estimates.

### R4 — A smoke test that fails a bad model (14 points)

A pod can be Ready and answer every request with HTTP 200 while it serves the wrong model. The
smoke test checks the model itself, once per release, before the new version gets traffic.

- Write a smoke test with at least three checks:
  - identity: the service runs the expected version, and its gate verdict is GO;
  - contract: an input your contract forbids gets a 422;
  - behaviour: records you are sure about get the expected answers.
- Pick the behaviour records from the ends of your data, and say in `docs/hw4.md` why the answers
  for them should not change between good models.
- The smoke test runs in-process against a store version, and against a deployed endpoint.
- It exits with a non-zero code when a check fails.
- Add a test in `tests/` that runs the smoke test against a model your gate refuses, and asserts
  that it fails and which checks failed.

### R5 — A canary and a rollback (16 points)

Run the release from your rollout plan on a local cluster with KServe, as in Lab 10, Exercises 3
and 5. Paste the output of each step into `docs/hw4.md`.

1. Deploy your first version as an `InferenceService`.
2. Deploy the second version as the canary at 0%, run the smoke test against its own address, and
   then give it your canary percentage.
3. Count which version answered at least 200 requests, sent from inside the cluster. Report the
   counts and the number of requests next to your canary percentage.
4. Roll back: set the canary percentage to 0. Time the command, and show that the first version
   gets all the traffic again.
5. List what the rollback did not put back. Check your registry alias, your baseline metrics, your
   DVC files and the answers the canary already gave.

A rollback that is described but never run scores zero for step 4.

Optional, for no points: run Lab 10's load test against your service and compare it with the `load`
values in your rollout plan.

## Part B — Monitor it (Labs 11 and 12, about 3 hours)

### R6 — Request metrics (10 points)

Prometheus reads metrics from the service. A label value creates a new time series, so every label
must come from a short list you can write down.

- Expose `/metrics` on your service with `prometheus_client`, as in Lab 11.
- Count requests with a counter labelled by method, route template and status code.
- Record request latency in a histogram with bucket boundaries you chose.
- Add a test: requests to two different paths that do not exist give one series in the counter,
  not two.

### R7 — An SLO and one alert (10 points)

An SLO is a target for a service level indicator over a time window. The error budget is the
failure that the target allows.

- Write an availability SLO for `/predict` in `slo.yaml`, a file of its own: the indicator as good
  requests divided by valid requests, the target and the window. Say in one line whether a 422
  counts as a valid request, and why.
- In `docs/hw4.md`, give the error budget in minutes for the window, with the arithmetic.
- Add Prometheus to your Compose stack, and scrape the service by its Compose service name.
- Write one alerting rule in a rules file, for example the service being down or the error budget
  burning fast. Say in one line whether it should page someone or open a ticket, and why.
- Make the alert fire once, for example by stopping the service container, and paste the firing
  alert from Prometheus's `/alerts` page or its API into `docs/hw4.md`.

### R8 — A drift report and a decision (10 points)

A model can be up, fast and error-free while the patients, customers or records it scores have
changed. A drift report compares a reference window with a current window, feature by feature.

- Run one drift report with Evidently, as in Lab 12. The reference window is your training data,
  named by its DVC version (the md5 in its `.dvc` file). The current window is data your model did not train on: rows from your
  prediction log, a later batch, or a held-out part of your data.
- Filter the reference window in the same way as the current window, for example drop the rows your
  contract rejects.
- In `docs/hw4.md`, report the method, the threshold and both window sizes, and the result for each
  feature.
- Choose what you would do: nothing, roll back, collect labels or retrain. Explain your choice in
  three to five sentences, and say whether you could measure the model's accuracy on the current
  window.

## Both parts

### R9 — `docs/hw4.md` (12 points)

Put your commands and evidence in one document, so a colleague can release and roll back your
model without asking you.

- How to publish a new version, deploy it as the canary and promote it: the exact commands.
- How to roll back: the exact command, how long it took, and how to check that it worked.
- The evidence for R3–R8: command output pasted as text or screenshots, not a description of it.

---

## Submission

Push to your project repository and submit **the URL of the commit** you want graded in the
HW 4 assignment in Moodle.

| Path | What |
| --- | --- |
| `src/.../api.py`, `src/.../metrics.py` (or equivalent) | the service and its metrics (R1, R6) |
| the serving Dockerfile and its `make` target | R2 |
| the publishing code and `release.yaml` | R3 |
| `src/.../smoke.py` | R4 |
| `k8s/` | your `InferenceService` manifests (R5) |
| `slo.yaml`, `compose.yaml`, your Prometheus config and rules file | R7 |
| `tests/` | including the R1, R4 and R6 tests |
| `docs/hw4.md` | the written work and the evidence |

**Do not commit:** `.env`, a kubeconfig, your model store, your prediction log, `.venv/`, your
data file, or model files outside the DVC cache. A kubeconfig gives access to a cluster, so treat
it like a password.

### The commands the grader will run

From a **fresh clone** of your submitted commit, the grader follows your setup instructions:

```bash
uv sync --locked --all-groups
uv run --frozen pytest -q             # with Docker stopped and no cluster; must pass
cp .env.example .env
<your documented data and model setup>  # for example, dvc pull and make repro
make <your image target>              # must build after a GO, and refuse after a NO-GO
<your in-process smoke command>       # for example, make smoke-local VERSION=v1; must PASS
```

The grader does not start your cluster or your Compose stack. R5, R7 and R8 are graded from
`docs/hw4.md` and the files in your repository, so paste the real output of each step. Evidence
copied from the lab or from another student is plagiarism.

---

## Grading

| Requirement | Points | Time | How |
| --- | --- | --- | --- |
| R1 a prediction service | 12 | 1.5 h | running |
| R2 a serving image | 6 | 0.5 h | running |
| R3 model versions and a rollout plan | 10 | 1 h | reading + running |
| R4 a smoke test that fails a bad model | 14 | 1 h | running + reading |
| R5 a canary and a rollback | 16 | 1.5 h | reading |
| R6 request metrics | 10 | 1 h | running + reading |
| R7 an SLO and one alert | 10 | 1 h | reading |
| R8 a drift report and a decision | 10 | 1 h | reading |
| R9 `docs/hw4.md` | 12 | 0.5 h | reading |
| **Total** | **100** | **9 h** | |

The times are estimates for a student who has done the labs.

### Deductions

These deductions apply in addition to points lost in the requirements.

| | |
| --- | --- |
| −10 | the image build or the store publish accepts a NO-GO model without being forced |
| −5 | the raw request path used as a metric label |
| −5 | tests that need a running server, a container or a cluster |
| −5 | `.env`, a kubeconfig, the model store or the prediction log committed |

---

## Advice

**Run the rollback when nothing is wrong.** Pixar had a backup of *Toy Story 2*, but nobody had
tested it, and it did not hold the film when it was needed (Week 10). A rollback you have run once
is one you can trust.

**Use the model your gate refuses as the bad model.** It loads, passes the readiness probe and
answers every request with HTTP 200. Your smoke test must still fail it.

**Count the split from inside the cluster.** Lab 10's `make split-measure` sends the requests from
a Job in the cluster, so they take the same route as real traffic.

**Send varied records for the drift report.** The same record sent many times has no distribution,
so it can never drift.

**Stop the cluster before you start the Compose stack.** A 16 GB laptop cannot run both, and Part B
needs no cluster.
