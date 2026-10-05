# Week 3 Lab — Reference Solution

The complete, runnable version of the Week 3 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_03_mlflow_integration/tracking.py` | 1 | `log_training_run` implemented: batched `log_params`, `set_tags` (incl. `git_commit`), `log_metrics`, and `log_model(name=..., signature=..., input_example=...)` |
| `src/week_03_mlflow_integration/plots.py` | 2 | `roc_curve_figure` and `confusion_matrix_figure` implemented with `RocCurveDisplay` / `ConfusionMatrixDisplay` |
| `src/week_03_mlflow_integration/tracking.py` | 2 | both figures logged via `mlflow.log_figure`, each followed by `plt.close` |
| `src/week_03_mlflow_integration/tracking.py` | 3 | `run_sweep` loop implemented — one `nested=True` child run per `SWEEP_GRID` cell |
| `src/week_03_mlflow_integration/tracking.py` | 4 | `search_sweep_runs` implemented: `filter_string` scoped to the latest sweep's children via `tags.mlflow.parentRunId`, `order_by` on the chosen metric |
| `src/week_03_mlflow_integration/registry.py` | 5 | `register_best_model` implemented, registering from `runs:/<run_id>/model` |
| `src/week_03_mlflow_integration/registry.py` | 6 | `promote_to_staging` (5 version tags incl. `promotion_reason`, 2 registered-model tags, `staging` and `champion` aliases) and `trace_alias` (the four-hop walk-back) implemented |
| `src/week_03_mlflow_integration/tracking.py`, `registry.py` | 6, part 3 | `git_dirty` recorded as a run tag and returned by `trace_alias` |
| `src/week_03_mlflow_integration/registry.py` | 7 | `roll_back` implemented: two guards, three rollback tags on the demoted version, both aliases moved |
| `src/week_03_mlflow_integration/cli.py` | — | the starter's "not implemented yet" guards removed |
| `tests/test_plots.py` | 2 | 2 `@pytest.mark.skip` markers removed |
| `tests/test_tracking.py` | 1, 3, 4, 6 | 6 `@pytest.mark.skip` markers removed |
| `tests/test_registry.py` | 5, 6, 7 | 6 `@pytest.mark.skip` markers removed |
| `compose.yaml` | — | `name: week03-mlflow-integration` (the starter uses `-starter`, so the two never share volumes) |

Everything else — `compose.yaml` service bodies, `mlflow.Dockerfile`, `bootstrap.sh`,
`config.py`, `data.py`, `model.py`, `Makefile`, `.env.example` — is identical to the starter.

## Running the solution

```bash
# 1. Stop any other lab stack — they all share the 55xx host ports
cd ../../week-02-local-services/solution && docker compose down; cd -

# 2. Install dependencies (uv.lock is committed)
uv sync --all-groups

# 3. Configuration
cp .env.example .env

# 4. Bring up the four-service stack
docker compose up -d --wait

# 5. Exercises 1-6 end to end
make all
```

## Expected output — `make all` (seed 42, empty database, clean tree)

MLflow's `🏃 View run ...` / `🧪 View experiment ...` progress lines and its INFO/WARNING log
lines are omitted below.

`make all` takes every default: it registers the top-F1 run and promotes the newest version,
and says so. Those defaults are exactly the choices Exercises 4–6 ask students to make
themselves, so their registry will not look like this one (see the next section). Captured
from a **committed** working tree, which is why line 4 of the trace reads "clean tree".

```
Week 3 — MLflow experiment tracking and model registry
======================================================
Dataset:          diabetes.csv (768 patients)
Diabetes rate:    34.9%
Random seed:      42
Tracking server:  http://127.0.0.1:5500
Experiment:       diabetes-week3
Registered model: diabetes-classifier

── Exercise 1-2: one fully-logged run ──
Run name:  logreg-C=1.0
Run ID:    7ca37dd9aeb04b1eb03750c950847fb7
Metrics:
{
  "accuracy": 0.7344,
  "precision": 0.6481,
  "recall": 0.5224,
  "f1": 0.5785,
  "roc_auc": 0.832
}

Open the run: http://127.0.0.1:5500
  -> the Artifacts tab has plots/roc_curve.png and
     plots/confusion_matrix.png; the model has a populated Schema tab.

── Exercise 3: sweeping 6 configurations ──
  logreg-C=0.01              f1=0.5047  roc_auc=0.8208
  logreg-C=0.1               f1=0.5714  roc_auc=0.8301
  logreg-C=1.0               f1=0.5785  roc_auc=0.8320
  logreg-C=10.0              f1=0.5785  roc_auc=0.8318
  rf-n_estimators=100        f1=0.6066  roc_auc=0.8150
  rf-n_estimators=300        f1=0.6240  roc_auc=0.8166

