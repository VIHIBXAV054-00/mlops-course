# Define Project Topic

**Due:** end of Week 3 (submit before the Week 4 class)
**Grading:** Approve / Request changes

---

## Objective

Choose a dataset and prediction task that you will carry through **all five homework assignments** (HW1–HW5) this semester.
The same project will grow from a tracked experiment in HW1 to a monitored production service in HW5 — so choose something you can work with for the entire semester.

Write a ~1-page proposal. Add images or tables if they help explain your dataset or task. Submit it as `docs/proposal.md` in **your project repo**.

---

## Constraints

Your chosen project must satisfy all of the following:

| Constraint | Requirement |
| --- | --- |
| **Data type** | preferably tabular (rows = examples, columns = features) |
| **Task type** | Supervised learning: binary or multi-class **classification**, or **regression** |
| **Scale** | Fits comfortably in memory on a 16 GB laptop; trains in under 60 seconds with scikit-learn |
| **Single target** | One clear target column (no multi-output, no multi-label) |
| **Availability** | Openly available with a usable license (CC0, CC-BY, MIT, or equivalent) |
| **Reproducibility** | Can be committed to a Git repository as a CSV (no API keys, no scraping required) |

**Need ideas?** See the curated **dataset catalogue** in [`datasets/README.md`](../../datasets/README.md) — four vetted options chosen for *different* real-world characteristics (hidden missing values, categorical-heavy data, a real time axis, sensitive attributes). Other suitable datasets: Titanic survival, Heart Disease UCI, California Housing, Breast Cancer Wisconsin, Wine Quality, Bank Marketing.

**Examples of unsuitable datasets:** ImageNet (images), SQuAD (text), any dataset requiring a paid API, datasets too large to commit to Git.

---

## What to submit

First, create **your project repository** from the **project template** ("Use this
template" → a new **private** repo). This is the repo you grow across HW1–HW5 — it
is separate from the course materials. Then write your proposal as `docs/proposal.md`
inside it, roughly one page (300–500 words), with the sections below. (Add your
dataset under `data/` and fill in `docs/DATA_DICTIONARY.md` while you're there.)

### 1. Dataset

- Name and brief description (1–2 sentences)
- Source URL and license
- Rough size: number of rows and number of features
- A **mini data dictionary**: for each feature, its meaning, unit, and a plausible range — plus any fields where the data is untrustworthy (missing values, sentinel codes, etc.). You will rarely be the domain expert on your data; find and write down that knowledge. Use [`datasets/diabetes-pima.md`](../../datasets/diabetes-pima.md) as the model for the expected depth.

### 2. Prediction task

- What are you predicting? Name the target column.
- Is this classification or regression?
- Why is this task interesting or useful?

### 3. Suitability check

- Confirm that the dataset fits in memory and trains quickly (you should be able to load it in Python and confirm before submitting)
- Name one known limitation or quirk of the dataset (e.g., class imbalance, missing values, duplicates)

### 4. Baseline idea

- Which scikit-learn model would you try first (e.g., `LogisticRegression`, `RandomForestClassifier`)?
- Which primary metric will you optimize for (accuracy, F1, RMSE, etc.) and why?

---

## Submission

1. Commit `docs/proposal.md` (and your dataset + `docs/DATA_DICTIONARY.md`) to **your project repo**.
2. Share the repo link with your instructor, or open a pull request, per the method your instructor specified.
3. Your instructor will respond with one of:
   - **Approved** — proceed to HW1 with this dataset
   - **Request changes** — revise per feedback and resubmit before HW1 deadline

---
