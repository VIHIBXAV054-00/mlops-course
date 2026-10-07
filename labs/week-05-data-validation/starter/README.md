---
description:
  title: "Week 5 Lab: Data Validation"
  summary: |
    Write the data contracts for the diabetes pipeline with Pandera: one for
    the batches the clinic sends, one for what the model may see. Put the first
    in front of the pipeline as a DVC stage that stops `dvc repro`, fill the
    missing values inside the model, and check every prediction request
    against the same contract.
---

# Week 5 Lab: Data Validation

In Week 4 you versioned the dataset with DVC, so you can tell which data each model was
trained on. You have not checked the quality of that data yet. A new batch from the clinic
can bring an impossible value, a missing column or text in a numeric column. The
pipeline trains on it without a warning.

Today you write the data contracts as Pandera schemas. You put a validation stage in front
of the pipeline, so that `dvc repro` stops on a bad batch. Then you turn the zeros into
missing values that the model fills itself, and you check every prediction request against
the same contract.

Background for every exercise: the Week 5 lecture and `docs/notes/week-05-notes.md`.

## Based on

- **Pandera documentation and quick start:** https://pandera.readthedocs.io/en/stable/
- **DataFrame models (`DataFrameModel`, `Field`, `Config`):** https://pandera.readthedocs.io/en/stable/dataframe_models.html
- **Lazy validation:** https://pandera.readthedocs.io/en/stable/lazy_validation.html
- **Checks:** https://pandera.readthedocs.io/en/stable/checks.html
- **scikit-learn `SimpleImputer`:** https://scikit-learn.org/stable/modules/generated/sklearn.impute.SimpleImputer.html

**Deviations from the tutorial:**

1. **`pandera[pandas]`**, not `pandera`. Since Pandera 0.24 the base package has no pandas
   support; the extra installs it.
2. **`import pandera.pandas as pa`**, the import the documentation uses for pandas. Older
   blog posts write `import pandera as pa`.
3. **Two schemas, not one.** The pipeline validates the data twice before training, as in
   the lecture. The ingestion contract checks a batch when it arrives. The training
   contract checks what the model may see. The clinic sends zeros in every batch, so the
   first contract allows them and the second does not.
4. **The CSV is read as text** (`read_raw`), and the schema converts the types
   (`coerce = True`). A cell that is not a number then fails with its column and row.
5. **The gate is a DVC stage**, not the `@pa.check_types` decorator from the lecture,
   because a decorator cannot stop `dvc repro`.

## Prerequisites

- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Docker Desktop, or Docker Engine with the Compose plugin, version 24+. You need it only
  in Exercise 6.
- Ports **5500, 5510, 5511, 5532** free for Exercise 6.
- **Stop your Week 4 stack first.** It uses the same ports:
  ```bash
  cd ../../week-04-dvc-introduction/starter && docker compose down
  ```

---

## Step 1: dependencies

```bash
uv sync --all-groups
```

New this week: **`pandera[pandas]`**.

## Step 2: configuration

```bash
cp .env.example .env
```

Set `MLFLOW_MODEL_OWNER` to your name. The experiment is now `diabetes-week5`.

`params.yaml` has one new value, `train.impute_strategy`. You use it in Exercise 5.

## Step 3: the dataset

The DVC setup from Week 4 comes with this lab: `.dvc/config` names the Silo remote, and
`data/measurements.csv.dvc` is the pointer. The data file itself is not in Git. Build it
from the two batches in `data/raw/`:

```bash
make build-data
uv run python src/main.py verify-data
```

`build-data` prints 768 rows. This is the same data as version 3 of your Week 4 dataset,
so `verify-data` prints `workspace matches pointer: True`.

## Step 4: tests before you start

```bash
uv run pytest tests/
```

Expected: **40 passed, 52 skipped**.

Start the stack with `make up` and leave it running.

---

## Exercises

Do them in order. Exercises 2, 4 and 6 ask for a **written answer**: write it in
`answers.md` in this folder and **commit it with your code**. Exercise 6 is optional.
Exercises 1–5 need no Docker.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| The ingestion contract | 1–2 | 25 min |
| The training contract | 3 | 10 min |
| The gate | 4 | 20 min |
| Missing values in the model | 5 | 10 min |
| Finish: commit and submit | — | 5 min |
| Optional: serving, and the run | 6 | 15 min |

### Exercise 1: write the ingestion contract (≈ 15 min)

A contract says what a batch from the clinic is allowed to contain. You write it as a
Pandera class, and code checks every batch against it. This is the file a data engineer
and you agree on, and the one you read first when a batch is rejected.

**Do:**

1. Open `data/raw/batch_01_baseline.csv` and look at the header and a few rows.
2. In `src/week_05_data_validation/schemas.py`, declare the columns of `RawMeasurements`,
   the ingestion contract. Its `Config` and the `no_duplicate_rows` check are written. The
   clinic sends zeros in the five `SENTINEL_COLUMNS` in every batch, and the contract must
   accept every real batch.
