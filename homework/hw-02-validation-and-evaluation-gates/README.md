# HW 2: Data Validation and Evaluation Gates

| | |
| --- | --- |
| **Released** | Week 7 |
| **Due** | 23:59 (Budapest) on Sunday of **Week 10** (15 November) |
| **Estimated effort** | 8–10 hours |
| **Builds on** | HW 1 (your project repository), Week 5 (Pandera contracts), Week 6 (model quality gates) |

---

## Objective

Put two gates into your project: one at the **entrance**, which refuses data that does not
satisfy a contract you wrote, and one at the **exit**, which refuses a model that does not
satisfy criteria you agreed to in advance.

The capability this proves is a single sentence: **your pipeline can say no, and it says it for
reasons written down before the run.** Everything below exists to make that sentence checkable
by running commands.

This extends the repository you submitted for HW 1 — the one created from `project-template/`
with your own dataset. Do not start a new project. If your HW 1 was incomplete, fix it as part
of this submission; the graders re-run those steps.

You will use only tools from Labs 1–6. This assignment is released in the same week as the CI
lab, and that ordering is deliberate: **build the gates first, automate them second.** A
GitHub Actions workflow is not required and will not earn marks here — add one if you want it,
but it is worth nothing until the gates it runs actually exist. No Prefect and no serving
either; those are Weeks 8 and 9.

---

## Requirements

Each requirement is independently checkable. The grader runs commands for R1–R7 and reads for
R8–R10.

### R1 — Two Pandera contracts (14 points)

- A `schemas.py` (or equivalent) declaring **two** `DataFrameModel` classes: an **ingestion**
  contract for the data as it arrives, and a **model-input** contract for what the model may
  see. Two, not one — a dataset has two boundaries and they need different rules.
- The ingestion contract uses `Config.strict = True`, declares dtypes, and bounds every numeric
  column with a range that is **defensible for your data**, not copied from the lab.
- The model-input contract is stricter than the ingestion contract in at least one way that
  matters for *your* dataset, and a one-line comment says why.
- Install `pandera[pandas]` and use `import pandera.pandas as pa`. The bare package ships
  neither pandas nor numpy.

If your dataset genuinely has no impossible values, say so in `docs/hw2.md` and declare the
constraints that *would* catch corruption — an upper bound that no real record reaches is still
a contract.

### R2 — A validation gate in the pipeline (12 points)

- A `validate` stage in `dvc.yaml` that runs the ingestion contract and writes a verdict to a
  `cache: false` output (e.g. `reports/validation.json`).
- Your `prepare` stage declares that verdict file in its `deps`. **That edge is the gate.**
- The stage exits **non-zero** when the contract fails, so `dvc repro` stops.
- A documented way to demonstrate it: a command, a script or a `make` target that plants a
  fault in your data, shows `dvc repro` refusing, and restores the data. Record the output in
  `docs/hw2.md`.

### R3 — A slice evaluation (12 points)

- Your `evaluate` stage writes per-slice metrics to a `cache: false` output alongside the
  aggregate ones (e.g. `metrics/slices.json`).
- **At least two slice definitions**, declared in `params.yaml` rather than hard-coded, and
  meaningful for your problem. "Meaningful" means you can say who is in each group and why a
  stakeholder would care.
