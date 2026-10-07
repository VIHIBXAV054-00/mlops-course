---
description:
  title: "Week 2 Lab: Local Services Stack"
  summary: |
    Stand up a four-service Docker Compose stack (Postgres + Silo + MLflow)
    and wire the Week 1 diabetes pipeline into it to produce one reproducible,
    centrally-recorded training run.
---

# Week 2 Lab: Local Services Stack

In Week 1 your run lived in the terminal history, and your model on one disk. This week you
start the services that record every run in one place:

- **Postgres** stores run metadata (params, metrics, tags).
- **Silo** stores artifacts (the model file).
- **MLflow** is the tracking server your pipeline talks to.
- **Docker Compose** starts all of them with one command.

After this lab, running the pipeline twice gives two recorded runs with the same seed and
the same metrics. Anyone with the tracking URI can find them.

## Based on

- **MLflow remote tracking server:** https://mlflow.org/docs/latest/ml/tracking/tutorials/remote-server/
- **MLflow tracking server architecture:** https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/
- **Silo container:** https://silo.pigsty.io/operations/deployments/baremetal-deploy-minio-as-a-container/
- **Docker Compose:** https://docs.docker.com/compose/

**Deviations from the tutorial:**

1. **The tracking server runs in a container**, as a fourth Compose service. The MLflow
   tutorial (Step 3) runs `mlflow server` on the host. In a container, the whole stack
   starts with one command, `docker compose up -d --wait`.
2. **Silo instead of MinIO.** MinIO stopped publishing free images and removed them from
   Docker Hub in September 2026. Silo is a community fork of MinIO. It keeps MinIO's
   environment variables, `mc` client and web console, so the tutorial's MinIO steps still
   apply.

## Prerequisites

- Docker Desktop (macOS, Windows) or Docker Engine with the Compose plugin (Linux), version 24+
- At least 16 GB RAM
- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Ports **5500, 5510, 5511, 5532** free on your computer

---

## Step 1: dependencies

In this folder (`labs/week-02-local-services/starter/`), run:

```bash
uv sync --all-groups
```

It installs the versions pinned in `uv.lock`.

## Step 2: configuration

```bash
cp .env.example .env
```

The defaults work. Never commit `.env`; it is git-ignored.

## Step 3: tests before you start

```bash
uv run pytest tests/
```

Expected: **10 passed, 1 skipped**.

---

## Exercises

Do them in order. Exercises 4 and 5 ask for a **written answer**: write it in `answers.md`
in this folder and **commit it with your code**.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–3) | — | 10 min |
| The object store | 1 | 15 min |
| The tracking server | 2 | 15 min |
| A tracked run | 3 | 15 min |
| Where each piece is stored | 4 | 10 min |
| Reproducibility | 5 | 10 min |
| Finish: commit and submit | — | 5 min |

### Exercise 1: stand up the object store (≈ 15 min)

The object store keeps the files a run produces, such as the model. You define the Silo
service in Compose, and a one-shot job that creates the bucket MLflow writes to. On a new
team, bringing up the team's local stack from its `compose.yaml` is often the first task.

**Do:**

1. In `compose.yaml`, fill in the empty keys of the `s3` service: the image
   `pgsty/silo:RELEASE.2026-09-16T00-00-00Z`, the environment variables, the command and
   the healthcheck test. The `TODO(student)` comment above it has a hint for each.
2. In the same file, fill in the `s3-create-bucket` job: the image
   `pgsty/mc:RELEASE.2026-09-16T00-00-00Z`, and the entrypoint that creates the bucket.
3. Start only the storage services:
   ```bash
   docker compose up -d s3 s3-create-bucket
   ```

**Check:**

- Run `docker compose ps -a`.
  Expected output: `s3` is `healthy`, and `s3-create-bucket` has `Exited (0)`.
- Open http://localhost:5511 and log in with `S3_ACCESS_KEY` and `S3_SECRET_KEY` from your
  `.env`. Expected: the bucket `mlflow-artifacts` exists.

**Stuck?**

- Lecture: "Object store" and "Object store in our stack: Silo"
- Notes: "The three storage planes of a tracked run" and "Docker Compose as one-command,
  reproducible local infrastructure"
