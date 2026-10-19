---
description:
  title: "Week 6 Lab: Evaluation Pipeline"
  summary: |
    Cut the test set into groups and score each one, write the acceptance
    criteria and the go/no-go gate for the diabetes model, and make `dvc repro`
    stop and `register` refuse when the model fails. Then check the model's
    errors per group, and optionally move the bar with a better model.
---

# Week 6 Lab: Evaluation Pipeline

In Week 5 you put a gate in front of the data. A model can still be unsafe to release.
One accuracy number hides the groups of patients the model is wrong about, and nobody
has written down what "good enough" means.

Today you cut the test set into groups and score each group. You write the acceptance
criteria and a gate that says GO or NO-GO. You make the gate stop `dvc repro` and make
`register` and `promote` refuse a model without a GO. At the end you check the model's
errors per group, and optionally raise the bar with a better model.

Background for every exercise: the Week 6 lecture and `docs/notes/week-06-notes.md`.

## Based on

- **scikit-learn, model evaluation:** https://scikit-learn.org/stable/modules/model_evaluation.html
- **fairlearn, assessment guide** (`MetricFrame` and the fairness metrics): https://fairlearn.org/main/user_guide/assessment/perform_fairness_assessment.html
- **Google, Rules of Machine Learning**, rules 12–19 on metrics and slicing: https://developers.google.com/machine-learning/guides/rules-of-ml
- **Breck et al., The ML Test Score**, the rubric this lab implements: https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/

**Deviations from the references:**

1. **Two rules on top of fairlearn.** fairlearn compares every group, however small, and
   reports a TPR of 0.0 for a group with no positives. `fairness_report` reports such a rate
   as undefined (None), and leaves out of the gaps any group under 5 rows or without both
   classes, so a gap is never set by two patients or by a rate that does not exist.
2. **The gate is a DVC stage, but nothing depends on it.** Week 5's gate worked because
   `prepare` depended on the verdict file. `gate` is the last stage, so `register` and
   `promote` read its verdict instead (Exercise 4).
3. **You choose the thresholds after you see the numbers.** In a real project the team
   agrees them before the run.

## Prerequisites

- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Docker Desktop, or Docker Engine with the Compose plugin, version 24+. You need it from
  Exercise 4 on.
- Ports **5500, 5510, 5511, 5532** free.
- **Stop your Week 5 stack first.** It uses the same ports:
  ```bash
  cd ../../week-05-data-validation/solution && docker compose down
  ```

---

## Step 1: dependencies

```bash
uv sync --all-groups
```

New this week: **`fairlearn`**, which scores every group in one call (`MetricFrame`) and
computes the fairness metrics.

## Step 2: configuration

```bash
cp .env.example .env
```

Set `MLFLOW_MODEL_OWNER` to your name. The experiment is now `diabetes-week6`.

## Step 3: the dataset

The DVC setup comes with this lab: `.dvc/config` names the Silo remote, and
`data/measurements.csv.dvc` is the pointer. Build the data from the two batches in
`data/raw/`, then run the pipeline:

```bash
make data-v2
make verify-data
make repro
```

Expected output of `make verify-data`: `workspace matches pointer: True`. `make repro` runs
`validate`, `prepare`, `train` and `evaluate`, and prints accuracy 0.7656, precision 0.6964,
recall 0.5821, F1 0.6341 and ROC AUC 0.8345. These are the Week 5 numbers: this week does
not change the model.

## Step 4: tests before you start

```bash
uv run pytest tests/
```

Expected: **136 passed, 31 skipped**.

Start the Docker stack (MLflow and its stores) with `make up` and leave it running. Exercises 4 and 6 need it.

---

## Exercises

Do them in order. Exercises 2, 4 and 5 ask for a **written answer**: write it in
`answers.md` in this folder and **commit it with your code**. Exercise 6 is optional.
Exercises 1–3 and 5 need no Docker.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| Slices | 1–2 | 25 min |
| The gate | 3–4 | 35 min |
| Fairness | 5 | 15 min |
| Finish: commit and submit | — | 5 min |
| Optional: the ratchet | 6 | 15 min |

### Exercise 1: slice the test set (≈ 15 min)

One accuracy number is an average over all 192 test patients. To find a group the model is
wrong about, you score the same test set group by group. Teams do this when a model is fine
in the dashboard and a clinic, a market or an age group complains.