3. In `src/week_05_data_validation/validation.py`, implement `validate_frame`. It runs a
   schema and returns a report. `_add_failures` below it builds the report from Pandera's
   failure table.

**Check:**

- Delete the Exercise 1 skip markers in `tests/test_schemas.py` and
  `tests/test_validation.py`.
- Run `uv run pytest tests/test_schemas.py tests/test_validation.py`.
  Expected output: `19 passed, 10 skipped`
- Run `make validate`. Expected output:
  ```text
  [PASS] RawMeasurements v1.0.0 on measurements.csv — 768 rows
    zeros in the sentinel columns: {'glucose': 5, 'blood_pressure': 35, 'skin_thickness': 227, 'insulin': 374, 'bmi': 11}
  ```

**Stuck?**

- Lecture: "The same schema as a class", "`Field`: rules for one column" and "`Config`:
  rules for the whole table"
- Notes: "The same schema as a class" and "`Field`: rules for one column"
- Pandera docs: DataFrame models and Lazy validation (links above)
- If the real data fails `greater_than(0)`, look again at where a 0 is allowed.

### Exercise 2: read a validation report (≈ 10 min) *(written answer)*

`data/quality/broken_batch.csv` is a batch of 60 rows with four faults edited in by hand.
You check it against your contract and read the report. Reading a report fast matters when
the nightly pipeline stops and the clinic asks what is wrong with their file.

**Do:**

1. Check the broken batch:
   ```bash
   make validate-broken
   ```
   It prints the report and exits with 0, because reading a broken file is not an error.
2. Open `data/quality/broken_batch.csv` in your editor and find the row behind each line of
   the report. Pandera's row numbers start at 0 and do not count the header.

**Check:**

- The report lists **7 failure cases**.

**Stuck?**

- Lecture: "Stop at the first error, or collect them all" and "Reading a real report"
- Notes: "Reading a validation report"
- Pandera docs: Lazy validation (link above)
- A line with `—` in the `row` column is a check on the whole frame or the whole column.

**Written answer** (in `answers.md`):

1. The batch has a `notes` column that the contract does not name. The clinic says it is
   free text and will come in every batch from now on. Would you add it to the contract,
   drop it before validation, or keep rejecting the batch? Decide, and say who must agree.
2. List the four faults in the batch: for each, the row, the column and the bad value. The
   report has 7 lines for 4 faults. Which fault caused more than one line, and why?

### Exercise 3: write the training contract (≈ 10 min)

The model must not see a zero that means "not measured". A second contract, `ModelInput`,
describes what the model may see: in the five sentinel columns a 0 fails and a missing value
passes. Before the check, `to_nullable` turns the zeros into missing values. It fills
nothing in.

**Do:**

1. In `schemas.py`, declare the columns of `ModelInput`. Its `Config` sets
   `ordered = True`, so the columns must come in the order you declare them.
   `PredictionInput`, the contract for a prediction request, inherits from `ModelInput`.
2. In `validation.py`, implement `to_nullable`.

**Check:**

- Delete the Exercise 3 skip markers in `tests/test_schemas.py`,
  `tests/test_validation.py` and `tests/test_inference.py`.
- Run `uv run pytest tests/test_schemas.py tests/test_validation.py tests/test_inference.py`.
  Expected output: `37 passed, 4 skipped`
- Run `make validate-model-input`. It checks the data against `ModelInput` before and
  after the conversion. Expected output: `652 failure case(s)` before the conversion,
  then:
  ```text
  [PASS] ModelInput v1.0.0 on measurements.csv, converted — 768 rows
    missing values now: 652
  ```

**Stuck?**

- Lecture: "Two contracts, at two boundaries" and "Zero becomes missing"
- Notes: "Two contracts at two boundaries"
- Pandera docs: https://pandera.readthedocs.io/en/stable/dtypes.html
- pandas docs: https://pandas.pydata.org/docs/user_guide/missing_data.html
- The type is `"Float64"` with a capital F. Plain `float64` turns `pd.NA` into `NaN`.

### Exercise 4: the gate as a pipeline stage (≈ 20 min) *(written answer)*

So far a contract runs only when someone calls it. In this exercise it becomes the first
stage of the pipeline, and `dvc repro` stops when the data breaks the contract. First you
see what the pipeline does with a bad batch today.

**Do:**

1. Run the pipeline as it is, then read the `gate-fail` target in the Makefile and run it.
   It plants `age = 250` in one row, runs `dvc repro`, and puts the data back:
   ```bash
   make repro
   make gate-fail
   ```
   Expected output: the md5 of `data/processed/train.csv` changes from `d9eba76c…` to
   `267b4f5e…`.
