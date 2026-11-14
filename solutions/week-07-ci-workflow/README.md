# Week 7 Lab: Reference Solution

The complete, runnable version of the Week 7 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

## Changes from starter

| File | Exercise | What changed |
| --- | --- | --- |
| `Makefile` | 2 | `ci` runs `ensure-env ensure-data lint test-fast repro gate` |
| `tests/test_*.py` | 3 | one `pytestmark` layer per module; `test_dvc_repo.py` and `test_mlflow_link.py` keep their `dvc` and `live` guards next to it |
| `tests/test_workflows.py` | 4, 5 | the skip markers removed |
| `.github/workflows/ci.yml` | 4 | the code path: `lint`, a `test` matrix over three layers, and `pipeline` |
| `.github/workflows/ct.yml` | 5 | the model path: `workflow_dispatch` with a `reason`, and a weekly `schedule` |
| `compose.yaml` | — | `name: week07-ci-workflow` (the starter uses `-starter`, so the two never share volumes) |

Everything else is identical to the starter. New this week in both: `workflows.py` (reads
workflows and audits their pins), `format_gate_markdown` in `gates.py`, the `ci-explain` and
`gate-summary` commands, the CI targets in the `Makefile`, ruff in the `lint` group, and the four
layer markers in `pyproject.toml`.

## Running the solution

```bash
uv sync --locked --all-groups
make data-v2              # 768 rows, md5 a8fd7b4f0d6d1bc4e378a8f76c5fff0c
make ci                   # lint, tests, pipeline and gate; no Docker, no .env needed
make ci-fail              # train.C 0.005: make ci must fail at the gate
make ci-explain
```

## Expected output

### `make ci`

On a clean copy with the stack down, `make ci` copies `.env.example` to `.env` and ends with:

```
Running stage 'gate':
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)
...
CI passed: lint, tests, pipeline, gate.
```

It took about 30 s on a laptop (16 Oct 2026). `train` prints `MLflow not reachable — model
written, no run recorded.` The metrics are the same as in Weeks 5 and 6: accuracy 0.7656,
precision 0.6964, recall 0.5821, F1 0.6341, ROC AUC 0.8345.

CI needs no service because of four earlier decisions:

| Week | Decision | What CI gains |
| --- | --- | --- |
| 4 | `build_measurements` rebuilds the dataset from batches committed to Git | no object store, no credentials |
| 4 | `tracking.mlflow_available` guards `train` | training skips the run log instead of failing |
| 5 | the contracts read committed files | validation runs offline |
| 6 | `evaluate_gate` is a pure function over plain dicts | the gate needs no server |

So CI can train, evaluate and gate, but it cannot register or promote: both need the tracking
server. Both workflows stop at the gate.

### `make ci-fail` (Exercise 2)

```
NO-GO. 4 acceptance criteria failed: minimum.f1, regression.f1, slice.age_band.30-39, fairness.age_band.tpr_gap.
...
make ci exit code: 2
params.yaml restored. Run make repro to return to a GO.
```

### The test layers (Exercise 3)

| Layer | Tests | Modules |
| --- | ---: | --- |
| `unit` | 34 | `test_config`, `test_smoke`, `test_workflows` |
| `data` | 72 | `test_datasets`, `test_gate`, `test_inference`, `test_schemas`, `test_validation`, `test_dvc_repo` |
| `eval` | 72 | `test_evaluation`, `test_fairness`, `test_gates`, `test_model_gate`, `test_pipeline` |
| `integration` | 8 | `test_mlflow_link` (needs the stack) |

Total 186. `pytest -m "not unit and not data and not eval and not integration"` prints
`186 deselected`. `make test-unit`, `test-data` and `test-eval` print `34 passed`, `62 passed`
(the 10 `dvc` tests are left out) and `72 passed`. The full suite with the stack down:
`178 passed, 8 skipped`.

Two classifications are worth discussing. `test_gate` checks Week 5's data gate, so it is
`data`, although it is called a gate. `test_smoke` trains the baseline model and checks its
pinned metrics; it is `unit` here because it protects our code on a fixed file, and `eval` is a
defensible answer.

### `make ci-explain` (Exercise 1)

In a student repository (16 Oct 2026):

```
Action pins, against a snapshot recorded 2026-10-16:

  file                   action                        ref        status   detail
  ---------------------- ----------------------------- ---------- -------- ----------------------------------
  autograde.yml          actions/checkout              v7         current  v7
  autograde.yml          astral-sh/setup-uv            v9.0.0     exact    pinned to v9.0.0; newest release is v10.x
  slides.yml             actions/checkout              v7         current  v7
  slides.yml             pnpm/action-setup             v4         stale    v4 -> v6 (2 major(s) behind)
  slides.yml             actions/setup-node            v7         current  v7
  slides.yml             actions/upload-pages-artifact v5         current  v5
  slides.yml             actions/deploy-pages          v5         current  v5

  1 pin(s) behind the newest published major tag.
```

`setup-uv` has releases up to v10.3.0, but its newest major tag is still `v7`, so `@v9` or `@v10`
does not resolve: the exact release tag is the pin that works. On 6 August 2026, all six pins in
the course's two workflows were 1–3 major tags behind; they were updated by hand. The snapshot
in `workflows.py` goes stale the same way: `ci-explain` compares with it, not with GitHub.

## On GitHub (August 2026)

Measured on GitHub-hosted runners in a test repository.

**Green, CI on push:** `lint` 12 s, `test (unit)` 22 s, `test (data)` 25 s, `test (eval)` 36 s,
`pipeline` 53 s; the artifact `gate-evidence` was 4,281 bytes. The test jobs run side by side.

**Red, the same push with `train.C: 0.005`:** `lint` and the three test jobs passed;
`pipeline` failed at the step that runs `make ci`, after 43 s. The annotation said
`See the job summary and the gate-report artifact.`, and the artifact (4,425 bytes) was uploaded
because the upload step has `if: always()`. The verdict then listed 3 failed criteria; since
Week 6 gates the age-band TPR gap, the same change fails 4 (see `make ci-fail` above).

**CT, started by hand:** one `retrain` job, 33 s, GO. The log printed the trigger and the reason.

Two errors appeared only on a real runner. `astral-sh/setup-uv@v9` failed at "Set up job" with
`unable to find version v9`, because the newest release had no major tag. And a workflow called
`make gate-summary` before the Makefile defined it; `test_workflows.py` now checks every target a
workflow calls against the Makefile.

## Linting

`ruff==0.16.1`, with `select = ["E4", "E7", "E9", "F"]`. On this lab's code, ruff's default rule
set reports 23 findings and the explicit `select` none (16 Oct 2026). The code from Week 6 had two
unused imports, in `cli.py` and `pipeline.py`; both are removed in the starter too. There is no
`ruff format` check: it would change 19 of the 37 files.

## Make targets

| Target | What it does |
| --- | --- |
| `make ci` | the one pipeline definition: lint, tests, pipeline and gate |
| `make ci-local` / `make ct-local` | the steps of `ci.yml` / `ct.yml`, on your machine |
| `make ci-fail` | change `train.C` to 0.005, run `make ci`, restore `params.yaml` |
| `make ci-explain` | the workflows and their action pins |
| `make install-ci` / `make uninstall-ci` | copy the workflows to the repository root, or remove the copies |
| `make test-unit` / `test-data` / `test-eval` / `test-integration` | one test layer each |
| `make gate-summary` | the recorded gate verdict as Markdown |