**Do:**

1. Read `slice_labels` in `src/week_06_evaluation_pipeline/evaluation.py`. It is complete.
   It turns one slice definition from `params.yaml` (under `evaluation`) into a group label
   for each row. Look at how a BMI of 0 gets the label `missing`, not the lowest band.
2. In the same file, implement `group_scores` with fairlearn's `MetricFrame`. It scores
   every group of one slice in one call and returns a table with one row per group.
   `group_metrics` below it turns that table into the JSON records.
3. In `pipeline.py`, fill in the arguments of the `slice_report` call in `evaluate`.
4. Run the pipeline and print the table:
   ```bash
   make repro
   make slices
   ```
   Expected output: `make repro` prints `10 slice group(s) across 3 axes -> metrics/slices.json`,
   and `make slices` prints a table for each of the three slices, with `n` and `pos` on every row.

**Check:**

- Delete the Exercise 1 skip markers in `tests/test_evaluation.py`.
- Run `uv run pytest tests/test_evaluation.py`.
  Expected output: `16 passed`
- Run `make slices`. The first line of the output is:
  ```text
  192 rows, 67 positive (34.9% prevalence)
  ```
  The age band `50+` has `n` 19, and the BMI band `under_normal` has `n` 30 and `pos` 1.

**Stuck?**

- Lecture: "Slice metrics in code" and "Which BMI group is a patient with no BMI in?"
- Notes: "Slices and support" and "Slice the raw values"
- fairlearn docs: https://fairlearn.org/main/user_guide/assessment/perform_fairness_assessment.html
- scikit-learn docs: the model evaluation guide (link above)
- If the `missing` BMI group is absent from the table, check which frame you slice.

### Exercise 2: read the slice table (≈ 10 min) *(written answer)*

Two things in the table are invisible in the aggregate row. Reading a slice table fast is
what you do when a reviewer asks "is it good for everyone?" and you have five minutes.

**Do:**

1. Run `make slices`. On every row, read `n` and `pos` first, then compare the metrics with
   the `aggregate` line.
2. Find the group with the lowest ROC AUC. Note its `n`, and compare its `fpr` with the
   `fpr` of the `21-29` group.
3. Find the group with an F1 of 0.0000 and a ROC AUC of 1.0000, and look at its `pos`.

**Check:**

- You can name the worst group, its `n`, and its ROC AUC against the aggregate 0.8345.

**Stuck?**

- Lecture: "How many patients make a slice?" and "Always check what was skipped"
- Notes: "Slices and support"
- ROC AUC does not use the 0.5 threshold. F1 does.

**Written answer** (in `answers.md`):

1. Which group is the model worst on, and by how much against the aggregate? How far can
   you trust that gap, given the group's `n`?
2. What can you do with this finding now, and what would you need before you act on it?
3. One group has an F1 of 0.0000 and a ROC AUC of 1.0000 on the same patients. How can both
   be correct, and what do they tell you about that group?

### Exercise 3: write the acceptance criteria and the gate (≈ 20 min)

A release needs an answer to "do we ship it?" that a person agreed on in advance and that
lives in Git. You write the criteria in `params.yaml` and the rules that apply them.
This is the file a reviewer reads when someone asks why a model was allowed out.

**Do:**

1. Run the gate before you write any criteria:
   ```bash
   make gate
   ```
   Expected output: the first line is
   ```text
   GO — 10 passed, 0 failed, 1 SKIPPED (criteria v1.0.0)
   ```
   Every slice passes, including `50+` with 19 patients and `under_normal` with one
   positive. A gate without criteria lets everything through.
2. In `params.yaml`, add the `acceptance` block under `criteria_version`: the floors in
   `minimum`, the champion comparison in `regression`, and the group rules in
   `slice_rules`. Run `make slices` first, and choose each value from the numbers it prints.
   A floor that a model predicting "no diabetes" for everyone clears is not a floor.
3. Read `evaluate_gate` and `_minimum_checks` in `src/week_06_evaluation_pipeline/gates.py`.
   They are complete. `_minimum_checks` shows the shape of one check: an `id`, a `status`
   (pass, fail or skipped) and a `reason`.
4. In the same file, fill in the TODO in `_regression_checks`. It decides when a drop
   against the champion fails.