6 child runs logged under one parent run.
In the UI: select all the children -> Compare -> Parallel Coordinates.

── Exercise 4: the latest sweep, ranked by f1 ──
                          run_id tags.mlflow.runName params.model_family params.C params.n_estimators  metrics.f1  metrics.roc_auc  metrics.accuracy  metrics.recall
8c1205c613724241bd622218ed294e32 rf-n_estimators=300                  rf        -                 300      0.6240           0.8166            0.7552          0.5821
363ffec414184172b43ea21c1a494140 rf-n_estimators=100                  rf        -                 100      0.6066           0.8150            0.7500          0.5522
001979b882684ef289f64c59991fd4fe       logreg-C=10.0              logreg     10.0                   -      0.5785           0.8318            0.7344          0.5224
6d9c6715bc3042c9846bcc44e503bf7d        logreg-C=1.0              logreg      1.0                   -      0.5785           0.8320            0.7344          0.5224
e3cee722d975476f8d346436c892d6ea        logreg-C=0.1              logreg      0.1                   -      0.5714           0.8301            0.7344          0.5075
1199879035764d78b95469b3f94f0835       logreg-C=0.01              logreg     0.01                   -      0.5047           0.8208            0.7240          0.4030

Top by f1: 8c1205c613724241bd622218ed294e32
Register the run YOU chose: make register RUN_ID=<run_id>

── Exercise 5: register a run's model ──
No RUN_ID given, so registering the top-F1 run by default.
Exercise 4 asked whether that is the right choice: make register RUN_ID=<id>
Registered:  diabetes-classifier
Version:     1
Source run:  8c1205c613724241bd622218ed294e32

── Exercise 6: promote to @staging ──
No VERSION given, so promoting the newest one (version 1).
No REASON given. Record why: make promote VERSION=<n> REASON="..."
Version 1 now carries aliases: ['champion', 'staging']
Governance tags:
{
  "registered_from": "week3-sweep",
  "validation_f1": "0.6240",
  "validation_roc_auc": "0.8166",
  "promoted_by": "your-name",
  "promoted_at": "2026-09-22T20:37:04+00:00"
}

── Exercise 6: traceability walk-back ──
1. Model URI:   models:/diabetes-classifier@staging
2. Version:     1  (aliases: ['champion', 'staging'])
3. Run ID:      8c1205c613724241bd622218ed294e32  (rf-n_estimators=300)
4. Git commit:  87399fb  (clean tree: this commit IS the code that ran)
5. Params that produced it:
{
      "model_family": "rf",
      "random_seed": "42",
      "test_size": "0.25",
      "max_iter": "1000",
      "data_path": "diabetes.csv",
      "n_rows": "768",
      "n_estimators": "300"
}
   Version tags (the promotion evidence):
{
      "registered_from": "week3-sweep",
      "validation_f1": "0.6240",
      "validation_roc_auc": "0.8166",
      "promoted_by": "your-name",
      "promoted_at": "2026-09-22T20:37:04+00:00"
}

Take hop 4 yourself:  git diff --stat 87399fb -- .