2. In `src/week_05_data_validation/pipeline.py`, implement `validate`. It checks the
   dataset, writes `reports/validation.json`, and stops when the data fails. Write the
   report before you stop the pipeline: whoever fixes the data needs it.
3. In the same file, add the check to `prepare`. It must not run after a failed
   validation, even when someone runs it by hand.
4. In `dvc.yaml`, add the `validate` stage and make `prepare` depend on its report.

**Check:**

- Delete the Exercise 4 skip markers in `tests/test_gate.py` and `tests/test_dvc_yaml.py`.
- Run `uv run pytest tests/test_gate.py tests/test_dvc_yaml.py`.
  Expected output: `7 passed, 4 skipped`
- Run `make repro`, then `make dag`.
  Expected output: the graph has the edge `validate --> prepare` (`node5-->node3` in the
  mermaid form).
- Run `make gate-fail`.
  Expected output: the pipeline stops at `validate`, and the md5 of
  `data/processed/train.csv` is `d9eba76c…` before and after.

**Stuck?**

- Lecture: "The gate is one dependency edge" and "Did it really stop?"
- Notes: "The data quality gate"
- DVC docs: https://doc.dvc.org/user-guide/project-structure/dvcyaml-files
- If `prepare` still runs after a failed `validate`, check that `reports/validation.json`
  is in the `deps` of `prepare`.

**Written answer** (in `answers.md`):

1. Compare the two runs of `make gate-fail`. Without the gate, which files did the row with
   `age = 250` reach, and who or what would use them next?
2. `validate` has failed. A teammate in a hurry runs `uv run python src/main.py prepare` by
   hand. What happens, and which line of your code makes it happen? Why is the edge in
   `dvc.yaml` not enough on its own?
3. You raise `MAX_AGE` from 120 to 125. Predict which stages `make repro` runs and which
   it skips. Try it, then set the value back and run `make repro` again. Explain why each
   stage ran or skipped, and say whether the model needed to be trained again.

### Exercise 5: fix the model, not the data (≈ 10 min)

The training data now has missing values instead of fake zeros. The model must fill them,
and it must fill a request at serving time in the same way. So the imputer goes inside the
model's scikit-learn `Pipeline`, where it learns the medians from the training split and is
saved with the model.

**Do:**

1. In `pipeline.py`, implement `prepare_model_input`. `train` and `evaluate` call it to
   get the features. Today it passes the zeros to the model.
2. In `src/week_05_data_validation/model.py`, add the imputer step to `build_model`.
3. Change `train.impute_strategy` from `median` to `mean` in `params.yaml` and run the
   pipeline:
   ```bash
   make repro
   ```
   Expected output: only `train` and `evaluate` run. Then set the value back to `median`
   and run `make repro` again.

**Check:**

- Delete the Exercise 5 skip markers in `tests/test_gate.py`.
- Run `uv run pytest tests/test_gate.py`.
  Expected output: `8 passed`
- Run `make metrics`, and compare with the metrics from step 1 of Exercise 4.
  Expected output: accuracy 0.7656, F1 0.6341 and ROC AUC 0.8345. In Exercise 4 they
  were 0.7656, 0.6154 and 0.8183.

**Stuck?**

- Lecture: "Fill the gaps inside the model"
- Notes: "Filling the gaps inside the model"
- scikit-learn docs: `SimpleImputer` (link above)
- If `test_the_model_carries_an_imputer` fails, check the step's name: `"imputer"`.

### Exercise 6 (optional): training-serving skew (≈ 15 min) *(written answer)*

A deployed model receives requests, not batches. A request can carry the same zeros as the
clinic's files, or two values in the wrong fields. In this exercise you first send three bad
requests to the model, then put `PredictionInput` in front of it. At the end, the MLflow run
records which contract the training data passed. `log_validation` in
`src/week_05_data_validation/dvc_link.py` is written: it tags the training run with the
verdict and the contract version.

**Do:**

1. Read the four example requests at the end of `src/week_05_data_validation/inference.py`:
   `EXAMPLE_PAYLOAD`, `ILLEGAL_PAYLOAD`, `SWAPPED_PAYLOAD` and `INCOMPLETE_PAYLOAD`. Note
   what is wrong with each of the last three.
2. Send one legal and three bad requests to the model you trained in Exercise 5:
   ```bash
   make predict
   make predict-bad
   ```
   Expected output: the legal request gets 0.7173, `illegal` gets 0.0092, `swapped` gets
   1.0, and `incomplete` stops with an error from scikit-learn.
3. In the same file, add the check to `predict_one`. Today it sends every request to the
   model.
4. Send the bad requests again:
   ```bash
   make predict-bad
   ```
   Expected output: all three print `no prediction: the request was rejected`.
5. Record a new training run, then register and promote its model:
   ```bash
   make link
   make register && make promote
   ```