5. In the same file, fill in the two TODOs in `_slice_checks`: first the support rules,
   which skip a group too small to judge, then the F1 rules.
6. Run the gate again:
   ```bash
   make gate
   ```
   Expected output: the first line is
   ```text
   GO — 10 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)
   ```
   Under `SKIPPED` the age band `50+` and the BMI band `under_normal` are listed.

**Check:**

- Delete the Exercise 3 skip markers in `tests/test_gates.py`.
- Run `uv run pytest tests/test_gates.py tests/test_model_gate.py`.
  Expected output: `36 passed, 6 skipped`
- Check that every threshold can fire: for each one, name a model that would fail it.

**Stuck?**

- Lecture: "Four kinds of acceptance criteria", "How many patients make a slice?" and
  "Make sure every rule can fire"
- Notes: "Acceptance criteria", "Skipped checks" and "Make sure every rule can fire"
- If the headline shows 0 skipped, check `too_small` in `_slice_checks`.
- With `minimum.f1` in place, a `max_f1_gap` wider than the aggregate F1 minus `min_f1` can
  never fire.

### Exercise 4: the gate as a stage, and a real regression (≈ 15 min) *(written answer)*

A verdict file that nothing reads is a log line. In this exercise `dvc repro` stops on a
NO-GO, and `register` and `promote` refuse without a GO. In a team this is the difference
between a gate and a suggestion: someone types `make register` on a Friday evening.

**Do:**

1. In `dvc.yaml`, add the `gate` stage.
2. In `registry.py`, make `register_best_model` and `promote_to_staging` call `require_go`
   from `pipeline.py`.
3. Break the model on purpose. The `gate-fail` target in the Makefile changes `train.C` from
   1.0 to 0.005, runs `dvc repro`, tries `register` and `promote`, and restores
   `params.yaml`:
   ```bash
   make gate-fail
   ```
   Expected output: `evaluate` prints F1 0.5243 and ROC AUC 0.8427. With the reference
   thresholds, the gate then prints the lines below; your thresholds may list other checks:
   ```text
   Running stage 'gate':
   Cannot run `gate` yet:
     NO-GO. 4 acceptance criteria failed: minimum.f1, regression.f1, slice.age_band.30-39,
     fairness.age_band.tpr_gap.
   ```
   `models/model.pkl` is still listed, and `register` and `promote` both print
   `Refusing to release.`

**Check:**

- Delete the Exercise 4 skip markers in `tests/test_model_gate.py`.
- Run `uv run pytest tests/test_model_gate.py`.
  Expected output: `18 passed, 1 skipped`
- Run `make dag`.
  Expected output: `gate` is the last node, and no stage depends on it.
- With the stack up, run `uv run pytest tests/test_mlflow_link.py`.
  Expected output: `8 passed`

**Stuck?**

- Lecture: "The gate in the pipeline" and "Inspect the report"
- Notes: "The gate as a stage" and "Measurement and policy"
- DVC docs: https://doc.dvc.org/user-guide/project-structure/dvcyaml-files
- If `dvc repro` does not stop, look at the exit code of `main.py gate`.

**Written answer** (in `answers.md`):

1. Week 5's gate worked because `prepare` depended on the verdict file. Why can that not
   work for this gate, and what replaces it?
2. What happens if `register` does not call `require_go`? Who would notice, and when?
3. With `C: 0.005`, F1 fell by 0.1098 and ROC AUC rose. Which one is the right answer? What
   do you need to know about how the model is used, and what does
   `acceptance.regression.primary_metric` commit you to?

### Exercise 5: check the errors per group (≈ 15 min) *(written answer)*

Two groups can get the same share of positive predictions and still have very different
numbers of missed cases. In this exercise you compute the three fairness metrics from the
lecture with fairlearn: **demographic parity**, **equal opportunity** and **equalized odds**.
Each one is a difference between groups. It is the largest gap in one rate (selection rate,
TPR or FPR) between any two groups, and 0 means every group gets the same rate. The code and
`params.yaml` call these differences *gaps* (`selection_rate_gap`, `tpr_gap`). Then you
choose which fairness metrics to gate on which axis. This is the check an ethics review or
an audit asks for.

**Do:**

1. In `src/week_06_evaluation_pipeline/fairness.py`, implement `rates_by_group`: the
   selection rate, TPR and FPR of every group, with a `MetricFrame`.
