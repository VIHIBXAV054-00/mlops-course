---
description:
  title: "Week 7 Lab: CI Workflow"
  summary: |
    Run the Week 5 and 6 checks on every push with GitHub Actions (CI), and
    retrain the model on a schedule with the same checks (CT).
---

# Week 7 Lab: CI Workflow

In previous weeks, you wrote a data contract and a model gate. Currently, these are run manually.
**Continuous integration (CI)** makes a machine run the checks on every
push, on a fresh runner that has nothing but your repository, so a broken change fails
the build before anyone merges it. **Continuous training (CT)** retrains the model on a
schedule, and the same checks decide whether the new model is good enough.

Today you set up both with GitHub Actions.

Background for every exercise: the Week 7 lecture and `docs/notes/week-07-notes.md`.

## Based on

- **GitHub Actions quick start:** https://docs.github.com/en/actions/get-started/quickstart
- **Workflow syntax:** https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- **Events that trigger workflows** (`push`, `pull_request`, `schedule`, `workflow_dispatch`):
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- **Workflow commands** (annotations, `$GITHUB_STEP_SUMMARY`):
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- **Astral, Using uv in GitHub Actions:** https://docs.astral.sh/uv/guides/integration/github/
- **pytest, Working with custom markers:** https://docs.pytest.org/en/stable/example/markers.html
- **Ruff linter:** https://docs.astral.sh/ruff/linter/

**Deviations from the references:**

1. **You write the workflows inside the lab, and `make install-ci` copies them to the
   repository root.** GitHub runs workflows only from `.github/workflows/` at the root. The
   copy keeps each lab in its own folder.
2. **No service containers.** The pipeline runs on a bare runner, with no Docker, MLflow,
   Silo or DVC remote. So CI can train, evaluate and gate, but it cannot register or
   promote a model.
3. **`ruff check` with an explicit `select`, and no `ruff format` check.** A formatting
   check would change half of the files and hide this week's changes.
4. **Actions are pinned to a major tag (`@v7`), not to a commit SHA.** The lecture explains
   the trade-off.

## Prerequisites

- `uv`: https://docs.astral.sh/uv/getting-started/installation/
- Git, and your copy of the course repository on GitHub, with **Actions enabled**
  (Settings → Actions → General). You push to it from Exercise 4 on.
- Docker is needed only for the 8 tests that use the MLflow stack. CI does not run them.
- **Stop your Week 6 stack if it runs.** Every lab uses the same ports:
  ```bash
  cd ../../week-06-evaluation-pipeline/solution && docker compose down
  ```

---

## Step 1: dependencies

```bash
uv sync --all-groups
```

New this week: **`ruff`**, a linter, in the `lint` group. Its version and its rules are set
in `pyproject.toml`.

## Step 2: configuration

```bash
cp .env.example .env
```

The experiment is now `diabetes-week7`.

## Step 3: the dataset and the pipeline

Build the data from the two batches in `data/raw/`, then run the pipeline:

```bash
make data-v2
make verify-data
make repro
```

Expected output of `make verify-data`: `workspace matches pointer: True`. `make repro` prints
accuracy 0.7656, precision 0.6964, recall 0.5821, F1 0.6341 and ROC AUC 0.8345, and the gate
prints:

```text
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)
```

These are the Week 6 numbers: this week does not change the model.

## Step 4: lint and tests before you start

```bash
make lint
uv run pytest tests/
```

Expected output: `All checks passed!`, then **162 passed, 24 skipped**. Of the skipped tests,
16 wait for Exercises 4 and 5, and 8 need the MLflow stack.

---

## Exercises

Do them in order. Exercises 1, 5 and 6 ask for a **written answer**: write it in
`answers.md` in this folder and **commit it with your code**.

| Block | Exercises | Time |
| --- | --- | --- |
| Setup (Steps 1–4) | — | 10 min |
| The checks | 1–3 | 35 min |
| The workflows | 4–5 | 40 min |
| Finish: commit and submit | — | 5 min |
| Optional: inspect a failed build | 6 | 15 min |

### Exercise 1: the autograder workflow (≈ 10 min) *(written answer)*