**Check:**

- Delete the Exercise 6 skip markers in `tests/test_inference.py` and
  `tests/test_mlflow_link.py`.
- Run `uv run pytest tests/test_inference.py tests/test_mlflow_link.py`.
  Expected output: `16 passed`
- Run `make trace`. It follows the chain from the alias to the validation verdict.
  Expected output: the last line is
  `6. Validation   : pass  (contract v1.0.0, 0 failure case(s))`

**Stuck?**

- Lecture: "One contract at both boundaries" and "Record the verdict with the run"
- Notes: "Training-serving skew" and "Recording the verdict with the run"
- Pandera docs: DataFrame models (link above)
- MLflow docs: https://mlflow.org/docs/latest/ml/tracking/
- Return before the `model_path.exists()` check: `tests/test_inference.py` passes a path
  where no model file exists.

**Written answer** (in `answers.md`):

1. A mobile app sends `"insulin": null` when the test was not done, in about 40% of its
   requests. Send one such request (`uv run python src/main.py predict --payload '<JSON>'`).
   Would you keep filling insulin with the training median, or reject these requests?
   Who should make the decision?

## Finish: commit and submit your work (≈ 5 min)

1. Run `uv run pytest tests/`.
   Expected output: `84 passed, 8 skipped`, or `92 passed` if you did Exercise 6.
2. Commit your work:
   ```bash
   git status          # answers.md must appear; .env and .venv/ must not
   git add .
   git commit -m "week05: data contracts, a validation gate, and written answers"
   ```
3. Check that `reports/validation.json`, `dvc.lock`, `metrics/metrics.json` and
   `answers.md` are in the commit, and that **none** of these appear: `.env`, `.venv/`,
   `.dvc/cache/`, `data/measurements.csv`.
4. Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
   and upload that URL to Moodle.

---

## What lives where

| Thing | Where it lives | Why |
| --- | --- | --- |
| `src/.../schemas.py` | Git | the contracts: `RawMeasurements`, `ModelInput`, `PredictionInput` |
| `src/.../validation.py` | Git | runs a contract and builds the report; `to_nullable` |
| `reports/validation.json` | Git | the last verdict of `validate` (`cache: false`) |
| `data/quality/broken_batch.csv` | Git | the broken batch of Exercise 2 |
| `data/raw/batch_*.csv` | Git | the batches the dataset is built from |
| `data/measurements.csv` | Silo (`dvc-storage`) | the versioned dataset; Git has its pointer |
| `dvc.yaml`, `params.yaml`, `dvc.lock` | Git | what you declared, and what ran |
| `metrics/metrics.json`, `models/mlflow_run_id.json` | Git | `cache: false`, so they show in a diff |
| `models/model.pkl`, `data/processed/*.csv` | DVC cache | outputs the pipeline can rebuild |

## Tear-down

```bash
make down      # stop; data and runs stay in the volumes
make down-v    # stop AND delete both buckets and the database
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'pandera.pandas'` | Run `uv sync --all-groups`; `pyproject.toml` asks for `pandera[pandas]`. |
| `make validate` reports `greater_than(0)` on the real data | `RawMeasurements` rejects the clinic's zeros. Look again at where a 0 is allowed (Exercise 1). |
| `validate_frame` raises a `SchemaErrors` traceback | The `except` names `SchemaError`, without the s. |
| `SchemaInitError: custom check 'required' is not available` | This Pandera version has no `Field(required=...)`. Write `Optional[Series[int]]` for a column that may be absent. |
| `column_ordered` failures on data you did not change | Declare the `ModelInput` columns in the order of `FEATURE_COLUMNS`, then `outcome`. |
| A test sees a different number of failures after another test | Something changed `Model.to_schema()`, which returns one shared object. Change a `copy.deepcopy` of it instead. |
| `data/measurements.csv is missing` | Run `make build-data` (Step 3). |
| `Cannot run ... not written yet (Exercise N)` | That exercise's function is still a TODO. |
| `make predict-bad` ends with `make: *** [predict-bad] Error 1` before your fix | Expected in step 1 of Exercise 6: the `incomplete` request crashes scikit-learn. |
| `make repro` says "didn't change, skipping", but you want a new MLflow run | Correct: nothing changed. Use `make link`. |
| `Bind for 0.0.0.0:5500 failed: port is already allocated` | Another week's stack is running. Stop it with `docker compose down` in that folder. |
| `dvc dag` opens a pager | Press `q`. The Makefile avoids this with `DVC_PAGER=cat`. |

## Next steps

The data now has to pass a contract before it trains a model. Nothing checks yet whether
the model is good enough to ship: in Exercise 5 accuracy stayed the same while F1 and
ROC AUC rose. Week 6 adds model quality gates: acceptance criteria, a comparison with the
current model, and a go/no-go decision.
