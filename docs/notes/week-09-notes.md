# Week 9 — Model Serving & Deployment — Study Notes

These notes accompany the lecture and lab on model serving. The training pipeline produces a model file, but callers need a way to use it. A serving program loads the model and makes its predictions available. In the lab, you package that program and its model in a container, then run it on a cluster. The serving environment must include the code, packages and other information the model needs.

## Why this matters

**Deployment and model serving.** Deployment puts a version of software where its users can reach it. A build produces an artifact, and deployment puts it on servers. Training also produces an artifact: a model file. The file needs a program that loads it and uses it to make predictions. **Model serving** is running a model so that people or other programs can get those predictions. The input may be a request, a file of rows or an event; the output may be a response, a table or an action. A service can load the model once at startup and use it for many requests.

**What must travel with the model.** A reproducible training run records the code, data and package versions used to produce a model. When the model leaves the training machine, the serving environment needs:

- the model file;
- the Python version;
- the libraries, at the versions that trained it;
- the code that loads the model and answers;
- the contract for what a request may contain;
- the metadata: model version, run, gate verdict.

The lab's container image carries these together. MLflow also records the environment alongside a logged model in `python_env.yaml` and `requirements.txt`.

### More cases from the lecture

The lecture may also include these cases:

- **Knight Capital (2012).** Knight Capital was a US trading firm whose router, SMARS, sent customers' stock orders to the market from eight servers. In July 2012, a technician copied new code to the servers by hand but missed one. The deployment was not checked. On 1 August, the old code on that server sent a stream of orders: 397 million shares were traded in about 45 minutes, and Knight lost about $460 million. The SEC wrote that "a simple double-check of the deployment" could have found the missed server. Knight paid a $12 million penalty and had to hire an independent consultant to review its software development and deployment controls (US SEC, Release No. 34-70694, 16 Oct 2013, paragraphs 15–17, 41 and 51). A team can reduce this risk by deploying with a script and checking which version each server runs. In the lab, `/health` reports the model version. Week 10 opens with the same case.
- **A slower Google search (2009).** Google's web search team delayed the results page by 100 to 400 ms for some users. With 400 ms, searches per user fell by 0.44% in the first three weeks and by 0.76% in the next three. In the five weeks after the delay was removed, those users still searched 0.21% less (Jake Brutlag, "Speed Matters", Google Research blog, 23 June 2009).
- **Pokémon GO's launch (2016).** Pokémon GO is a mobile game by Niantic, launched in July 2016 on Google's Kubernetes service (GKE). The teams planned for 1× traffic, with a worst case of about 5×. Traffic reached 50×. Before the launch in Japan, the team upgraded GKE so that the cluster could add more than a thousand nodes. The Japan launch, with three times the US sign-ups, went without incident (Luke Stone, Google Cloud blog, 30 Sept 2016).

## Core concepts

### Batch and online inference

Batch and online inference serve different needs. To choose between them, consider when the input is available and how fresh the answer needs to be.

**Batch** inference scores a set of rows, often on a schedule, and stores the predictions in a table or a key-value store. An app can then read those predictions when it needs them. Examples include:

- Spotify's Discover Weekly: a playlist of new songs for each user, every Monday.
- Netflix's recommendations: computed offline and stored for the app (Amatriain and Basilico, Netflix Technology Blog, March 2013).
- A bank's monthly list of customers likely to leave.
- The diabetes risk of every patient on a ward, every night.

Batch works well when the inputs are known in advance and a prediction that is a few hours old is good enough.

**Online** inference scores an input when a request arrives, while the caller waits for an answer. Examples include:

- The fraud risk of a card payment, before the payment is approved. Stripe says its fraud model answers in less than 100 ms (Stripe newsroom, 30 April 2025).
- When an Uber Eats meal will arrive, computed when the customer orders (Hermann and Del Balso, Uber Engineering blog, September 2017).
- The order of search results for a query, at Booking.com or a web search engine.
- The chance that a user clicks an ad, in each ad auction. Google waits 80 to 1,000 ms for a bid, depending on the auction, and drops a later bid (Google Authorized Buyers, real-time bidding guide, updated 17 September 2026).
- The diabetes risk of a new patient, while a nurse admits the patient.

