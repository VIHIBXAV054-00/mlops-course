# HW 1: Data Versioning and Experiment Tracking

| | |
| --- | --- |
| **Released** | Week 5 |
| **Due** | 23:59 (Budapest) on Sunday of **Week 8** (1 November) |
| **Estimated effort** | 8–10 hours |
| **Builds on** | Week 1 (dev environment), Week 2 (local services), Week 3 (MLflow), Week 4 (DVC) |

---

## Objective

Turn your project repository into a **reproducible MLOps project**:

- One command brings up its infrastructure.
- One command runs its pipeline.
- The dataset is versioned by content hash and stored in object storage.
- Every training run records the model's parameters, metrics, and the dataset version it was trained on.
- The best model is registered under a name and alias that a colleague can resolve.

This is the first of five assignments that build on the same repository - the one you created
from `project-template/` in the Week 2 *Define Project Topic* milestone, with your own dataset.

You will use only tools from Labs 1–4. **No Pandera, no data validation.**

---

## Requirements

Each requirement is independently checkable. The grader runs commands for R1–R7 and reads for
R8–R10.

### R1: A reproducible environment (8 points)

- The repository is a `uv` project with `pyproject.toml` **and a committed `uv.lock`**.
- `uv sync --all-groups` succeeds from a fresh clone.
- `uv run pytest -q` passes, and passes **without** Docker running (tests that need
  infrastructure must skip, not fail).
- `README.md` states the exact commands to install, configure and run.

### R2: One-command local services (10 points)

- A `compose.yaml` bringing up **Postgres, Silo and MLflow**, adapted from the Week 2 lab.
- `docker compose up -d --wait` succeeds and all services report healthy.
- An explicit top-level `name:` - otherwise Compose derives the project name from your
  directory and collides with the course labs.
- Host ports documented. If you keep the labs' 55xx block, say so in the README, because it
  means only one stack can run at a time.
- **No secrets in Git.** Credentials come from `.env`, which is git-ignored; `.env.example`
  is committed with placeholder values.

### R3: DVC tracking your dataset (12 points)

- `dvc init --subdir` (or plain `dvc init` if your project repo has its own root) is done, and
  `.dvc/config` **is committed**.
- Your dataset is tracked with `dvc add`, and the resulting `.dvc` pointer file **is committed**
  while the data file itself is git-ignored.
- The README quotes your pointer's `md5` and `size`, and states the row and column count of the
  data it names.

### R4: Silo as the DVC remote, working both ways (12 points)

- A default DVC remote pointing at a Silo bucket over `endpointurl`.
- `dvc push` uploads the data; the object is visible in the Silo console under
  `files/md5/<first two chars>/<remaining 30>`.
- **`dvc pull` works from a fresh clone.** Prove it: clone your own repo into a new directory,
  `dvc pull`, and confirm the data appears with the same md5. Put the commands and their output
  in `docs/hw1.md`.
- **`.dvc/config` contains no credentials.** If you used `dvc remote modify --local`, confirm
  `.dvc/config.local` is git-ignored and not in the repository.

### R5: At least two dataset versions (10 points)

- Two distinct versions of your dataset, each with its own commit and its own pointer md5. How
  you produce the second is up to you: append rows, add a feature, fix an encoding, or split
  your file into batches as the course dataset does. Say in `docs/hw1.md` what changed and why.
- Demonstrate moving between them: `git checkout <commit> -- <your>.dvc` followed by
  `dvc checkout`, with the md5 before and after.

### R6: A declared pipeline (12 points)

- A `dvc.yaml` with at least three stages: **prepare → train → evaluate**.
- Every `cmd` is something you can also run by hand.
- Source files appear in `deps`, so editing your training code makes `train` stale.
- Hyperparameters live in **`params.yaml`**, not in `.env` - DVC can only hash a file.
- `metrics/metrics.json` is a `cache: false` metrics output, so it is committed.
- `dvc.lock` **is committed**.
- Running `dvc repro` twice re-runs nothing the second time. Show that output.
- Change one parameter and show that **only the affected stages** re-run.

### R7: MLflow tracking and the model registry (16 points)

- Runs land in a named experiment on the containerised MLflow server, with **parameters,
  metrics and a logged model** (`mlflow.sklearn.log_model`).
- At least **four runs** comparing more than one hyperparameter setting. One table in
  `docs/hw1.md` comparing them, with your reasoning about which is best and on which metric.
