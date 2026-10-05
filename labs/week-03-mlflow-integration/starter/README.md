---
description:
  title: "Week 3 Lab: MLflow Integration"
  summary: |
    Use the Week 2 stack properly: structured logging with plots as artifacts,
    a parameter sweep producing comparable runs, server-side run search, and the
    model registry — registering a version, promoting it with an alias, and
    walking the traceability chain back to the params that produced it.
---

# Week 3 Lab: MLflow Integration

Week 2 built the infrastructure and proved it worked by logging **one** run. One run
is not an experiment: you cannot rank it, you cannot see a trend, and you cannot say
which model is *the* model.

This week you use MLflow as an engineering discipline:

- **structured logging** — batched params and metrics, tags you can search on, a
  model signature, and diagnostic plots stored as artifacts
- **a parameter sweep** — one parent run with one child run per configuration
- **run search** — finding the winner with a query
- **the model registry** — a named model, immutable versions, and a movable alias
- **traceability** — walking backwards from a deployed alias to the exact params,
  metrics, and git commit that produced it

The infrastructure does not change at all. `compose.yaml` is the Week 2 stack — **every exercise this week is in Python.**

## Based on

This lab follows official tutorials with minimal changes — keep them open as references:

- **MLflow tracking quickstart (primary template):** https://mlflow.org/docs/latest/ml/getting-started/quickstart/
- **Hyperparameter tuning — nested runs and comparing runs:** https://mlflow.org/docs/latest/ml/getting-started/hyperparameter-tuning/
- **Model Registry concepts:** https://mlflow.org/docs/latest/ml/model-registry/
- **Model Registry workflows:** https://mlflow.org/docs/latest/ml/model-registry/workflow/
- **MLflow tracking concepts and run search:** https://mlflow.org/docs/latest/ml/tracking/

**Required deviations from the official tutorials**:

1. **Aliases instead of stages.** MLflow deprecated model *stages* (`None`/`Staging`/`Production`/`Archived` and
   `transition_model_version_stage`) in version 2.9, and the official registry tutorial
   now uses **aliases** exclusively. This lab therefore promotes with
   `set_registered_model_alias` and the URI `models:/diabetes-classifier@staging`.
   You will meet the old API in older blog posts and tutorial videos.
2. **No Optuna.** The official sweep tutorial drives the grid with Optuna; we use a plain
   `for` loop over a small grid to minimise dependencies and keep the focus on MLflow.
3. **A remote tracking server, not a local `mlruns/` directory.** We point at the
   containerized Week 2 stack via `MLFLOW_TRACKING_URI=http://127.0.0.1:5500`.
4. **`name=` instead of `artifact_path=`** in `log_model`. MLflow 3 deprecates
   `artifact_path`.
5. **The Pima diabetes dataset** instead of the tutorial's toy dataset, per the course's
   one-running-example rule.

## Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine + Compose plugin (Linux) — version 24+
- At least 16 GB RAM
- `uv` — https://docs.astral.sh/uv/getting-started/installation/
- Ports **5500, 5510, 5511, 5532** free on your host (the 55xx block; see `.env.example`)
- **Stop your Week 2 stack first.** It uses the same host ports:
  ```bash
  cd ../../week-02-local-services/starter && docker compose down
  ```

---

## Step 1 — Install Python dependencies

From this directory (`labs/week-03-mlflow-integration/starter/`):

```bash
uv sync --all-groups
```

New this week: **matplotlib**, for the diagnostic plots in Exercise 2.

## Step 2 — Create your local configuration

```bash
cp .env.example .env
```

Read the new `MLFLOW_REGISTERED_MODEL_NAME` / `MLFLOW_MODEL_ALIAS` / `MLFLOW_MODEL_OWNER`
block at the bottom, and set `MLFLOW_MODEL_OWNER` to your own name — it gets recorded as a
governance tag when you promote a model. **Never commit `.env`** — it is git-ignored.

Notice what is *absent* from the client config: any `AWS_*` credentials. Your pipeline
talks only to the tracking server, which holds the Silo keys and proxies artifacts on your
behalf.

## Step 3 — Run the tests (no stack required)

```bash
uv run pytest tests/ -v
```

Expected: **21 passed, 14 skipped**. Each skipped test names the exercise that unlocks it —
implement the code, delete that test's `@pytest.mark.skip` line, and the test becomes your
check that you got it right.

## Step 4 — Bring up the stack

```bash
docker compose up -d --wait
```

This is the Week 2 stack, unchanged. All four services must report healthy.

| Service | URL | Credentials |
| --- | --- | --- |
| MLflow UI | http://localhost:5500 | none |
| Silo console | http://localhost:5511 | `S3_ACCESS_KEY` / `S3_SECRET_KEY` from `.env` |
| Postgres | `localhost:5532` | `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env` |

