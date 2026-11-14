# Week 9 Lab — Reference Solution

The complete, runnable version of the Week 9 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

Week 8 made the pipeline run on a schedule. Week 9 makes its model usable by someone else: a
service over HTTP, a container image with the model in it, and copies of that image on a local
Kubernetes cluster.

## Changes from starter

What a student writes this week. Everything else is identical between `starter/` and `solution/`.

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_09_serving/api.py` | 2 | the two decorators and each `...` filled in: `GET /health` (503 until the model is loaded, then the model version, run ID and gate verdict from `build_info`) and `POST /predict` (the `PredictionInput` contract, a 422 that names the failed check, then `predict_proba`) |
| `src/week_09_serving/bench.py` | 3 | `online_score`: one request per row, each timed with `time.perf_counter()`, the responses that were not 200 counted, p50 and p95 from `statistics.quantiles` |
| `k8s/deployment.yaml`, `k8s/service.yaml` | 5 | each `<fill in>` replaced: a Deployment with two pods, `imagePullPolicy: IfNotPresent` and the readiness and liveness probes on `/health`; a Service that selects `app: diabetes-api` |
| `tests/test_api.py` | 2, 3 | the 16 skip markers removed |
| `tests/test_k8s_manifests.py` | 5 | the 10 skip markers removed |
| `pyproject.toml` | — | only in the starter: ruff ignores the unused `...` blanks in `api.py` |
| `k8s/README.md` | — | only in the starter: what the files must say |
| `compose.yaml` | — | `name: week09-serving` (the starter's is `week09-serving-starter`) |

## New this week, already in the starter

| File | Used in | What it is |
| --- | --- | --- |
| `src/week_09_serving/api.py` | 2, 4 | the request model (`extra="forbid"`, `null` allowed where the contract allows it), the response models, `_build_info()`, the skeletons of `health` and `predict`, and the model loaded once at startup |
| `src/week_09_serving/bench.py` | 3 | `batch_score`, `to_payloads`, the comparison table and `run_bench`, which converts the sentinel zeros as training does |
| `src/week_09_serving/cli.py` | 2–4 | `serve-api`, `bench` and `build-info` subcommands |
| `serve.Dockerfile`, `.dockerignore` | 4 | the serving image; the model, its version, run ID and gate verdict are written in at build time |
| `Makefile` | 1–5 | `serve-mlflow`, `serve-api`, `bench`, `image` (refuses unless the verdict is GO), `run-image`, `kind-up`, `kind-down`, `k8s-deploy`, `k8s-status` |
| `pyproject.toml` | 2 | `fastapi`, `uvicorn[standard]` and `httpx` declared. The lock grows from 229 to 232 packages (uvicorn's extras `httptools`, `uvloop`, `watchfiles`); no installed version moved |
| `tests/test_scope.py` | — | `fastapi`, `starlette` and `uvicorn` removed from the list of later weeks' tools |

## Running the solution

```bash
cd ../../week-08-prefect-flow/solution && make down; cd -
cp .env.example .env
make sync
make up && make data-v2 && make repro          # a GO verdict, and models/model.pkl
make register && make promote-champion         # the champion that Exercise 1 serves
make serve-mlflow                              # Exercise 1; Ctrl-C to stop
make bench                                     # Exercise 3
make image && make run-image                   # Exercise 4
make down && make kind-up && make k8s-deploy   # Exercise 5
make kind-down
```

Only Exercise 1 and `make image` need the Compose stack. The service, the benchmark, the container
and the cluster run with it down, because the model is in the image.

## What MLflow's server checks (Exercise 1)

Measured on 29 Oct 2026 against `models:/diabetes-classifier@champion`, with the request columns in
the training order unless stated:

| Request | `mlflow models serve` | This service |
| --- | --- | --- |
| valid patient | 200 `{"predictions": [1]}` | 200, probability 0.7293 |
| `glucose: 0` | 200 `{"predictions": [0]}` | 422 `greater_than(0)` |
| `glucose: -50` | 200 `{"predictions": [0]}` | 422 `greater_than(0)` |
| `age: 250, bmi: 336` | 200 `{"predictions": [1]}` | 422 `less_than_or_equal_to(120)`, `less_than_or_equal_to(100.0)` |
| extra column `cholesterol` | 400 `BAD_REQUEST` | 422 `extra_forbidden` |
| no `bmi` column | 400 `BAD_REQUEST` | 422 `missing` |
| the same columns in another order | 400 `BAD_REQUEST` | 200 |

The model was logged without a signature, so MLflow checks nothing of its own. It builds a data
frame and calls the model; the 400s come from scikit-learn, whose stack trace says that the feature
names do not match those seen in `fit`. Everything that has the right columns is scored, including
three patients the Week 5 contract rejects. `instances` and `inputs` work only as lists of rows in
the training order.

## Batch versus online (Exercise 3)

Three runs of `make bench` on 2 Nov 2026, with no Docker services running:

```
             rows   wall clock     rows/s       p50       p95
  batch       192      0.0095s    20235.9         —         —
  online      192      0.8875s      216.3     4.45ms     5.31ms
