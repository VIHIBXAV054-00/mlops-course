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

In Week 2 you logged one run. One run is not an experiment: you cannot rank it, see a trend,
or say which model is the one to use. This week you use the same stack to:

- log runs properly: params and metrics in one call each, tags you can search on, a model
  signature, and plots as artifacts;
- run a sweep: one parent run with one child run per configuration;
- find the best run with a query;
- register the chosen model, promote it with an alias, and roll the alias back;
- trace a model from its alias back to the params, metrics and commit that produced it.

`compose.yaml` is the Week 2 stack, unchanged: every exercise this week is in Python.

## Based on

- **MLflow tracking quickstart:** https://mlflow.org/docs/latest/ml/getting-started/quickstart/
- **Hyperparameter tuning, nested runs and comparing runs:** https://mlflow.org/docs/latest/ml/getting-started/hyperparameter-tuning/
- **Model Registry concepts:** https://mlflow.org/docs/latest/ml/model-registry/
- **Model Registry workflows:** https://mlflow.org/docs/latest/ml/model-registry/workflow/
- **MLflow tracking and run search:** https://mlflow.org/docs/latest/ml/tracking/

**Deviations from the tutorials:**

1. **Aliases instead of stages.** MLflow deprecated model stages (`Staging`, `Production`,
   `transition_model_version_stage`) in version 2.9, and the registry tutorial now uses
   aliases only. This lab promotes with `set_registered_model_alias` and the URI
   `models:/diabetes-classifier@staging`. You will still meet the old API in older blog
   posts.
2. **No Optuna.** The sweep tutorial drives the grid with Optuna. We use a plain `for` loop
   over a small grid, to keep the focus on MLflow.
3. **A remote tracking server, not a local `mlruns/` folder.** We use the Week 2 stack at
   `MLFLOW_TRACKING_URI=http://127.0.0.1:5500`.
4. **`name=` instead of `artifact_path=`** in `log_model`. MLflow 3 deprecates
   `artifact_path`.
5. **The Pima diabetes dataset** instead of the tutorial's toy dataset, so the course keeps
   one running example.

## Prerequisites

- Docker Desktop (macOS, Windows) or Docker Engine with the Compose plugin (Linux), version 24+
- At least 16 GB RAM
- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Ports **5500, 5510, 5511, 5532** free on your computer
- **Stop your Week 2 stack first.** It uses the same ports:
  ```bash
  cd ../../week-02-local-services/starter && docker compose down
  ```

---

## Step 1: dependencies

In this folder (`labs/week-03-mlflow-integration/starter/`), run:

```bash
uv sync --all-groups
```

New this week: **matplotlib**, for the plots in Exercise 2.

## Step 2: configuration

```bash
cp .env.example .env
```

Set `MLFLOW_MODEL_OWNER` to your name: it is recorded as a tag when you promote a model.
Never commit `.env`; it is git-ignored. The file has no Silo keys: your pipeline talks only
to the tracking server, which holds the keys.

## Step 3: tests before you start

```bash
uv run pytest tests/
```

Expected: **21 passed, 14 skipped**.

## Step 4: the stack

```bash
docker compose up -d --wait
```

Expected: all four services report healthy.

| Service | URL | Credentials |
| --- | --- | --- |
| MLflow UI | http://localhost:5500 | none |
| Silo console | http://localhost:5511 | `S3_ACCESS_KEY` / `S3_SECRET_KEY` from `.env` |
| Postgres | `localhost:5532` | `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env` |

The MLflow experiment list is empty: this lab has its own database, so your Week 2 runs do
not appear here.

---

## Exercises

Do them in order. Every `TODO(student)` is in `src/week_03_mlflow_integration/`, and every
exercise has a `make` target. Exercises 4, 6 and 7 ask for a **written answer**: write it in
`answers.md` in this folder and **commit it with your code**. Exercise 7 is optional.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| Tracking | 1–3 | 30 min |
| Choosing | 4 | 15 min |
| Governing | 5–6 | 25 min |
| Finish: commit and submit | — | 5 min |
| Optional: rolling back | 7 | 10 min |
| Finished early? | Stretch | — |

### Exercise 1: log one run properly (≈ 10 min)

Week 2 logged three params with three separate calls. Here you log them in one call, because
each call is one request to the server. You also add tags, which make a run easy to find
later, and a signature, which makes the logged model describe its own input. The
`git_commit` tag links a metric back to the code; Exercise 6 tests how far you can trust
that link.

**Do:**