- Silo docs: the container guide (link above) and the `mc` commands:
  https://silo.pigsty.io/reference/minio-mc/
- If the bucket is missing, read the job's log: `docker compose logs s3-create-bucket`.

### Exercise 2: wire the tracking server (≈ 15 min)

MLflow's tracking server sits between your pipeline and the two stores. It writes metadata
to Postgres and model files to Silo, so your code needs only one address. You tell the
server how to reach both stores. Inside the Compose network, a service's name is its
hostname: the server reaches Postgres at `postgres`, not at `localhost`.

**Do:**

1. In `compose.yaml`, fill in the empty values of the `mlflow` service. The `TODO(student)`
   comment above it has a hint for each:
   - `MLFLOW_S3_ENDPOINT_URL`: Silo's address inside the Compose network
   - `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: the Silo keys
   - `--backend-store-uri`: the Postgres address, with the service name `postgres` as the
     host
   - `--artifacts-destination`: the bucket from Exercise 1, as an `s3://` URI
   - `--allowed-hosts`: the names the server is reached by. The check compares the port
     too, so a list without ports gives an "Invalid Host header" error at `localhost:5500`.
2. Start the full stack:
   ```bash
   docker compose up -d --wait
   ```
   `--wait` returns when every healthcheck passes. The first start pulls the images, so it
   takes longer.

**Check:**

- Run `docker compose ps`.
  Expected output: `postgres`, `s3` and `mlflow` are `healthy`.
- Open http://localhost:5500. Expected: the MLflow UI, with no runs yet.

**Stuck?**

- Lecture: "MLflow tracking server architecture" and "Docker Compose: the compose network"
- Notes: "The tracking server sits in front"
- MLflow docs: the remote tracking server tutorial (link above), and allowed hosts:
  https://mlflow.org/docs/latest/self-hosting/security/network/
- If `docker compose up --wait` never returns, read `docker compose logs mlflow` and check
  the `--backend-store-uri`.

### Exercise 3: log a tracked run (≈ 15 min)

The stack runs, but the pipeline does not use it yet. You add MLflow calls to the pipeline,
so every run is recorded with its parameters, its metrics and the model file.

**Do:**

1. In `src/week_02_local_services/cli.py`, connect to the tracking server and select the
   experiment from `settings`. The first `TODO(student)` comment has the details.
2. In the same function, put the training and evaluation inside an MLflow run. In the run,
   log the params `random_seed`, `test_size` and `max_iter`, each metric, and the fitted
   pipeline as a model named `model`. The second `TODO(student)` comment has the details.
3. Run the pipeline:
   ```bash
   uv run python src/main.py
   ```

**Check:**

- Open http://localhost:5500 and the `diabetes-week2` experiment.
  Expected: one run with the params `random_seed=42`, `test_size=0.25` and
  `max_iter=1000`, the metrics `accuracy`, `precision`, `recall` and `f1`, and an artifact
  named `model`.
- Delete the Exercise 3 skip marker in `tests/test_smoke.py`.
- Run `uv run pytest tests/`.
  Expected output: `11 passed`

**Stuck?**

- Lecture: "Logging a run: what happens step by step"
- Notes: "The tracking server sits in front"
- MLflow docs: the tracking quickstart, https://mlflow.org/docs/latest/ml/tracking/quickstart/
- If the run does not appear, check `MLFLOW_TRACKING_URI` in `.env`: it must be
  `http://127.0.0.1:5500`.

### Exercise 4: find where each piece is stored (≈ 10 min) *(written answer)*

A tracked run is split over two stores: the model file in Silo, and the params and metrics
in Postgres. You find each piece yourself, so you know where to look when one is missing.

**Do:**

1. Open http://localhost:5511, open the `mlflow-artifacts` bucket, and find the model
   files of your run.
2. List the tables in Postgres:
   ```bash
   docker compose exec postgres psql -U mlflow -d mlflowdb -c "\dt"
   ```
   Expected output: tables such as `runs`, `params`, `metrics`, `tags` and `experiments`.