The MLflow experiment list should be **empty**. This lab is a separate Compose project with
its own database volume, so none of your Week 2 runs appear here.

---

## Exercises

Complete these in order — each builds on the previous. Every exercise has a `make` target,
and every `TODO(student)` is in `src/week_03_mlflow_integration/`.

The first two exercises spell out the API calls, because the API is new. From Exercise 3 on,
the TODOs state **what** the code must do and link the reference page; working out **how**
is the exercise. The tests say when you are right.

Three exercises ask for a **written answer**. Put those in a file called `answers.md` in this
directory, and **commit it with your code**. It is part of your submission, and it is read
alongside your solution.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| Tracking | 1–3 | 30 min |
| Choosing | 4 | 15 min |
| Governing | 5–6 | 25 min |
| Rolling back | 7 | 10 min |
| Finished early? | Stretch | — |

### Exercise 1 — Log one run properly

Open `src/week_03_mlflow_integration/tracking.py` and fill in the four blanks in
`log_training_run`: `log_params`, `set_tags`, `log_metrics`, and `log_model`.

Week 2 logged three params with three separate `log_param` calls. Here you log them in one
batched call, because one call is one HTTP round-trip and three calls are three. You also add
two new things:

- **tags** — free-form labels. Params exist so someone can *reproduce* a run; tags exist so
  someone can *find* it. The `git_commit` tag links a recorded metric back to the code —
  Exercise 6 tests how far that link can be trusted.
- **a signature and input example** — these make the logged model self-describing.

```bash
make run
```

Then open the run in the UI. Confirm you see a populated params table, five metrics, your
tags, and — on the logged model — a filled-in **Schema** tab.

### Exercise 2 — Log two plots as artifacts

Implement `roc_curve_figure` and `confusion_matrix_figure` in
`src/week_03_mlflow_integration/plots.py`, then log them from `log_training_run` with
`mlflow.log_figure`.

Both functions **return** a `Figure` and never call `plt.show()` or `plt.savefig()`.

```bash
make run
```

In the UI, the run's Artifacts tab should show `plots/roc_curve.png` and
`plots/confusion_matrix.png`, rendered inline. Read the confusion matrix: how many false
positives and false negatives did your model make on the test set?

### Exercise 3 — Sweep six configurations

Implement the loop in `run_sweep` (`tracking.py`). `SWEEP_GRID` is already defined: four
regularisation strengths for logistic regression and two forest sizes. The docstring says
what the loop must produce; `log_training_run`'s keyword arguments are how.

```bash
make sweep
```

In the UI: expand the `sweep` run to see its six children, select all six, and click
**Compare**. Then switch to the **Parallel Coordinates** view.

### Exercise 4 — Choose the winner, and defend the choice *(written answer)*

Implement `search_sweep_runs` in `tracking.py`: one `mlflow.search_runs` call whose
`filter_string` selects the latest sweep's children and whose `order_by` ranks them.
Syntax reference: https://mlflow.org/docs/latest/ml/search/search-runs/

```bash
make best                  # ranked by F1
make best METRIC=roc_auc   # the same six runs, ranked by ROC-AUC
```

The filter string is sent to the tracking server, which evaluates it against Postgres, so
only the matching rows come back. You cannot see that from the result: a pandas filter
over a full download would return the same six rows. The difference is what crosses the
network, and it matters when an experiment has ten thousand runs rather than seven.

**Written answer** (in `answers.md`):

1. Do F1 and ROC-AUC pick the same winner? If not, why might two reasonable metrics
   disagree about the same six models?
2. **Pick the run you would promote**, write down its `run_id`, and justify it in two or
   three sentences. There is more than one defensible answer; "it has the highest F1" on its
   own is not one of them. Look at the confusion matrices before you decide.
3. Name one thing MLflow recorded about these runs that you did not have to remember.

You will use that `run_id` in Exercise 5 and that justification in Exercise 6.

### Exercise 5 — Register the run you chose

Implement `register_best_model` in `src/week_03_mlflow_integration/registry.py`.

```bash
make register RUN_ID=<the run_id you chose in Exercise 4>
make register RUN_ID=<the same run_id>    # a second time
```

You now have versions **1** and **2**, from the same run. Versions are immutable and
monotonic: you never edit version 1, you register version 2. In the UI's **Models** tab,
open a version and follow its **Source run** link back to the sweep child it came from.

(Without `RUN_ID`, `make register` falls back to the top-F1 run and tells you so. That
default is exactly the decision Exercise 4 asked you not to delegate.)

### Exercise 6 — Promote, trace back, and find the broken link *(written answer)*

