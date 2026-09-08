# Data Dictionary — Telco Customer Churn

A **business / telecom** alternative for your course project. Chosen as a contrast to the medical Pima data: it needs almost no domain expertise, but it is **categorical-heavy** and contains a classic real-world data trap (a numeric column stored as text with blanks). Predict whether a customer **churned** last month.

## What the dataset is

A fictitious California telco's customer records (IBM sample dataset). Binary classification of `Churn` (Yes/No).

- Rows: 7,043 · Columns: 21 (1 ID + 19 features + target)
- Class balance: **~26.5% churn** (≈73.5% stay) — moderate imbalance.
- Feature mix: 3 numeric, the rest categorical (mostly Yes/No service flags).

## Feature dictionary

| Column | Meaning | Type / values | Notes |
| :--- | :--- | :--- | :--- |
| `customerID` | Unique customer id | string | **Drop for modelling** — identifier, no signal, risk of leakage. |
| `gender` | Customer gender | `Female` / `Male` | |
| `SeniorCitizen` | Is a senior citizen | **`0` / `1` (numeric)** | Watch out: the only binary stored as 0/1 while the rest are `Yes`/`No`. |
| `Partner` | Has a partner | `Yes` / `No` | |
| `Dependents` | Has dependents | `Yes` / `No` | |
| `tenure` | Months with the company | int, 0–72 | `tenure = 0` ⇒ brand-new customer (see `TotalCharges`). |
| `PhoneService` | Has phone service | `Yes` / `No` | |
| `MultipleLines` | Multiple phone lines | `Yes` / `No` / `No phone service` | The third value is a real category, **not** missing. |
| `InternetService` | Internet type | `DSL` / `Fiber optic` / `No` | |
| `OnlineSecurity` | Add-on | `Yes` / `No` / `No internet service` | "No internet service" is a category, not missing. |
| `OnlineBackup` | Add-on | `Yes` / `No` / `No internet service` | |
| `DeviceProtection` | Add-on | `Yes` / `No` / `No internet service` | |
| `TechSupport` | Add-on | `Yes` / `No` / `No internet service` | |
| `StreamingTV` | Add-on | `Yes` / `No` / `No internet service` | |
| `StreamingMovies` | Add-on | `Yes` / `No` / `No internet service` | |
| `Contract` | Contract term | `Month-to-month` / `One year` / `Two year` | Strong churn predictor. |
| `PaperlessBilling` | Paperless billing | `Yes` / `No` | |
| `PaymentMethod` | Payment method | 4 categories (e.g. `Electronic check`, `Mailed check`, `Bank transfer (automatic)`, `Credit card (automatic)`) | |
| `MonthlyCharges` | Current monthly charge | float (USD) | |
| `TotalCharges` | Lifetime charges | **stored as text; ~11 blanks** | The data trap: looks numeric but loads as `object` because of blank strings. |
| `Churn` | Churned last month (**target**) | `Yes` / `No` | |

## Domain-expert notes (the gotchas)

- **`TotalCharges` is the trap.** It should be numeric but loads as a string because ~11 rows are blank. Those blanks line up exactly with `tenure = 0` — new customers who have never been billed. So the missingness has a *cause*: don't blindly impute a mean, decide what a zero-tenure customer's total should be (often 0).
- **Mixed binary encodings.** `SeniorCitizen` is `0/1` while every other yes/no field is `Yes`/`No`. A naive "encode all object columns" step silently skips it.
- **"No internet/phone service" is a category, not a null.** Several columns have a third level meaning the customer can't have the add-on. Treat it as its own category.
- **Drop `customerID`.** Pure identifier.
- **Low domain knowledge needed** — features are self-explanatory, which makes this a good first project if you'd rather spend effort on the lifecycle than on a domain.

## How this dataset "changes over time" in the course

Static snapshot (no signup dates). Use the **batch simulation** convention (see `./README.md`): split into an initial customer base plus a later "new signups arrived" batch, optionally shifting the mix (e.g. more month-to-month contracts, higher churn rate) so Weeks 11–12 have a real shift to detect. `tenure` gives a natural ordering if you want batches to look chronological.

## Source & licence

IBM "Telco Customer Churn" sample dataset; most commonly obtained from Kaggle (`blastchar/telco-customer-churn`). Widely used for education; confirm the licence on the specific mirror before redistributing.

_Last updated: 2026-06. Verify source and licence before use._
