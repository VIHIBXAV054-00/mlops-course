# Week 10 Lab — Rollout with KServe

Your model now runs in a container on a local cluster, but a new model still reaches every user at
once, and nothing checks what it predicts. In this lab, you release a new model with KServe:

1. Publish a model version.
2. Write the rollout plan.
3. Run a canary deployment.
4. Smoke-test the canary.
5. Roll it back.

## What you already have

You already have the training pipeline, the data contracts, the quality gate, the FastAPI service
with `/health` and `/predict`, the serving image and the kind cluster. The model, metrics and
thresholds stay the same.

New in this lab:

- `rollout.py`: publishes a model version into `model-store/`, a folder the cluster reads.
- `release.yaml`: the rollout plan.
- `smoke.py`: the smoke test.
- `loadtest.py`: counts which version answered, and measures latency under load.
- `k8s/inferenceservice.yaml`: the running version as a KServe `InferenceService`.
- The service's `/health` now also reports the store version and the revision that answered.

To refresh the concepts (canary, smoke test, rollout plan, `InferenceService`), read the lecture
slides or the KServe docs below.

## Based on (official tutorials)

- **KServe quick start:** https://kserve.github.io/website/docs/getting-started/quickstart-guide
- **KServe canary example:** https://kserve.github.io/website/docs/model-serving/predictive-inference/rollout-strategies/canary-example
- **KServe custom predictor:** https://kserve.github.io/website/docs/model-serving/predictive-inference/frameworks/custom-predictor

## Prerequisites

- Weeks 1–9 working, with `kind` and `kubectl` installed.
- Keep the Compose stack down: `make down`.
- Run `make kind-up` and `make kserve-install` before the lab session if you can. The first
  install takes about 5 minutes.

## Setup

```bash
cp .env.example .env
make sync               # install all dependency groups
make data-v2            # rebuild the dataset from the committed raw batches
make repro              # train and check the gate; you should get a GO and models/model.pkl
make kind-up            # create the cluster; it mounts ./model-store into the node
make kserve-install     # install cert-manager, Istio, Knative and KServe
make kserve-status      # every component Running
```

Run `uv run pytest -q` before starting the exercises. With the stack down, the expected result is:

```
252 passed, 27 skipped
```

Eight of the skipped tests need the MLflow server. The other 19 belong to this lab, and each skip
names its exercise: 1 in `tests/test_rollout.py`, 2 in `tests/test_release.py`, 7 in
`tests/test_smoke_suite.py`, and 9 in `tests/test_isvc_manifests.py`, which skip while
`k8s/inferenceservice-canary.yaml` does not exist.

## Exercises

Write your answers to the questions in `answers.md`, and commit the file with your code.

### Exercise 1 — Publish a model version (`make model-publish`)

KServe does not need a new image for a new model: it copies a model version from a store when the
pod starts. Publishing a version is therefore a file copy into `model-store/`. A copy needs no
build and no approval, so it is the easiest way to put a model the gate rejected into production.
At work, an upload script that skips the gate is a typical audit finding. In this exercise, you
publish three model versions and make the store refuse a model that the gate rejected.

1. Publish the current model and the random forest from Week 6, then list the store:

   ```bash
   make model-publish VERSION=v1
   make model-publish-variant VERSION=v2 FAMILY=rf
   make store-list
   ```

2. Publish the model the gate rejects: `make model-publish-variant VERSION=v3 C=0.001`. The
   pipeline prints NO-GO, and the store still accepts it. `make store-list` shows v3 with
   `NO-GO`. Delete it: `rm -r model-store/v3`.
3. In `src/week_10_kserve_rollout/rollout.py`, `publish_version()`, refuse a model whose gate
   verdict is not GO, unless `force` is true.
4. Run step 2 again. Now publish v3 on purpose, as the bad model that Exercise 4 needs:
   `make model-publish-variant VERSION=v3 C=0.001 FORCE=1`.

**Check:** delete the skip marker in `tests/test_rollout.py`, and the tests pass. Step 4's first
command prints a message that starts with `REFUSING to publish v3` and leaves no `v3` folder. After the forced publish, `make store-list` shows v1 and v2 with `GO` and v3 with `NO-GO`.

### Exercise 2 — Write the rollout plan (`make release-check`, `make smoke-local`) — **written**

The rollout plan is a checklist in a YAML file, kept in Git next to the model's code. It holds the
decisions that only the ML engineer can make:
- which version replaces which,
- the canary percentage,
- what a sane answer looks like,
- what load to expect,
- when to promote,
- when to roll back.
With the plan written down, the engineer on call can act alone.
For this model the strategy is already chosen: a canary, because the platform cannot store and compare shadow
answers. In this exercise, you fill in `release.yaml` and write the smoke test's behaviour check.

1. Open `release.yaml` and replace each `<fill in>`.
   Run `make release-check` until it prints `release.yaml is complete.`
2. In `src/week_10_kserve_rollout/smoke.py`, write `check_behaviour()`. It sends a clearly ill and
   a clearly healthy patient to `/predict` and compares the answers.
