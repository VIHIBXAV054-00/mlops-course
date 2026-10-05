# Week 2 — Reproducible Runtimes — Study Notes

These notes accompany the Week 2 lecture and lab. Week 1 left you with a baseline pipeline that runs on one laptop and writes nothing durable. Week 2 builds the **local services stack** that turns that throwaway run into a reproducible, permanently-recorded one — and teaches the distinction between an *artifact* and its *metadata*.

## Why this matters

"It worked on my machine..." Two weeks later nobody can reproduce it. Even an identical Docker image is not automatically enough — package resolvers pull different transitive versions over time, and unpinned environments quietly change underneath you.

A *developer run* is ephemeral: untracked, unpinned, with its outputs scattered on local disk. A *reproducible runtime* is the opposite: dependencies are pinned (a lockfile), the runtime is a pinned image, configuration is externalised, and the run's inputs and outputs are recorded somewhere durable and shared. Week 2 is about setting up the infrastructure that makes a reproducible runtime possible with a single command.

## Core concepts

**The three storage planes of a tracked run.** A run produces three very different kinds of thing, and each belongs in a different store:
- **Code** → Git. Text, low-volume, diff-able.
- **Metadata** (parameters, metrics, tags, run lineage and timestamps) → a **relational backend store** (here, **PostgreSQL**). Small, structured, *queryable* — so you can later ask "show every run where F1 > 0.55."
- **Artifacts** (the serialized model, plots, large or binary outputs) → an **object store** (here, **Silo**, a community fork of MinIO that speaks the S3 protocol). Cheap, scalable blob storage.

The split exists because the stores have opposite strengths: a relational database is the wrong place for hundred-megabyte binary blobs (slow, expensive, no useful queries over their contents), and an object store is the wrong place for structured metadata you want to filter and join. Putting each kind of data where it belongs is what makes runs both durable *and* searchable.

**The tracking server sits in front.** **MLflow** runs as a tracking server: your pipeline talks to it over HTTP, and the server writes metadata to its *backend store* (Postgres) and pushes artifacts to its *artifact store* (Silo). Two flags express the split — `--backend-store-uri` (where metadata goes) and `--artifacts-destination` (where artifacts go). The client only needs the tracking URI; it never holds the object-store credentials, because artifacts are proxied through the server.

**Docker Compose as one-command, reproducible local infrastructure.** Compose describes a set of services in one file and starts them together. The concepts you meet here:
- *Pinned images* — every service uses a specific version tag, never `latest`, so the stack is the same on every machine.
- *Service DNS* — inside the Compose network, services reach each other by name (`postgres`, `s3`), not `localhost`.
- *Healthchecks and `depends_on`* — a service can wait until another is genuinely *ready* (not merely started) before it launches; `docker compose up -d --wait` blocks until everything is healthy. This prevents the classic race where the app connects before the database is accepting connections.
- *Named volumes* — state (the database files, the bucket contents) persists across restarts in volumes rather than inside the container, so `down` then `up` does not wipe your runs.

**Reproducibility, now recorded centrally.** As in Week 1, running twice with the same seed gives identical metrics — but now both runs are recorded in MLflow with their parameters, addressable by run ID, and comparable side by side.

**A note on ports (lab-specific).** The lab maps the services' host ports into an uncommon block (MLflow `5500`, Silo API `5510`, console `5511`, Postgres `5532`) to avoid clashes with things that commonly occupy the defaults. The *container-internal* ports stay at each tool's native default, so the official docs still apply unchanged.

## Key terms

- **Developer run** — an untracked, unpinned local execution.
- **Reproducible runtime** — pinned dependencies + pinned image + externalised config + recorded inputs/outputs.
- **Backend store** — the relational database holding run *metadata*.
- **Artifact store** — the object store holding run *artifacts* / blobs.
- **Tracking server** — MLflow process that records metadata and proxies artifacts on the client's behalf.
- **Object storage / S3-compatible** — blob storage addressed by bucket/key via the S3 API.
- **Healthcheck** — a probe that reports when a service is actually ready to serve.
- **Named volume** — Docker-managed storage that persists data outside a container's lifecycle.

## How this connects to the lab

The Week 2 lab brings up a four-service Compose stack — Postgres, Silo, a bucket-bootstrap job, and a containerised MLflow server — with one `docker compose up -d --wait`. You complete `TODO` blanks to (1) stand up Silo and create the artifacts bucket, (2) wire the MLflow server's backend store and artifact destination, and (3) add the MLflow logging calls so the Week 1 pipeline records one tracked run. Then you *verify the split directly*: find the model artifact in the Silo console, and the params/metrics rows in Postgres. Finally you re-run to see reproducible, centrally-recorded results. Note: Week 2 proves the stack with a single tracked run; the MLflow **model registry, stage promotion, and multi-run experiment comparison are Week 3's topic**.

## Recommended reading

- **Practical MLOps (Gift & Deza), Ch. 3 — containers** — *Focus on:* why containerising the runtime (not just the code) is what makes execution reproducible across machines.
- **Machine Learning Design Patterns (Lakshmanan et al.), Ch. 6 — Reproducibility patterns** — *Focus on:* the *Workflow Pipeline* and *Transform* patterns; they formalise what the stack is doing.
- **Designing Machine Learning Systems (Huyen), Ch. 10 — Infrastructure & Tooling** — *Focus on:* the development-environment and storage sections; how dev/artifact/metadata layers fit together.
- **MLflow docs — "Tracking Server" architecture** — *Focus on:* the diagram of client → server → {backend store, artifact store}, and the `--backend-store-uri` / `--artifacts-destination` split.
- Optional: the **Silo** container guide (object storage / buckets) and the **Docker Compose** docs (services, healthchecks, volumes). MLOps Zoomcamp Module 1 covers the same Docker/environment groundwork.

(Full citations and links: `docs/resources.md`.)

## Check yourself

1. A teammate cannot reproduce your run. Which of the three storage planes (code / metadata / artifacts) might have failed, and how would you tell?
2. Why store the serialized model in Silo rather than in Postgres? Give the trade-off in both directions.
3. What does a healthcheck plus `depends_on: condition: service_healthy` protect you from at startup?
4. The client logs a run but holds no Silo credentials. How does the model artifact still reach the object store?
