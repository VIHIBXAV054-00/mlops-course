# Data Dictionary — UCI Adult / Census Income

A **socio-economic classification** alternative, and the catalogue's pick for engaging with **Responsible AI / fairness** (Weeks 6 and 13): it carries **sensitive attributes** (sex, race, age, national origin). Predict whether a person's annual income exceeds **$50K**, from 1994 US Census data.

## What the dataset is

- Rows: **48,842** (split 32,561 train / 16,281 test in the original) · Columns: 15 (14 features + target)
- Task: binary classification of `income` (`>50K` vs `<=50K`).
- Class balance: **~24% are `>50K`** (≈76% `<=50K`) — notable imbalance.

## Feature dictionary

| Column | Meaning | Type / values | Notes |
| :--- | :--- | :--- | :--- |
| `age` | Age in years | int (continuous) | |
| `workclass` | Employment type | categorical | **Missing as `?`** (e.g. Private, Self-emp, Government…). |
| `fnlwgt` | Final sampling weight | int (continuous) | Census survey weight, **not a personal attribute** — usually **dropped** for prediction. |
| `education` | Highest education (label) | categorical | **Redundant** with `education-num`. |
| `education-num` | Education as an ordinal number | int 1–16 | Numeric encoding of `education`; keep one of the two, not both. |
| `marital-status` | Marital status | categorical | |
| `occupation` | Occupation | categorical | **Missing as `?`**. |
| `relationship` | Role in household | categorical | Correlated with `marital-status` and `sex`. |
| `race` | Race | categorical | **Sensitive attribute.** |
| `sex` | Sex | `Female` / `Male` | **Sensitive attribute.** |
| `capital-gain` | Capital gains | int (continuous) | **Highly zero-inflated and skewed** (most are 0, a few very large). |
| `capital-loss` | Capital losses | int (continuous) | Zero-inflated, skewed. |
| `hours-per-week` | Hours worked per week | int (continuous) | |
| `native-country` | Country of origin | categorical | **Missing as `?`**; dominated by `United-States`. Sensitive. |
| `income` | Income bracket (**target**) | `<=50K` / `>50K` | See the formatting gotcha below. |

## Domain-expert notes (the gotchas)

- **Missing values hide as `?`** (not blank/`NaN`) in `workclass`, `occupation`, and `native-country` — about 7.4% of rows. Same lesson as Pima's zeros: missingness is disguised by a sentinel.
- **`education` and `education-num` are the same thing** — one is the label, the other its ordinal code. Keep one.
- **`fnlwgt` is a survey weight**, included so the sample reflects the US population; it is not a property of the person and is normally dropped from features.
- **Label formatting differs across files.** The original test split writes the target with a trailing period (`>50K.`), while train uses `>50K`. Strip it, or your join/eval silently breaks — a very common parsing bug with this dataset.
- **Skewed money columns.** `capital-gain`/`capital-loss` are mostly zero with rare huge values; consider transformation or binning.
- **Sensitive attributes ⇒ fairness work.** Because `sex`, `race`, `age`, and `native-country` are present, this is the right dataset if you want to do slice-based evaluation and fairness checks. It is *the* reference dataset for fairness benchmarking — and also carries known societal bias, so frame findings carefully.

## How this dataset "changes over time" in the course

Static 1994 snapshot. Use the **batch simulation** convention for Weeks 4/11–12. (If you specifically want *real* temporal income data, the modern "Folktables / Retiring Adult" datasets reconstruct this task across multiple census years — a good extension, though larger.)

## Source & licence

UCI Machine Learning Repository, "Adult" / "Census Income" (ids 2 / 20), licensed **CC BY 4.0**. Derived from the 1994 US Census Bureau database (Ronny Kohavi & Barry Becker).

_Last updated: 2026-06. Verify source and licence before use._
