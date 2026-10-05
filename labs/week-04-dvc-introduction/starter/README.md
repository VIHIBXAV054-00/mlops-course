---
description:
  title: "Week 4 Lab: DVC Introduction"
  summary: |
    Put the training data under version control with DVC, using the Week 2/3
    Silo as an S3 remote. Track a dataset by content hash, push the bytes,
    travel between versions, declare the pipeline as a graph with dvc.yaml, and
    stamp the data version onto the MLflow run so the traceability chain finally
    reaches the bytes.
---

# Week 4 Lab: DVC Introduction

Last week's traceability chain went from a deployed alias back to a run and its git
commit, and then stopped at `data/diabetes.csv`: a **path**.

Today you give the data an identity. You track a dataset by its content hash and store the
bytes in Silo. You add new batches as new versions, move between them, and declare the pipeline in
`dvc.yaml`. Then
you record the data version on the MLflow run, and stop a run that would record the wrong
one.

Background for every exercise: the Week 4 lecture and `docs/notes/week-04-notes.md`.

## Based on

- **DVC Get Started:** https://doc.dvc.org/start
- **S3-compatible remotes (for Silo):** https://doc.dvc.org/user-guide/data-management/remote-storage/amazon-s3
- **`dvc.yaml`:** https://doc.dvc.org/user-guide/project-structure/dvcyaml-files
- **Command reference:** https://doc.dvc.org/command-reference
- **MLflow datasets:** https://mlflow.org/docs/latest/ml/dataset/

**Deviations from the tutorial:**

1. **`dvc init --subdir`**, because this lab is a subfolder of a larger Git repository.
2. **A Silo remote**, not a local folder, because "the data is on my laptop" is the
   problem we are solving.
3. **Keys from the environment**, not `dvc remote modify --local`. You export the Silo
   keys from `.env` in your terminal (the Makefile does the same), so no key is written
   into a config file.
4. **`core.autostage true`**, so a forgotten `git add` of a `.dvc` file cannot lose a data
   version.
5. **The Pima diabetes batches**, the course's running example.

## Prerequisites

- Docker Desktop, or Docker Engine with the Compose plugin, version 24+
- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Ports **5500, 5510, 5511, 5532** free
- **Stop your Week 3 stack first.** It uses the same ports:
  ```bash
  cd ../../week-03-mlflow-integration/starter && docker compose down
  ```

---

## Step 1: dependencies

```bash
uv sync --all-groups
```

New this week: **`dvc[s3]`**. `boto3` and `matplotlib` are no longer needed.

## Step 2: configuration

```bash
cp .env.example .env
```

Set `MLFLOW_MODEL_OWNER` to your name. `DVC_BUCKET` names a **second** Silo bucket, for
the data.

`PIPELINE_RANDOM_SEED`, `PIPELINE_TEST_SIZE` and `PIPELINE_MAX_ITER` are moved to `params.yaml` for tracking.

## Step 3: tests before you start

```bash
uv run pytest tests/ -v
```

Expected: **26 passed, 25 skipped**. Each skip names the exercise that unlocks it.

## Step 4: start the stack

```bash
make up
```

Open the Silo console at http://localhost:5511. You should see **two** buckets:
`mlflow-artifacts` and `dvc-storage`.

---

## Exercises

Do them in order. Exercises 2, 4, 5 and 6 ask for a **written answer** (and Exercise 7, if
you do it): write it in `answers.md` in this folder and **commit it with your code**.
Exercise 7 is optional.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| Version the data | 1–3 | 25 min |
| New batches | 4 | 15 min |
| The pipeline | 5 | 15 min |
| Link to MLflow | 6 | 15 min |
| Finish: commit and submit | — | 5 min |
| Optional: data you have not added | 7 | 10 min |

### Exercise 1: initialise DVC and point it at Silo (≈ 5 min)

DVC needs a project and a **remote**: the storage that holds the data. Here the remote is
the `dvc-storage` bucket in Silo. The remote is written into `.dvc/config`, which is
committed to Git. You set this up once per repository, and you check it in every new project you join.

**Do:**

1. Read the `dvc-init` target in the Makefile: it is six commands. `--subdir` is needed
   here; `endpointurl` is what points an "S3" remote at Silo.
2. Run it: `make dvc-init`
3. Look at what was created, then commit:
   ```bash
   cat .dvc/config          # the remote, and no keys
   cat .dvc/.gitignore
   git add .dvc/config      # dvc init staged it before the remote was added
   git status               # .dvc/config, .dvc/.gitignore and .dvcignore are staged
   git commit -m "week04: initialise DVC with Silo as the remote"
   ```

