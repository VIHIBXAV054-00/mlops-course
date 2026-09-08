# Week 1 — Introduction to MLOps — Study Notes

These notes accompany the Week 1 lecture and lab. They are meant for self-study: read them after the lecture to consolidate the ideas, and before the lab to know what you are building toward. The course's running example — a diabetes-prediction pipeline — starts here and is carried, one capability at a time, all the way to a monitored production service by Week 14.

## Why this matters

In November 2021 Zillow shut down its house-flipping business after its pricing model systematically overpaid for homes as the market shifted. Roughly $300M was written off in a single quarter. There was no crashed server and no failing test: every request returned HTTP 200, latency was fine, the dashboards were green. The model was simply wrong about the world, and nothing in the system was built to notice.

That is the gap MLOps exists to close. Traditional software is *deterministic*: the same code on the same input produces the same output, so once it is correct and the tests pass, it stays correct until someone changes the code. A machine-learning system is *probabilistic* and depends on three things at once — **code, data, and the trained model** — and the world it observes keeps changing underneath it. Classic DevOps watches the code and the infrastructure; it was never designed to watch whether the data has drifted or whether the relationship the model learned still holds. MLOps is the engineering discipline that extends software practice to manage all three.

## Core concepts

**The ML lifecycle vs. the DevOps cycle.** DevOps moves code from commit → build → test → deploy, and the only moving part is the code. The ML lifecycle adds data collection and validation, training, offline evaluation, deployment, and *continuous monitoring with feedback back into retraining*. It is a loop, not a line, because a deployed model decays even when its code is frozen. A useful mental model is the "triad of change": behaviour can change because the **code** changed, because the **data** changed, or because the **model** (weights learned from that data) changed — and the last two have no equivalent in ordinary software.

**Why ML systems are entangled.** Because a model is learned from data rather than written by hand, small changes ripple in non-obvious ways — change one feature, one hyperparameter, or the input distribution, and seemingly unrelated outputs move. This is often summarised as *CACE: Changing Anything Changes Everything*. It is why ad-hoc ML systems accumulate "hidden technical debt" — glue code, undocumented data pipelines, and downstream consumers nobody registered — far faster than normal software.

**The three pillars.** The course frames good ML engineering around three properties:
- *Reproducibility* — being able to recreate a result exactly, which requires recording the code version, the data version, and the configuration (including random seeds) that produced it.
- *Scalability* — being able to grow from a laptop script to services that handle real load.
- *Automation* — replacing manual, error-prone steps with pipelines, so that the path from data to deployed model is repeatable and auditable.

**Reproducibility is not free.** In the lab you will run the same code twice and change only the random seed, and get a different model and a different score. The lesson generalises: a metric like "F1 = 0.84" is meaningless on its own. It is an engineering artifact only when you can say *which code, which data snapshot, and which configuration* produced it. Most of this course is about building the systems that capture exactly that.

**Roles across the lifecycle.** Real teams split the work. A *Data Scientist* focuses on framing the problem, the data, and model quality; a *Machine Learning Engineer* productionises models and builds pipelines; an *MLOps / ML Platform Engineer* builds the infrastructure (tracking, serving, monitoring) the others rely on. The boundaries blur in small teams, but knowing the roles helps you understand who owns which failure.

**The starter toolchain.** Week 1 introduces only the foundation: **Git** for code versioning, **uv** for reproducible Python environments (a pinned `pyproject.toml` + lockfile), and **Docker** for reproducible runtimes. Later weeks layer on MLflow (tracking), DVC (data versioning), Prefect (orchestration), KServe (serving), and Prometheus/Grafana/Evidently (monitoring). The guiding idea introduced now: keep the *ML* trivial and spend the engineering effort on the *lifecycle*.

## Key terms

- **MLOps** — engineering practices for the full ML lifecycle: reproducibility, versioning, automation, deployment, monitoring, governance.
- **Triad of change** — code, data, and model; any of the three can change system behaviour.
- **CACE** — "Changing Anything Changes Everything"; the entanglement property of ML systems.
- **Reproducibility** — recreating a result exactly from recorded code + data + config.
- **Technical debt (ML)** — hidden, compounding maintenance cost from ad-hoc ML systems (glue code, pipeline jungles, undeclared consumers).
- **Random seed** — the value that fixes otherwise-random steps (e.g. the train/test split); changing it changes the learned model.

## How this connects to the lab

The Week 1 lab sets up a cross-platform dev environment (Python via `uv`, Git, Docker) and runs a baseline scikit-learn pipeline — `StandardScaler` + `LogisticRegression` — on the Pima Indians Diabetes dataset. You will: get the environment reproducible from a lockfile, run the pipeline, then do the **seed experiment** (change the seed, watch the metric move) to feel why reproducibility needs recorded configuration, and make a guided Git commit. Notice that the dataset has physically impossible zeros (e.g. zero blood pressure) — these are deliberately left untreated until Week 5; do not "fix" them now.

## Recommended reading

Start here, then go deeper if you want:

- **Designing Machine Learning Systems (Huyen), Ch. 1–2** — the clearest overview of ML systems and how their lifecycle differs from traditional software. *Focus on:* why ML systems fail differently, and the iterative lifecycle diagram.
- **Practical MLOps (Gift & Deza), Ch. 1–2** — MLOps motivation and foundations, hands-on framing. *Focus on:* the maturity ladder and the DevOps-vs-MLOps comparison.
- **Sculley et al., "Hidden Technical Debt in Machine Learning Systems"** (NeurIPS 2015) — the founding paper; short and worth reading in full. *Focus on:* CACE, glue code, pipeline jungles, undeclared consumers.
- **Zinkevich, "Rules of Machine Learning"** (Google) — practitioner wisdom. *Focus on:* the first ~10 rules and Rule #29/#31/#32 on training–serving skew (you'll revisit these in Week 5).
- **Google, "MLOps: Continuous delivery and automation pipelines in ML"** (whitepaper) — *Focus on:* the maturity levels 0/1/2; place this course's trajectory on that ladder.
- Optional: **Introducing MLOps (Treveil et al.), Ch. 1–2**; **ml-ops.org** principles page.

(Full citations and links: `docs/resources.md`.)

## Check yourself

1. Give one failure that DevOps monitoring would catch and one it would miss but MLOps should catch.
2. Why is "F1 = 0.84" not, by itself, a reproducible result? What three things must accompany it?
3. In the triad of change, which two elements have no equivalent in traditional software, and why does that make ML systems harder to maintain?
4. Name the three roles across the lifecycle and one responsibility each.