Every push you made since Week 1 ran a workflow: `.github/workflows/autograde.yml` at the
root of your repository. Until now it ran in the background; now open it and see what
it does.

**Do:**

1. Open `.github/workflows/autograde.yml` at the repository root and read it: what starts
   it, which jobs it has, and which commands it runs.
2. List every workflow and its action pins:
   ```bash
   make ci-explain
   ```
   Expected output: `autograde.yml` and `slides.yml` under "Workflows GitHub runs", and a
   table with one row per `uses:`. The last line is:
   ```text
     1 pin(s) behind the newest published major tag.
   ```

**Check:**

- You can name the command `autograde.yml` runs, and the folders it runs it in.
- You can name the stale pin, and the pin whose newest release has no major tag.

**Stuck?**

- Lecture: "GitHub Actions example" and "Our pins on 6 August 2026"
- Notes: "GitHub Actions example" and "Pinning actions"
- GitHub docs: the workflow syntax page (link above)
- `make ci-explain` compares the pins with a snapshot in `workflows.py`, not with GitHub.

**Written answer** (in `answers.md`):

1. What is `autograde.yml` for? Which commands does it run, and in which folders?

### Exercise 2: one pipeline definition (≈ 10 min)

When code is used in several places, you write it once, as a function, and call it. A
pipeline is the same: write it once, as the `make ci` target, and let your laptop and every
workflow call it.

**Do:**

1. Run the target before you write it:
   ```bash
   make ci
   ```
   Expected output: `make ci is not written yet (Exercise 2).`
2. In the `Makefile`, write the `ci` target: lint, the tests that need no services, the
   pipeline and the gate, in this order. Use the targets that already exist.
3. Run it:
   ```bash
   make ci
   ```
   Expected output: the gate prints `GO — 13 passed, 0 failed, 4 SKIPPED`, and the last line
   is `CI passed: lint, tests, pipeline, gate.`

**Check:**

- Run `make ci-fail`. It changes `train.C` to 0.005, runs `make ci`, and restores
  `params.yaml`.
  Expected output:
  ```text
  NO-GO. 4 acceptance criteria failed: minimum.f1, regression.f1, slice.age_band.30-39, fairness.age_band.tpr_gap.
  ```
  and then `make ci exit code: 2`. Run `make repro` afterwards to return to a GO.
- The `ci` target has no recipe lines of its own apart from the final message.

**Stuck?**

- Lecture: "One pipeline definition" and "What is on your laptop and not in
  the repository?"
- Notes: "One pipeline definition"
- GNU make manual, prerequisites: https://www.gnu.org/software/make/manual/make.html#Prerequisite-Types
- `make` builds the prerequisites in the order you list them, and stops at the first that
  fails.

### Exercise 3: sort the tests into layers (≈ 15 min)

CI runs each test layer as its own job, so only tests with a layer marker run in CI. A test
without one is left out. Classify the existing tests by the part of the system they check:
the code, the data or the model.

**Do:**

1. Run a test layer before adding markers:
   ```bash
   make test-unit
   ```
   Expected output: `186 deselected`, and make stops with `Error 5`, pytest's code for "no
   tests ran".
2. In each module in `tests/`, replace the Exercise 3 TODO with a `pytestmark` line: `unit`,
   `data`, `eval` or `integration`. Decide the layer by what the assertions check. In
   `test_dvc_repo.py` and `test_mlflow_link.py`, add the layer to the list next to the guard
   (`dvc`, `live`).
3. Where a module could fit two layers, write your choice and one reason in a comment above
   its `pytestmark`.

**Check:**

- Run `uv run pytest -m "not unit and not data and not eval and not integration"`.
  Expected output: `186 deselected`, so no test is without a layer.
- Run `make test-unit`, `make test-data` and `make test-eval`.
  Expected output, with the reference layers: `18 passed, 16 skipped, 152 deselected`,
  `62 passed, 124 deselected` and `72 passed, 114 deselected`. Your numbers differ if you
  chose another layer for a module; the total stays 186.

**Stuck?**