3. Query the runs:
   ```bash
   docker compose exec postgres psql -U mlflow -d mlflowdb \
     -c "SELECT run_uuid, status, start_time FROM runs LIMIT 5;"
   ```
   Expected output: your run, with the status `FINISHED`.

**Check:**

- You found the folder with `MLmodel` and `model.pkl` in Silo, and your run in the `runs`
  table.

**Stuck?**

- Lecture: "Metadata vs. artifacts"
- Notes: "The three storage planes of a tracked run"
- MLflow docs: the tracking server architecture (link above)
- MLflow 3 stores a logged model in the experiment's `models/` folder, not in the run's
  folder.

**Written answer** (in `answers.md`):

1. Which store holds which data? Why are model files not stored in Postgres?

### Exercise 5: check reproducibility (≈ 10 min) *(written answer)*

In Week 1 the same seed gave the same metrics, but the results lived only in your terminal.
Now every run is recorded, so you can compare runs side by side.

**Do:**

1. Run the pipeline again without changing anything:
   ```bash
   uv run python src/main.py
   ```
2. In the MLflow UI, select the two runs and click **Compare**.
   Expected: the same metrics.
3. Set `PIPELINE_RANDOM_SEED=7` in `.env` and run the pipeline again.
   Expected: a third run with different metrics. Then set the seed back to 42.

**Check:**

- The experiment has three runs: two with seed 42 and the same metrics, and one with
  seed 7.

**Stuck?**

- Lecture: "Developer run vs. reproducible run"
- Notes: "Reproducibility, now recorded centrally"
- MLflow docs: https://mlflow.org/docs/latest/ml/tracking/

**Written answer** (in `answers.md`):

1. Now that runs are recorded centrally, what can you answer that you could not answer
   after Week 1? Think about reproducing a run, sharing it, and comparing runs.

## Finish: commit and submit your work (≈ 5 min)

1. Run `uv run pytest tests/`.
   Expected output: `11 passed` with the stack up.
2. Commit your work:
   ```bash
   git status          # answers.md must appear; .env and .venv/ must not
   git add .
   git commit -m "week02: local services stack and written answers"
   ```
3. Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
   and upload that URL to Moodle.

---

## Service UIs

| Service | URL | Credentials |
| --- | --- | --- |
| MLflow UI | http://localhost:5500 | — |
| Silo console | http://localhost:5511 | `S3_ACCESS_KEY` / `S3_SECRET_KEY` from `.env` |
| Postgres | `localhost:5532` | Connect with `psql` or a DB client |

> Host ports are remapped into the 55xx block to avoid clashes with macOS AirPlay (5000) and a local Postgres (5432). See `.env.example` for the full scheme.

---

## Tear-down

Stop the stack (data persists in named volumes):

```bash
docker compose down
```

Wipe all volumes for a completely fresh start:

```bash
docker compose down -v
```

---

## Repository structure

```
starter/
├── .env.example
├── .gitignore
├── compose.yaml
├── mlflow.Dockerfile
├── Makefile
├── pyproject.toml
├── uv.lock
├── README.md
├── data/
│   └── diabetes.csv
├── src/
│   ├── main.py
│   └── week_02_local_services/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── data.py
│       └── model.py
└── tests/
    ├── __init__.py
    ├── test_config.py
    └── test_smoke.py
```

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Port already in use | `docker compose down` any previous stacks; or change port in `.env` |
| `docker compose up --wait` never returns | `docker compose logs mlflow` — if you see a connection refused error, check the `--backend-store-uri` syntax in `compose.yaml` |
| Silo console shows no bucket | The `s3-create-bucket` job may have failed; check `docker compose logs s3-create-bucket` |
| MLflow UI shows "No experiments" | The pipeline hasn't run yet, or `MLFLOW_TRACKING_URI` in `.env` points to the wrong address |
| `uv run pytest` import error | Run from inside `starter/`, not from the repo root |
| `docker compose down -v` wipes my runs | That is correct — volumes hold all state. Use `down` (without `-v`) to keep data |
| MLflow server refused connection | MLflow 3.5.0+ requires `--allowed-hosts`; check the `mlflow` service command in `compose.yaml` |