**Check:** to check your work, run `uv run pytest tests/test_dvc_repo.py`. It prints
`4 passed, 6 skipped`.
`.dvc/config` names the remote `storage` and contains no key or password.

**Stuck?**
1. Lecture: "Install DVC and start a project" · Notes: "Installing DVC and `dvc init`"
2. DVC docs: https://doc.dvc.org/command-reference/init and
   https://doc.dvc.org/command-reference/remote/add
3. "Not tracked by any supported SCM tool" means `dvc init` ran without `--subdir`.

### Exercise 2: add, read the pointer, push (≈ 15 min) *(written answer)*

A clinic sends its measurements in batches, one CSV file at a time. The batches wait in
`data/incoming/`. When a batch arrives, it is copied to `data/raw/`, which is committed to
Git. The training data is one file, `data/measurements.csv`: all the batches in `data/raw/`,
merged. DVC tracks this file. Each time a batch arrives, you rebuild the file, and DVC
records a new version.

In this exercise the first batch arrives, and you record it as version 1 (461 rows). The
data goes to Silo, and a small pointer file goes to Git. This is how you share a dataset
with a teammate without emailing a CSV.

The code you use:

- `src/week_04_dvc_introduction/cli.py` runs every command of this lab
  (`uv run python src/main.py <command>`), and the Makefile targets call it. You do not need
  to change it.
- `make next-batch` copies the next batch from `data/incoming/` to `data/raw/`.
- `make build-data` calls `build_measurements` in `src/week_04_dvc_introduction/datasets.py`.
  You write this function.

**Do:**

1. The first batch arrives: `make next-batch` prints `batch_01.csv arrived: 461 rows`.
2. Implement `build_measurements` in `src/week_04_dvc_introduction/datasets.py`.
3. Build the dataset: `make build-data`. It prints 461 rows and the md5.
4. Give this terminal the Silo keys from `.env`. `dvc push` and `dvc pull` need them.
   Run this once in every new terminal:
   ```bash
   set -a && . ./.env && set +a
   export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
   ```
5. Track, commit and push version 1:
   ```bash
   uv run dvc add data/measurements.csv
   git add data/raw
   git status               # the pointer, data/.gitignore and data/raw/batch_01.csv are staged
   git commit -m "week04: dataset version 1 (batch_01)"
   uv run dvc push          # 1 file pushed
   ```
6. Look at three things:
   - `data/measurements.csv.dvc`: the pointer (`md5`, `size`, `hash`, `path`);
   - `data/.gitignore`: DVC wrote it, so Git ignores the data file;
   - the Silo console: in `dvc-storage`, open `dvcstore/files/md5/`, then the folder named
     after the **first two characters** of your md5.

**Check:** to check your work, delete the Exercise 2 skip markers in `tests/test_datasets.py`
and run `uv run pytest tests/test_datasets.py`. It prints `6 passed, 2 skipped`. The md5 in
your pointer is `786c54f2770fa1e7ea5438e6e44b6486`.

**Stuck?**
1. Lecture: "`dvc add` writes a pointer file" · Notes: "DVC: pointers in Git, data in Silo"
   and "Byte-exact hashing and line endings"
2. pandas docs: https://pandas.pydata.org/docs/reference/api/pandas.concat.html and
   https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
3. A different md5 usually means line endings or a pandas index column in the file.

**Written answer** (in `answers.md`):

1. What did Git gain in this commit, and about how many bytes is it? What did Silo gain?
   Why is that difference the whole idea of DVC?
2. A classmate runs `make build-data` with the same batch and gets a byte-identical `.dvc` file. Name two things
   `build_measurements` does to make that true, and one thing that would break it.
3. A teammate clones the repository. They have `data/measurements.csv.dvc` but no
   `data/measurements.csv`. What single command do they run, and what two things must be
   true for it to work?

### Exercise 3: prove the round trip (≈ 5 min)

DVC has two ways to get data back. `dvc checkout` restores it from the local cache, and
`dvc pull` downloads it from the remote first. You need the difference when you restore a
file after an accidental deletion, and when a new teammate clones the repository.

**Do:** delete the data file **and** the cache, then try to get the data back:

```bash
rm data/measurements.csv
rm -rf .dvc/cache
uv run dvc checkout data/measurements.csv   # fails: the bytes are not in the cache
uv run dvc pull data/measurements.csv       # downloads them from Silo
uv run python src/main.py verify-data       # compares the file with its pointer
```

