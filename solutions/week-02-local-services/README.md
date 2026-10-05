# Week 2 Lab — Reference Solution

Completed reference solution for all five exercises.
Instructors can use it to verify student submissions.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `compose.yaml` | 1 | `s3` service: filled image, command, environment, volume, healthcheck |
| `compose.yaml` | 1 | `s3-create-bucket`: filled image and bucket-creation entrypoint |
| `compose.yaml` | 2 | `mlflow` service: filled `MLFLOW_S3_ENDPOINT_URL`, `AWS_*` env, `--backend-store-uri`, `--artifacts-destination`, `--allowed-hosts` |
| `src/week_02_local_services/cli.py` | 3 | Added `mlflow.set_tracking_uri`, `mlflow.set_experiment`, `mlflow.start_run()`, `log_param`, `log_metric`, `log_model` |
| `tests/test_smoke.py` | 3 | `test_mlflow_run_logged` changed from `@pytest.mark.skip` to a reachability-guarded live test |

## Running the solution

```bash
# 1. Create your local config
cp .env.example .env

# 2. Install Python dependencies (requires Python 3.12+)
uv sync --all-groups

# 3. Bring up the full stack (first run pulls images — ~2 min)
docker compose up -d --wait

# 4. Run the pipeline (logs one tracked run)
uv run python src/main.py

# 5. Open the UIs
#    MLflow:   http://localhost:5500
#    Silo:    http://localhost:5511  (login: values from .env)

# 6. Run tests (no stack required for first 5; test_mlflow_run_logged needs the stack)
uv run pytest tests/ -v

# 7. Tear down
docker compose down        # keeps data in volumes
docker compose down -v     # wipes volumes (fresh start)
```

---

## Expected output — `uv run python src/main.py` (seed 42)

```
Week 2 — Diabetes prediction pipeline
======================================
Dataset:        diabetes.csv (768 patients)
Diabetes rate:  34.9%
Random seed:    42
Training rows:  576
Test rows:      192

Logistic Regression metrics:
{
  "accuracy": 0.7344,
  "precision": 0.6481,
  "recall": 0.5224,
  "f1": 0.5785
}

Run logged to:  http://127.0.0.1:5500
Experiment:     diabetes-week2
Run ID:         <32-character hex run ID>

Open the MLflow UI:     http://127.0.0.1:5500
Open the Silo console: http://127.0.0.1:5511
```

**Seed-42 metrics (consistent with Week 1):**
- LR accuracy: 0.7344
- LR F1: 0.5785

The run ID will differ between runs, but the metrics are deterministic given seed 42.

---

## Expected output — `uv run pytest tests/ -v` (stack running)

```
tests/test_config.py::test_settings_defaults PASSED
tests/test_config.py::test_load_settings_returns_valid_settings PASSED
tests/test_config.py::test_invalid_test_size_rejected PASSED
tests/test_config.py::test_mlflow_tracking_uri_overridable PASSED
tests/test_config.py::test_mlflow_experiment_name_overridable PASSED
tests/test_smoke.py::test_dataframe_loads PASSED
tests/test_smoke.py::test_dataset_split_sizes PASSED
tests/test_smoke.py::test_logistic_regression_returns_model PASSED
tests/test_smoke.py::test_evaluate_model_keys PASSED
tests/test_smoke.py::test_seed_42_metrics PASSED
tests/test_smoke.py::test_mlflow_run_logged PASSED

11 passed in X.XXs
```

Without the stack running, `test_mlflow_run_logged` is auto-skipped:
```
tests/test_smoke.py::test_mlflow_run_logged SKIPPED (MLflow tracking server not reachable ...)
10 passed, 1 skipped
```

---

## Verifying the storage split (Exercise 4)

### Silo (artifacts)

Open http://localhost:5511, log in with credentials from `.env`, and browse the
`mlflow-artifacts` bucket.

In MLflow 3 a logged model is a **first-class entity**, not a folder inside a run, so the
model files do *not* live under `<run_id>/artifacts/`. They live under the experiment's
`models/` prefix:

```
mlflow-artifacts/
  <experiment_id>/
    models/m-<32 hex chars>/artifacts/
      MLmodel          ← MLflow model metadata (YAML)
      model.pkl        ← serialized scikit-learn Pipeline
      conda.yaml       ← conda environment spec
      python_env.yaml  ← python version spec
      requirements.txt ← pip requirements
```

Anything logged with `mlflow.log_artifact` / `log_figure` *does* land under the run:
`<experiment_id>/<run_id>/artifacts/...`. Week 3 logs plots there and shows both prefixes
side by side.

`model.pkl` rather than `model.skops` because `mlflow==3.13.0` defaults
`serialization_format` to `cloudpickle`. Re-verify this before bumping the pin.

### Postgres (metadata)

```bash
# List tables
docker compose exec postgres psql -U mlflow -d mlflowdb -c "\dt"

# View the run record
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT run_uuid, status, start_time FROM runs;"

# View logged params
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT run_uuid, key, value FROM params ORDER BY key;"

# View logged metrics
docker compose exec postgres psql -U mlflow -d mlflowdb \
  -c "SELECT run_uuid, key, value FROM metrics;"
```

---