Online inference works well when the input is available only at request time or the answer must reflect recent information.

| | Batch | Online |
| --- | --- | --- |
| Optimises | throughput: rows per second | latency: time for one answer |
| The answer is computed | before anyone asks | when someone asks |
| The input | known in advance, may be hours old | arrives with the request |
| Must keep running | a scheduled job, for minutes | a service, all the time |
| A failure looks like | a late or missing table | a slow or failed request |

A delivery estimate or a results page may have more time to respond than a payment decision, but every online request has a time budget.

If a prediction computed in advance is fresh enough, batch can be simpler. There is no prediction service to keep running, and a bad table can be rebuilt before anyone reads it.

Other serving patterns combine these approaches or move the model closer to its users:

- **Streaming inference:** online inference can use *streaming features* computed from recent events. For example, Uber Eats estimates delivery time using a restaurant's mean preparation time. The mean over seven days is a batch feature. The mean over the last hour is a streaming feature, computed by a stream job on Kafka (Hermann and Del Balso, Uber Engineering blog, September 2017). Other examples include the number of card payments in the last 10 minutes and the videos a user watched in the current session. These features help an answer reflect recent activity, but the stream job must keep running. Training and serving must also compute the feature in the same way. If the stream stops, old values may remain without an error.
- **On the device:** the model runs on a phone or in a car. Examples include Face ID on an iPhone, next-word suggestions on a phone keyboard and lane detection in driver assistance. Predictions need no network connection, add no network latency and keep the data on the device. The model must fit within the device's memory and battery limits, though. A new version reaches users only when they update the app, and its inputs are difficult to observe.
- **Batch and online together:** the expensive work runs in advance, followed by a final step for each request. Netflix describes offline, nearline (after an event) and online computation in one system. An online shop, for example, can choose candidate products for each user every night and rank them using the current basket. Both paths must compute shared features in the same way, and either path can fail.
- **Cache:** a service stores the answer for an input that repeats, then looks it up for the next matching request. Examples include results for a popular search query, "similar products" on a product page and Booking.com's precomputation and caching (below). A cache helps only when inputs repeat. Stored answers can also become outdated, so a new model version must clear the cache.
- **Champion and challenger side by side** (shadow mode): the service sends each request to both models. The champion's answer goes back to the user, while the challenger's answer is logged for a later comparison on the same inputs (Huyen, Ch. 9). For example, a new fraud model can score real payments before it is allowed to block one. Running both models takes twice the compute, and the answers must be stored and compared. The challenger must not take actions such as sending emails or writing data. Week 10 uses the same idea to release a new model.

### What latency costs

