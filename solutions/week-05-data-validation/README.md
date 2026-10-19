# Week 5 Lab: Reference Solution

The complete, runnable version of the Week 5 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_05_data_validation/schemas.py` | 1, 3 | `RawMeasurements` columns declared (zero allowed in the sentinel columns, `ge=0`); `ModelInput` columns declared (`gt=0, nullable=True` in the sentinel columns) |
| `src/week_05_data_validation/validation.py` | 1, 3 | `validate_frame` runs the schema with `lazy=True` and catches `SchemaErrors`; `to_nullable` converts the sentinel zeros to `pd.NA` in `Float64` columns |
| `src/week_05_data_validation/pipeline.py` | 4, 5 | `validate` writes the report, then raises `ValidationFailed`; `prepare` calls `_require_validated`; `prepare_model_input` converts, checks `ModelInput` and returns float64 features |
| `dvc.yaml` | 4 | `validate` stage declared; `reports/validation.json` added to the deps of `prepare` |
| `src/week_05_data_validation/model.py` | 5 | `build_model` puts a `SimpleImputer` named `imputer` before the scaler |
| `src/week_05_data_validation/inference.py` | 6 (optional) | `predict_one` checks the request against `PredictionInput` and returns before loading the model |
| `dvc.lock`, `reports/validation.json`, `metrics/metrics.json`, `models/mlflow_run_id.json` | 4–6 | Written by `dvc repro` and `make link` |
| `tests/*` | 1–6 | `@pytest.mark.skip` markers removed |
| `compose.yaml` | — | `name: week05-data-validation` (the starter uses `-starter`, so the two never share volumes) |

Everything else is identical to the starter, including the DVC files that ship with it
(`.dvc/config`, `data/measurements.csv.dvc`, `data/.gitignore`).

## Running the solution

```bash
# 1. Stop any other lab stack: they all use the 55xx host ports
cd ../../week-04-dvc-introduction/solution && docker compose down; cd -

# 2. Dependencies (uv.lock is committed)
uv sync --locked --all-groups
cp .env.example .env      # then set MLFLOW_MODEL_OWNER to your name

# 3. Rebuild the DVC-tracked dataset from the two batches in data/raw/
make build-data           # 768 rows, md5 a8fd7b4f0d6d1bc4e378a8f76c5fff0c

# 4. The contracts and the pipeline: no Docker needed
make validate
make validate-broken
make validate-model-input
make repro
make gate-fail
make predict-bad

# 5. The MLflow half
make up
make link
make register && make promote && make trace
```

## Expected output

### The contracts

`make validate`:

```
[PASS] RawMeasurements v1.0.0 on measurements.csv — 768 rows
  zeros in the sentinel columns: {'glucose': 5, 'blood_pressure': 35, 'skin_thickness': 227, 'insulin': 374, 'bmi': 11}
```

`make validate-broken` (the order of the lines comes from Pandera):

```
[FAIL] RawMeasurements v1.0.0 on broken_batch.csv — 60 rows
  7 failure case(s)

    row  column             check                            failure_case
  -----  ------------------ -------------------------------- ------------------------
      —  RawMeasurements    column_in_schema                 notes
      3  glucose            coerce_dtype('float64')          unknown
      3  glucose            dtype('float64')                 unknown
     23  bmi                less_than_or_equal_to(100.0)     280.0
      7  age                less_than_or_equal_to(120)       250
      —  glucose            greater_than_or_equal_to(0)      TypeError("'>=' not supp
      —  glucose            less_than_or_equal_to(400.0)     TypeError("'<=' not supp

  by check : {"column_in_schema": 1, "coerce_dtype('float64')": 1, "dtype('float64')": 1, ...}
  by column: {"glucose": 4, "RawMeasurements": 1, "bmi": 1, "age": 1}
```

`make validate-model-input`: `652 failure case(s)` (all `greater_than(0)`) before
`to_nullable`, then `[PASS]` and `missing values now: 652`.

### The gate

`make gate-fail` plants `age = 250` in row 1. Without the gate (the starter after Setup),
the row reaches training: the md5 of `data/processed/train.csv` changes from
`d9eba76cf921c13f5af2032d09a12f35` to `267b4f5e6768bdff8b28e710b5a1b7f4`, and accuracy
drops to 0.7604. With the gate:

```
--- md5 of data/processed/train.csv before ---
d9eba76cf921c13f5af2032d09a12f35
--- planted age = 250 in row 1; dvc repro ---
Running stage 'validate':
Cannot run `validate`:
  measurements.csv failed the RawMeasurements contract with 1 failure case(s). The report is in reports/validation.json.
ERROR: failed to reproduce 'validate': failed to run: uv run python src/main.py validate, exited with 1
--- md5 of data/processed/train.csv after ---
d9eba76cf921c13f5af2032d09a12f35
```

`dvc dag --mermaid`; the edge `node5-->node3` (`validate --> prepare`) is the gate:

```
flowchart TD
	node1["data/measurements.csv.dvc"]
	node2["evaluate"]
	node3["prepare"]
	node4["train"]
	node5["validate"]
	node1-->node3
	node1-->node5
	node3-->node2
	node3-->node4
	node4-->node2
	node5-->node3
```

### The metrics

Seed 42, 576 training and 192 test rows.

| Metric | Starter (no imputer, zeros as values) | Solution, `median` | Solution, `mean` |
| --- | --- | --- | --- |
| accuracy | 0.7656 | **0.7656** | 0.7656 |
| precision | 0.7200 | 0.6964 | 0.6964 |
| recall | 0.5373 | 0.5821 | 0.5821 |
| f1 | 0.6154 | **0.6341** | 0.6341 |
| roc_auc | 0.8183 | **0.8345** | 0.8380 |

Changing `train.impute_strategy` re-runs `train` and `evaluate` only. `tests/test_smoke.py`
still checks the Week 1–3 pins (F1 0.5785, accuracy 0.7344) on `data/diabetes.csv`.

### Requests

| Request | Without the check in `predict_one` | With it |
| --- | --- | --- |
| `example` | probability 0.7173 | probability 0.7173 |
| `illegal` (glucose and insulin 0) | probability 0.0092 | rejected: `greater_than(0)` on glucose and insulin |
| `swapped` (insulin and bmi) | probability 1.0 | rejected: `less_than_or_equal_to(100.0)` on bmi |
| `incomplete` (no insulin) | scikit-learn error: feature names missing `insulin` | rejected: `column_in_dataframe` |
| `insulin: null` | — | legal; the imputer fills 122.0, probability 0.7304 |

### The MLflow run

`make trace` after `make link`, `make register` and `make promote`:

```
── Traceability chain ──
1. Model URI    : models:/diabetes-classifier@staging
2. Version      : 1  (aliases: ['champion', 'staging'])
3. Run          : <run id>  (dvc-logreg)
4. Git commit   : <commit>
5. Data version : a8fd7b4f0d6d1bc4e378a8f76c5fff0c
   Data location: s3://dvc-storage/dvcstore/files/md5/a8/fd7b4f0d6d1bc4e378a8f76c5fff0c
6. Validation   : pass  (contract v1.0.0, 0 failure case(s))
7. Params:
{
      "model_family": "logreg", "C": "1.0", "max_iter": "1000", "random_seed": "42",
      "test_size": "0.25", "impute_strategy": "median", "n_rows_train": "576"
}
```

The run carries the tags `data_validation=pass`, `schema_version=1.0.0`,
`n_failure_cases=0` and `ingestion_validation=pass`, and `reports/validation.json` as the
artifact `validation/validation.json`. Its MLflow dataset digest is `2857c4e0`.

## Tests

| State | Result |
| --- | --- |
| Starter, after Setup | 40 passed, 52 skipped |
| Starter, Exercises 1–5 done | 84 passed, 8 skipped |
| Solution, stack down | 88 passed, 4 skipped |
| Solution, stack up | 92 passed |

The four tests in `tests/test_mlflow_link.py` need the stack.