3. Run the smoke test in-process, without a cluster, against each store version:

   ```bash
   make smoke-local VERSION=v1
   make smoke-local VERSION=v2
   make smoke-local VERSION=v3
   ```

**Check:** delete the skip markers in the "Exercise 2" sections of `tests/test_release.py` and
`tests/test_smoke_suite.py`, and the tests pass. `make smoke-local` prints `PASS` for v1 and v2,
and `FAIL` for v3, with `identity.gate` and `behaviour.positive_is_positive` among the failed
checks.

Questions:

1. Pick one item from your `promote.when` list and one from your `rollback.when` list. For each,
   name the signal it watches and how soon after the canary starts it can decide. Why can neither
   of them use the true diagnosis?
2. At 300 requests a day, how many patients a day reach the candidate at your `canary.percent`?
   Is that enough to show that v2 is better than v1? What can it show?
3. Which `min_probability_spread` did you choose? `make smoke-local` prints the spread of each
   version. Which value would make the spread check catch v3 as well, and what would a value close
   to v2's spread risk?

### Exercise 3 — Run a canary (`make isvc-deploy`, `make isvc-canary`, `make canary-shift`) — **written**

A canary sends a small percentage of real requests to the new version while the old one keeps
serving the rest. Before the canary gets any traffic, the smoke test checks it through its own
address. In this exercise, you deploy v1, write the canary manifest, smoke-test the canary at 0%,
give it its canary percentage, and count which version answered.

1. Build the image, so it contains your code from Exercises 1 and 2: `make image`.
2. Deploy v1: `make isvc-deploy`. Then `make isvc-health` shows `"store_version":"v1"` and the
   revision that answered. Send a prediction through the gateway:

   ```bash
   curl -s -X POST -H 'Host: diabetes.default.example.com' -H 'Content-Type: application/json' \
     -d '{"pregnancies":6,"glucose":148,"blood_pressure":72,"skin_thickness":35,"insulin":125,"bmi":33.6,"diabetes_pedigree":0.627,"age":50}' \
     http://127.0.0.1:5550/predict
   ```

3. Write `k8s/inferenceservice-canary.yaml`: a copy of `k8s/inferenceservice.yaml` with two
   changes. `k8s/README.md` says which.
4. Deploy the canary with no traffic: `make isvc-canary`. `make isvc-status` shows the new
   revision at 0% with the tag `latest`.
5. Give it traffic: `make canary-shift`. It runs the smoke test against the new revision first,
   and sets the canary percentage to your `canary.percent` only if the test passes.
6. Count the split: `make split-measure N=200`.

**Check:** `uv run pytest tests/test_isvc_manifests.py` passes with nothing skipped.
`make canary-shift` prints the smoke test's `PASS`, and `make isvc-status` then shows the two
revisions with your traffic split. `make split-measure` prints how many of the 200 answers came
from each version, next to your declared canary percentage.

Question:

4. Your measured percentage is not exactly your `canary.percent`. Why not? How many requests would
   you need before a difference of one percentage point meant something?

### Exercise 4 — Stop a bad canary (`make isvc-canary VERSION=v3`) — **written**

A readiness probe proves that the model loaded. It cannot tell whether this is the model you meant
to release, or whether its predictions make sense. The smoke test is responsible for that, and `make
canary-shift` refuses to move traffic when it fails. At work, this is the step in a deployment
pipeline that blocks a release. In this exercise, you deploy the bad model from Exercise 1 as the
canary and watch everything the platform checks stay green while the smoke test stops it.

1. Make v3 the canary, at 0%: `make isvc-canary VERSION=v3`. Then
   `kubectl get pods -l serving.knative.dev/service=diabetes-predictor` shows every pod Ready.
2. Try to give it traffic: `make canary-shift VERSION=v3`, then `echo $?`.
3. `make isvc-status` shows where the traffic goes now.

**Check:** step 2 prints the smoke test's `FAIL`, with `identity.gate` and
`behaviour.positive_is_positive` failed, then `canary-shift stopped`, and exits with a non-zero
code. `make isvc-status` shows v1 with 100% and the v3 revision with 0%.

Question:

5. The v3 pod is Ready and would answer every request with HTTP 200. Which checks failed, and
   which passed? If you could keep only one check, which would it be, and why?

### Exercise 5 — Roll back (`make rollback`) — **written**

When a bad canary does get traffic, the old version must take all of it again, fast and in a way
you have tested. For a canary, the rollback sets the canary percentage to 0, with the same field
you deploy with. The old version kept running, so nothing has to start. In this exercise, a
colleague skips the smoke test, and you roll back and time it.

1. Skip the check, as the colleague does: `make canary-shift VERSION=v3 FORCE=1`. `make
   isvc-status` shows v3 with your `canary.percent`.
2. Roll back: `time make rollback`. `make isvc-status` shows the old revision at 100% and v3 at 0%.

**Check:** after step 2, `make isvc-status` shows 100% on the revision that serves v1, and
`make isvc-health` reports `"store_version":"v1"`.

