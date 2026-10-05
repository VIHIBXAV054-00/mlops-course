---
theme: default
title: Week 2 — Reproducible Runtimes
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers developer runs vs. reproducible environments, the three storage planes of
  a tracked run, MLflow tracking server architecture, and Docker Compose as local
  reproducible infrastructure.
class: text-left
transition: slide-left
mdc: true
# hash routing + relative base (built with --base ./) so the SPA works in a
# GitHub Pages subdirectory: slides live after the # and assets load relatively.
routerMode: hash
---

# Week 2: Reproducible Runtimes

**Lifecycle of Artificial Intelligence Systems**

- Developer runs vs. reproducible environments
- Artifacts, metadata, and where each belongs
- Docker Compose as local infrastructure
- One-command startup: standing up the stack

---

# Learning objectives

By the end of this lecture, students should be able to:

- distinguish a *developer run* from a *reproducible run* and explain why the difference matters
- name the three storage planes of a tracked ML run and justify why each is separate
- describe the MLflow tracking server's role between client and storage
- explain how Docker Compose helps: service ordering, healthchecks, named volumes, and one-command startup
- bring up the local services stack from this week's lab and trace a run end-to-end through it

---

# How we left off last week

> *Set `PIPELINE_RANDOM_SEED=7` in `.env` and run again.*

The accuracy moved by ~5 percentage points — **same code, same data file, different model**.

You might find the number if you scrollback through your terminal.

<br>

**Which run produced the number you brought to the leaderboard?**

Can you re-run it? Prove it? Share it with a teammate?

<!--
The leaderboard from Week 1 is the motivating pain point. Students cannot answer "which run?"
because nothing was recorded anywhere durable. This week fixes that.
-->

---

# Zillow recap

Week 1: Zillow's $300M loss — *the dashboards were green the whole time*; the model was wrong about the world and nobody noticed.

A contributing factor: **nobody could reproduce the model's training run** when it mattered.

- Which data snapshot trained it?
- Which seed? Which dependency versions?
- What were the exact metrics that justified deployment?

**Evidence of reproducibility is the first thing an audit asks for.**

<!--
Reinforce the Week 1 motivating story.
-->

---

# What "reproducible" actually means

Given the same inputs, the same process, and the same environment — **anyone, anywhere, at any time gets the same result**.

For an ML run those inputs are:

| Input | What drifts silently |
| --- | --- |
| **Code** | a colleague's `pip install mlflow --upgrade` |
| **Data** | a CSV that was edited on disk |
| **Config / seeds** | a config file was modified |
| **Environment** | `numpy==1.24` on your laptop vs. `numpy==2.1` in CI |

A metric without all four is a **coincidence**.

---

# Developer run vs. reproducible run

| | Developer run | Reproducible run |
| --- | --- | --- |
| **Where it runs** | Any laptop, whatever Python is installed | Pinned deps via `uv.lock` + pinned Docker image |
| **Config** | Local `.env` nobody committed | `.env.example` in Git; secrets injected at runtime |
| **Outputs** | Terminal scrollback, or a local file | Metadata → DB; artifacts → object store |
| **Can you re-run it?** | Maybe, on your machine today | Yes! Anyone from a fresh clone |
| **Can you compare it?** | Copy-paste from terminal | Query by param/metric from the tracking server |

Week 1 = developer run. Week 2 = the infrastructure that turns it into a reproducible run.

<!--
The table is the core concept of this slide. Talk through each row.
-->

---

# What makes an artifact **business-ready**?

1. **Retrieve** — it lives somewhere with an address
2. **Reproduce** — given the same inputs, the process gives the same result
3. **Compare** — you can line it up against other runs and explain the difference
4. **Audit** — you can prove what produced it

<br>

> The goal of this week is not a better model. The goal is a **reproducible runtime** that produces auditable, comparable artifacts.

---

# What does a training run actually generate?

- What must be saved to reproduce the run?
- What must be saved to compare the run to other runs?
- What must be saved to audit the run?
- What must be saved to use the model?

---

# The three storage planes of a tracked run

Every ML run produces three kinds of outputs. Each needs a different storage backend.

```mermaid
graph LR
    RUN["⚙️ A Training Run"] --> CODE["💻 Code"]
    RUN --> META["📊 Metadata"]
    RUN --> ART["📦 Artifacts"]
```

<!--
Walk through each plane. The key insight is WHY the split exists — see next slide.
-->

---

# Version control

**Main use case:**
- Track how files change over time, coordinate contributions, and recover an earlier version of a project.