- Lecture: "The ML test pyramid", "Pytest markers" and "Marker types"
- Notes: "The ML test pyramid" and "Pytest markers"
- pytest docs: the custom markers page (link above)
- The layers are registered in `pyproject.toml`; `pytestmark` at the top of a module marks
  every test in it.

### Exercise 4: the code path, `ci.yml` (≈ 25 min)

Write the workflow that runs the checks on a runner on every push. Check its structure
locally, then run it on GitHub.

**Do:**

1. Write `.github/workflows/ci.yml`. The TODO at the top of the file lists what it needs,
   and `tests/test_workflows.py` checks it. The job graph:
   ```text
   lint ─┐
         ├─▶ pipeline ─▶ job summary and artifact
   test ─┘   (matrix: unit, data, eval)
   ```
2. Pin each action to a tag that exists. Run `make ci-explain` and read the rows for
   `ci.yml`.
3. Run the same steps as the runner, on your machine:
   ```bash
   make ci-local
   ```
   Expected output: lint, the three layers and the pipeline in turn, ending with the `GO`
   line.
4. Copy the workflows to the repository root, commit and push:
   ```bash
   make install-ci
   git add -A && git commit -m "week07: ci.yml" && git push
   ```
   Expected output of `make install-ci`: `installed -> .github/workflows/week07-ci.yml` and
   the same line for `week07-ct.yml`.
5. Open the Actions tab on GitHub and wait for the run. Save its URL.

**Check:**

- Delete the Exercise 4 skip markers in `tests/test_workflows.py`.
- Run `uv run pytest tests/test_workflows.py`.
  Expected output: `10 passed, 9 skipped`
- On GitHub: the run is green, its summary shows the gate verdict table, and the run has
  an artifact you can download.

**Stuck?**

- Lecture: "GitHub Actions example", "The job graph" and "One job per test layer"
- Notes: "The job graph and the matrix" and "A red build you can read"
- GitHub docs: the workflow syntax and workflow commands pages (links above)
- Astral docs: the uv in GitHub Actions guide (link above)
- If nothing runs after the push, check that the workflow is at the repository root.
- If every job fails at its first `make` step, check `defaults.run.working-directory`.

### Exercise 5: continuous training, `ct.yml` (≈ 15 min) *(written answer)*

A retrained model can reach production with no code change. With a CT workflow, the
retraining runs on a schedule, for example every Monday night; you can also start it by
hand from the Actions tab. It runs the same pipeline as CI and stops at the gate. The new
model is not registered: the runner has no MLflow, so registering stays a step you run
yourself.

**Do:**

1. Write `.github/workflows/ct.yml`. The TODO at the top of the file lists what it needs.
2. Run its steps locally:
   ```bash
   make ct-local
   ```
   Expected output: the pipeline runs, and the gate prints the `GO` line.
3. Install, commit and push as in Exercise 4. Then start the workflow by hand from the
   Actions tab ("Run workflow"), with a reason. Save the run's URL.

**Check:**

- Delete the Exercise 5 skip markers in `tests/test_workflows.py`.
- Run `uv run pytest tests/test_workflows.py`.
  Expected output: `19 passed`
- On GitHub: the CT run is green, and its summary shows the gate verdict table.

**Stuck?**

- Lecture: "Continuous training" and "Can a clock be trusted?"
- Notes: "Continuous training"
- GitHub docs: the events page, `schedule` and `workflow_dispatch` (link above)
- `ct.yml` needs no lint and no test jobs.

**Written answer** (in `answers.md`):

1. What differs between `ci.yml` and `ct.yml`, and what is the same? What does the
   difference change: who waits for the run, is there a diff to read, and who approved the
   input?
2. `ct.yml` stops at the gate: it does not register, promote or deploy. Give a reason that
   is not about credentials. Is a GO enough to release a model?
3. Name one way a `schedule:` trigger can run late, or not at all, without anyone being
   told.

### Exercise 6 (optional): inspect a failed build (≈ 15 min) *(written answer)*

CI keeps a worse model out of your main branch. In this exercise you push a worse model on
a branch, and inspect the report the CI run gives you: which jobs failed, at which step,
and why.

**Do:**

