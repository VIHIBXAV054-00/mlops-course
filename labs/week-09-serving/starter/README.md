# Week 9 Lab — Model Serving

Your training pipeline can produce a model on a schedule, but a caller still needs Python code to
load and use it. In this lab, you make the model available over HTTP with FastAPI and compare
online predictions with batch scoring. Then you package the service and model in a container and
run them on a local Kubernetes cluster with kind.

## What you already have

You already have the Compose stack, MLflow, DVC with Silo, the
`validate → prepare → train → evaluate → gate` pipeline, both data contracts, the quality gate,
`make ci` and the Prefect flow. The model, metrics and thresholds stay the same in this lab.

New in this lab:

- `fastapi`, `uvicorn[standard]` and `httpx` in `pyproject.toml`.
- `api.py`: a FastAPI app with the request and response models.
- `bench.py`: scores the test rows in batch and online.
- `serve.Dockerfile`: the recipe for the serving image. `make image` builds it.
- `k8s/`: the directory for your Kubernetes manifests.

You have used `make predict` to check a request against the data contract and score it in a Python
process. The service does the same over HTTP, so a caller can send a request without loading the
model. The container image holds the service, its locked packages and the model; Kubernetes keeps
copies of the service running.

## Based on (official tutorials)

- **FastAPI tutorial:** https://fastapi.tiangolo.com/tutorial/ · testing: https://fastapi.tiangolo.com/tutorial/testing/
- **MLflow, deploy a model locally:** https://mlflow.org/docs/latest/deployment/deploy-model-locally/
- **Docker, building best practices:** https://docs.docker.com/build/building/best-practices/
- **kind quick start:** https://kind.sigs.k8s.io/docs/user/quick-start/
- **Kubernetes:** Deployment https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ ·
  Service https://kubernetes.io/docs/concepts/services-networking/service/ ·
  probes https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

## Prerequisites

- Weeks 1–8 working: `uv`, Docker, Git.
- Install `kind` and `kubectl`:
  https://kind.sigs.k8s.io/docs/user/quick-start/#installation and
  https://kubernetes.io/docs/tasks/tools/. The lab was tested with kind v0.32.0 and kubectl v1.36.
- On a 16 GB laptop, stop the Compose stack before starting the cluster to leave enough memory.
   Exercises 1–4 use the stack; Exercise 5 uses the cluster.
