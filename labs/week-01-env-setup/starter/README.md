---
description:
  title: "Week 1 Lab: Environment Setup and Baseline ML Pipeline"
  summary: |
    Set up a reproducible Python environment and train a diabetes prediction
    model — the project you will productionize for the rest of the semester.
---

# Week 1 Lab: Environment Setup and Baseline ML Pipeline

You will train a model that predicts whether a patient will develop diabetes, using real diagnostic measurements (glucose, BMI, age, ...) from 768 patients. **This exact pipeline is the project you will version, track, validate, deploy, and monitor for the next 13 weeks.**

## Lab goals

After finishing this lab, you should be able to:

- verify that Python, Git, and Docker are installed correctly
- use `uv` to create a reproducible Python environment
- manage runtime configuration through a `.env` file
- run and modify a baseline Scikit-learn training pipeline
- write a basic unit test with pytest

This lab follows the official getting-started guides with minimal changes — keep them open as references:

- Scikit-learn: https://scikit-learn.org/stable/getting_started.html (Pipeline + fit/predict pattern)
- uv: https://docs.astral.sh/uv/getting-started/installation/

## The dataset

`data/diabetes.csv` — the Pima Indians Diabetes dataset (originally from the US National Institute of Diabetes and Digestive and Kidney Diseases, via the UCI ML Repository). 768 patients, 8 diagnostic features, binary outcome (diabetes within 5 years). 34.9% positive rate.

> Watch out: some patients have a BMI of 0.0 or a glucose level of 0 — medically impossible values that are really missing data in disguise. Our pipeline currently ignores this.

## Prerequisites

- Python 3.12 or newer
- Git
- Docker (installed and running; first used at the end of this lab)

---

## Step 1 — Install `uv`

### macOS and Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

Restart your terminal after installation if `uv: command not found`.

## Step 2 — Prepare the lab environment

Open a terminal in this directory (`labs/week-01-env-setup/starter/`) and run:

```bash
uv sync --all-groups
```

This creates a `.venv` virtual environment and installs all dependencies (including `pytest` from the `test` group), pinned exactly by `uv.lock` — everyone in the room gets the identical environment.

## Step 3 — Create your local configuration

```bash
cp .env.example .env
```

Open `.env` and review the variables. You will change them in the exercises.

**Never commit `.env` to Git.** It is listed in `.gitignore`. (`.env.example` is committed instead — that is how teams document required configuration without leaking secrets.)

## Step 4 — Run the baseline pipeline

```bash
uv run python src/main.py
```

### Expected output

```
Week 1 — Diabetes prediction baseline
=====================================
Dataset:        diabetes.csv (768 patients)
Diabetes rate:  34.9%
Random seed:    42
Training rows:  576
Test rows:      192

Logistic Regression metrics:
{
  "accuracy": 0.7344,
  "precision": 0.6481,
  "recall": 0.5224,
  "f1": 0.5785
}
```

If you see these exact metrics, your environment is ready — and identical to everyone else's. That is what reproducibility means.

## Step 5 — Run the tests

```bash
uv run pytest tests/ -v
```

Expected: **3 passed, 1 skipped**. The skipped test is yours to write in Exercise 3.

---

## Exercises

Complete these exercises before the next lab session.

### Exercise 1 — Same code, different model (5 min)

1. Run the pipeline twice without changing anything. Confirm the metrics are identical both times.
2. Now set `PIPELINE_RANDOM_SEED=7` in `.env` and run again.
3. **The accuracy just changed by ~5 percentage points — and you did not touch a single line of code or data.** Which model is "the real one"? Write a 2–3 sentence answer in `answers.md` (create the file): what changed under the hood, and why is this a problem for a team shipping models to production?
4. Restore `PIPELINE_RANDOM_SEED=42`.

### Exercise 2 — Model competition (15 min)

Beat the baseline. Currently the best F1 is **0.5785**.

1. In `src/week_01_env_setup/model.py`, add a function `train_random_forest(x_train, y_train, settings)` that returns a fitted `RandomForestClassifier(random_state=settings.random_seed)` (import it from `sklearn.ensemble`; no scaler needed for trees).
2. Update `src/week_01_env_setup/cli.py` to train and evaluate **both** models and print each under a clear heading.
3. Tune hyperparameters if you like (`n_estimators`, `max_depth`, ...). Keep `random_state` fixed so your result is reproducible.
4. Bring your best F1 to the next session. There will be a leaderboard. Note how quickly "which run produced that number?" becomes hard to answer.

### Exercise 3 — Write a test for data splitting (10 min)

1. Open `tests/test_data.py`. The instructions are in the test's docstring.
2. Implement the assertions, delete the `@pytest.mark.skip` line, and make `uv run pytest tests/ -v` report **4 passed**.

### Exercise 4 — Break it on purpose (5 min)

1. Set `PIPELINE_TEST_SIZE=1.5` in `.env` (an invalid value) and run the pipeline.
2. **Question:** Which module raises the error, and why is failing *here* better than failing inside `train_test_split`? One sentence in `answers.md`.
3. Restore `PIPELINE_TEST_SIZE=0.25`.

### Exercise 5 — Commit your work (5 min)

1. Run `git status` from the repository root. You should see your modified files — and you should **not** see `.env` or `.venv/` (that is `.gitignore` doing its job).
2. Stage and commit with a meaningful message:

   ```bash
   git add labs/week-01-env-setup/starter
   git commit -m "week01: add random forest model and split test"
   ```

3. Run `git log --oneline -3` and confirm your commit is on top. From now on, every exercise ends with a commit — version control is the first MLOps habit.

### Exercise 6 — Docker smoke test (2 min)

```bash
docker run --rm python:3.12-slim python -c "print('Docker works')"
```

If it prints `Docker works`, you are ready for Week 2.

---

## Repository structure

```
starter/
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── README.md
├── data/
│   └── diabetes.csv
├── src/
│   ├── main.py
│   └── week_01_env_setup/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── data.py
│       └── model.py
└── tests/
    ├── __init__.py
    ├── test_config.py
    └── test_data.py
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `uv: command not found` | Restart your shell after installation |
| `python` points to wrong version | Ensure Python 3.12+ is first on `PATH`, or let `uv` manage it: `uv python install 3.12` |
| `FileNotFoundError: Dataset not found` | Run commands from the `starter/` directory |
| Docker daemon not running | Start Docker Desktop (macOS/Windows) or `sudo systemctl start docker` (Linux) |
| Import errors | Use `uv run python src/main.py`, not plain `python` |

## Next steps

In Week 2 this project gets its first real infrastructure: MLflow, MinIO, and Postgres running via Docker Compose.