**Part 1 — promote.** Implement `promote_to_staging` in `registry.py`, then promote
version 2, recording your Exercise 4 justification as evidence:

```bash
make promote VERSION=2 REASON="<your one-sentence justification>"
```

Promotion does two separable things, and only the second is an API call:

1. It records the **evidence**: the validation metrics (read back from the source run, so
   the tag cannot drift from what was measured), who promoted it, when, and why.
2. It **moves a pointer**. The version does not change. `@staging` and `@champion` simply
   resolve somewhere new. Both names are ours; neither is built into MLflow.

**Part 2 — trace, and take the last hop yourself.** Implement `trace_alias`, then:

```bash
make trace
```

It walks backwards: alias → version → `run_id` → params, metrics, and the `git_commit`
tag. The last line loads the model through `models:/<name>@staging` and predicts five
rows, with no object-store credentials on your side.

Hop 4 — from the commit to the code — is not MLflow's job. It is yours. Take it:

```bash
git diff --stat <the git_commit that make trace printed> -- .
```

Read the output. Then count the unfinished exercises in the code that commit contains:

```bash
git show <git_commit>:./src/week_03_mlflow_integration/registry.py | grep -c "TODO(student)"
```

**Part 3 — fix it.** A commit hash is only evidence if the working tree was clean when the
run was logged. (Edits to `answers.md` do not count: `git_dirty()` ignores that one file, so
you can keep writing answers without dirtying your runs.) `tracking.py` already has a `git_dirty()` helper. Record its value as a
`git_dirty` tag in `log_training_run`, and return it from `trace_alias` under the key
`git_dirty`. Delete the Exercise 6 part 3 skip marker in `tests/test_tracking.py`. Then make
the chain true:

```bash
git add . && git commit -m "week03: exercises 1-6"
make sweep
make best METRIC=<your metric>    # same configuration, new run_id
make register RUN_ID=<the new run_id of the configuration you chose>
make promote VERSION=3 REASON="<same justification>, retrained from committed code"
make trace                        # line 4 should now say: clean tree
git diff --stat <the new git_commit> -- .    # prints nothing
```

**Written answer** (in `answers.md`):

1. Write the traceability chain as an ordered list of lookups, starting from
   `models:/diabetes-classifier@staging`. What call do you make at each hop?
2. What did hop 4 give you in Part 2, concretely? What did recording `git_dirty` fix, and
   what does it still not give you?
3. Should `promote_to_staging` **refuse** a version whose source run had `git_dirty=true`?
   Take a side, and name what your choice costs.
4. What can an alias do that a fixed `Staging` stage could not? Give at least two things.
5. Walk the chain as far back as it goes. It ends at a **file path** — `data/diabetes.csv`.
   What does that mean for the metrics you just recorded, and what would you need in order
   to close that last gap?

### Exercise 7 — Roll the alias back *(written answer)*

Suppose version 3 misbehaves once it is in staging. Implement `roll_back` in `registry.py`,
then try to roll back to version 1, and then to version 2:

```bash
make rollback VERSION=1 REASON="v3 misbehaves in staging"   # refused — why?
make rollback VERSION=2 REASON="v3 misbehaves in staging"
make trace
```

Now look at what the registry itself stores about aliases:

```bash
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT name, alias, version FROM registered_model_aliases;"
```

**Written answer** (in `answers.md`):

1. What changed when you rolled back, and what did not? Think of a server that loads
   `models:/diabetes-classifier@champion`.
2. A month from now, how would an auditor learn that version 3 was champion for a while?
   What would they have if `roll_back` did not write tags?
3. Look at line 4 of your last `make trace`. Was version 2 a safe rollback target?

(This is the registry half of a rollback. Rolling back what a serving system actually runs
is Week 10.)

### Stretch — ask your own questions *(if you finish early)*

`make query` runs any `search_runs` filter across the whole experiment. Answer each with a
single query, and put the query strings in `answers.md`:

1. Every forest with recall above 0.55, best ROC-AUC first.
   (`make query FILTER="..." ORDER_BY="metrics.roc_auc DESC"`)
2. Every run logged from a dirty working tree. Why can this query never find the runs from
   before Part 3, even though every one of them was logged from uncommitted code?
3. Add a tag to one run by hand in the UI, then find it with a query.

### Finish — commit your work

```bash
git status          # answers.md must appear; .env and .venv/ must NOT
git add labs/week-03-mlflow-integration/starter
git commit -m "week03: roll back, written answers, and the stretch queries"
```

---

## Where the artifacts actually live