- Optional: an API client for sending requests in Exercises 1 and 2. We recommend Bruno
  (https://www.usebruno.com/), which saves requests as plain files; Postman
   (https://www.postman.com/) also works. You can also send the example requests with `curl`.

## Setup

```bash
# Stop any other lab stack; the labs share the 55xx host ports
cd ../../week-08-prefect-flow/starter && make down; cd -

cp .env.example .env
make sync               # install all dependency groups
make up                 # start postgres, s3, mc, mlflow and prefect
make data-v2            # rebuild the DVC-tracked dataset from the committed raw batches
make repro              # train, log the run to MLflow and check the gate
make register           # register the model as a new version
make promote-champion   # give that version the champion alias, which Exercise 1 serves
```

Run `uv run pytest -q` before starting the exercises. With the stack still up after Setup, the
expected result is:

```
209 passed, 25 skipped
```

The 25 skipped tests belong to this lab: 16 in `tests/test_api.py` and 9 in
`tests/test_k8s_manifests.py`. Each `@pytest.mark.skip` names an exercise. Once you have completed
the code for an exercise, delete its skip markers and run the tests. With the stack down, the 8
MLflow-link tests are skipped too: 201 passed, 33 skipped.

## Exercises

Complete the exercises in order. Write your answers to Exercises 1, 3 and 4 in `answers.md` in this
directory, and commit the file with your code.

### Exercise 1 — The MLflow model server (`make serve-mlflow`) — **written**

MLflow can put a registered model behind an HTTP endpoint with one command. But a request that
reaches the model is not necessarily valid: it might contain a glucose value of zero or a missing
field. The server does not use your data contract, so you need to find out what it checks. In this
exercise, you send valid and invalid requests to the champion and record the answers.

1. Run `make serve-mlflow` and leave it running. It serves the champion on port 5540.
2. In a second terminal, send one patient. In Bruno or Postman, send the same JSON body as a
   `POST` to `http://localhost:5540/invocations`.

   ```bash
   curl -w '\n%{http_code}\n' -X POST localhost:5540/invocations -H 'Content-Type: application/json' -d '{"dataframe_split": {"columns": ["pregnancies", "glucose", "blood_pressure", "skin_thickness", "insulin", "bmi", "diabetes_pedigree", "age"], "data": [[6, 148, 72, 35, 125, 33.6, 0.627, 50]]}}'
   ```

3. Change the request and send it again, one change at a time, each time starting from the
   patient in step 2: `glucose` 0; `glucose` −50; `age` 250 with `bmi` 336; an extra column
   `cholesterol`; no `bmi` column; the same columns in another order. When you add, remove or move
   a column, change its value in `data` in the same way. Record the status code (the last line
   that curl prints) and the answer each time.
4. Stop the server with Ctrl-C.

**Check:** the first request answers `{"predictions": [1]}`, and you have a status and an answer
for each of the six changed requests.

1. Which requests did the server score, and which did it refuse? For each refusal, read the stack
   trace and find which component detected the problem.
2. Which of the scored requests should never reach the model? Name the rule from the Week 5
   contract that would stop each one.
3. Name two more things your team would need from a prediction service that this server does not
   give you.

### Exercise 2 — Your own service (`make serve-api`)

Your service can check a request before the model sees it and tell the caller what went wrong.
FastAPI uses Pydantic to check the types; the `PredictionInput` data contract checks the values,
including whether a glucose of 0 was sent as a measurement. The service also answers `/health`,
so Kubernetes and the people on call can check whether it is ready and which model it runs. In
this exercise, you write both endpoints and send the requests from Exercise 1 again.

1. In `api.py`, read `PredictionRequest`, `PredictionResponse`, `HealthResponse` and the start of
   `create_app`. The model is loaded once, when the app starts.
2. Write `GET /health` and `POST /predict` inside `create_app`, as the TODO describes.
3. Run `make serve-api` and open http://127.0.0.1:5541/docs. Send the requests from Exercise 1,
   from the docs page or with curl. This service takes one JSON object per patient:

   ```bash
   curl -w '\n%{http_code}\n' -X POST localhost:5541/predict -H 'Content-Type: application/json' -d '{"pregnancies": 6, "glucose": 0, "blood_pressure": 72, "skin_thickness": 35, "insulin": 125, "bmi": 33.6, "diabetes_pedigree": 0.627, "age": 50}'
   ```

**Check:** remove the skip markers in the "Your service (Exercise 2)" section of
`tests/test_api.py`, and the tests pass. With a glucose of 148, `/predict` answers
`"prediction": 1, "probability": 0.7293`. With a glucose of 0, it answers 422 with
`"failures": {"greater_than(0)": 1}`. With `"insulin": null`, a value that was not measured, it
scores the patient. `/health` answers `"model_source": "working tree (not baked)"`.

### Exercise 3 — Batch versus online in the lab (`make bench`) — **written**

When a team has a list of patients to score, it can send them to the model in one batch. When a
patient's details arrive during an interaction, the service can score that request online. The
choice depends on when the input is available and how quickly the caller needs an answer.

Some requests take longer than others, so teams report latency percentiles: half of the requests
were faster than p50, and one in twenty was slower than p95. In this exercise, you score the 192
test patients both ways and compare the time each takes.

1. Implement `online_score` in `bench.py`. The TODO lists the keys to return.
2. Run `make bench` twice, to see how much the numbers move between runs. Batch scores all rows
   in one `predict_proba` call. Online sends one request per row to your service from Exercise 2,
   through FastAPI's `TestClient` in the same process, so no network is involved.

**Check:** remove the skip markers in the "Batch versus online (Exercise 3)" section of
`tests/test_api.py`, and the tests pass. `make bench` prints both rows of the table and no failed
requests, and online takes tens to hundreds of times the wall clock of batch. Our runs gave 72× to
104×, with a p50 of about 4.5 ms; your numbers depend on your laptop.

1. Online took far longer for the same rows. Where does the time go? Name the steps that a request
   passes through and the batch call does not.
2. Give one workload where batch scoring is the right choice, and one where online scoring is.
   What distinguishes them?
3. Why does the table report p50 and p95, and not the mean?

### Exercise 4 — A container image with the model in it (`make image`, `make run-image`) — **written**

To run your service on another machine, you need its code, Python, packages and model together.
The container image holds all four. Because the model is copied into the image at build time, the
container can start without the registry and report which model it holds. An image is a release,
so the model must pass the quality gate before you build it. In this exercise, you build an image,
check its model and see what happens when you try to build one with a NO-GO model.

1. Read `serve.Dockerfile` from top to bottom. Find where the locked packages are installed,
   where the model is copied in, and where the model version comes from.
2. With the stack up, run `make image`. Then run `make run-image`, and in a second terminal
   `curl localhost:5542/health`. Compare the answer with `make trace`. Stop the container with
   Ctrl-C.
3. Make a NO-GO model: in `params.yaml`, set `C` under `train` to `0.01`, and run `make repro`.
   The gate stage fails. Run `make image` again.
4. Set `C` back to `1.0`, and run `make repro`.

**Check:** `/health` from the container shows the same `model_version` and `run_id` as lines 2
and 3 of `make trace`, with `"gate_verdict": "GO"` and `"model_source": "registry champion"`. In
step 3, `make image` ends with `REFUSING to build: the recorded gate verdict is 'NO-GO'.`

1. The registry is down when Kubernetes starts a new pod, for example to replace one that
   crashed. What happens with this image, and with an image that downloads the model from the
   registry when the container starts?

### Exercise 5 — A Deployment, a Service and probes (`make kind-up`, `make k8s-deploy`)

If a container stops, someone has to start it again. Kubernetes can do that for you: a Deployment
declares how many pods should run, and a Service gives those pods one stable address. The Service
finds its pods by their labels.

Kubernetes also sends probes to check a container. A pod receives traffic only after its
readiness probe passes; if its liveness probe fails, Kubernetes restarts the container. In this
exercise, you write the Deployment and Service manifests with both probes and deploy your image to
a local cluster using kind. You will also see what happens when the cluster cannot find the image.

1. Stop the stack with `make down`. The cluster needs the memory.
2. Write `k8s/deployment.yaml` and `k8s/service.yaml`, as `k8s/README.md` describes.
3. In `k8s/deployment.yaml`, add a `readinessProbe` and a `livenessProbe` to the container. Both
   call `GET /health` on the port named `http`. Set `initialDelaySeconds`, `periodSeconds` and
   `failureThreshold` on each, so that the liveness probe gives up later than the readiness probe.
4. Run `make kind-up`. The first time, it downloads the image for the cluster's node.
5. Apply the manifests before the image is on the cluster: `kubectl apply -f k8s/`. After half a
   minute, run `make k8s-status`, then `kubectl describe pod -l app=diabetes-api`. The events at
   the end of the output say what went wrong.
6. Run `make k8s-deploy`. It copies the image onto the kind node with
   `kind load docker-image`, applies the manifests and waits for the pods.
7. Run `make k8s-status`. In a second terminal, run
   `kubectl port-forward svc/diabetes-api 5543:80` and leave it running. In a third terminal, run
   `curl localhost:5543/health`. Paste the answer at the top of `answers.md`.

**Check:** remove the skip markers in the "A Deployment, a Service and probes (Exercise 5)" section
of `tests/test_k8s_manifests.py`, and the tests pass. `make k8s-status` shows two pods `Running`
with `1/1` in the `READY` column, which means their readiness probes pass, and two addresses on
the Service's `Endpoints` line. `/health` through the port-forward shows the model version from
Exercise 4.

### Finish — commit your work

```bash
make kind-down      # delete the cluster
git status          # include answers.md and k8s/*.yaml; exclude .env and .venv/
git add .
git commit -m "week09: serving, benchmark, cluster and written answers"
```

Commit your code, your manifests and `answers.md`, with the `/health` answer from Exercise 5 at
the top. If `git status` shows `params.yaml` as modified, the experiment from Exercise 4 is still
in it. Set `C` back to `1.0` before you commit.

## Make targets

| Target | What it does |
| --- | --- |
| `make serve-mlflow` | MLflow's server for the champion, port 5540 (Exercise 1) |
| `make serve-api` | your service, port 5541 (Exercise 2) |
| `make bench` | batch and online scoring of the test rows, with p50 and p95 (Exercise 3) |
| `make image` | build `diabetes-api:local`, only after a GO (Exercise 4) |
| `make run-image` | run the image alone, port 5542 (Exercise 4) |
| `make kind-up` / `make kind-down` | create or delete the kind cluster `mlops` (Exercise 5) |
| `make k8s-deploy` | copy the image onto the cluster, apply `k8s/`, wait for the pods (Exercise 5) |
| `make k8s-status` | the pods, and the pods behind the Service (Exercise 5) |

The earlier targets still work, including `make ci`, `make repro`, `make flow` and both GitHub
Actions workflows. `make serve` still starts the scheduled Prefect flow.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `make serve-mlflow` fails, and the error names the alias `champion` | no version has the champion alias yet | `make register` and `make promote-champion` (Setup) |
| `make serve-mlflow` fails with `No such artifact: 'MLmodel'` | the registered version's files are gone, for example after `make down-v` | with the stack up, `make repro`, `make register`, `make promote-champion` |
| `make serve` starts a Prefect deployment | `serve` is Week 8's target | `make serve-api` |
| `/health` answers 503 | no `models/model.pkl` | `make repro` |
| `make image` refuses to build | the recorded gate verdict is not GO | `make repro`, and check `reports/gate.json` |
| `docker build` fails with `OSError: Readme file does not exist` | a file that `pyproject.toml` names is not copied into the image | `COPY` it in `serve.Dockerfile` |
| Pods show `ErrImagePull` or `ImagePullBackOff` | the image is not on the kind node | `make k8s-deploy`, which runs `kind load docker-image` |
| `port-forward` connects, then requests hang | the Service's selector does not match the pod labels | `make k8s-status`: the `Endpoints` line is empty. Fix the labels |
| Pods restart again and again | the liveness probe fails before the app has started | give liveness a longer `initialDelaySeconds` than readiness |
| Port already in use | another week's stack is running | `make down` in that lab first |

## Submission

Submit the commit from Finish. It contains your code, `k8s/deployment.yaml`, `k8s/service.yaml`
and `answers.md`, with the pod's `/health` answer at the top. Do not include `.env` or `.venv/`.
Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`), and upload
that URL to Moodle.

## Deviations from the tutorials

1. **MLflow's server comes before FastAPI.** You check what the server accepts before you write
   your own service.
2. **The image contains the model.** `make image` copies `models/model.pkl` into the image, so
   the cluster runs with the Compose stack down. Week 10 loads the model at startup instead.
3. **The manifests are written by hand** and contain only a Deployment, a Service and two probes:
   no Ingress, autoscaling or Helm. That is enough for one model on one laptop.
4. **The tests need no server and no cluster.** FastAPI's `TestClient` runs the app in the test
   process, and the manifests are checked as YAML.