2. In the same file, implement `gaps`: the fairness metrics, each a difference between the
   groups computed by one fairlearn function. The TODO names the four keys: the
   demographic parity difference, the equal opportunity difference, the FPR difference and
   the equalized odds difference.
3. Read `fairness_report` in the same file. It adds the two rules fairlearn does not have:
   a rate with nothing to measure is None, and only groups with at least 5 rows and both
   classes enter the gaps.
4. In `gates.py`, fill in the TODO in `_fairness_checks`: when a gap is over its limit. The loop over
   the axes in `acceptance.fairness`, with each axis's own limits, is there.
5. Print the rates and the fairness metrics:
   ```bash
   make fairness
   ```
   Expected output: for `age_band`, the selection-rate gap is 0.3030 and the equalized odds
   difference is 0.3482. For `insulin_missing`, the selection-rate gap is 0.0070 and the TPR
   gap is 0.1562.
6. In `params.yaml`, add the `fairness` block to `acceptance`: one key per gated axis, with
   the gaps you gate on it and their limits. Gate the selection-rate and TPR gaps on
   `insulin_missing`, and the TPR gap on `age_band` with a looser limit. Then run `make gate`.

**Check:**

- Delete the Exercise 5 skip markers in `tests/test_fairness.py` and `tests/test_gates.py`.
- Run `uv run pytest tests/test_fairness.py tests/test_gates.py`.
  Expected output: `29 passed`
- Run `make gate`.
  Expected output: the headline is `GO — 13 passed, 0 failed, 4 SKIPPED`, and three checks
  start with `fairness.`.

**Stuck?**

- Lecture: "Three rates for each group", "Three fairness metrics" and "Which groups get a
  fairness gate?"
- Notes: "Group fairness" and "Choosing a fairness criterion"
- fairlearn docs: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
- `rates_by_group` has the same shape as `group_scores` from Exercise 1.

**Written answer** (in `answers.md`):

1. `age_band` has a selection-rate gap over 0.30, yet you gate only its TPR gap. Why is the
   large selection-rate gap defensible?
2. The TPR limit on `age_band` is looser than on `insulin_missing`. Why, and what would make
   you tighten it?
3. This dataset has no sex, ethnicity, income or clinic column. Name one group you would
   want to audit this model for and cannot. What would have had to happen, and when?

### Exercise 6 (optional): raise the bar with a ratchet (≈ 15 min) *(written answer)*

A gate that compares with the current champion turns one way: every better model raises the
bar. You make a better model the champion, sync the baseline, and see the original model
fail. This is the situation when someone retrains a model "just to check" and the old one no
longer passes.

This exercise needs the Docker stack from Setup Step 4 running: the MLflow tracking server
and its stores. The registry, the `champion` alias and the training runs live there, so
`make ratchet` fails without it.

**Do:**

1. Check that the stack is up. If you stopped it, start it again:
   ```bash
   make up
   make ps
   ```
   Expected output: `make up` returns once every service is healthy, and `make ps` lists
   `mlflow`, `postgres` and `s3` as `Up` (`healthy`). MLflow answers at
   http://localhost:5500.
2. In `src/week_06_evaluation_pipeline/baseline.py`, fill in the TODO in
   `baseline_from_registry`: load the champion by its alias and score it on today's test
   split with `score_on_test_set`. The alias lookup and the record it returns are there.
3. Run the whole loop. The target trains a random forest and registers it as champion. It
   syncs `metrics/baseline.json`, runs the original model against the new baseline, then
   restores `params.yaml` and `metrics/baseline.json`. The `champion` alias stays on the
   random forest:
   ```bash
   make ratchet
   ```
   Expected output: act 1 prints `GO` with `regression.f1` passing at +0.0111. Act 3 prints
   `NO-GO. 1 acceptance criteria failed: regression.f1.` and
   `The logistic regression did not get worse. The bar got higher.`

**Check:**

- Delete the Exercise 6 skip marker in `tests/test_model_gate.py`.
- Run `uv run pytest tests/test_model_gate.py`.
  Expected output: `19 passed`
- Run `make baseline`.
  Expected output: the first line is `baseline source : week-05 reference run`, and `f1` is
  0.6341. The ratchet put the bar back.

**Stuck?**

