---
description:
  title: "Week 2 Lab: Local Services Stack"
  summary: |
    Stand up a four-service Docker Compose stack (Postgres + Silo + MLflow)
    and wire the Week 1 diabetes pipeline into it to produce one reproducible,
    centrally-recorded training run.
---

# Week 2 Lab: Local Services Stack

In Week 1 your run lived in the terminal history and your model lived on one disk.
This week you stand up the **local services stack** that makes runs durable and reproducible:

- **Postgres** stores run metadata (params, metrics, tags)
- **Silo** stores artifacts (the serialized model file)
- **MLflow** is the tracking server that your pipeline talks to
- **Docker Compose** brings all four up with one command

After this lab, re-running the pipeline twice gives you two centrally-recorded runs —
same seed, identical metrics, both queryable by anyone with the tracking URI.

This lab follows official tutorials with minimal changes — keep them open as references:

- **MLflow remote tracking server:** https://mlflow.org/docs/latest/ml/tracking/tutorials/remote-server/
- **MLflow tracking server architecture:** https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/
- **Silo container:** https://silo.pigsty.io/operations/deployments/baremetal-deploy-minio-as-a-container/
- **Docker Compose:** https://docs.docker.com/compose/

**Required deviation from the official tutorial:** The official MLflow tutorial (Step 3) runs
`mlflow server` on the host. This lab containerizes it as a fourth compose service so the entire
stack starts with a single `docker compose up -d --wait` — no separate terminal, no separate
environment, no manual credential export.

**Second deviation:** the MLflow tutorial uses MinIO as the object store. MinIO stopped
publishing free images and removed them from Docker Hub in September 2026, so this lab uses
**Silo**, a community fork of MinIO. It keeps MinIO's environment variables, `mc` client
and web console, so the tutorial's MinIO steps still apply.

## Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine + Compose plugin (Linux) — version 24+
- At least 16 GB RAM (all four containers fit easily, but leave headroom)
- `uv` — https://docs.astral.sh/uv/getting-started/installation/
- Ports **5500, 5510, 5511, 5532** free on your host (host-mapped 55xx block; see `.env.example`)

---

## Step 1 — Install Python dependencies

From this directory (`labs/week-02-local-services/starter/`):

```bash
uv sync --all-groups
```

This creates `.venv/` and installs everything pinned by `uv.lock`. You can run tests immediately — no running stack required.

## Step 2 — Create your local configuration

```bash
cp .env.example .env
```

Review the values. The defaults work out of the box. **Never commit `.env`** — it is git-ignored.

## Step 3 — Run the tests (no stack required)

```bash
uv run pytest tests/ -v
```

Expected: **10 passed, 1 skipped**. The skipped test is Exercise 3's MLflow-integration test,
which auto-skips until the tracking server is reachable.

---

## Exercises

Complete these exercises in order — each builds on the previous.

Exercises 4 and 5 ask for a **written answer**. Put those in a file called `answers.md` in this
directory, and **commit it with your code**. It is part of your submission, and it is read
alongside your solution.

### Exercise 1 — Stand up storage (Silo)

Open `compose.yaml` and find the `s3` and `s3-create-bucket` service blocks marked `TODO(student)`.

Fill in:
- `s3`: the image (`pgsty/silo:RELEASE.2026-09-16T00-00-00Z`), command, environment variables, volume mount, and healthcheck
- `s3-create-bucket`: the image (`pgsty/mc:RELEASE.2026-09-16T00-00-00Z`), and the entrypoint that creates the bucket


Then start only the storage services:

```bash
docker compose up -d s3 s3-create-bucket
docker compose ps  # both should show "healthy" / "exited 0"
```

Open **http://localhost:5511** and log in with `S3_ACCESS_KEY` / `S3_SECRET_KEY` from your `.env`.

Confirm: the bucket named `mlflow-artifacts` exists.

### Exercise 2 — Wire the metadata and tracking server

Open `compose.yaml` and find the `mlflow` service block. Fill in the `TODO(student)` placeholders:

- `MLFLOW_S3_ENDPOINT_URL` — the Silo endpoint inside the compose network
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — Silo root credentials
- `--backend-store-uri` — the Postgres connection string using the compose DNS name `postgres`
- `--artifacts-destination` — the Silo bucket (`s3://mlflow-artifacts`)
- `--allowed-hosts` — required by MLflow 3.5.0+ security middleware. Note: the host check does **not** strip the port, so include the `host:port` form (e.g. the `localhost:*,127.0.0.1:*` wildcards) or the browser will get an "Invalid Host header" error at `localhost:5500`

Bring up the full stack:

```bash
docker compose up -d --wait
```

The `--wait` flag blocks until all service healthchecks pass. This takes about 20-30 seconds on first run (image pulls).

Open **http://localhost:5500** — you should see the MLflow UI with no experiments yet.

**Key concept:** Notice that `--backend-store-uri` points to `postgres` (a hostname), not `localhost`. Inside the compose network, service names are DNS names. The MLflow server and Postgres talk to each other inside the network; the host port `5432` is mapped for your inspection.

### Exercise 3 — Log a tracked run from the pipeline

Open `src/week_02_local_services/cli.py`. Find the `TODO(student)` blocks and replace the placeholder code with real MLflow calls:

1. Set the tracking URI and experiment from `settings`
2. Wrap the training block in `mlflow.start_run()`
3. Log `random_seed`, `test_size`, and `max_iter` as params
4. Log each metric from `evaluate_model` with `mlflow.log_metric`
5. Log the fitted pipeline with `mlflow.sklearn.log_model(model, name="model")`

Run the pipeline:

```bash
uv run python src/main.py
```

Open the MLflow UI at **http://localhost:5500**, click into the `diabetes-week2` experiment, and confirm:
- The run appears with params (`random_seed=42`, `test_size=0.25`, `max_iter=1000`)
- Metrics are recorded (`accuracy`, `precision`, `recall`, `f1`)
- An artifact named `model` is listed under the run

### Exercise 4 — Verify the storage split

Confirm **where each piece lives**.

**Silo (artifacts):**

Open **http://localhost:5511**, navigate to the `mlflow-artifacts` bucket, and browse to the model artifact directory. You should find `model.pkl` (or `model/` directory with `model.pkl` and `MLmodel` inside).

**Postgres (metadata):**

```bash
docker compose exec postgres psql -U mlflow -d mlflowdb -c "\dt"
```

You should see tables like `runs`, `params`, `metrics`, `tags`, `experiments`.

Query a run:

```bash
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT run_uuid, status, start_time FROM runs LIMIT 5;"
```

**Written answer** (add to `answers.md`): Which storage plane holds which data? Why are model files not stored in Postgres?

### Exercise 5 — Reproducibility check (ties back to Week 1)

Run the pipeline a second time without changing anything:

```bash
uv run python src/main.py
```

Open the MLflow UI. You now have two runs. Compare them — the metrics should be **identical** (same seed, same data, same code).

Now change the seed:

```bash
# In .env: PIPELINE_RANDOM_SEED=7
uv run python src/main.py
```

You have three runs now. The third has different metrics. Both the "seed-42" runs and the "seed-7" run are permanently recorded with their configuration.

**Written answer** (add to `answers.md`): Now that runs are centrally recorded, what can you answer that you could not answer after Week 1's terminal-scrollback experiment? (Think about: reproducibility, shareability, comparability.)

### Finish — commit your work

```bash
git status          # answers.md must appear; .env and .venv/ must NOT
git add labs/week-02-local-services/starter
git commit -m "week02: local services stack and written answers"
```

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
