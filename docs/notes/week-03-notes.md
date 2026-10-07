# Week 3 — Experiment Tracking — Study Notes

These notes accompany the Week 3 lecture and lab. Week 2 built the infrastructure and proved it worked by logging **one** run. Week 3 is about using it as an engineering discipline: many runs compared deliberately, plots stored alongside the numbers that explain them, and a registry that gives one chosen model an identity, an approval record, and a walkable chain back to its evidence.

## Why this matters

In June 2021 a study in *JAMA Internal Medicine* externally validated a proprietary sepsis-prediction model shipped inside a widely deployed electronic health record system and described as in use at hundreds of US hospitals. The vendor's documentation reported an AUC of 0.76–0.83; across 27,697 patients the measured AUC was 0.63, and at the alert threshold hospitals actually ran, sensitivity was 33% — it missed roughly two thirds of sepsis cases. No independent validation had ever been published, and only limited information about the model was public. The failure here was not an outage: the service was up and the alerts fired. It was the absence of a record anyone outside the vendor could reach.

The everyday version is smaller and much more common. Three teammates run twelve experiments in a week. The best F1 gets pasted into a chat thread as a screenshot. The model file that produced it sits in someone's Downloads folder with a name like `model_final2.pkl`. A month later nobody can say which configuration produced the number, whether it was ever beaten, or which file to deploy. Tracking makes runs *comparable*; the registry makes exactly one of them *accountable*.

## Core concepts

**Four kinds of run metadata.** A run records four different things, and confusing them is the most common beginner error. **Params** are inputs you chose (`C=1.0`, `random_seed=42`) — they exist so someone can *reproduce* the run. **Metrics** are numbers you measured (`f1=0.6240`), and each is technically a time series with a `step` axis, even when it has only one point. **Tags** are free-form, mutable labels — they exist so someone can *find* the run later, and `git_commit` is the single most valuable one you will ever log. **Artifacts** are files: the serialized model, plots, tables. Params, metrics, and tags go to the relational backend store; artifacts go to the object store — Week 2's split, reused rather than re-explained. The classic mistake is logging a *result* as a param: the call succeeds, and you discover three weeks later that you cannot sort, chart, or filter on it.

**Experiments, sweeps, and search.** An experiment is a question; a run is one attempt at answering it. Naming matters — `diabetes-week3` is a question, `final_v2` is not — and only runs in the same experiment can be compared in the UI. A **sweep** is expressed as one parent run holding the grid definition, with one `mlflow.start_run(nested=True)` child per configuration; without `nested=True` you get N unrelated top-level runs and a flat UI tree. Once runs live in a queryable store, comparison stops being a scroll and becomes a query: `mlflow.search_runs(filter_string="tags.sweep = 'week3-baseline' and metrics.f1 > 0.55", order_by=["metrics.f1 DESC"])`. The filter is evaluated *on the server, against Postgres* — that is the payoff of Week 2's backend store. Note the syntax traps: the operator is `=` not `==`, param values are always strings needing single quotes, and metric comparisons are bare numbers. The UI offers four complementary views — run table, chart view, parallel coordinates, and run detail with the artifact browser.

**Plots are artifacts.** `mlflow.log_figure(fig, "plots/confusion_matrix.png")` sends a figure straight to the artifact store, filed under the run that produced it, at the same path in every run — so it is addressable, comparable across runs, and still there in six months. A screenshot in a chat thread satisfies none of that. The confusion matrix is worth logging even when you already know the recall, because the bottom-left cell turns an abstract 0.58 into a count of diabetic patients the model called healthy.

**The registry object model.** Tracking answers "which run scored best?" It cannot answer "what are we serving?" — `runs:/30b3dfb2.../model` is an address nobody can remember and nobody approved. The registry adds four nouns. A **registered model** is a name. A **version** is an immutable, numbered snapshot of one run's model under that name. An **alias** is a mutable, arbitrary name pointing at exactly one version (`models:/diabetes-classifier@staging`). A **tag** is a recorded fact attached to a version. The invariant that makes everything work: a version came from exactly one run, and that link is permanent. Runs and versions are append-only history; aliases and tags are the only two things you may ever move. Registering deliberately after evaluation — rather than passing `registered_model_name=` on every training call — keeps the version list a record of decisions instead of a log of executions.

**Stages, aliases, and what changed.** MLflow's original registry had four fixed stages: `None`, `Staging`, `Production`, `Archived`, moved with `transition_model_version_stage`. These were **deprecated in MLflow 2.9**, and the official registry documentation and tutorials now use **aliases plus version tags** instead. The old call still exists in current releases and emits a deprecation warning, so code copied from an older blog post will appear to work — recognise it as historical. Four reasons the change was an improvement: many aliases can point at one version; alias names are arbitrary, so a team can express `challenger`, `eu-prod`, or "approved but not deployed"; aliases are freely reassignable with no state-machine constraints; and deployment code can name a role rather than a version number. The documented mapping is that `Production` corresponds to a `champion` alias. The *word* "staging" remains completely standard workplace vocabulary — it is only the API that went away.