Name the file in each command. Without it, DVC also tries to restore other outputs.
`make dvc-roundtrip` runs the same steps.

**Check:** `dvc checkout` ends with `Checkout failed for following targets`, `dvc pull`
prints `1 file fetched and 1 file added`, and `verify-data` prints
`workspace matches pointer: True`.

**Stuck?**
1. Lecture: "`dvc checkout`: restore from the cache" and "`dvc pull`: download data" ·
   Notes: "`checkout` and `pull`".
2. DVC docs: https://doc.dvc.org/command-reference/checkout and
   https://doc.dvc.org/command-reference/pull
3. `Unable to locate credentials` means this terminal has no keys: repeat step 4 of
   Exercise 2.

### Exercise 4: new batches and time travel (≈ 15 min) *(written answer)*

Two more batches arrive, so the dataset gets versions 2 and 3. Then you go back to
version 1 and forward again. "Which data did last month's model see?" is a question you
will be asked at work, and this is how you answer it.

**Do:**

1. The second batch arrives. Build, track, commit and push version 2:
   ```bash
   make next-batch                                 # batch_02.csv arrived: 107 rows
   make build-data                                 # 568 rows
   uv run dvc status data/measurements.csv.dvc     # modified: data/measurements.csv
   uv run dvc add data/measurements.csv
   git add data/raw
   git commit -m "week04: dataset version 2 (batch_02)"
   uv run dvc push
   ```
2. The third batch arrives: repeat step 1 for version 3 (`batch_03.csv`, 768 rows).
3. Find the version 1 commit: `git log --oneline -- data/measurements.csv.dvc` lists three
   commits, with version 3 on top. Copy the hash of version 1. Compare the versions, go back
   to version 1, then forward again:
   ```bash
   uv run dvc diff --targets data/measurements.csv -- <version 1 commit>
   git checkout <version 1 commit> -- data/measurements.csv.dvc
   uv run dvc checkout data/measurements.csv
   uv run python src/main.py verify-data           # 461 rows
   git checkout HEAD -- data/measurements.csv.dvc
   uv run dvc checkout data/measurements.csv       # 768 rows again
   ```
   `make dvc-timetravel REV=<version 1 commit>` runs the same time travel.

**Check:** to check your work, delete the Exercise 4 skip markers in `tests/test_datasets.py`
and run `uv run pytest tests/test_datasets.py`. It prints `8 passed`. Version 2's md5 is
`66f7...`, and version 3's is `a8fd...`.

**Stuck?**
1. Lecture: "Going back to version 1" · Notes: "Going back to an earlier version".
2. DVC docs: https://doc.dvc.org/command-reference/diff and
   https://doc.dvc.org/command-reference/checkout
3. `pathspec ... did not match` means that commit has no pointer. Use the version 1 commit
   from `git log --oneline -- data/measurements.csv.dvc`.

**Written answer** (in `answers.md`):

1. Time travel took **two** commands. What did `git checkout` change on disk, what did
   `dvc checkout` change, and why can neither do the other's job?
2. You try the same time travel on a laptop that never pulled version 1. What happens?

### Exercise 5: declare the pipeline (≈ 15 min) *(written answer)*

The pipeline has three stages: `prepare → train → evaluate`. You declare them in
`dvc.yaml`, so DVC knows what each stage reads and writes, and re-runs only what a change
affects. A declared pipeline lets a colleague, or CI, rebuild your model without asking you
how.

**Do:**

1. In `dvc.yaml`, add the `train` and `evaluate` stages. Read `train()` and `evaluate()` in
   `pipeline.py`, and list every file each stage reads (data and source code), every param
   it uses and every file it writes.
2. Run the pipeline twice:
   ```bash
   make repro      # runs every stage
   make repro      # runs nothing: "didn't change, skipping"
   make dag
   make metrics
   ```
3. Change `train.C` from `1.0` to `0.1` in `params.yaml`, run `make repro` again, then:
   ```bash
   uv run dvc params diff
   uv run dvc metrics diff
   ```
   Set `train.C` back to `1.0` and run `make repro`.
4. Open `dvc.lock` and read it.

**Check:** to check your work, delete the skip markers in `tests/test_dvc_yaml.py` and run
`uv run pytest tests/test_dvc_yaml.py`. It prints `3 passed`. After the `C` change,
`prepare` is skipped and `train` and `evaluate` run. `make dag` shows four nodes.