**Example software:**
- Git, hosted by GitHub, GitLab, or Bitbucket

**What questions does it let us answer?**
- Which exact code and configuration produced this training run?
- What changed between the code version for run A and run B?

**What do we store there?**
- Source code, configuration files, documentation, schemas, and the history of changes.
- A commit records a particular state of the project.

---

# Version control in our stack: Git

Code is already in Git from Week 1.

- A Git commit hash is a **content address** — the hash *is* the content
- MLflow can log the `git_commit` tag on every run automatically
- That tag links the metric to the exact code that produced it

Here the tooling from Week 1 is already sufficient.

---

# The three storage planes of a tracked run

Every ML run produces three kinds of outputs. Each needs a different storage backend.

```mermaid
graph LR
    RUN["⚙️ A Training Run"] --> CODE["💻 Code\n(Version Control — Git)"]
    RUN --> META["📊 Metadata"]
    RUN --> ART["📦 Artifacts"]

    CODE -->|"text, diffable, low-volume"| GIT["📝 git push"]
```

<!--
Walk through each plane. The key insight is WHY the split exists — see next slide.
-->

---

# Relational database

**Main use case:**
- Store structured facts and query relationships between them using rows, columns, indexes, and joins.

**Example software:**
- PostgreSQL, MySQL, or MariaDB
- Microsoft SQL Server, or Oracle Database

**What questions does it let us answer?**
- Which runs used this parameter and achieved a metric above a given threshold?
- How does the performance of a model change over time?

**What do we store there?**
- Structured records such as experiment names, run IDs, parameters, metrics, tags, and timestamps.

---

# Relational database in our stack: Postgres

**Why Postgres (not SQLite):**
- Postgres is network-accessible → multiple team members can write to the same server
- SQLite is a local file → only one process at a time, no sharing

**What do we store there?**
```
experiments    → experiment id, name, artifact location
runs           → run id, experiment id, status, start/end time
params         → run id, key, value
metrics        → run id, key, value, timestamp, step
tags           → run id, key, value
```

<!--
Students can run `docker compose exec postgres psql …` in Exercise 4 to see these tables.
-->


---

# The three storage planes of a tracked run

Every ML run produces three kinds of outputs. Each needs a different storage backend.

```mermaid
graph LR
    RUN["⚙️ A Training Run"] --> CODE["💻 Code\n(Version Control — Git)"]
    RUN --> META["📊 Metadata\n(Relational DB — Postgres)"]
    RUN --> ART["📦 Artifacts"]

    CODE -->|"text, diffable, low-volume"| GIT["📝 git push"]
    META -->|"params, metrics, tags, run lineage"| PG["🗄️ postgres://…"]
```

<!--
Walk through each plane. The key insight is WHY the split exists — see next slide.
-->

---

# Object store

**Main use case:**
- Store and retrieve large files or binary payloads durably using a bucket and an object key.

**Example software:**
- Amazon S3, Google Cloud Storage, or Azure Blob Storage
- MinIO, or its community fork Silo, for self-hosted or local development

**What questions does it let us answer?**
- Which model artifact belongs to this run, and can I download it?
- Which plots, reports, or checkpoints were produced by this run?

**What do we store there?**
- Large or binary files such as trained model files, plots, confusion matrices, and feature importance charts.

---

# Object store in our stack: Silo

**Silo** is an S3-compatible object store you run locally. It is a community fork of MinIO,
whose free images left Docker Hub in September 2026[^1][].

Its API is identical to AWS S3.

- Objects live in **buckets** (like top-level folders)
- Each object has a **key** (path) and binary content
- No SQL, no joins — just `PUT`, `GET`, `LIST`

[^1]: Removal dated 11–14 September 2026 in "MinIO Vanished From Docker Hub", bex.co, 25 September 2026, https://bex.co/blog/2026/09/25/minio-docker-hub-removal-quay-repoint; `minio/minio` returned 404 when checked on 3 October 2026. Fork: PGSTY Silo, https://github.com/pgsty/silo.

<!--
The course used MinIO until its images were removed from Docker Hub. Silo is a drop-in fork, so the lab still uses the MINIO_* variables inside the container.
-->

---

# The three storage planes of a tracked run

Every ML run produces three kinds of outputs. Each needs a different storage backend.

