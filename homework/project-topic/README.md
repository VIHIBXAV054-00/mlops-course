# Milestone: Define Project Topic

**Due:** end of Week 2 (submit before the Week 3 lab session)
**Estimated effort:** 1–2 hours
**Grading:** Approve / Request changes / Default to Pima fallback

---

## Objective

Choose a dataset and prediction task that you will carry through **all five homework assignments** (HW1–HW5) this semester. The same project will grow from a tracked experiment in HW1 to a monitored production service in HW5 — so choose something you can work with for the entire semester.

This milestone is a ~1-page proposal. No code yet. You are defining your canvas.

---

## Constraints

Your chosen project must satisfy all of the following:

| Constraint | Requirement |
| --- | --- |
| **Data type** | Tabular (rows = examples, columns = features) — no images, audio, or raw text |
| **Task type** | Supervised learning: binary or multi-class **classification**, or **regression** |
| **Scale** | Fits comfortably in memory on a 16 GB laptop; trains in under 60 seconds with scikit-learn |
| **Single target** | One clear target column (no multi-output, no multi-label) |
| **Availability** | Openly available with a usable license (CC0, CC-BY, MIT, or equivalent) |
| **Reproducibility** | Can be committed to a Git repository as a CSV (no API keys, no scraping required) |

**Need ideas?** See the curated **dataset catalogue** in [`datasets/README.md`](../../datasets/README.md) — four vetted options chosen for *different* real-world characteristics (hidden missing values, categorical-heavy data, a real time axis, sensitive attributes). Other suitable datasets: Titanic survival, Heart Disease UCI, California Housing, Breast Cancer Wisconsin, Wine Quality, Bank Marketing.

**Examples of unsuitable datasets:** ImageNet (images), SQuAD (text), any dataset requiring a paid API, datasets too large to commit to Git.

### Fallback

If you have no preference, or if your proposal is not approved before HW1 is due, you will automatically work with the **Pima Indians Diabetes dataset** — the same dataset used in labs throughout the semester. This is not a penalty; the course dataset is well-understood and will produce clean results across all five homework assignments.

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

### 5. Forward thread

Fill in one line for each homework:

| Homework | What you will do |
| --- | --- |
| **HW1** (due Week 6): Data versioning + experiment tracking | e.g. "Version my dataset with DVC + MinIO; track training runs in MLflow" |
| **HW2** (due Week 8): Data validation + evaluation gates | e.g. "Add Pandera schema to validate feature columns; define go/no-go threshold on F1" |
| **HW3** (due Week 10): Prefect orchestration | e.g. "Wrap prepare + validate + train + evaluate into a Prefect flow with retry on data load" |
| **HW4** (due Week 12): KServe serving | e.g. "Serve the registered model as a KServe InferenceService; write smoke tests" |
| **HW5** (due Week 14): Observability + drift | e.g. "Add Prometheus metrics to the serving endpoint; detect distribution drift on features" |

---

## Submission

1. Commit `docs/proposal.md` (and your dataset + `docs/DATA_DICTIONARY.md`) to **your project repo**.
2. Share the repo link with your instructor, or open a pull request, per the method your instructor specified.
3. Your instructor will respond with one of:
   - **Approved** — proceed to HW1 with this dataset
   - **Request changes** — revise per feedback and resubmit before HW1 deadline
   - **Defaulted to Pima** — if no proposal is received or approved by HW1 deadline, you work with the course dataset

---

## Approval criteria (for instructors)

A proposal is approved if:

- [ ] The dataset is tabular with a single clear target column
- [ ] The task is classification or regression (not unsupervised, not multi-label)
- [ ] The dataset is small enough to train in under 60 seconds on a 16 GB laptop with scikit-learn
- [ ] Source URL and license are provided and usable
- [ ] The student can commit the dataset as a CSV to Git (size and license permit)
- [ ] All five forward-thread rows are filled in with plausible entries

A proposal can be approved in under 5 minutes. If borderline, default to the Pima dataset and note why.

---

## How the projects thread forward

Every homework assignment builds on the same dataset and pipeline:

- **HW1 (due Week 6):** Add DVC + MinIO data versioning; add MLflow tracking and register the first model version. *Prove: `dvc push` and `dvc pull` work from a fresh clone; run appears in MLflow with logged artifact.*
- **HW2 (due Week 8):** Add Pandera schema validation for your features; define a go/no-go F1 threshold. *Prove: invalid data is rejected before training; documented threshold justification.*
- **HW3 (due Week 10):** Wrap the pipeline in a Prefect flow with parameterization and retries. *Prove: flow runs end-to-end with a task-level retry; parameterized seed run is recorded.*
- **HW4 (due Week 12):** Serve the registered model with KServe; document traffic splitting and a rollback. *Prove: inference endpoint answers POST requests; smoke test passes.*
- **HW5 (due Week 14):** Add Prometheus metrics to the serving endpoint; run an Evidently drift report; define an alert threshold. *Prove: dashboard shows latency; drift report identifies at least one shifted feature.*

Choosing a dataset you are curious about makes five weeks of incremental work significantly more engaging.