1. In `src/week_03_mlflow_integration/tracking.py`, fill in blanks 1a–1d of
   `log_training_run`: the params, the tags, the metrics and the model. Each `TODO(student)`
   says what to log.
2. Log one run:
   ```bash
   make run
   ```

**Check:**

- Open the run in the MLflow UI (http://localhost:5500).
  Expected: the params table, five metrics, your tags, and, on the logged model, a
  filled-in **Schema** tab.

**Stuck?**

- Lecture: "Four kinds of metadata, four different jobs" and "Experiment vs. run"
- Notes: "Four kinds of run metadata"
- MLflow docs: https://mlflow.org/docs/latest/ml/tracking/tracking-api/ and
  https://mlflow.org/docs/latest/ml/model/signatures/
- `log_params` and `log_metrics` each take a dict.

### Exercise 2: log two plots as artifacts (≈ 10 min)

A metric says how good a model is; a plot shows where it goes wrong. You draw a ROC curve and
a confusion matrix for each run and store them with the run. Anyone can then open them in
the UI.

**Do:**

1. In `src/week_03_mlflow_integration/plots.py`, implement `roc_curve_figure` and
   `confusion_matrix_figure`. Both return a `Figure` and never call `plt.show()` or
   `plt.savefig()`.
2. In `tracking.py`, fill in blank 2 of `log_training_run`: log both figures.
3. Log a run:
   ```bash
   make run
   ```
   Expected: the run's Artifacts tab shows `plots/roc_curve.png` and
   `plots/confusion_matrix.png`. Read the confusion matrix: how many false positives and
   false negatives did the model make on the test set?

**Check:**

- Delete the Exercise 2 skip markers in `tests/test_plots.py` and the Exercises 1–2 skip
  marker in `tests/test_tracking.py`.
- Run `uv run pytest tests/test_plots.py tests/test_tracking.py`.
  Expected output: `5 passed, 5 skipped`

**Stuck?**

- Lecture: "Logging a plot" and "How to make plots comparable"
- Notes: "Plots are artifacts"
- scikit-learn docs: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.RocCurveDisplay.html
  and https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ConfusionMatrixDisplay.html
- If matplotlib warns that more than 20 figures are open, close each figure after you log
  it.

### Exercise 3: sweep six configurations (≈ 10 min)

One run cannot be ranked. A sweep trains several configurations on the same split. It
records each as a child of one parent run, so you can compare them side by side.
`SWEEP_GRID` is already defined: four regularisation strengths for logistic regression and
two forest sizes.

**Do:**

1. In `tracking.py`, implement the loop in `run_sweep`. The docstring says what the loop
   must produce; the keyword arguments of `log_training_run` say how.
2. Run the sweep:
   ```bash
   make sweep
   ```
3. In the UI, expand the `sweep` run to see its six children, select all six, and click
   **Compare**. Then switch to the **Parallel Coordinates** view.

**Check:**

- Delete the Exercise 3 skip markers in `tests/test_tracking.py`.
- Run `uv run pytest tests/test_tracking.py`.
  Expected output: `3 passed, 3 skipped`

**Stuck?**

- Lecture: "One sweep, many runs" and "Four ways to compare runs in the UI"
- Notes: "Experiments, sweeps, and search"
- MLflow docs: the hyperparameter tuning tutorial (link above)
- If the UI shows seven top-level runs instead of one tree, the children are not nested
  under the parent.

### Exercise 4: choose the winner, and defend the choice (≈ 15 min) *(written answer)*

You rank the six runs with a query. The filter goes to the tracking server, which runs it
in Postgres, so only the matching rows come back. A pandas filter over a full download
would return the same six rows. The difference is what crosses the network, which matters
when an experiment has ten thousand runs.

**Do:**

1. In `tracking.py`, implement `search_sweep_runs`: one `mlflow.search_runs` call whose
   `filter_string` selects the latest sweep's children and whose `order_by` ranks them.
2. Rank the runs by two metrics:
   ```bash
   make best
   make best METRIC=roc_auc
   ```

**Check:**

- Delete the Exercise 4 skip markers in `tests/test_tracking.py`.
- Run `uv run pytest tests/test_tracking.py`.
  Expected output: `5 passed, 1 skipped`

**Stuck?**

- Lecture: "Run search is a query" and "But its syntax has some traps..."
- Notes: "Experiments, sweeps, and search"
- MLflow docs: https://mlflow.org/docs/latest/ml/search/search-runs/
- Tag and param values need single quotes inside the string, and the operator is `=`, not
  `==`.

**Written answer** (in `answers.md`):

1. Do F1 and ROC-AUC pick the same winner? If not, why might two reasonable metrics
   disagree about the same six models?
2. **Pick the run you would promote**, write down its `run_id`, and justify it in two or
   three sentences. There is more than one defensible answer; "it has the highest F1" on its
   own is not one of them. Look at the confusion matrices before you decide.
3. Name one thing MLflow recorded about these runs that you did not have to remember.

You use that `run_id` in Exercise 5 and that justification in Exercise 6.

### Exercise 5: register the run you chose (≈ 10 min)

The registry gives a model a name and numbered versions. A version never changes: to change
a model, you register a new version. You register the run you chose in Exercise 4, twice,
and see the version number go up.

**Do:**

1. In `src/week_03_mlflow_integration/registry.py`, implement `register_best_model`.
2. Register the run you chose, twice:
   ```bash
   make register RUN_ID=<the run_id you chose in Exercise 4>
   make register RUN_ID=<the same run_id>
   ```
   Expected: versions 1 and 2, and a warning that the run "has no artifacts at artifact
   path 'model'". The warning is expected: MLflow 3 stores the model outside the run's
   folder, and the version still links to the run.
3. In the UI's **Models** tab, open a version and follow its **Source run** link back to the
   sweep child it came from.

Without `RUN_ID`, `make register` falls back to the top-F1 run and tells you so. That
default is the decision Exercise 4 asked you not to hand over.

**Check:**

- Delete the Exercise 5 skip marker in `tests/test_registry.py`.
- Run `uv run pytest tests/test_registry.py`.
  Expected output: `1 passed, 5 skipped`

**Stuck?**

- Lecture: "The registry object model" and "Registering a model version"
- Notes: "The registry object model"
- MLflow docs: the Model Registry workflows (link above)
- The `TODO(student)` explains which form of the model URI to use, and why.

### Exercise 6: promote, trace back, and find the broken link (≈ 15 min) *(written answer)*

Promotion does two things, and only the second is an API call. It records the evidence: the
metrics, read back from the source run, who promoted the model, when and why. Then it moves
a pointer: `@staging` and `@champion` resolve to a new version, and the version itself does
not change. Then you walk the chain back from the alias, and find where it breaks.

**Do:**

1. In `registry.py`, implement `promote_to_staging`. Then promote version 2 with your
   Exercise 4 justification:
   ```bash
   make promote VERSION=2 REASON="<your one-sentence justification>"
   ```
2. In the same file, implement `trace_alias`, and run it:
   ```bash
   make trace
   ```
   Expected: the chain alias → version → `run_id` → params, metrics and the `git_commit`
   tag. The last line loads the model through `models:/<name>@staging` and predicts five
   rows, with no Silo keys on your side.
3. Take the last hop, from the commit to the code, yourself:
   ```bash
   git diff --stat <the git_commit that make trace printed> -- .
   git show <git_commit>:./src/week_03_mlflow_integration/registry.py | grep -c "TODO(student)"
   ```
   Read both outputs: compare the code in that commit with the code that ran.
4. Record whether the working tree was clean. In `log_training_run`, record the value of
   `git_dirty()` as a `git_dirty` tag. In `trace_alias`, return it under the key
   `git_dirty`. `git_dirty()` ignores `answers.md`, so writing answers does not make your
   runs dirty.
5. Make the chain true:
   ```bash
   git add . && git commit -m "week03: exercises 1-6"
   make sweep
   make best METRIC=<your metric>
   make register RUN_ID=<the new run_id of the configuration you chose>
   make promote VERSION=3 REASON="<same justification>, retrained from committed code"
   make trace
   git diff --stat <the new git_commit> -- .
   ```
   Expected: line 4 of `make trace` says `clean tree`, and the last command prints nothing.

**Check:**

- Delete the Exercise 6 skip markers in `tests/test_registry.py` and the Exercise 6, part 3
  skip marker in `tests/test_tracking.py`.
- Run `uv run pytest tests/test_tracking.py tests/test_registry.py`.
  Expected output: `10 passed, 2 skipped`

**Stuck?**

- Lecture: "Promotion is a process..." and "Tracing back from the alias"
- Notes: "Promotion and traceability" and "Stages, aliases, and what changed"
- MLflow docs: https://mlflow.org/docs/latest/api_reference/python_api/mlflow.client.html
- Promote with aliases. `transition_model_version_stage` still exists, but it is
  deprecated.

**Written answer** (in `answers.md`):

1. Write the traceability chain as an ordered list of lookups, starting from
   `models:/diabetes-classifier@staging`. What call do you make at each hop?
2. What did the last hop give you in step 3, concretely? What did recording `git_dirty`
   fix, and what does it still not give you?
3. Should `promote_to_staging` **refuse** a version whose source run had `git_dirty=true`?
   Take a side, and name what your choice costs.
4. What can an alias do that a fixed `Staging` stage could not? Give at least two things.
5. Walk the chain as far back as it goes. It ends at a **file path**, `data/diabetes.csv`.
   What does that mean for the metrics you just recorded, and what would you need to close
   that last gap?

### Exercise 7 (optional): roll the alias back (≈ 10 min) *(written answer)*

Suppose version 3 misbehaves in staging. A rollback is the same pointer move as a promotion,
in the other direction, and it must leave a record. This is the registry half of a
rollback; rolling back what a serving system runs is Week 10.

**Do:**

1. In `registry.py`, implement `roll_back`.
2. Roll back to version 1, then to version 2:
   ```bash
   make rollback VERSION=1 REASON="v3 misbehaves in staging"
   make rollback VERSION=2 REASON="v3 misbehaves in staging"
   make trace
   ```
   Expected: the rollback to version 1 is refused, the rollback to version 2 works, and
   `make trace` shows version 2.
3. Look at what the registry itself stores about aliases:
   ```bash
   docker compose exec postgres psql -U mlflow -d mlflowdb \
     -c "SELECT name, alias, version FROM registered_model_aliases;"
   ```

**Check:**

- Delete the Exercise 7 skip markers in `tests/test_registry.py`.
- Run `uv run pytest tests/test_registry.py`.
  Expected output: `6 passed`

**Stuck?**

- Lecture: "Vocabulary of aliases" and "What to use in deployment code: alias or version?"
- Notes: "Stages, aliases, and what changed"
- MLflow docs: the Model Registry workflows (link above)
- Check the target version's `promoted_at` tag before you move anything.

**Written answer** (in `answers.md`):

1. What changed when you rolled back, and what did not? Think of a server that loads
   `models:/diabetes-classifier@champion`.
2. A month from now, how would an auditor learn that version 3 was champion for a while?
   What would they have if `roll_back` did not write tags?
3. Look at line 4 of your last `make trace`. Was version 2 a safe rollback target?

### Stretch: ask your own questions (if you finish early)

`make query` runs any `search_runs` filter across the whole experiment. Answer each with a
single query, and put the query strings in `answers.md`:

1. Every forest with recall above 0.55, best ROC-AUC first.
   (`make query FILTER="..." ORDER_BY="metrics.roc_auc DESC"`)
2. Every run logged from a dirty working tree. Why can this query never find the runs from
   before Exercise 6, step 4, although every one of them was logged from uncommitted code?
3. Add a tag to one run by hand in the UI, then find it with a query.

## Finish: commit and submit your work (≈ 5 min)

1. Run `uv run pytest tests/` with the stack up.
   Expected output: `33 passed, 2 skipped`, or `35 passed` if you did Exercise 7.
2. Commit your work:
   ```bash
   git status          # answers.md must appear; .env and .venv/ must not
   git add .
   git commit -m "week03: registry, written answers"
   ```
3. Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
   and upload that URL to Moodle.

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
It is why registering from `runs:/<run_id>/model` prints the warning in the troubleshooting table below.

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
| `UserWarning: Hint: Inferred schema contains integer column(s)` | Expected. `infer_signature` notices that integer columns cannot carry missing values. Our dataset hides its missing values as zeros until Week 5. Leave it alone. |
| Nothing appears in the MLflow UI | Confirm the stack is healthy (`docker compose ps`) and that `MLFLOW_TRACKING_URI` in `.env` is `http://127.0.0.1:5500`. |
| `RuntimeWarning: More than 20 figures have been opened` | You are missing `plt.close(figure)` after each `mlflow.log_figure` — the sweep opens 12 figures. |
| Want to start completely over | `docker compose down -v && docker compose up -d --wait`. This wipes both the Postgres metadata and the Silo artifacts. |

## Next steps

Walk your traceability chain all the way back and it stops at `data/diabetes.csv` — a
**path**. Nothing you recorded this week says which data was in that file.
Edit one row and every metric above becomes obsolete. Week 4 closes that gap with DVC:
dataset snapshots tracked by content hash, Silo as the storage remote, and a data version
linked to each MLflow run.