```mermaid
graph LR
    RUN["⚙️ A Training Run"] --> CODE["💻 Code\n(Version Control — Git)"]
    RUN --> META["📊 Metadata\n(Relational DB — Postgres)"]
    RUN --> ART["📦 Artifacts\n(Object Store — Silo)"]

    CODE -->|"text, diffable, low-volume"| GIT["📝 git push"]
    META -->|"params, metrics, tags, run lineage"| PG["🗄️ postgres://…"]
    ART  -->|"model files, plots, large/binary"| S3["🪣 s3://mlflow-artifacts"]
```

<!--
Walk through each plane. The key insight is WHY the split exists — see next slide.
-->

---

# Metadata vs. artifacts

| | Metadata (Postgres) | Artifacts (Silo) |
| --- | --- | --- |
| **Content** | accuracy=0.578, seed=42, run_id=abc | `model.pkl`, `confusion_matrix.png` |
| **Volume** | Small — kBs per run | Large — MBs/GBs per run |
| **Structure** | Rows and columns | Blobs |
| **Access pattern** | "show me all runs with F1 > 0.55" | "download model for run abc" |

<!--
Blobs are large, binary, and opaque.
-->

---

# Meet MLflow

**MLflow is an open-source platform for managing ML projects.**

It gives a place to:

- record parameters, metrics, and tags
- store models and other run artifacts
- retrieve the complete record of a run later

---
layout: image
image: /mlflow-tracking-setup-overview.png
backgroundSize: 80%
---

---
layout: center
---

# MLflow tracking server architecture

```mermaid {scale: 0.8}
graph TD
    subgraph "Your laptop (host)"
        CLI["Python pipeline (uv run python src/main.py)"]
    end

    subgraph "Docker Compose network"
        MLF["mlflow:5000\n(tracking server)"]
        PG["postgres:5432\n(backend store)"]
        MINIO["s3:9000\n(artifact store)"]
    end

    CLI -->|"HTTP REST\nMLFLOW_TRACKING_URI=http://127.0.0.1:5500"| MLF
    MLF -->|"SQLAlchemy\nparams, metrics, tags"| PG
    MLF -->|"boto3 / S3 API\nmodel files, plots"| MINIO
```

<!--
The key teaching point: the client only needs the tracking URI.
The server holds Silo credentials; artifacts are proxied through the server.
-->

---

# What the client does not need to know

The MLflow client only needs:

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5500
```

It does **not** need:
- `MLFLOW_S3_ENDPOINT_URL`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- Any knowledge that Silo exists

The server holds those credentials and proxies all artifact reads/writes.

---

# Logging a run: what happens step by step

```mermaid
sequenceDiagram
    participant P as Pipeline (client)
    participant S as MLflow server
    participant DB as Postgres
    participant OBJ as Silo

    P->>S: POST /api/2.0/mlflow/runs/create
    S->>DB: INSERT INTO runs (run_id, …)
    S-->>P: { run_id: "abc123" }

    P->>S: POST /api/2.0/mlflow/runs/log-batch (params + metrics)
    S->>DB: INSERT INTO params, metrics

    P->>S: PUT /mlflow-artifacts/abc123/model (model file bytes)
    S->>OBJ: PUT s3://mlflow-artifacts/abc123/artifacts/model/

    P->>S: POST /api/2.0/mlflow/runs/update (status=FINISHED)
    S->>DB: UPDATE runs SET status='FINISHED'
```

<!--
Walk through this slowly. Each arrow is a real HTTP call or DB write.
The student can verify steps 2-3 in Postgres (Exercise 4) and step 4 in the Silo console.
-->

---

# Docker Compose: what it is

Docker Compose is a tool for defining and running multi-container applications.

You write one YAML file describing all services, and bring everything up with one command:

```bash
docker compose up -d --wait
```

This week's stack has four services:
1. **postgres** — metadata store
2. **s3** — artifact store (Silo)
3. **s3-create-bucket** — one-shot job that creates the bucket on first run
4. **mlflow** — tracking server

<!--
Keep focus on WHY each service exists, not the YAML syntax yet.
-->

---

# Docker Compose: key concepts

**Images and version pinning**

```yaml
image: postgres:16.3       # pinned — everyone gets the same binary
image: pgsty/silo:latest   # NOT pinned — avoid; "latest" changes
```

The pinned Docker image is an **immutable, versioned artifact**.

"It ran on my machine" means nothing if the image wasn't pinned.

**Named volumes**

```yaml
volumes:
  - postgres-data:/var/lib/postgresql/data