- The winning model is **registered** under a model name, with a **version** and an **alias**
  (e.g. `staging`).
- The registered version's `run_id` is **populated**: it is the link from the registry back to
  the run, and without it the whole chain breaks. Registering from `runs:/<run_id>/model` (as
  the labs do) or from the `models:/<model_id>` URI that `log_model` returns both populate it
  on the course's MLflow version. Show the `run_id` in `docs/hw1.md`.
- Every run carries a `git_commit` tag.

### R8: The data version on the run (10 points)

- Each training run records **which data it trained on**: a tag carrying your dataset's DVC md5
  (`dvc_md5` or equivalent), plus the remote URI.
- A short script or CLI subcommand that, given a data md5, lists the runs trained on it - the
  Week 4 `runs-for-data` pattern. Show its output.

### R9: The traceability chain, written down (6 points)

In `docs/hw1.md`, walk the chain for your registered model, with the real values from your
project:

```
alias -> model version -> run id -> params + metrics -> git commit -> data md5 -> remote URI
```

Every arrow must be something the grader could follow themselves.

### R10 - README and reflection (4 points)

- `README.md`: what the project predicts, how to run it, what the host ports are.
- `docs/hw1.md`: the evidence for R3–R9, plus **one paragraph** on the hardest thing you hit
  and how you diagnosed it.

---

## Submission

Push to your project repository (the private one created from `project-template/`) and submit
**the URL of the commit** you want graded in the HW 1 assignment in Moodle, for example
`https://github.com/<your-username>/<your-project-repo>/commit/<SHA>`.

Your repository must contain:

| Path | What |
| --- | --- |
| `pyproject.toml`, `uv.lock` | the environment |
| `compose.yaml`, `.env.example` | the services (never `.env`) |
| `.dvc/config`, `<your-data>.dvc`, `dvc.lock`, `params.yaml`, `dvc.yaml` | data versioning + pipeline |
| `metrics/metrics.json` | the committed metrics output |
| `src/`, `tests/` | your code and its tests |
| `README.md`, `docs/hw1.md`, `docs/proposal.md`, `docs/DATA_DICTIONARY.md` | documentation |

**Do not commit:** `.env`, `.dvc/cache/`, `.dvc/tmp/`, `.dvc/config.local`, `.venv/`, your data
file, or model binaries outside the DVC cache.

Grant your instructor read access to the repository.

### The commands the grader will run

From a **fresh clone** of your submitted commit:

```bash
uv sync --all-groups
uv run pytest -q                      # must pass with Docker stopped
cp .env.example .env                  # then fill in per your README
docker compose up -d --wait
dvc pull                              # must fetch your data from Silo
dvc repro                             # must reproduce, or report everything up to date
dvc repro                             # must re-run nothing
dvc metrics show
dvc dag
```

---

## Grading

| Requirement | Points | How |
| --- | --- | --- |
| R1 reproducible environment | 8 | running |
| R2 one-command services | 10 | running |
| R3 DVC tracking | 12 | running + reading |
| R4 Silo remote, round trip | 12 | running (fresh clone + `dvc pull`) |
| R5 two dataset versions | 10 | running + reading |
| R6 declared pipeline | 12 | running |
| R7 MLflow tracking + registry | 16 | running + reading |
| R8 data version on the run | 10 | running |
| R9 traceability chain | 6 | reading |
| R10 README + reflection | 4 | reading |
| **Total** | **100** | |

**Automatic deductions**, because these are the failures the assignment exists to prevent:

- credentials committed anywhere (`.env`, `.dvc/config`, hardcoded in source): **−20**
- `uv.lock` or `dvc.lock` missing: **−10** each
- the data file not DVC-tracked: **−10**
- a registered model version with an empty `run_id`: **−8**
- `uv run pytest` failing on a fresh clone with Docker stopped: **−8**

**Tooling scope.** Requirements are satisfiable with Labs 1–4 only.

**AI tool policy.** Assistants are permitted and encouraged. You must be able to explain every
line you submit, and you may be asked to.

---

## Advice

- **Do R4 early and do it properly.** The fresh-clone `dvc pull` is where most submissions
  break, and it always breaks for one of two reasons: the pointer was never committed, or the
  data was never pushed.
- **Read the lab READMEs' troubleshooting tables before debugging from scratch.** Many errors are documented there with their exact error messages and solutions.
- **Commit as you go.** R5 needs two dataset versions in two commits, and your history is
  easier to produce as you work than to reconstruct afterwards.