**Stuck?**
1. Lecture: "Pipeline stages" and "`dvc repro` is like `make`" · Notes: "The pipeline"
2. DVC docs: `dvc.yaml` files (link above)
3. If `evaluate` does not re-run after `train`, check that every file it reads is in its
   `deps`.

**Written answer** (in `answers.md`):

1. List the `deps` of your `evaluate` stage. Pick one and say what happens if it is missing
   from the list. Does the pipeline fail, or does it run and give a wrong result?
2. Version 3 has the same 768 rows as `data/diabetes.csv`. Compare `make metrics` with the
   course's pinned baseline (accuracy 0.7344, F1 0.5785). They differ. Explain why "the
   same rows" is not "the same dataset".

### Exercise 6: link the run to the data version (≈ 15 min) *(written answer)*

Your MLflow runs do not record yet which data they trained on. In this exercise every
training run gets the data version as tags, so you can find runs by the data they used. In
an incident review, "which runs used the broken data?" must take one query.

**Do:**

1. Implement `log_data_version` and `log_dataset_input` in
   `src/week_04_dvc_introduction/dvc_link.py`. The TODOs name the tags and fields.
2. Run:
   ```bash
   make link             # forces a fresh training run
   make runs-for-data
   make register && make promote && make trace
   ```

`make link` runs `dvc repro -f -s train`: `-f` forces the stage, and `-s` forces only that
one stage. Without it, `dvc repro` would correctly skip `train`, because nothing changed.

**Check:** to check your work, delete the skip markers in `tests/test_mlflow_link.py` and
run `uv run pytest tests/test_mlflow_link.py`. It prints `5 passed` with the stack up.
`make link` prints the MLflow digest next to the DVC md5: they differ. `make trace` shows the md5
on its `5. Data version` line.

**Stuck?**
1. Lecture: "A tag with the hash makes a new question possible" and "Two hashes of the same
   file" · Notes: "Linking the data version to the MLflow run"
2. MLflow docs: Datasets (link above)
3. The `source` you pass to MLflow must be an `s3://` URI; the helper `dvc_data_url` gives one.

**Written answer** (in `answers.md`):

1. MLflow's digest has 8 characters; DVC's md5 has 32. What does each one hash? Which would
   you give an auditor who asks you to prove which bytes trained this model? What is the
   other one good for?
2. Run `make runs-for-data` and write down the filter string it used. What question does it
   answer that Week 3 could not?
3. Run `make trace` and compare it with Week 3's output. Which line is new? Is the chain now
   complete, or is there still a link you cannot follow?

### Exercise 7 (optional): catch data you have not added (≈ 10 min) *(written answer)*

A run's data tag is only true if the file on disk is the file its pointer names. At work you
fix a few rows and retrain at once, before `dvc add`. A year later, an audit trusts the
run's tag. In this exercise you see a run record the wrong version, and you add a check
that stops it.

**Do:**

1. Open `data/measurements.csv` in your editor. In the first patient's row, change `bmi`
   from `33.6` to `33.7`, and save.
2. Look at the file the way Week 3 did, then the way DVC does:
   ```bash
   uv run python src/main.py verify-data          # same name, 768 rows, a new md5
   uv run dvc status data/measurements.csv.dvc    # modified: data/measurements.csv
   ```
   Week 3 logged only the file name and the row count. Both are unchanged.
3. Train by hand, as you would when you debug a stage:
   ```bash
   uv run python src/main.py prepare
   uv run python src/main.py train
   make runs-for-data
   ```
   Compare the `DVC md5` that `train` prints with the md5 from `verify-data`. The new run
   is listed as trained on version 3, but it trained on your edit.
4. Implement `require_data_added` in `dvc_link.py`. Run `uv run python src/main.py train`
   again: it stops.
5. Undo your edit and rebuild:
   ```bash
   uv run dvc checkout --force data/measurements.csv
   make repro
   ```

**Check:** to check your work, delete the skip markers in `tests/test_data_added.py` and run
`uv run pytest tests/test_data_added.py`. It prints `2 passed`. In step 4, `train`
prints ``Cannot run `train` yet`` and tells you to run `dvc add`.

**Stuck?**
1. Lecture: "Last week's data tracking was incomplete" and "Training on data you have not
   added" · Notes: "Training on data you have not added"
2. DVC docs: https://doc.dvc.org/command-reference/status
3. `file_md5` and `pointer_md5` give you the two values to compare.