Loaded via the alias and predicted 5 rows: [0, 0, 0, 0, 1]
```

Run IDs, the `promoted_at` timestamp, and `git_commit` will differ on your machine.
**Every metric above is deterministic** and should reproduce exactly.

## The student path, measured

Measured by working through the starter in a scratch clone, from uncommitted code, the way a
student does during the session. The student defends the ROC-AUC winner, `logreg-C=1.0`.

| Step | Command | Result |
| --- | --- | --- |
| Ex 5 | `make register RUN_ID=<logreg-C=1.0>` twice | versions 1 and 2, same source run |
| Ex 6.1 | `make promote VERSION=2 REASON="..."` | `@staging` and `@champion` on version 2 |
| Ex 6.2 | `make trace` | line 4: `tree state not recorded` |
| Ex 6.2 | `git diff --stat <git_commit> -- .` | `plots.py`, `registry.py`, `tracking.py` differ |
| Ex 6.2 | `git show <git_commit>:./src/.../{tracking,registry,plots}.py \| grep -c "TODO(student)"` | **11 / 4 / 2**: the recorded commit is the starter |
| Ex 6.3 | commit, `make sweep`, register the new `logreg-C=1.0` run, `make promote VERSION=3` | line 4: `clean tree`; `git diff --stat` prints nothing |
| Ex 7 | `make rollback VERSION=1 REASON="..."` | `Refused: Version 1 was never promoted` (exit 1, aliases unchanged) |
| Ex 7 | `make rollback VERSION=2 REASON="..."` | both aliases on version 2; version 3 tagged `rolled_back_at` / `rolled_back_to` / `rollback_reason` |
| Ex 7 | `make trace` | back on version 2, line 4: `tree state not recorded` |
| Ex 7 | `SELECT name, alias, version FROM registered_model_aliases;` | two rows, both version 2: no timestamp, no history |

Wall-clock on an Apple-silicon laptop with the images already built: `make run` 5.8 s,
`make sweep` 8.5 s, `make trace` 3.4 s; `docker compose up -d --wait` 18 s. The session time
goes on reading, deciding and writing, not on waiting.

### The two pinned baselines are inside the sweep

`logreg-C=1.0` and `rf-n_estimators=100` use scikit-learn's defaults, so they reproduce the
Week 1 / Week 2 reference metrics exactly:

| Cell | F1 | Accuracy | Matches |
| --- | --- | --- | --- |
| `logreg-C=1.0` | 0.5785 | 0.7344 | Week 1/2 logistic-regression baseline |
| `rf-n_estimators=100` | 0.6066 | 0.7500 | Week 1 Exercise 2 random-forest baseline |

`tests/test_tracking.py::test_sweep_preserves_locked_baseline` asserts both. If it fails,
the dataset, the split, or the pipeline changed unintentionally.

### The two metrics disagree — on purpose

F1 ranks `rf-n_estimators=300` first (0.6240); ROC-AUC ranks `logreg-C=1.0` first (0.8320).
This is the substance of the Exercise 4 written answer, and it is not manufactured — it falls
out of the grid. Also worth noting: the F1 winner's recall is 0.5821, so it still misses over
40% of diabetic patients.

## Expected results — `uv run pytest tests/ -v`

| Command | Stack | Result |
| --- | --- | --- |
| `make test` | up | **35 passed** |
| `make test` | down | **23 passed, 12 skipped** (the `live` tests self-skip via the `live_settings` fixture) |
| `make test-fast` | either | **23 passed, 12 deselected** |
| `uv run pytest tests/ -v` in `starter/` | either | **21 passed, 14 skipped** |

The suite is safe to run repeatedly against the same database: searches are scoped to the
latest sweep, and the rollback tests use their own registered model.

The 7 warnings are `infer_signature`'s hint that integer columns cannot carry missing values.
That is our dataset's disguised-zeros quirk, left untreated until Week 5 by design.

The `live` fixtures write to `diabetes-week3-tests` and `diabetes-classifier-tests`, so running
the suite never pollutes the experiment or inflates the version numbers you are grading.

## Verifying the storage split in Silo

```bash
docker compose exec s3 sh -c \
  'mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null && \
   mc ls --recursive local/mlflow-artifacts'
```

Run artifacts and model artifacts land in **different prefixes** — worth showing students
directly, because it explains the registration warning:

```
1/<run_id>/artifacts/plots/confusion_matrix.png            <- mlflow.log_figure
1/<run_id>/artifacts/plots/roc_curve.png
1/models/m-<32hex>/artifacts/MLmodel                       <- mlflow.sklearn.log_model
1/models/m-<32hex>/artifacts/model.pkl
1/models/m-<32hex>/artifacts/conda.yaml
1/models/m-<32hex>/artifacts/python_env.yaml
1/models/m-<32hex>/artifacts/requirements.txt
1/models/m-<32hex>/artifacts/input_example.json
1/models/m-<32hex>/artifacts/serving_input_example.json
```

`model.pkl` (not `model.skops`) because `mlflow==3.13.0` defaults
`serialization_format` to `cloudpickle`. The filename is version-dependent, which is one
reason the client and server pins move together.

## Verifying the registry in Postgres

```bash
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT name, version, run_id, current_stage FROM model_versions;" \
  -c "SELECT name, alias, version FROM registered_model_aliases;"
```

`run_id` must be non-empty: it is hop 2 of the traceability walk. On `mlflow==3.13.0` both
`runs:/<run_id>/model` and the `models:/m-<id>` URI that `log_model` returns record it
(measured). A version created from a bare artifact path would not. Note that `current_stage` still exists as a
column (legacy schema) and is irrelevant: promotion lives in `registered_model_aliases`.

## The expected registration warning

`make register` prints this, and it is **not** an error:

```
WARNING mlflow.tracking._model_registry.fluent: Run with id 30b3dfb252fc4ff9adacf878c6ecbf75
has no artifacts at artifact path 'model', registering model based on
models:/m-bc6a853a0163483cbf47d35ff3777ce5 instead
```

MLflow 3 stores logged-model files outside the run's artifact root, so the `runs:/` path
resolves indirectly. The version is still created, `run_id` is still recorded, and the
Source-run link in the UI still works. Pre-empt this in the lab session — otherwise every
student reports it as a bug.

## Tear-down

```bash
docker compose down      # stop; runs persist in the named volumes
docker compose down -v   # stop AND wipe volumes for a from-scratch re-run
```

---

> Model answers and the grading rubric are kept instructor-only in
> `.agents/grading/week-03.md` (not shipped with student or solution releases).