**Promotion and traceability.** Promotion is a process with gates; the alias assignment is merely its last line of code. This week the gate is one threshold comparison and the evidence is recorded as four version tags (`validation_f1`, `validation_roc_auc`, `promoted_by`, `promoted_at`) read back from the source run so they cannot drift from what was measured, plus two facts about the registered model as a whole (`owner`, `task`). **Traceability** is then a four-hop walk: alias → version → `run_id` → the run's params, metrics, and tags → `git checkout <git_commit>`. Only the last hop is not MLflow's job. Every arrow is a lookup a human can do months later, from a laptop, having never seen the code — and that, rather than the existence of a record somewhere, is what traceability means. The last arrow is only true if the run was logged from a **clean working tree**: a `git_commit` tag names the last commit, not the uncommitted edits that actually ran, which is why the lab records `git_dirty` beside it. Aliases add a second caveat: the open-source registry stores only where each alias points *now*, so a rollback that writes no tag leaves no trace. One honest gap remains: the chain ends at a *file path*, `data/diabetes.csv`, so nothing recorded proves which data was in that file.

## Key terms

- **Experiment** — a named group of runs answering one question; the unit of comparison.
- **Run** — one execution, identified by a `run_id`.
- **Nested (child) run** — a run created with `nested=True` inside another; how sweeps are structured.
- **Parameter** — an input you chose; exists so a run can be reproduced.
- **Metric** — a measured number, with an optional `step` axis making it a series.
- **Tag** — a mutable, free-form label; exists so a run can be found.
- **Artifact** — a file logged to the object store under a run (plots, tables, the model).
- **Model signature** — the recorded input/output schema of a logged model.
- **Registered model** — a named entry in the registry.
- **Model version** — an immutable, numbered snapshot of one run's model.
- **Model alias** — a mutable pointer to exactly one version; replaced stages.
- **Model URI** — `models:/<name>/<version>` (a fact) or `models:/<name>@<alias>` (a decision).
- **Promotion gate** — the evidence required before an alias is moved.
- **Champion / challenger** — conventional alias names for the serving model and its rival.
- **Traceability** — the property that anyone entitled to ask can walk from what is deployed back to the evidence for it.

## How this connects to the lab

The Week 3 lab reuses the **same Compose stack as Week 2, completely unchanged** (MLflow on `:5500`, Silo console on `:5511`) under a new experiment, `diabetes-week3` — every exercise is in Python. You (1) log a single deliberate run with batched params, searchable tags including the git commit, five metrics, and a model with an inferred signature; (2) implement a ROC curve and a confusion matrix and log both as run artifacts; (3) sweep six configurations as one parent run with six children, then compare them in the parallel-coordinates view; (4) rank the latest sweep with a server-side `search_runs` query, discover that F1 and ROC-AUC pick *different* winners, and **choose and defend** the run you would promote; (5) register that run twice, to see that versions are immutable and monotonic; (6) promote a version with its evidence and your reason attached, walk the chain back from `@staging` — and then take the last hop yourself with `git diff`, finding that the recorded commit is not the code that trained the model, because the runs were logged from uncommitted work. You fix it by recording a `git_dirty` tag, committing, and retraining; (7) roll the aliases back, see the guard refuse a never-promoted version, and confirm in Postgres that the registry keeps no alias history of its own. Note the scope line: the data itself is still referenced by **path** — dataset versioning with DVC and Silo is Week 4's topic, systematic quality gates are Week 6's, and rolling back what a server actually runs is Week 10's.

## Recommended reading

- **Designing Machine Learning Systems (Huyen), Ch. 6 — experiment tracking & versioning** — *Focus on:* what is worth logging and why "log everything" collapses under its own weight; the distinction between experiment tracking and versioning.
- **MLOps Zoomcamp, Module 2 — Experiment tracking with MLflow** — *Focus on:* the run-comparison workflow and the model-registry walkthrough. Note that older recordings still use the deprecated stage transitions.
- **MLflow docs — Model Registry (concepts and workflow pages)** — *Focus on:* the alias and tag APIs.
- **Practical MLOps (Gift & Deza), Ch. 2** — *Focus on:* treating a model as a packaged, versioned deliverable.
- Optional: **Made With ML — experiment tracking** — *Focus on:* keeping tracking code from crowding out the training code it wraps.

(Full citations and links: `docs/resources.md`.)

## Check yourself

1. You log `f1` as a parameter and `C` as a metric. Both calls succeed. What breaks later, concretely, in each direction?
2. A teammate says "promote it to Production." MLflow 3 has no Production stage. What exactly do you do — and what have you *not* done merely by doing it?
3. `models:/diabetes-classifier@staging` returns a model with test F1 = 0.62. Someone asks which data and which code produced it. List the lookups in order, and name the one link this week cannot supply.
4. Aliases are mutable, so `@champion` pointed at version 2 last month and version 5 today. Does that destroy auditability? What in the registry preserves the history — and what does not?
