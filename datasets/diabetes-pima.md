# Data Dictionary — Pima Indians Diabetes (the course running example)

This is the **domain reference** for the dataset used in every lab. In a real project you will rarely be the domain expert; you rely on someone who is to tell you what each field means, what a *plausible* value looks like, and where the data is untrustworthy. This document plays that role. Read it before you trust any column.

## What the dataset is

Diagnostic measurements for **768 female patients of Pima Indian heritage, aged 21 or older**, collected by the US National Institute of Diabetes and Digestive and Kidney Diseases. The task is binary classification: predict whether the patient had an **onset of diabetes within 5 years** of the measurement (per WHO criteria).

- Rows: 768 · Features: 8 numeric · Target: `outcome` (0/1)
- Class balance: **500 negative / 268 positive** (~34.9% positive) — mild imbalance, realistic for screening.
- File: `data/diabetes.csv` (committed identically into each lab), snake_case headers.

## Feature dictionary

| Column | Meaning | Unit | Plausible range* | `0` = missing? | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pregnancies` | Number of times pregnant | count | 0–17 | **No** | `0` is a **valid** value (some patients have never been pregnant). Do not treat as missing. |
| `glucose` | Plasma glucose, 2-hour oral glucose tolerance test (OGTT) | mg/dL | ~40–200 | **Yes** (5 rows) | Clinical reference: <140 normal, 140–199 impaired, ≥200 diabetic. A value of 0 is physiologically impossible. |
| `blood_pressure` | **Diastolic** blood pressure | mmHg | ~40–120 | **Yes** (35 rows) | Normal diastolic < 80. `0` impossible. (Note: this is diastolic only, not systolic.) |
| `skin_thickness` | Triceps skin-fold thickness | mm | ~7–50 | **Yes** (227 rows) | A body-fat proxy. `0` impossible; standardized "normal" ranges are population-dependent. |
| `insulin` | 2-hour serum insulin | µU/mL | ~15–276 | **Yes** (374 rows) | The dirtiest column — **~49% are 0** (missing). 2-hour post-load insulin varies widely; treat ranges as indicative only. |
| `bmi` | Body mass index | kg/m² | ~15–67 | **Yes** (11 rows) | Reference: 18.5–24.9 normal, 25–29.9 overweight, ≥30 obese. `0` impossible. |
| `diabetes_pedigree` | Diabetes Pedigree Function — a synthesized score of diabetes family history | unitless | ~0.08–2.42 | n/a | **Engineered, not measured**: a model output from the original 1988 study, not a lab value. No missing values. |
| `age` | Age | years | 21–81 | n/a | Population is ≥21 by construction. |
| `outcome` | Diabetes onset within 5 years (target) | 0/1 | — | n/a | 1 = developed diabetes, 0 = did not. |

\* "Plausible range" = a rough sanity band combining the observed data and general clinical references — useful for spotting bad values, **not** a diagnostic threshold. Confirm against medical guidance before any real clinical use.

## Domain-expert notes (read these — they explain the "gotchas")

- **Missing values are hidden as zeros.** Five columns use `0` as a sentinel for "not recorded": `glucose`, `blood_pressure`, `skin_thickness`, `insulin`, `bmi`. There are **no `NaN`s** in the file — the missingness is disguised, which is exactly how bad data sneaks into real pipelines. Counts: insulin 374 (≈49%), skin_thickness 227 (≈30%), blood_pressure 35, bmi 11, glucose 5.
- **Not every zero is missing.** `pregnancies = 0` is legitimate. Blindly replacing all zeros would corrupt this column. The lesson: you need the domain meaning of each field, not a blanket rule.
- **The course leaves this untreated until Week 5.** Earlier weeks deliberately train on the dirty data so the validation lab (Pandera, Week 5) has something real to catch. Do not "fix" the zeros before then.
- **Feature scales differ by orders of magnitude** (insulin up to 846 vs. pedigree 0.08–2.42) — this is why the baseline pipeline applies `StandardScaler` before logistic regression.
- **`diabetes_pedigree` is engineered, not observed** — a useful reminder that some "features" are themselves model outputs with their own assumptions.
- **Known limitations.** Single narrow population (adult female Pima), small (768 rows), 1980s data. Good for teaching, not for general clinical claims.

## How this dataset "changes over time" in the course

The file is a single static snapshot — it has no real time axis. To teach **data versioning** (Week 4) and **drift/monitoring** (Weeks 11–12) on realistic terms, the course treats it as if it arrived in **measurement batches**: an initial cohort, then "a new batch of measurements arrived" later in the semester. Later batches may carry a deliberate, documented shift (e.g. a cohort skewed toward higher glucose, or a changed positive rate) so there is something genuine to version and to detect as drift. This is a **teaching simulation** of evolving data, and it will be clearly labelled as such when introduced — Weeks 1–2 use the dataset as one snapshot. The pre-generated batches (and the reproducible generator) live in [`batches/`](./batches/): a baseline cohort and a later "new arrival" batch deliberately shifted toward higher glucose (PSI ≈ 0.59, positive rate 29% → 44%), built from real rows only.

## Source & citation

- Origin: National Institute of Diabetes and Digestive and Kidney Diseases; widely redistributed (UCI ML Repository, Kaggle, `scikit-learn`-adjacent mirrors). Treat as public for educational use.
- Original study: Smith, J.W., Everhart, J.E., Dickson, W.C., Knowler, W.C., & Johannes, R.S. (1988). *Using the ADAP learning algorithm to forecast the onset of diabetes mellitus.* Proc. Annual Symposium on Computer Applications in Medical Care.

_Last updated: 2026-06. Verify clinical reference ranges against current medical guidance before any non-educational use._