Open the Silo console (http://localhost:5511) and browse the `mlflow-artifacts` bucket.
Run artifacts and model artifacts sit in **different prefixes**:

```
mlflow-artifacts/
  <experiment_id>/
    <run_id>/artifacts/plots/roc_curve.png            <- mlflow.log_figure
    <run_id>/artifacts/plots/confusion_matrix.png        (a RUN artifact)
    models/m-<32 hex chars>/artifacts/MLmodel          <- mlflow.sklearn.log_model
    models/m-<32 hex chars>/artifacts/model.pkl           (a first-class logged model,
    models/m-<32 hex chars>/artifacts/requirements.txt     addressable independently of
    models/m-<32 hex chars>/artifacts/python_env.yaml      the run that produced it)
    models/m-<32 hex chars>/artifacts/input_example.json
```

In MLflow 3 a logged model is its own entity, not a folder inside a run.
It is exactly why registering from `runs:/<run_id>/model` prints the warning in the troubleshooting table below.

## Tear-down

```bash
docker compose down      # stop; your runs persist in the named volumes
docker compose down -v   # stop AND wipe the volumes for a from-scratch re-run
```

## Repository structure

```
starter/
├── compose.yaml                    # the Week 2 stack, complete — no TODOs here
├── mlflow.Dockerfile               # pinned MLflow server image
├── Makefile                        # one target per exercise
├── bootstrap.sh                    # one-time uv lock (already committed)
├── .env.example                    # copy to .env
├── pyproject.toml / uv.lock        # + matplotlib, new this week
├── data/diabetes.csv
├── src/
│   ├── main.py
│   └── week_03_mlflow_integration/
│       ├── config.py               # + registry settings (complete)
│       ├── data.py                 # unchanged from Weeks 1-2
│       ├── model.py                # + build_model, + roc_auc (complete)
│       ├── plots.py                # TODO: Exercise 2
│       ├── tracking.py             # TODO: Exercises 1, 3, 4, 6 (part 3)
│       ├── registry.py             # TODO: Exercises 5, 6, 7
│       └── cli.py                  # the subcommand dispatcher (complete)
└── tests/
    ├── conftest.py                 # the "is the stack up?" guard, as fixtures
    ├── test_cli.py                 # 5 tests, no stack needed
    ├── test_config.py              # 7 tests, no stack needed
    ├── test_smoke.py               # 7 tests, no stack needed
    ├── test_plots.py               # 4 tests, no stack needed
    ├── test_tracking.py            # 6 tests, needs the stack
    └── test_registry.py            # 6 tests, needs the stack
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Bind for 0.0.0.0:5500 failed: port is already allocated` | Your Week 2 stack (or another Week 3 stack) is still running. `cd ../../week-02-local-services/starter && docker compose down`. Only one stack can hold the 55xx ports at a time. |
| `WARNING ... Run with id ... has no artifacts at artifact path 'model', registering model based on models:/m-... instead` | **Expected, not an error.** MLflow 3 stores logged-model files outside the run's artifact root (see the layout above). Your version is still created and its Source-run link still works. |
| `make trace` says **tree state not recorded** or **DIRTY** | Expected until Exercise 6 part 3, and a true statement: the runs were logged from uncommitted code. Commit, re-run the sweep, and register the new run. |
| `Refused: Version N was never promoted` | Expected in Exercise 7. A version that never passed promotion is not a known-good rollback target. |
| `make best` returns no rows even though the sweep ran | Check the `filter_string` quoting: tag and param values need single quotes *inside* the Python string (`tags.sweep = 'week3-baseline'`), the operator is `=` not `==`, and metric comparisons are bare numbers (`metrics.f1 > 0.5`). |
| `make best` shows twelve rows, or rows from an old sweep | The filter is not scoped to the latest sweep's children. Every `make sweep` adds six more. |
| `MlflowException: Could not find experiment with name ...` | Run `make sweep` before `make best` — the experiment is created on first write. |
| `UserWarning: Hint: Inferred schema contains integer column(s)` | Expected. `infer_signature` notices that integer columns cannot carry missing values. Our dataset hides its missing values as zeros — deliberately, until Week 5. Leave it alone. |
| Nothing appears in the MLflow UI | Confirm the stack is healthy (`docker compose ps`) and that `MLFLOW_TRACKING_URI` in `.env` is `http://127.0.0.1:5500`. |
| `RuntimeWarning: More than 20 figures have been opened` | You are missing `plt.close(figure)` after each `mlflow.log_figure` — the sweep opens 12 figures. |
| Want to start completely over | `docker compose down -v && docker compose up -d --wait`. This wipes both the Postgres metadata and the Silo artifacts. |

## Next steps

Walk your traceability chain all the way back and it stops at `data/diabetes.csv` — a
**path**. Nothing you recorded this week says which bytes were in that file.
Edit one row and every metric above becomes obsolete. Week 4 closes that gap with DVC:
dataset snapshots tracked by content hash, Silo as the storage remote, and a data version
linked to each MLflow run.