- Lecture: "The bar moves up" and "Where does the champion's score come from?"
- Notes: "The ratchet"
- MLflow docs: https://mlflow.org/docs/latest/ml/model-registry/workflow/
- Look up the version by the alias in `settings.champion_alias`, not by a number.
- A score stored at training time belongs to that day's test set; score the model again.

**Written answer** (in `answers.md`):

1. A ratchet only turns one way. Give one situation where that is what you want, and one
   where it locks you out of a model you should have shipped.
2. What is a champion's score a measurement of?

## Finish: commit and submit your work (≈ 5 min)

1. Run `uv run pytest tests/`.
   Expected output: `158 passed, 9 skipped`. The 8 skipped tests need the stack and `make link`;
   the ninth is Exercise 6 (`159 passed, 8 skipped` if you did it).
2. Commit your work:
   ```bash
   git status          # answers.md must appear; .env and .venv/ must not
   git add .
   git commit -m "week06: slices, acceptance gate, fairness checks and written answers"
   ```
3. Check that `params.yaml`, `dvc.yaml`, `dvc.lock`, `metrics/slices.json`,
   `reports/gate.json` and `answers.md` are in the commit, and that **none** of these
   appear: `.env`, `.venv/`, `.dvc/cache/`, `data/measurements.csv`.
4. Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
   and upload that URL to Moodle.

---

## Make targets

| Target | What it does |
| --- | --- |
| `make slices` | the per-group table, with `n` and `pos` on every row |
| `make gate` | the go/no-go decision; exits non-zero on a NO-GO |
| `make fairness` | the three gaps per axis |
| `make baseline` | the recorded champion the gate compares with |
| `make baseline-sync` | score the `champion` on today's test split and rewrite it (Exercise 6) |
| `make gate-fail` | break the model on purpose and watch the gate hold (Exercise 4) |
| `make ratchet` | a better model becomes champion and the old one is refused (Exercise 6) |
| `make data-gate-fail` | Week 5's data gate: break the data and watch it hold |
| `make repro`, `make dag`, `make metrics` | the pipeline, its graph, its numbers |
| `make register`, `make promote`, `make promote-champion`, `make trace` | the registry |

Every Week 5 target still works.

## What lives where

| Thing | Where it lives | Why |
| --- | --- | --- |
| `params.yaml` | Git | `evaluation` is what we measure, `acceptance` is whether it passes |
| `metrics/slices.json`, `reports/gate.json` | Git | `cache: false`, so the evidence is in the same commit as the claim |
| `metrics/baseline.json` | Git | the recorded champion; only `make baseline-sync` writes it |
| `src/.../gates.py` | Git | a pure function: plain dicts in, a verdict out |
| `data/measurements.csv` | Silo (`dvc-storage`) | the versioned dataset; Git has its pointer |
| `models/model.pkl`, `data/processed/*.csv` | DVC cache | outputs the pipeline can rebuild |

## Tear-down

```bash
make down      # stop; data and runs stay in the volumes
make down-v    # stop AND delete both buckets and the database
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Cannot run gate yet: metrics.json is missing` | `evaluate` has never run. Run `make repro`. |
| `The gate is not implemented yet, so nothing was checked` | Exercise 3 is not finished. The command exits with 1, so `dvc repro` stops. |
| `No slice report — evaluation.slice_report returns nothing yet` | Exercise 1 is not finished. |
| `Cannot run register: reports/gate.json is missing` | The gate has not run for this model. Run `make repro` or `make gate`. |
| `The recorded verdict is NO-GO ... Refusing to release` | The gate is doing its job. Read `reports/gate.json`, and fix the model. If you change a threshold, bump `criteria_version`. |
| `register` says `No MLflow run recorded yet` | The stack was down when `train` ran. Start it, then run `make link`. |
| `ModuleNotFoundError: No module named 'fairlearn'` | Run `uv sync --all-groups` again: `fairlearn` is new this week. |
| `dvc repro` says "up to date" after you edit a threshold | You edited a comment, not a value. Check `dvc params diff`. |
| `Bind for 0.0.0.0:5500 failed: port is already allocated` | Another week's stack is running. Stop it with `docker compose down` in that folder. |

## Next steps

The pipeline now has a gate at both ends. The gate runs only when someone runs it: nothing
stops a team member from skipping `make gate`, or from merging a change that breaks it. Week 7
runs these checks automatically on every commit, with continuous integration.