```

Online took 104×, 72× and 93× the wall clock of batch, and all 192 requests answered 200. The ratio
moves with the machine; the order of magnitude stays. The model itself takes microseconds per row:
the time goes into JSON, two rounds of validation and the HTTP layer for every request.

Both modes convert the sentinel zeros to missing values first, as training does. Before 2 Nov 2026
they did not: 88 of the 192 online requests got a 422 and never reached the model, while batch
scored the raw zeros. `make bench` now counts the failed requests and says so.

## The container (Exercise 4)

`make image` took 33 to 41 seconds with the base image cached; the image is 1.04 GB. The build
arguments come after `uv sync`, so a new model version rebuilds only the last layers: under a
second, measured on 30 Oct 2026. With the stack up,
`/health` from `make run-image`:

```json
{"status": "ok", "model_version": "2", "run_id": "17860f31aab145b588f54c3ac2e5ede4",
 "gate_verdict": "GO", "schema_version": "1.0.0", "model_source": "registry champion"}
```

`make trace` on the same stack reports version 2 and the same run ID. With `C: 0.01` in
`params.yaml`, the gate fails `regression.f1` and `fairness.age_band.tpr_gap`, and `make image`
stops with `REFUSING to build: the recorded gate verdict is 'NO-GO'.` Built with the stack down,
the image reports `"model_version": "unknown"` and `"model_source": "local models/model.pkl"`.

## Kubernetes (Exercise 5)

Measured on 29 Oct 2026 with kind v0.32.0 and kubectl v1.36.1.

- `kind create cluster` took 13 seconds with the node image already downloaded; `make k8s-deploy`
  took 51 seconds.
- Applied before `kind load docker-image`, both pods show `ErrImagePull`. The event says
  `pull access denied, repository does not exist`: Kubernetes looked for `diabetes-api:local` on
  Docker Hub.
- After `make k8s-deploy`, `make k8s-status` shows two pods `Running` and `1/1` ready, and two
  addresses on the Service's `Endpoints` line.

## Tests

| | |
| --- | --- |
| Solution, stack down | **227 passed, 8 skipped** (the MLflow-link tests) |
| Starter after Setup, stack up | **209 passed, 26 skipped** (the exercise markers) |
| Starter after Setup, stack down | **201 passed, 34 skipped** (26 exercise markers, 8 MLflow-link tests) |

`tests/test_api.py` runs the whole service with FastAPI's `TestClient` and a model that the fixture
trains, so it needs no server and no `models/model.pkl`. The Exercise 3 tests use a fake client
whose third request takes 50 ms, so a student who divides the total time by the number of rows
fails them, and another that answers 422 to every fourth request, which must be counted. `test_the_image_names_the_champion_only_when_it_holds_the_champion` checks that
`make image` claims a registry version only for the champion's own run.
`tests/test_k8s_manifests.py` checks the manifests as YAML.

## Defects found while building this

1. **`make serve` overrode Week 8's Prefect target.** `make` prints "overriding commands for
   target" and carries on. The service target is `serve-api`.
2. **`build-info`'s unquoted output broke `eval`.** `MODEL_SOURCE=local models/model.pkl` set the
   first word and ran the second as a command. The values are now quoted with `shlex.quote`.
3. **The Dockerfile did not copy `README.md`**, which `pyproject.toml` names, and the build failed
   with `OSError: Readme file does not exist`.
4. **The manifest scope test failed on a comment** that said "no Ingress here". It now checks the
   parsed YAML, not the text.
5. **The first availability measurement used `kubectl port-forward`** and showed an outage that
   users would not have seen.
6. **`gate` did not declare `models/mlflow_run_id.json` as a dependency**, so after a new run DVC
   skipped it and `make trace` showed no gate verdict. Fixed in Weeks 6–9.
7. **`make serve-mlflow` passed `models:/@` to MLflow** (found 29 Oct 2026): the recipe read two
   Make variables that nothing set. It now reads `.env`.
8. **`make k8s-status` never showed the Service** (29 Oct 2026): its `-l app=diabetes-api` filter
   matched only the pods. It now prints the Service's selector and endpoints.

## Make targets

| Target | What it does |
| --- | --- |
| `make serve-mlflow` | MLflow's server for the champion, port 5540 (Exercise 1) |
| `make serve-api` | the service, port 5541 (Exercise 2) |
| `make bench` | batch and online scoring, with p50 and p95 (Exercise 3) |
| `make image` / `make run-image` | build after a GO, and run the image on port 5542 (Exercise 4) |
| `make kind-up` / `make kind-down` | the kind cluster `mlops` (Exercise 5) |
| `make k8s-deploy` / `make k8s-status` | load, apply and inspect (Exercise 5) |

Every Week 4–8 target still works.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `make serve-mlflow` fails with `No such artifact: 'MLmodel'` | the registered version's files are not in Silo | with the stack up, `make repro`, `make register`, `make promote-champion` |
| Pods show `ErrImagePull` or `ImagePullBackOff` | the image is not on the kind node | `make k8s-deploy` |
| `port-forward` connects, then requests hang | the Service's selector does not match the pod labels | `make k8s-status`: the `Endpoints` line is empty |
| Pods restart again and again | the liveness probe fails before the app has started | a longer `initialDelaySeconds` on liveness |
| `make image` refuses to build | the recorded verdict is not GO | `make repro` |

## Submission

Students submit the URL of their commit in Moodle. Model answers and the grading rubric are kept
instructor-only in `.agents/grading/week-09.md`.