Booking.com is an online travel agent. In 2019 it ran about **150** customer-facing models, each tested on real users in an A/B test. In one experiment, about **30%** more latency cost **more than 0.5%** of the conversion rate, the share of visitors who book. To keep predictions fast, Booking lists six practices: precomputation and caching, model redundancy, a fast in-house linear prediction engine, sparse models, bulking requests and few feature transformations. Precomputation uses batch scoring where possible; model redundancy means running copies of each model across a cluster. The lab uses Kubernetes to run copies of its service (Bernardi, Mavridis and Estevez, "150 Successful Machine Learning Models: 6 Lessons Learned at Booking.com", KDD 2019, Section 5, https://doi.org/10.1145/3292500.3330744).

### Batch versus online in the lab

The lab scores the same 192 test patients with the same model on one laptop. As in training, sentinel zeros are converted to missing values: batch receives them as NaN, and online requests send them as `null`. In one run, batch scored all rows in **0.0095 s (20,236 rows per second)**. Online scoring, with one request per patient, took **0.8875 s (216 rows per second)**, or **93×** as long. Three runs on 2 Nov 2026 gave ratios of 104×, 72× and 93×. The numbers depend on the machine. Exercise 3 asks you to explain where the time goes.

A benchmark must check that every request succeeded. Before 2 Nov 2026, the lab sent sentinel zeros without converting them. The service returned 422 for 88 of the 192 requests, so those requests never reached the model and the online time measured something different. `make bench` now counts and reports failed requests.

### Latency metrics

Most requests may be fast while a few take much longer. These slow requests form the right tail of the latency distribution. The **mean** is the average, which can be pulled up by a few slow requests. Percentiles show more of the distribution: **p50**, the median, is the time within which half the requests finish; **p95** is the time within which 95% finish. The **max** is the time of the slowest request. Companies report percentiles: Uber gives p95 under 10 ms for its online predictions (Hermann and Del Balso, 2017).

On 2 Nov 2026 we timed each of the 192 requests through the lab's service, after 20 warm-up requests: **p50 4.39 ms, mean 4.40 ms, p95 4.80 ms, max 5.22 ms**. In this measurement, requests ran one at a time in one process, and the tail was short. A network adds to the time: Week 11 measures p50 8.79 ms and p95 22.97 ms from the host to the container. When reporting latency, name the percentile you quote. You cannot average the percentiles of two services to get the percentile of both.

### The MLflow model server

`mlflow models serve` gives a registered model a REST endpoint with one command and no serving code. Its `POST /invocations` endpoint accepts four payload shapes: `dataframe_split`, `dataframe_records`, `instances` and `inputs`. The `--env-manager local` option uses the current Python environment instead of building the model's environment from `python_env.yaml`.

MLflow's server does not know about the lab's data contract. When tested against the lab's champion in August 2026, a request with `glucose: 0` received `{"predictions": [0]}`. The server scored the patient even though the contract rejects a glucose of 0. In Exercise 1, you find out what the server checks and what it lets through.

### FastAPI, Pydantic and Uvicorn

The service you build uses three packages, each with its own job:

- **Uvicorn** is an ASGI web server. It listens on a port, handles HTTP and passes requests to the app. You can start it with `uvicorn app:app --port 8000`.
- **FastAPI** is a web framework for APIs, based on Python type hints. It sends each request to the function for its route, such as `@app.post("/predict")`, and returns 422 when a check fails.
- **Pydantic** is a data validation library. You write a class describing the request, and Pydantic checks each request body against it before the endpoint function runs.

We install FastAPI and Uvicorn; FastAPI brings Pydantic with it. The lecture's example serves an iris model:

```python
class Flower(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float = Field(gt=0)
    petal_width: float = Field(gt=0)

app = FastAPI()
model = joblib.load("iris.pkl")          # once, at startup
```

The model loads once at startup. Loading it inside the request function would add the load time to every request. The `Flower` class is a data contract: Pydantic checks that the fields are present and that their types and values follow the rules in the class. In the iris example, it rejects a missing field (422 `missing`), the string `"five"` for a float (422 `float_parsing`) and a `petal_length` of 0 (422 `greater_than`). A `sepal_length` of 51, sent in millimetres instead of 5.1 cm, passes the checks and gets a different species.

FastAPI was already installed as a dependency of `mlflow-skinny` and `prefect`. This lab declares `fastapi`, `uvicorn[standard]` and `httpx` directly. The lock file grows from 229 to 232 packages because of Uvicorn's extras: `httptools`, `uvloop` and `watchfiles`. No installed version moved. Before adding a dependency, you can check what your lock file already installs with `uv tree --invert`.

### Data checks

The lab's service checks each request twice before the model sees it. **Pydantic** checks that the fields are present and have suitable types. Inside the endpoint, the **`PredictionInput`** contract checks their values: a glucose of 0 represents a missing value, not a reading. `PredictionInput` uses the rules from `ModelInput` without requiring the label. It is `strict` but not `ordered`, because a JSON object has no column order.

A request with `glucose: 0` gets a 422 response naming the failed check, `greater_than(0)`, and the contract version. The caller can use that information to fix the request.

Pandera checks a whole table at once, which suits the training data. FastAPI uses Pydantic classes to parse each JSON request and return a 422 when validation fails. Writing a value rule such as glucose > 0 in both places would leave two copies to maintain. Instead, the lab keeps value rules in Pandera's `PredictionInput`, while Pydantic's `PredictionRequest` lists the fields and their types. A test checks that the two agree.

A type can also impose a rule: `float` rejects `null`. The five fields that may be missing in the contract use `float | None` in the request. A caller can send `null` for a value that was not measured, and the model's imputer fills it in. The test also checks that both sides allow `null` in the same fields.

### Beyond the simple service

A request travels client → Uvicorn → FastAPI → Pydantic → Pandera → model. The response carries the prediction, probability, model version and contract version back to the caller. If a check fails, the service returns 422 and the model never runs.

The lab's client sends all eight features, but some services receive less. A request may carry only an ID; the service then looks up stored features in a database or a **feature store** that both training and serving read. Uber stores such features in Cassandra. Its online predictions take p95 under 5 ms without the lookup and under 10 ms with it (Hermann and Del Balso, Uber Engineering blog, September 2017). A service may also compute a feature from the request and stored values, such as the change in glucose since the last visit. If serving computes a feature differently from training, the model can give wrong answers without an error. This is called training-serving skew.

The model returns a probability, but a decision also needs a **threshold**. Three thresholds gave the following results on the 192 test patients:

| Threshold | Finds, of 67 with diabetes | Flags, of 125 without |
| --- | --- | --- |
| 0.3 | 54 | 34 |
| 0.5, scikit-learn's `predict` | 39 | 17 |
| 0.7 | 26 | 7 |

The threshold is chosen during evaluation, so it must travel with the model version. A response can include the probability, threshold and decision so the caller can see what was decided and why.

To run the service on another server, the team needs Python, the locked packages, the serving code, the model and its threshold, metadata and a start command.

### Containers and images

An **image** packages the files a program needs, such as OS libraries, Python, packages, code and the model. A **container** is a running program started from an image and separated from other programs on the host. Containers share the host's Linux kernel, so they start in seconds; a virtual machine boots a whole operating system and takes minutes. **Docker** builds images and runs containers. The same image can run on a laptop, in CI and in a cluster.

`docker build` reads a Dockerfile, the recipe for an image, and builds it. `docker run` starts a container from that image. In the lab, `make image` and `make run-image` wrap these commands. The lab's `serve.Dockerfile` builds the image in layers, bottom first:

1. Select a base image: `FROM python:3.12-slim` (Debian and Python 3.12).
2. Copy the environment files: `COPY pyproject.toml uv.lock`.
3. Copy the code and install the environment: `COPY src`, `RUN uv sync --locked --no-dev`.
4. Label it with the model version, run ID and gate verdict: `ARG`, `LABEL`.
5. Add the model: `COPY models/model.pkl`, and a `RUN` step that writes `baked.json` from the build arguments.
6. Set the start command: `CMD uv run uvicorn …`.

The image is **1.04 GB**.

Docker rebuilds a layer when it or a layer below it changes, so the Dockerfile puts frequently changed items last. A new model version changes the build arguments and `model.pkl`, both after `uv sync`. The packages therefore stay cached; a rebuild took under a second on 30 Oct 2026. As in CI, `--locked` refuses a stale lock file, so the image uses the package versions in the lock file.

### Bake or fetch

**Baking** copies the model into the image when the image is built. **Fetching** downloads it from a registry each time a container starts.

| | **Bake at build** | **Fetch at startup** |
| --- | --- | --- |
| Two containers from one image | always serve the same model | may serve different models |
| Registry needed while running | no | yes |
| A new model needs | a new image | a restart |
| One image for many models | no | yes |

The lab bakes the model into the image. This lets the container start without the registry, which is useful on a 16 GB laptop that cannot run the five-service Compose stack and a Kubernetes cluster together. `make image` uses the stack to read the champion's version. Week 10 fetches the model instead, because KServe records which model each revision serves. There, one 1.04 GB image served three model versions without a rebuild.

The image also records which model it holds. `GET /health` returns the baked model version, run ID and gate verdict, while `make trace` shows the version and run ID from the registry. The health endpoint reads the information recorded at build time; it does not ask the registry. An image built with the stack down says `"model_version": "unknown"`.

### Check the gate in every path that ships

A model moves through train → gate → register → promote → image → deploy. Registering, promoting and building an image can each bring it closer to users, so these paths need a gate check. The lab's `register` and `promote` commands check the verdict. `make image` also reads `reports/gate.json` and refuses to build when the verdict is not GO:

```text
$ make image
REFUSING to build: the recorded gate verdict is 'NO-GO'.
```

A team may have other paths to deployment, such as a CI job, a Helm chart or a command run on a laptop. Each path needs a gate check. For example, a direct `docker build` bypasses the check in `make image`. Check the verdict on every path you can, and make the checked path easy to use. Week 10 adds another path: the model store that KServe reads.

### What is Kubernetes

A single container can crash or receive more requests than it can answer. Running several copies helps, but those copies also need to be started, replaced and kept running. An orchestrator manages that work. Prefect orchestrates pipeline runs that finish; Kubernetes orchestrates services that need to keep running.

**Kubernetes** runs containers on a group of machines called a **cluster** and works to keep them in the state you declare (Kubernetes docs, "Overview"). You describe the desired state in YAML, for example "two copies of this image", and send it with `kubectl apply`. The **control plane** stores that state, and its controllers compare it with what is running. The machines that run the containers are called **nodes**. Kubernetes can restart failed containers, spread copies across machines, send requests to healthy copies and replace a version step by step.

A simple architecture has these parts:

- A **Pod** runs one or more containers that share a network address; ours runs one.
- A **Deployment** declares how many pods should run (`replicas: 2`) and replaces them one at a time.
- A **Service** is a stable name and address in front of the pods. It finds them **by label** (`app: diabetes-api`), because pods come and go and change address.
- A **probe** is a request Kubernetes sends to each pod, here `GET /health`. A pod that does not answer gets no traffic. A probe is not an object of its own: it is a few lines in the container's part of the Deployment.

Kubernetes uses a **control loop**. The Deployment describes the desired state, and a controller compares it with what is running and acts on any difference. For example, if you delete one of two pods by hand, a new pod starts within seconds. `kubectl apply` sends the desired state; the controller works out what to do.

In production, Kubernetes often runs on many machines managed by a cloud provider (GKE, EKS or AKS) or a platform team. A **local cluster** runs Kubernetes on one laptop, with the same API and YAML files, for learning and testing. The lab uses **kind**, whose nodes are Docker containers. minikube and k3d are alternatives, but the course uses kind so that Week 10 can install KServe on the same cluster. The course does not use a cloud cluster. In our run, `kind create cluster` took about 60 seconds.

### A Deployment and a Service on kind

The lab describes these two objects in `k8s/deployment.yaml` and `k8s/service.yaml`. The command `kubectl apply -f k8s/` sends both to the cluster.

A kind node is a container with its own image store. An image built in your local Docker is not automatically on that node. Kubernetes tries to download the image from a registry, and the pods show `ErrImagePull` and `ImagePullBackOff`. The command `kind load docker-image diabetes-api:local --name mlops` copies the image onto the node.

The image pull policy also matters. If the manifest does not set `imagePullPolicy`, Kubernetes defaults to `IfNotPresent` for a tag such as `:local` and `Always` for `:latest` or no tag (Kubernetes docs, "Images", Default image pull policy). With `Always`, the pod tries to pull the image even when it is on the node. The lab's manifest sets `imagePullPolicy: IfNotPresent`, so it works with any tag.

The label `app: diabetes-api` appears three times: in the Deployment's selector, in the pod template's labels and in the Service's selector. All three must match.

### Probes

| **Probe** | **Asks** | **When it fails** |
| --- | --- | --- |
| Readiness | may this pod get traffic? | the pod leaves the Service's endpoints and keeps running |
| Liveness | is this container broken? | the kubelet restarts the container |

Both probes call an app endpoint, `GET /health` in this lab. The endpoint answers 503 until the model is loaded, so a pod gets traffic only when it can answer. The liveness probe must allow more time than the readiness probe; otherwise, a slow start can lead to a restart loop. The Kubernetes docs warn that a badly configured liveness probe can restart containers under load and cause cascading failures.

## Red flags and good practices

### Serve from the training lock file

The lab's `pyproject.toml` allows `scikit-learn>=1.8.0`, while the lock file records version 1.9.0. Installing from a `requirements.txt` without pinned versions could give the server different packages from training. Install the serving environment from the same lock file as training (`uv sync --locked --no-dev`) and let the build fail if the lock is stale.

### Check the endpoints, not only the Service

If the Service's selector does not match the pod labels, the commands can still succeed. `kubectl get svc` shows the Service, but `kubectl port-forward` connects and then hangs. The `Endpoints` line of `kubectl describe service diabetes-api` shows that no pods are behind the Service. One wrong character in a label, such as `diabetes-apl`, is enough. The lab's `tests/test_k8s_manifests.py` checks the selector against the pod labels without a cluster, so CI can catch the typo before deployment.

### Keep the health check honest

Suppose `/health` returns 200 whenever the process is up. Kubernetes may mark the pod ready before the model is loaded, and users can receive 500 responses. A health check can also depend on too much: if it calls a database, a slow database can make every pod fail readiness at once, leaving the Service with no ready pods. Check the smallest thing that proves the pod can answer. In the lab, that means checking whether the model is loaded.

## Commands

| **Command** | **What it does** |
| --- | --- |
| `mlflow models serve -m "models:/diabetes-classifier@champion" --env-manager local -p 5540` | serves the champion with no code (`make serve-mlflow`) |
| `uv add fastapi "uvicorn[standard]"` | installs FastAPI and its server |
| `uvicorn app:app --port 8000` | runs a FastAPI app |
| `curl -X POST localhost:8000/predict -H "Content-Type: application/json" -d '{…}'` | sends one request |
| `make serve-api` | runs the lab's service on port 5541 |
| `make bench` | scores the test rows in batch and online, and prints p50 and p95 |
| `uv tree --package fastapi --invert --depth 1` | shows which packages pulled FastAPI in |
| `make image` | checks the gate verdict, then builds `diabetes-api:local` with the model baked in |
| `make run-image` | runs the image alone, on port 5542 |
| `make trace` | prints the chain from the alias to the gate verdict |
| `kind create cluster --name mlops` | starts a local cluster (`make kind-up`) |
| `kind load docker-image diabetes-api:local --name mlops` | copies the image onto the kind node |
| `kubectl apply -f k8s/` | sends the Deployment and the Service to the cluster |
| `kubectl get pods -l app=diabetes-api` | shows the pods |
| `kubectl describe service diabetes-api` | shows the Service, its selector and the pods behind it, on the `Endpoints` line (`make k8s-status` prints both) |
| `kubectl rollout status deployment/diabetes-api` | waits until the Deployment's pods are ready |

## Key terms

- **Deployment**: installing a version of the software where its users can reach it.
- **Model serving**: running a model so that people or other programs get its predictions.
- **Batch / online inference**: scoring on a schedule / scoring on request.
- **Streaming inference**: online inference that also uses streaming features.
- **Streaming feature**: a feature computed from the latest events, minutes old, such as a restaurant's preparation time over the last hour.
- **On-device (edge) inference**: the model runs on the user's phone, car or browser.
- **Throughput / latency**: rows per second / time for one request.
- **p50 / p95**: the latency that half of the requests / 19 of 20 requests stay under.
- **Model signature**: MLflow's record of a model's column names and types.
- **Feature store**: a database of features that training and serving both read.
- **Training-serving skew**: a feature computed differently in serving than in training.
- **Decision threshold**: the probability above which the service returns a positive decision.
- **Web server / web framework**: the program that listens on a port and handles HTTP (Uvicorn) / the library that sends each request to your function (FastAPI).
- **Pydantic model**: a Python class whose types and limits Pydantic checks on every request.
- **Bake / fetch**: the model is copied into the image at build time / downloaded when the container starts.
- **Container image**: the files one program needs (code, Python, packages, here the model), built from a Dockerfile.
- **Container**: a running copy of an image; it shares the host's kernel.
- **Dockerfile**: the recipe `docker build` reads to write an image, one instruction per layer.
- **Layer**: the result of one Dockerfile instruction. Docker rebuilds a changed layer and every layer above it.
- **Image label**: metadata attached to an image; here, the model's version, run ID and gate verdict.
- **Pod / Deployment / Service**: the running containers / the declared number of pods / the stable address in front of them.
- **Controller / control loop**: a program that compares the declared state with the running state and acts on the difference.
- **Selector**: how a Service finds pods: by **label**, not by name.
- **Endpoints**: the pods behind a Service. An empty list means the selector matches no pod.
- **Readiness probe**: may this pod get traffic? Failure takes it out of the Service's endpoints.
- **Liveness probe**: is this container broken? Failure restarts it.
- **`imagePullPolicy`**: whether Kubernetes pulls an image that the node may already have.
- **kind**: Kubernetes in Docker; a local cluster whose nodes are containers.
- **`kubectl port-forward`**: a debugging tool that forwards a local port to one pod.
- **Kubelet**: the Kubernetes agent on each node that starts and restarts containers.

## How this connects to the lab

The lab adds a serving path to the training pipeline. You:

1. run `mlflow models serve` and record what the server checks, including what happens with `glucose: 0`;
2. write your own service: `POST /predict` with the data contract, and `GET /health`;
3. measure batch against online on the same rows, and explain where the time goes;
4. build the image with the model baked in, check that `/health` in the container matches `make trace`, and say what a registry outage would do to this image and to one that fetches the model;
5. write a Deployment with readiness and liveness probes and a Service, start a kind cluster, see the pods fail to find the image, and deploy.

Exercises 1, 3 and 4 have written answers. Stop any previous lab stack before starting. Exercise 1 and `make image` need the Compose stack; on a 16 GB laptop, stop it before starting the kind cluster.

`tests/test_api.py` tests the API without a server, Docker or a cluster. Its fixture trains a model into `tmp_path` instead of reading the git-ignored `models/model.pkl`. `tests/test_k8s_manifests.py` checks the manifests as data, including the image pull policy and selector.

## Recommended reading

- **FastAPI tutorial** (https://fastapi.tiangolo.com/tutorial/). *Focus on:* request bodies, and testing with `TestClient` (https://fastapi.tiangolo.com/tutorial/testing/).
- **MLflow, deploying a model locally** (https://mlflow.org/docs/latest/deployment/deploy-model-locally/). *Focus on:* what the free server checks.
- **kind quick start** (https://kind.sigs.k8s.io/docs/user/quick-start/). *Focus on:* `kind load docker-image`.
- **Kubernetes: Deployment, Service, probes and images.** https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ · https://kubernetes.io/docs/concepts/services-networking/service/ · https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/ · https://kubernetes.io/docs/concepts/containers/images/
- **Docker, "Building best practices"** (https://docs.docker.com/build/building/best-practices/). *Focus on:* the order of layers and the build context.
- **Bernardi, Mavridis and Estevez, "150 Successful Machine Learning Models"**, KDD 2019 (https://doi.org/10.1145/3292500.3330744). *Focus on:* Section 5, "Deployment: Time is money".
- Huyen, *Designing Machine Learning Systems*, Ch. 7. *Focus on:* batch and online prediction, and ML on the edge.
- **Amatriain and Basilico, "System Architectures for Personalization and Recommendation"**, Netflix Technology Blog, March 2013 (https://netflixtechblog.com/system-architectures-for-personalization-and-recommendation-e081aa94b5d8). *Focus on:* offline, nearline and online computation.

## Check yourself

1. Your service reports a **mean** latency of 6 ms, and your users say it is slow. Explain how both can be true, and say which two numbers you would ask for instead.
2. `mlflow models serve` accepts a request that your own service rejects with a 422. Give an example from the lab, say what each system checks, and explain why neither is buggy.
3. You deploy a locally built image `diabetes-api:local` to a kind cluster, and the pods sit in `ErrImagePull`. Why is `kind load docker-image` needed? When does `imagePullPolicy` also matter?
4. A colleague changes `/health` to return 200 whenever the process is up, without checking that the model is loaded. What does the cluster now believe, what does a user see, and why is this no better than having no readiness probe at all?
5. A teammate wants the container to download the newest champion when it starts, "so we never rebuild the image". What do you gain, and what do you lose?
6. A shop wants a fraud score for every card payment, and a weekly list of customers likely to leave. Which way of serving fits each, and why?
7. A new deploy script copies `model.pkl` straight to a server. Which check from Week 6 does it skip, and where would you add it?
