# Week 6 Lab: Reference Solution

The complete, runnable version of the Week 6 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_06_evaluation_pipeline/evaluation.py` | 1 | `group_scores` implemented with fairlearn's `MetricFrame` |
| `src/week_06_evaluation_pipeline/pipeline.py` | 1, 4 | `evaluate` passes its arguments to `slice_report`; `require_go` is called |
| `params.yaml` | 3, 5 | the `acceptance` block filled in, including `fairness` |
| `src/week_06_evaluation_pipeline/gates.py` | 3, 5 | the TODOs in `_regression_checks`, `_slice_checks` and `_fairness_checks` filled in |
| `dvc.yaml` | 4 | the `gate` stage declared |
| `src/week_06_evaluation_pipeline/registry.py` | 4 | `register_best_model` and `promote_to_staging` call `require_go` |
| `src/week_06_evaluation_pipeline/fairness.py` | 5 | `rates_by_group` and `gaps` implemented with fairlearn |
| `src/week_06_evaluation_pipeline/baseline.py` | 6 (optional) | the TODO in `baseline_from_registry` filled in: it loads the champion and scores it on today's test split |
| `dvc.lock`, `metrics/*.json`, `reports/*.json`, `models/mlflow_run_id.json` | 1–6 | written by `dvc repro` and the gate; `metrics/baseline.json` ships with Week 5's scores as the first champion |
| `tests/*` | 1–5 | `@pytest.mark.skip` markers removed |
| `compose.yaml` | — | `name: week06-evaluation-pipeline` (the starter uses `-starter`, so the two never share volumes) |

Everything else is identical to the starter, including the DVC files that ship with it
(`.dvc/config`, `data/measurements.csv.dvc`, `data/.gitignore`).

## Running the solution

```bash
# 1. Stop any other lab stack: they all use the 55xx host ports
cd ../../week-05-data-validation/solution && docker compose down; cd -

# 2. Dependencies (uv.lock is committed)
uv sync --locked --all-groups
cp .env.example .env      # then set MLFLOW_MODEL_OWNER to your name

# 3. Rebuild the DVC-tracked dataset from the two batches in data/raw/
make data-v2              # 768 rows, md5 a8fd7b4f0d6d1bc4e378a8f76c5fff0c

# 4. The gate half: no Docker needed
make repro
make slices
make gate
make fairness
make gate-fail

# 5. The registry half
make up
make link
make register && make promote && make trace
make ratchet
```

## Expected output

### The pipeline

`make repro` on a clean checkout ends with:

```
Running stage 'evaluate':
{
  "accuracy": 0.7656,
  "precision": 0.6964,
  "recall": 0.5821,
  "f1": 0.6341,
  "roc_auc": 0.8345
}
  10 slice group(s) across 3 axes -> metrics/slices.json

Running stage 'gate':
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)
```

The metrics are the same as in Week 5: this week changes no model.

### The slice table (Exercises 1 and 2)

`make slices`:

```
192 rows, 67 positive (34.9% prevalence)
  aggregate      accuracy 0.7656  precision 0.6964  recall 0.5821  f1 0.6341  roc_auc 0.8345

  slice: age_band
  group                 n  pos     acc      f1  recall roc_auc     sel     fpr
  ------------------ ---- ---- ------- ------- ------- ------- ------- -------
  21-29                94   21  0.8511  0.6316  0.5714  0.8656  0.1809  0.0685
  30-39                48   22  0.6875  0.5946  0.5000  0.7832  0.3125  0.1538
  40-49                31   17  0.7419  0.7500  0.7059  0.8571  0.4839  0.2143
  50+                  19    7  0.5789  0.5000  0.5714  0.6071  0.4737  0.4167

  slice: bmi_band
  group                 n  pos     acc      f1  recall roc_auc     sel     fpr
  ------------------ ---- ---- ------- ------- ------- ------- ------- -------
  under_normal         30    1  0.9667  0.0000  0.0000  1.0000  0.0000  0.0000
  overweight           48    9  0.8125  0.4000  0.3333  0.7692  0.1250  0.0769
  obese               112   57  0.6964  0.6792  0.6316  0.7818  0.4375  0.2364
  missing               2    0  0.5000  0.0000      —       —   0.5000  0.5000

  slice: insulin_missing
  group                 n  pos     acc      f1  recall roc_auc     sel     fpr
  ------------------ ---- ---- ------- ------- ------- ------- ------- -------
  insulin_present     104   42  0.7308  0.6111  0.5238  0.8041  0.2885  0.1290
  insulin_missing      88   25  0.8068  0.6667  0.6800  0.8775  0.2955  0.1429
```

- `50+` is the worst group on every metric: ROC AUC 0.6071 against 0.8345 overall, FPR 0.4167
  against 0.0685 for the 21–29 group. It has 19 rows.
- `under_normal` has F1 0.0000 and ROC AUC 1.0000 on the same 30 patients. It has one
  positive: the model missed it, and ranked it above all 29 negatives.
- `bmi_band` has a `missing` group because the slices use the raw frame. After the imputer,
  those two patients would join `obese` (112 rows become 114, F1 0.6792 becomes 0.6729).

### The gate (Exercise 3)

`make gate`:

```
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)

  SKIPPED (not checked — read these before you trust the verdict):
    slice.age_band.50+                       support 19 < min_support 20
    slice.bmi_band.under_normal              positives 1 < min_positives 10
    slice.bmi_band.overweight                positives 9 < min_positives 10
    slice.bmi_band.missing                   support 2 < min_support 20

  check                                    status   detail
  ---------------------------------------- -------- ----------------------------------------
  minimum.accuracy                         pass     observed 0.7656 vs floor 0.7
  minimum.f1                               pass     observed 0.6341 vs floor 0.55
  minimum.roc_auc                          pass     observed 0.8345 vs floor 0.75
  regression.f1                            pass     0.6341 vs champion 0.6341 (delta +0.0000, tolerated -0.01)
  slice.age_band.21-29                     pass     n=94 pos=21 f1=0.6316 gap=0.0025
  slice.age_band.30-39                     pass     n=48 pos=22 f1=0.5946 gap=0.0395
  slice.age_band.40-49                     pass     n=31 pos=17 f1=0.75 gap=-0.1159
  slice.bmi_band.obese                     pass     n=112 pos=57 f1=0.6792 gap=-0.0451
  slice.insulin_missing.insulin_present    pass     n=104 pos=42 f1=0.6111 gap=0.023
  slice.insulin_missing.insulin_missing    pass     n=88 pos=25 f1=0.6667 gap=-0.0326
  fairness.age_band.tpr_gap                pass     observed 0.2059 vs limit 0.25
  fairness.insulin_missing.selection_rate_gap pass     observed 0.007 vs limit 0.1
  fairness.insulin_missing.tpr_gap         pass     observed 0.1562 vs limit 0.2
```

Without the `fairness` block (after Exercise 3 and before Exercise 5) the headline is
`10 passed, 0 failed, 4 SKIPPED`.

Why the floors are what they are: the majority-class rate on this test set is 0.6510, so
`minimum.accuracy: 0.70` is above what a constant classifier scores. With `min_f1: 0.50`
the largest possible gap is 0.1341, so `max_f1_gap: 0.10` can fire.

### The gate holding (Exercise 4)

`make gate-fail` changes `train.C` from 1.0 to 0.005 and runs the pipeline:

```
Running stage 'evaluate':
{
  "accuracy": 0.7448,
  "precision": 0.75,
  "recall": 0.403,
  "f1": 0.5243,
  "roc_auc": 0.8427
}

Running stage 'gate':
Cannot run `gate` yet:
  NO-GO. 4 acceptance criteria failed: minimum.f1, regression.f1, slice.age_band.30-39,
  fairness.age_band.tpr_gap.

ERROR: failed to reproduce 'gate': failed to run: uv run python src/main.py gate, exited with 1

--- the model must still be on disk ---
-rw-r--r--  1 ...  2273 models/model.pkl

--- register must REFUSE (expected exit 1) ---
Cannot run `register` yet:
  The recorded verdict is NO-GO (criteria v1.0.0): minimum.f1, regression.f1,
  slice.age_band.30-39, fairness.age_band.tpr_gap. Refusing to release.
```

`promote` prints the same refusal. F1 fell by 0.1098 and ROC AUC rose by 0.0082.

| `params.yaml` | accuracy | F1 | ROC AUC | 50+ F1 | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `C: 1.0` (shipped) | 0.7656 | 0.6341 | 0.8345 | 0.5000 | GO |
| `C: 0.01` | 0.7656 | 0.6087 | 0.8445 | 0.6250 | NO-GO (regression and age TPR gap 0.3052) |
| `C: 0.005` | 0.7448 | 0.5243 | 0.8427 | 0.5333 | NO-GO (4 criteria) |
| `C: 0.001` | 0.6510 | 0.0000 | 0.8407 | 0.0000 | NO-GO (9 criteria) |
| `impute_strategy: mean` | 0.7656 | 0.6341 | 0.8380 | 0.5000 | GO |
| `family: rf` | 0.7708 | 0.6452 | 0.8367 | 0.5333 | GO (an improvement) |

At `C: 0.001` the model predicts "no diabetes" for all 192 patients, and its ROC AUC is higher
than the shipped model's. A gate on ROC AUC alone would let it through.

### Fairness (Exercise 5)

`make fairness`:

```
  axis: insulin_missing  [GATED]
  group                 n  pos  sel_rate     tpr     fpr
  ------------------ ---- ---- --------- ------- -------
  insulin_missing      88   25    0.2955  0.6800  0.1429
  insulin_present     104   42    0.2885  0.5238  0.1290
    demographic parity difference (selection-rate gap): 0.0070
    equal opportunity difference  (TPR gap)           : 0.1562
    equalized odds difference     (max of TPR/FPR gap): 0.1562

  axis: age_band  [GATED]
  group                 n  pos  sel_rate     tpr     fpr
  ------------------ ---- ---- --------- ------- -------
  21-29                94   21    0.1809  0.5714  0.0685
  30-39                48   22    0.3125  0.5000  0.1538
  40-49                31   17    0.4839  0.7059  0.2143
  50+                  19    7    0.4737  0.5714  0.4167
    demographic parity difference (selection-rate gap): 0.3030
    equal opportunity difference  (TPR gap)           : 0.2059
    equalized odds difference     (max of TPR/FPR gap): 0.3482
```

### The ratchet (Exercise 6)

`make ratchet`, in four acts:

```
=== 1. a better model ===  (train.family: rf)
  "f1": 0.6452, "roc_auc": 0.8367
GO — 13 passed, 0 failed, 4 SKIPPED
  regression.f1   pass   0.6452 vs champion 0.6341 (delta +0.0111, tolerated -0.01)

=== 2. crown it ===
Registered diabetes-classifier version 2
Version 2 now carries aliases: ['champion', 'staging']
Baseline updated from mlflow://diabetes-classifier@champion (version 2)
  f1           0.6341 -> 0.6452  (+0.0111)

=== 3. the old model, against the new bar ===  (back to train.family: logreg)
  NO-GO. 1 acceptance criteria failed: regression.f1.

The logistic regression did not get worse. The bar got higher.

=== 4. put the bar back ===
```

Act 4 restores `params.yaml` and `metrics/baseline.json`. The `champion` alias stays on the
random forest, so a later `make baseline-sync` would raise the bar again.

### The traceability chain

`make trace`:

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
      "model_family": "logreg", "C": "1.0", "max_iter": "1000",
      "random_seed": "42", "test_size": "0.25", "n_rows_train": "576",
      "impute_strategy": "median"
}
8. Gate         : GO  (criteria v1.0.0, 0 failed, 4 skipped)
   Champion     : version 1
```

The run also carries the tags `gate`, `gate_criteria_version`, `gate_checks_failed` and
`gate_checks_skipped`, the artifacts `evaluation/gate.json` and `evaluation/slices.json`, and
one metric per slice (`slice.age_band.50plus.f1`; `+` is not allowed in an MLflow metric name).

### Which stages run again

Change `acceptance.minimum.f1` from 0.55 to 0.60 and run `make repro`: only `gate` runs. Change
a slice definition in `evaluation.slices` and `evaluate` and `gate` run, but `train` does not.

## Tests

| State | Result |
| --- | --- |
| Starter, after Setup | 136 passed, 31 skipped |
| Starter, Exercises 1, 3, 4 and 5 done | 158 passed, 9 skipped |
| Solution, stack down | 159 passed, 8 skipped |
| Solution, stack up | 167 passed |

The eight tests in `tests/test_mlflow_link.py` need the stack. `tests/test_fairness.py` shows
the two rules `fairness_report` adds to fairlearn: with a two-patient group, fairlearn alone
reports a TPR gap of 0.8, and the report says 0.4.
