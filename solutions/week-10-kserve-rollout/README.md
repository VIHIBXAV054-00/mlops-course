# Week 10 Lab — Reference Solution

The complete, runnable version of the Week 10 lab. Students get it after the deadline. Model
answers to the written questions and the grading rubric are kept instructor-only in
`.agents/grading/week-10.md`.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_10_kserve_rollout/rollout.py` | 1 | `publish_version()` refuses a non-GO model unless forced |
| `release.yaml` | 2 | every `<fill in>` replaced, with promotion and rollback conditions |
| `src/week_10_kserve_rollout/smoke.py` | 2 | `check_behaviour()` written |
| `k8s/inferenceservice-canary.yaml` | 3 | new: the base manifest with `canaryTrafficPercent: 10` and `STORAGE_URI` on v2 |
| `tests/` | 1–3 | no skip markers |

No new Python dependency: the load generator uses `httpx` (Week 9) and the percentiles use numpy.

## Running the solution

```bash
make down                               # the Compose stack stays down
make sync
make data-v2 && make repro              # a GO verdict, and models/model.pkl
make kind-up && make kserve-install     # 13 s, then 3 min 31 s with the images cached
make model-publish VERSION=v1           # Exercise 1
make model-publish-variant VERSION=v2 FAMILY=rf
make model-publish-variant VERSION=v3 C=0.001 FORCE=1
make release-check                      # Exercise 2
make smoke-local VERSION=v3
make image && make isvc-deploy          # Exercise 3
make isvc-canary && make canary-shift && make split-measure N=200
make isvc-canary VERSION=v3             # Exercise 4
make canary-shift VERSION=v3            # stops: the smoke test fails
make canary-shift VERSION=v3 FORCE=1    # Exercise 5
make rollback
make loadtest N=200                     # Exercise 6
```

## Exercise 1 — Publish a model version

```
$ make model-publish-variant VERSION=v3 C=0.001
REFUSING to publish v3: the recorded gate verdict is 'NO-GO'. Only a GO model may be published; FORCE=1 publishes it anyway.
```

The refusal comes before anything is written, so the store has no `v3` folder. With `FORCE=1` the
model is published and `provenance.json` records `"gate_verdict": "NO-GO"`, so the pod reports
the real verdict and the smoke test's identity check can refuse it.

## Exercise 2 — Write the rollout plan

`release.yaml` in this folder is one complete plan: v2 replaces v1 as a 10% canary, the smoke
test needs a probability spread of at least 0.1, the service must keep p95 under 300 ms with at
most 1% errors at 20 requests per second, and it lists when to promote and when to roll back. `make release-check` prints `release.yaml is complete.`

The smoke test in-process, measured on 6 November 2026:

| Version | Positive patient | Negative patient | Spread | Result |
| --- | --- | --- | --- | --- |
| v1, logistic regression | 0.9548 → 1 | 0.0355 → 0 | 0.9193 | PASS, 8 of 8 |
| v2, random forest | 0.71 → 1 | 0.0 → 0 | 0.7100 | PASS, 8 of 8 |
| v3, `C: 0.001` | 0.4751 → 0 | 0.2773 → 0 | 0.1978 | FAIL: `identity.gate`, `behaviour.positive_is_positive` |

```
  smoke test
    pass  identity.health                    status=ok revision=- store_version=v3
    pass  identity.version                   expected v3, serving v3
    FAIL  identity.gate                      gate_verdict=NO-GO (a release needs GO)
    pass  contract.illegal_rejected          422 naming ['greater_than(0)']
    FAIL  behaviour.positive_is_positive     p=0.4751 -> 0
    pass  behaviour.negative_is_negative     p=0.2773 -> 0
    pass  behaviour.not_a_constant           probability spread 0.1978 (minimum 0.1)
    pass  protocol.v1_agrees                 /predict 0 vs V1 0

  FAIL — 6 passed, 2 failed
```

With a spread of 0.1, the spread check does not catch v3; any threshold above 0.1978 and below
0.71 would catch it too and still pass v1 and v2.

## Exercise 3 — Run a canary

`make isvc-canary` applies the canary at 0%; `make canary-shift` runs the smoke test on the
`latest-` address, which passes for v2, and then sets the canary percentage to 10. Measured in August 2026
on the reference host (10 CPU, Docker limited to 8 GiB), with the canary at 10%:

```
$ make isvc-status          # the new revision was Ready in 8–11 s
NAME       URL                                   READY   PREV   LATEST   LATESTREADYREVISION
diabetes   http://diabetes.default.example.com   True    90     10       diabetes-predictor-00002
```

```
$ make split-measure N=200

  200 responses, by store version / revision:

    v1/diabetes-predictor-00001                    179   89.5%
    v2/diabetes-predictor-00002                     21   10.5%

  declared canary percentage: 10%   expected sampling spread at n=200: ±2.1% (1 s.e.)
```

A second run with 400 requests gave 8.2%, and a run on 5 November 2026 gave 23 of 200 (11.5%).
All three are passes: each request is routed at random, so the measured percentage varies like coin flips.
The canary serves v2 from the same image as v1; no image is rebuilt between model versions.

The split is counted by a Job inside the cluster (`k8s/job.yaml`), not through
`kubectl port-forward`, which holds one connection to one pod and would report 100/0.

## Exercise 4 — Stop a bad canary

With v3 as the canary at 0%, the pod is `2/2 Running` and both probes pass. `make canary-shift
VERSION=v3` runs the smoke test, which fails on the same two checks as in Exercise 2, prints
`canary-shift stopped: the smoke test failed, the canary keeps 0%.` and exits non-zero. v1 keeps
100% of the traffic; no patient got an answer from v3.

## Exercise 5 — Roll back

`make canary-shift VERSION=v3 FORCE=1` skips the smoke test and gives v3 its 10%. Then:

```
$ make rollback
    diabetes-predictor-00001 100%    tag=prev
    diabetes-predictor-00003 0%      tag=latest
```

The route changed about 1.5 s after the patch. The v3 revision keeps running at 0%, still
reachable through its `latest-` tag, ready for debugging. Nothing had to start, because v1 kept
running during the canary. `make rollback-reapply` applies the base manifest again, which creates
a new revision that serves v1, if you want the canary gone as well.

Promoting a canary under load (600 requests at concurrency 4, `canaryTrafficPercent` removed
halfway) gave 152 answers from v1, then 448 from v2, and 0 failed requests.

## Exercise 6 — Load test

200 requests per level, inside the cluster, one uvicorn worker, `cpu: 1` limit, August 2026:

```
  conc  reqs     wall      rps  errors      p50      p95      p99
  ---------------------------------------------------------------
     1   200   1.618s    123.6       0    7.20ms    9.19ms   11.13ms
     4   200   1.959s    102.1       0   35.30ms   67.21ms   91.49ms
    16   200   2.125s     94.1       0  100.79ms  526.69ms  775.62ms
    64   200   2.041s     98.0       0  426.38ms 1657.05ms 1917.46ms
```

A second run gave 148.4 rps and p50 6.41 ms at concurrency 1, and 105.7 rps and p95 1585.86 ms at
64. Throughput stays near 100 rps from concurrency 4 on while p95 grows: the one worker is
saturated, and the rest is queueing. Against this `release.yaml` (p95 under 300 ms), concurrency 1
and 4 are `within` and 16 and 64 are `OVER`.

## Tests

```bash
uv sync --locked --all-groups && uv run --frozen pytest
```

With the stack down: every test passes except the 8 that need the MLflow server.

## Make targets, troubleshooting

As in the starter README.