- Every slice row carries **`n` and the count of positive labels** (or, for regression, `n` and
  the target's spread). A metric column without them is not readable.
- Slices are computed on **raw** values, before any imputation or scaling. If your pipeline
  imputes, say in `docs/hw2.md` what would have changed had you sliced afterwards.

### R4 — Acceptance criteria, written down and justified (16 points)

- An `acceptance` block in `params.yaml` containing at minimum:
  **absolute floors** on at least two metrics, a **regression check** against a recorded
  baseline with a named primary metric and a tolerance, and **slice rules** with a minimum
  support.
- A `criteria_version` field.
- Every threshold **justified in `docs/hw2.md` against a measured number from your own
  project.** A threshold with no derivation earns no marks for this requirement, however
  sensible it looks.
- One of those justifications must address the trivial baseline: state what a constant
  predictor scores on your test set, and show your floor is above it.

### R5 — A gate stage that refuses (14 points)

- A `gate` stage in `dvc.yaml` that reads the metrics, the slice report, the baseline and the
  `acceptance` block, writes a verdict to a `cache: false` output, and **exits non-zero on a
  NO-GO**.
- The verdict distinguishes three statuses: **pass, fail, and skipped**. A criterion that could
  not be evaluated — a slice too small to score, a missing baseline — is reported as skipped
  with a reason, and the count of skipped checks is visible without opening the JSON.
- The verdict artifact contains no timestamp and is byte-identical across two runs with no
  changes. (It is committed to Git; a file that churns makes every diff meaningless.)

### R6 — The gate has teeth (10 points)

- Model registration or promotion **refuses** unless the recorded verdict is a GO. Wherever
  your project publishes a model, that path consults the verdict.
- A documented demonstration: change one hyperparameter to make the model genuinely worse, show
  `dvc repro` stopping at the gate, show the publish step refusing, and show that **the model
  artifact still exists**. Record the output in `docs/hw2.md`.
- Restore the hyperparameter; the committed state must be a GO.

### R7 — A recorded baseline (8 points)

- A committed baseline file holding the current champion's metrics, read by the gate.
- A documented command that refreshes it from your MLflow registry (from an alias, not a
  version number).
- The no-baseline path works: with the file absent, the regression check reports **skipped**
  and the verdict is **not** silently upgraded to a pass.

### R8 — One fairness or subgroup check (8 points)

- At least one **rate-based gap** across the groups of one slice — a selection-rate gap, a
  true-positive-rate gap, or an equivalent for a regression problem — computed and reported.
- In `docs/hw2.md`: which axis you chose, why that axis and not another, and whether the gap
  should be **gated** or only **reported**. Both answers are acceptable; only an undefended one
  is not.
- **Name one group you would want to audit for and cannot**, and say what would have had to
  happen, and when, for that to be possible. If your dataset genuinely contains every attribute
  you would want, say that instead and explain how you know.

### R9 — `docs/hw2.md` (4 points)

One document, containing: the threshold justifications from R4, the two demonstration
transcripts from R2 and R6, the slice discussion from R3, the fairness discussion from R8, and
a short section on **what your gate cannot catch**. That last section is graded on honesty, not
on length.

### R10 — Tests (2 points)

At least three tests covering your gate logic, passing with **Docker stopped**. Write the gate
as a function over plain data structures and this is easy; write it as a script that reads
files and calls a registry and it is not — which is itself the lesson.

---

## Submission

Push to your project repository and submit **the URL of the commit** you want graded in the
HW 2 assignment in Moodle.

Your repository must contain, in addition to everything from HW 1:

| Path | What |
| --- | --- |
| `src/.../schemas.py` | the two Pandera contracts |
| `params.yaml` | the slice definitions and the `acceptance` block |
| `dvc.yaml` | `validate` and `gate` stages, with the gate edge on `prepare` |
| `reports/validation.json`, `reports/gate.json` | the two verdicts, `cache: false`, committed |
| `metrics/slices.json`, `metrics/baseline.json` | the slice table and the recorded champion |
| `docs/hw2.md` | the written work |
| `tests/` | including the gate tests |

**Do not commit:** `.env`, `.dvc/cache/`, `.venv/`, your data file, or model binaries outside
the DVC cache.

### The commands the grader will run

From a **fresh clone** of your submitted commit:

```bash
uv sync --all-groups
uv run pytest -q                      # must pass with Docker stopped
cp .env.example .env                  # then fill in per your README
docker compose up -d --wait
dvc pull
dvc repro                             # must reproduce, ending in a GO
dvc repro                             # must re-run nothing
cat reports/gate.json                 # verdict, criteria_version, skipped count
```

Then, from your `docs/hw2.md`: the data-gate demonstration (R2) and the model-gate
demonstration (R6), run verbatim as documented.

Anything that requires a step not in your README or `docs/hw2.md` counts as not working.

---

## Grading

| Requirement | Points | How |
| --- | --- | --- |
| R1 two Pandera contracts | 14 | running + reading |
| R2 validation gate in the pipeline | 12 | running |
| R3 slice evaluation | 12 | running + reading |
| R4 acceptance criteria, justified | 16 | reading |
| R5 gate stage that refuses | 14 | running |
| R6 the gate has teeth | 10 | running |
| R7 recorded baseline | 8 | running + reading |
| R8 fairness / subgroup check | 8 | reading |
| R9 `docs/hw2.md` | 4 | reading |
| R10 gate tests | 2 | running |
| **Total** | **100** | |

**Automatic deductions**, because these are the failures the assignment exists to prevent:

| | |
| --- | --- |
| −10 | a threshold with no justification anywhere |
| −10 | the gate reports a verdict but nothing refuses on it |
| −8 | a skipped check reported as a pass, or not reported at all |
| −8 | slices computed after imputation without acknowledging it |
| −5 | the committed verdict contains a timestamp, or changes between two identical runs |
| −5 | a contract so loose it cannot fail, or so tight it fails on your own real data |
| −5 | `.env`, data or cache committed |

---

## Advice

**Measure before you threshold.** Run the slice table first. Every number in your `acceptance`
block should be traceable to something you observed, and the honest version of that sentence is
that you will be choosing the criteria *after* seeing the model — which a real project must not
do. Say so in `docs/hw2.md`; noticing the inversion is worth more than pretending it did not
happen.

**Expect the small-slice problem.** Almost every real dataset has a group that is both the most
interesting and the least populated. Your `min_support` rule is where you decide what to do
about it, and "skip it and say so loudly" is a defensible answer. "Score it on nine rows and
gate on the result" is not, and neither is dropping it from the table.

**Keep the gate logic pure.** A function that takes metrics, slices, a baseline and the criteria
and returns a verdict is trivially testable and trivially arguable. A gate tangled up with file
reads and registry calls is neither, and R10 will be painful.

**The two gates are not the same shape.** The data gate works by being *upstream*: make
`prepare` depend on its verdict and a failure means the work never happens. The model gate is at
the end, so there is nothing downstream to withhold — and it must not delete the model, because
you need the artifact to find out why it failed. Its teeth come from whatever publishes models
consulting the verdict instead.

**Do not gate on drift.** Comparing this month's data to last month's is a different question
with different tooling, and it is Weeks 11–12. A contract asserts what a row must be, on its
own, forever.