**Written answer** (in `answers.md`):

1. Which bytes did the run from step 3 train on, and which version does its tag name? An
   auditor finds this run a year later. What do they conclude, and why is that worse than a
   run with no data tag?
2. Your check runs inside the `train` stage. Name one other place in a team's workflow
   where the same check could run, and say what it costs.

## Finish: commit and submit your work (≈ 5 min)

Run the whole test suite first: `uv run pytest tests/` prints `49 passed, 2 skipped` with the
stack up (`51 passed` if you did Exercise 7), and `44 passed, 7 skipped` with it down (`46 passed, 5 skipped` with Exercise 7).

```bash
git status          # answers.md must appear; .env and .venv/ must NOT
git add .
git commit -m "week04: version the dataset with DVC, link it to MLflow, and write up the exercises"
```

Check that **none** of these appear: `.env`, `.venv/`, `.dvc/cache/`, `.dvc/config.local`,
`data/measurements.csv`. The last one is supposed to be missing: its pointer is what belongs
in Git.

Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
and upload that URL to Moodle.

---

## What lives where

| Thing | Where it lives | Why |
| --- | --- | --- |
| `data/incoming/batch_*.csv` | Git | the batches that have not arrived yet (a simulation) |
| `data/raw/batch_*.csv` | Git | the batches that have arrived; the dataset is built from them |
| `data/diabetes.csv` | Git | the Week 1–3 snapshot, unchanged |
| `data/measurements.csv` | **Silo** (`dvc-storage`) | the versioned dataset |
| `data/measurements.csv.dvc` | Git | four lines naming the bytes above |
| `dvc.yaml`, `params.yaml` | Git | what you declared |
| `dvc.lock` | Git | what actually ran |
| `metrics/metrics.json`, `models/mlflow_run_id.json` | Git | `cache: false`, so they show in a diff |
| `models/model.pkl`, `data/processed/*.csv` | DVC cache / Silo | outputs the pipeline can rebuild |
| `.dvc/config` | Git | the shared remote definition |
| `.dvc/config.local`, `.dvc/cache/`, `.dvc/tmp/` | nowhere (git-ignored) | local only; `config.local` can hold keys |

## Tear-down

```bash
make down      # stop; data and runs stay in the volumes
make down-v    # stop AND delete both buckets and the database
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `ERROR: failed to initiate DVC - ... is not tracked by any supported SCM tool` | You ran `dvc init` without `--subdir`. Use `make dvc-init`. |
| `NoCredentialsError` / `Unable to locate credentials` on `dvc push` or `dvc pull` | This terminal has no Silo keys. Repeat step 4 of Exercise 2, or use the Makefile. |
| `dvc push` fails with a TLS/SSL error | The endpoint is `http://`. Run `uv run dvc remote modify storage use_ssl false`. |
| `make repro` says "didn't change, skipping", but you want a new MLflow run | Correct: nothing changed. Use `make link`. |
| `No batch file in data/raw` | No batch has arrived yet. Run `make next-batch` (Exercise 2). |
| `ERROR: Checkout failed ... Is your cache up to date?` | That version is not in your cache. Run `dvc pull` (Exercise 3). |
| `dvc checkout` or `dvc pull` fails on `data/processed/*.csv` before Exercise 5 | Name the file: `uv run dvc pull data/measurements.csv`. |
| `error: pathspec ... did not match` in Exercise 4 | That commit has no pointer. Use the version 1 commit from `git log --oneline -- data/measurements.csv.dvc`. |
| `Can't remove the following unsaved files without confirmation` | `dvc checkout` protects your edit. Add `--force` to discard it (Exercise 7). |
| `dvc status` says `modified` after a fresh clone | Line endings (CRLF). The lab's `.gitattributes` forces LF; try `git add --renormalize .`. |
| `Bind for 0.0.0.0:5500 failed: port is already allocated` | Another week's stack is running. Stop it with `docker compose down` in that folder. |
| `dvc dag` opens a pager | Press `q`. The Makefile avoids this with `DVC_PAGER=cat`. |
| Only one bucket in the Silo console | Your `.env` is older than this lab. Set `DVC_BUCKET=dvc-storage`, then `make down-v && make up`. |

## Next steps

You can now prove which data trained a model. Nothing has checked whether the data is
correct: `data.require_columns` only checks that the columns exist, and it is not a schema.
The `glucose`, `insulin` and `bmi` columns still contain impossible zeros. Week 5
adds data contracts and validation with Pandera.