1. Create a branch, change `train.C` from 1.0 to 0.005 in `params.yaml`, commit and push:
   ```bash
   git switch -c week07-worse-model
   git commit -am "week07: train.C 0.005" && git push -u origin week07-worse-model
   ```
2. On GitHub, wait for the run to finish, and open its summary page. Check which jobs are
   green and which are red, read the job summary under the job graph, and download the
   artifact. Save the run's URL.
3. Switch back and delete the branch:
   ```bash
   git switch main
   git push origin --delete week07-worse-model && git branch -D week07-worse-model
   ```

**Check:**

- The `lint` and `test` jobs are green, and `pipeline` is red at the step that runs
  `make ci`.
- The job summary shows a FAIL verdict table with the failed checks.

**Stuck?**

- Lecture: "What can a green build hide?"
- Notes: "A red build you can read"
- If the run is green, check that the change reached `params.yaml` in the pushed commit.

**Written answer** (in `answers.md`):

1. Which jobs passed, which failed, and at which step? What does that tell you about what
   your tests check?
2. Where did the run say why it failed? List every place, and say which one you would send
   to a colleague.
3. The artifact was uploaded although the job failed. What made that happen?

## Finish: commit and submit your work (≈ 5 min)

1. Run `uv run pytest tests/`.
   Expected output: `178 passed, 8 skipped`. The 8 skipped tests need the MLflow stack.
2. At the top of `answers.md`, put the URLs of your green CI run and your manual CT run, and
   of your failed run if you did Exercise 6.
3. Commit your work:
   ```bash
   git status          # answers.md must appear; .env and .venv/ must not
   git add .
   git add ../../../.github/workflows/week07-ci.yml ../../../.github/workflows/week07-ct.yml
   git commit -m "week07: CI and CT workflows, test layers and written answers"
   ```
4. Check that the `Makefile`, the two workflows (in this lab and at the root), the test
   modules and `answers.md` are in the commit, and that `.env` and `.venv/` are not.
5. Push the commit, open it on GitHub (`https://github.com/<you>/<repo>/commit/<hash>`),
   and upload that URL to Moodle.

---

## Make targets

| Target | What it does |
| --- | --- |
| `make ci` | the one pipeline definition: lint, tests, pipeline and gate (Exercise 2) |
| `make ci-local` | the steps of `ci.yml`, on your machine, in the runner's order |
| `make ct-local` | the steps of `ct.yml`: retrain and gate |
| `make ci-fail` | change `train.C` to 0.005, run `make ci`, restore `params.yaml` |
| `make ci-explain` | the workflows, and their action pins against the snapshot |
| `make install-ci` / `make uninstall-ci` | copy the workflows to the repository root, or remove the copies |
| `make lint` | `ruff check src tests` with the pinned version and rules |
| `make test-unit` / `test-data` / `test-eval` / `test-integration` | one test layer each |
| `make gate-summary` | the recorded gate verdict as Markdown, for the job summary |

Every Week 6 target still works: `make repro`, `make gate`, `make slices`, `make fairness`,
`make register`, `make promote`, `make trace` and the rest.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| You pushed, and no workflow ran | The workflow is still only in the lab folder. Run `make install-ci`, then commit and push the copies at the repository root. |
| `Unable to resolve action ...@vN` | That major tag does not exist. Run `make ci-explain` and pin a tag that exists. |
| Every job fails at its first `make` or `uv` step | Without `defaults.run.working-directory`, the commands run at the repository root. |
| `make: *** No rule to make target '...'` | The workflow calls a target the Makefile does not have. `make ci-local` shows it in seconds. |
| `data/measurements.csv is missing` | The data is not in Git. Run `make data-v2`; the workflows do the same. |
| `make test-unit` stops with `Error 5` | No test has the marker yet (Exercise 3). |
| Every commit in the repository starts a build | The `push` trigger has no `paths:` filter. |
| `Bind for 0.0.0.0:5500 failed: port is already allocated` | Another week's stack is running. Stop it with `docker compose down` in that folder. |

## Next steps

The checks now run on every push and on a schedule. A scheduled run can still be late or
missing, and you will not know about it; a failed step is not retried. In Week 8 you add an
orchestrator to the pipeline that records every run and retries a failed step.