```

Data persists across `docker compose down` and `docker compose up`.

Wipe with `docker compose down -v`.

---

# Docker Compose: service ordering and healthchecks

**The problem:** Postgres takes ~2 seconds to start accepting connections. If the MLflow container starts before Postgres is ready, it crashes.

**`depends_on` without healthchecks:** only waits for the container to *start* — not for the service to be *ready*.

**`depends_on` with healthchecks:** waits for the healthcheck to pass — the service is actually ready.

```yaml
depends_on:
  postgres:
    condition: service_healthy
  s3-create-bucket:
    condition: service_completed_successfully
```

This is why `docker compose up -d --wait` works reliably — `--wait` itself blocks until all healthchecks pass.

---

# Docker Compose: the compose network

All services in a compose file share a private network.

Inside that network, **service names are DNS hostnames**:

```
postgres://user:pass@postgres:5432/mlflowdb     ← "postgres" resolves inside compose
http://s3:9000                                    ← "s3" resolves inside compose
```

From your host machine:
```
http://127.0.0.1:5500     ← MLflow UI (mapped from mlflow:5000)
http://127.0.0.1:5511     ← Silo console (mapped from s3:9001)
```

This separation between internal DNS names and host port mappings is fundamental to how compose stacks work.

---

# The containerized MLflow server: the required deviation

The official tutorial runs `mlflow server` **on the host** (Step 3 in the tutorial docs).

We run it as a **fourth compose service**, built from a pinned `Dockerfile`:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir \
    mlflow==3.13.0 \
    psycopg2-binary==2.9.12 \
    boto3==1.43.29
EXPOSE 5000
ENTRYPOINT ["mlflow", "server"]
```

**Why:** Running the server on the host would require a separate terminal, a separate environment, and environment variable management outside the compose stack. The image is pinned, isolated, and started and stopped with the rest of the stack.

<!--
State the deviation explicitly as required by AGENTS.md and TASK_W2.md.
-->

---

# The lab stack end-to-end walkthrough

```mermaid
graph LR
    subgraph "Host ports"
        H5000["localhost:5500\n(MLflow UI)"]
        H9000["localhost:5510\n(Silo API)"]
        H9001["localhost:5511\n(Silo console)"]
        H5432["localhost:5532\n(Postgres)"]
    end

    subgraph "Compose network (mlflow-net)"
        MLF["mlflow"]
        PG["postgres:16.3"]
        MINIO["pgsty/silo:RELEASE..."]
        BUCKET["pgsty/mc\n(one-shot bucket create)"]
    end

    H5000 <--> MLF
    H9000 <--> MINIO
    H9001 <--> MINIO
    H5432 <--> PG

    MLF --> PG
    MLF --> MINIO
    BUCKET --> MINIO

    CLI["uv run python src/main.py"] -->|"http://127.0.0.1:5500"| H5000
```

<!--
Walk through this diagram before the exercise walkthrough. It is the map students keep
open during the lab.
-->

---

# Lab exercise overview

| # | Exercise | What you prove |
| --- | --- | --- |
| 1 | Stand up storage (Silo) | Silo service and bucket-bootstrap job work; bucket visible in console |
| 2 | Wire the tracking server | MLflow uses Postgres for metadata, Silo for artifacts; UI loads |
| 3 | Log a tracked run | Pipeline run appears in UI with params + metrics + model artifact |
| 4 | Verify the storage split | Model file is in Silo bucket; metadata rows are in Postgres |
| 5 | Reproducibility check | Re-run with same seed → identical metrics, now centrally recorded |

> Each exercise builds on the previous one.

---

# Key takeaways

- A developer run lives on one laptop and is unreproducible. A reproducible run has its metadata in a DB and its artifacts in an object store, both addressable and queryable.
- **Code → Git. Metadata → Postgres. Artifacts → Silo.** The split is driven by access pattern and volume.
- MLflow tracking server is the single endpoint that writes metadata to Postgres and proxies artifacts to Silo. The client only needs the tracking URI.
- Docker Compose gives you ordered startup (healthchecks), a shared network (service DNS), and one command to bring everything up.
- Pinning Docker image versions is the same discipline as pinning Python dependencies — reproducible runtime management, just at the OS/service layer.

---

# Next week

**Week 3: Experiment Tracking**

Now that the infrastructure exists and records every run, we use MLflow *well*:

- comparing multiple runs in the UI
- parameter sweeps and run search
- custom plots logged as artifacts
- the **Model Registry**: named models, versions, stage transitions, promotion to Staging

<!--
The words "stage transitions, promotion to Staging" on this slide are DELIBERATE and must not
be "corrected" to aliases. MLflow deprecated stages in 2.9, and Week 3 opens its
required-deviation slide by quoting this line verbatim and explaining why the vocabulary
outlived the API.
-->
