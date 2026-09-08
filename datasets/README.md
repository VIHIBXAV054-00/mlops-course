# Dataset Catalogue (for your course project)

A short, curated list of tabular datasets you may use for the **course project** (the "Define Project Topic" milestone in Week 2, carried through HW1–HW5). Each was picked to show a **different flavour of real-world messiness** — because the point of this course is the lifecycle, not the modelling, and lifecycle tools only earn their keep when the data is imperfect.

> Two ground rules. (1) The **labs always use the Pima diabetes dataset** — the single running example — so everyone follows the same steps; these alternatives are for *your own project*. (2) Whatever you pick, you must **document it like a domain expert would**: see `./diabetes-pima.md` for the expected depth (what each field means, its unit, a plausible range, and where the data is untrustworthy). You will rarely be the expert on your data; part of the job is finding and writing down that knowledge.

## At a glance

| Dataset | Domain | Task | Size | Target balance | Standout real-world trait | Domain knowledge needed | Natural time axis? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Pima Diabetes** (default/fallback) | Healthcare | Binary classification | 768 × 8 | ~35% positive | Missing values hidden as `0`; not all zeros are missing | High (clinical) | No (batch-simulated) |
| **Telco Customer Churn** | Business / telecom | Binary classification | 7,043 × ~20 | ~27% churn | Mostly categorical; real blank values in `TotalCharges`; class imbalance | Low (intuitive) | No (batch-simulated) |
| **UCI Bike Sharing** | Urban mobility | Regression (rental count) | 17,379 × ~16 (hourly) | continuous | **Real datetime axis** — hourly 2011–2012, strong seasonality | Low | **Yes** |
| **UCI Adult / Census Income** | Socio-economic | Binary classification | 48,842 × 14 | ~24% ">50K" | Missing encoded as `?`; **sensitive attributes** (sex, race, age) | Medium | No (batch-simulated) |

## Profiles

**Pima Indians Diabetes — the default.** If you have no strong preference, or your proposal isn't approved, use this. It's the running example, fully documented in `./diabetes-pima.md`. Teaches: sentinel-encoded missingness, the "not every zero is missing" trap, scale heterogeneity, mild imbalance. Static — see the batch-simulation note below.

**Telco Customer Churn.** A fictitious telco's 7,043 customers; predict who churns. Mostly **categorical** features (contract type, services, payment method) plus a few numeric — a good contrast to Pima because it needs almost no domain expertise but forces you to handle encodings. Has genuine **blank values** in `TotalCharges` (~11 rows) and ~27% class imbalance. Commonly distributed via Kaggle (IBM sample dataset); check the specific mirror's license before redistributing.

**UCI Bike Sharing.** Hourly bike-rental counts for 2011–2012 with weather/season fields; predict the count (**regression**). The one option with a **real time axis**, so it's the easiest place to show authentic temporal/seasonal **drift** and genuine data **versioning** ("the next month's data arrived") without simulation. License: UCI, CC BY 4.0 — cite Fanaee-T & Gama (2014).

**UCI Adult / Census Income.** 1994 US census records; predict whether income > $50K. Carries **sensitive attributes** (sex, race, age), which makes it the right pick if you want to engage with the **Responsible-AI / fairness** material (Week 6, Week 13). Missing values are encoded as `?` (~7.4% of rows). License: CC BY 4.0.

## Simulating "evolving data" (for static datasets)

Three of these have no real time axis. To exercise **data versioning** (Week 4) and **drift monitoring** (Weeks 11–12), treat a static file as if it **arrived in measurement batches**: split it into an initial cohort and one or more later batches, and reveal the later ones as "a new batch of measurements arrived." You can optionally inject a documented shift in a later batch (e.g. resample toward higher values of one feature, or change the positive rate) so there is something genuine to detect. Always label this as a teaching simulation. Bike Sharing needs none of this — split it by month or season for a real temporal story.

A worked example for the running dataset lives in [`batches/`](./batches/), with a reusable generator (`make_batches.py`) you can point at **your own** dataset.

## Data that is supposed to fail (Week 5)

[`quality/`](./quality/) holds `broken_batch.csv` — a **deliberately corrupted** batch with one injected fault per error class (wrong dtype, out-of-range value, negative measurement, invalid label, missing value, unit change, unexpected column, duplicated row). It exists so the Week 5 data-validation lab has something a contract must reject, and so every row of Pandera's failure report maps back to a documented edit. **Never train on it.** The batches in [`batches/`](./batches/) are the opposite: every row there is real and unmodified.

## Choosing well

Pick something you can live with for the whole semester (HW1→HW5 build on it): tabular, supervised, small enough to train in seconds on a 16 GB laptop with scikit-learn, with a clear single target and a usable licence. Then document it to the standard of `./diabetes-pima.md` before you start — your future self (and your grader) will thank you.

_Last updated: 2026-06. Verify each dataset's current source and licence before use; terms change._