Questions:

6. What did the rollback change, and what did it not put back? Look at the registry alias,
   `metrics/baseline.json`, the DVC files and the answers v3 gave while it had traffic.
7. Write the rollback steps for this model as a short list, as you would add them to the rollout
   plan. Which step did you just test, and which one have you not tested yet?

### Exercise 6 — Load test (optional) (`make loadtest`) — **written**

The rollout plan promised a latency at a load. A load test checks that: it sends
requests at rising concurrency and reports throughput, error rate and p50/p95/p99. In this
exercise, you run it from inside the cluster and compare the result with your `release.yaml`.

1. Run `make loadtest N=200`. `LEVELS=1,4,16,64` is the default list of concurrency levels.

**Check:** the output has a table with one row per concurrency level, and below it each level
marked `within` or `OVER` your `load.max_p95_ms` and `load.max_error_rate`.

Question:

8. At which concurrency does the service stop meeting your rollout plan? What would you tell
   the platform team, and which numbers would you give with it?

### Finish — commit your work

```bash
git status          # include answers.md, release.yaml and k8s/inferenceservice-canary.yaml
git add .
git commit -m "week10: rollout plan, canary, smoke test and written answers"
```

`model-store/`, `.env` and `.venv/` are not committed. If `git status` shows `params.yaml` as
modified, run `git checkout params.yaml`.

## Make targets

| Target | What it does |
| --- | --- |
| `make kserve-install` / `make kserve-status` | install KServe and its parts, then show them (Setup) |
| `make model-publish VERSION=v1` | publish the current model into the store (Exercise 1) |
| `make model-publish-variant VERSION=v2 FAMILY=rf` | retrain a variant, publish it, restore `params.yaml` (Exercise 1) |
| `make store-list` | the store's versions and their gate verdicts (Exercise 1) |
| `make release-check` | is `release.yaml` complete? (Exercise 2) |
| `make smoke-local VERSION=v1` | the smoke test in-process, against a store version (Exercise 2) |
| `make isvc-deploy` | load the image into kind and apply `k8s/inferenceservice.yaml` (Exercise 3) |
| `make isvc-canary [VERSION=v3]` | apply the canary manifest at 0%, with another store version if given (Exercises 3, 4) |
| `make canary-shift [VERSION=v3] [FORCE=1]` | smoke-test the newest revision, then give it `canary.percent`; FORCE=1 skips the test (Exercises 3–5) |
| `make isvc-status` / `isvc-health` / `isvc-url` | revisions and traffic split, `/health` through the gateway, the URLs |
| `make split-measure N=200` | count which version answered, from inside the cluster (Exercise 3) |
| `make smoke VERSION=v2` | the smoke test alone, against the newest revision's own address |
| `make rollback` / `rollback-reapply` / `promote-canary` | canary percentage to 0, re-apply the base manifest, or promote (Exercise 5) |
| `make loadtest` | throughput, errors and p50/p95/p99 against `release.yaml` (Exercise 6) |
| `make kind-down` | delete the cluster |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `make smoke-local` fails with `NotImplementedError` | `check_behaviour()` is not written yet | Exercise 2, step 2 |
| a `make` target says `release.yaml has no ...` | a key in `release.yaml` was renamed or removed | compare with the comments in the file |
| pods show `ErrImagePull` | the image is not on the kind node | `make isvc-deploy` runs `kind load docker-image` |
| a revision never becomes Ready, `/health` answers 503 | `STORAGE_URI` names a version that is not in the store | `make store-list` |
| `/health` has no `store_version`, or the smoke Job fails with `NotImplementedError` | the image was built before Exercise 2 | `make image`, `make isvc-deploy`, then `make isvc-canary` again |
| `kubectl get isvc` shows `RevisionMissing` | a revision was deleted by hand | `make rollback-reapply` |
| `make isvc-canary VERSION=v3` creates no new revision | the canary manifest's `STORAGE_URI` is not a `pvc://diabetes-models/<version>` path | compare with `k8s/inferenceservice.yaml` |
| everything is slow | the Compose stack is up as well as the cluster | `make down` in this and other labs |

## Submission

Submit the commit from Finish. It contains your code, `release.yaml`,
`k8s/inferenceservice-canary.yaml` and `answers.md`. Do not include `.env`, `.venv/` or
`model-store/`. Push the commit, open it on GitHub
(`https://github.com/<you>/<repo>/commit/<hash>`), and upload that URL to Moodle.

## Deviations from the tutorials

1. **`pvc://` instead of the quick start's `gs://`.** The store is a folder on the laptop that the
   cluster mounts, so no cloud account is needed.
2. **Our own image instead of KServe's built-in `sklearn` server.** The built-in server reads our
   model with an older scikit-learn and takes a list of numbers without names, so the data
   contract cannot check a request.
3. **The installer is downloaded, checked against its hash, then run,** instead of piping it from
   the internet into `bash`.
4. **Our own load generator instead of `hey`.** It runs inside the cluster, so the requests take
   the same route as real traffic, and it records which version answered each request.
