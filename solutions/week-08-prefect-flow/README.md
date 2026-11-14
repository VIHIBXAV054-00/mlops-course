# Week 8 Lab — Reference Solution

The complete, runnable version of the Week 8 lab. Instructors can use it to verify student
submissions; students get it after the deadline.

Week 7 made the checks run without being asked. Week 8 answers the question that creates:
**how do you know it ran?**

## Changes from starter

What a student writes this week. Everything else is identical between `starter/` and `solution/`.

| File | Exercise | What changed |
| --- | --- | --- |
| `src/week_08_prefect_flow/flows.py` | 1 | `training_flow` body: `build_dataset` → `run_pipeline` → optional `push_data` / `register_model` (GO only) → `notify`, with `notify` also on the `except` path before re-raising |
| `src/week_08_prefect_flow/tasks.py` | 3 | `NETWORK_RETRIES`: `retries=3`, `exponential_backoff(backoff_factor=2)`, `retry_jitter_factor=0.5` (the starter has `retries=0`) |
| `src/week_08_prefect_flow/tasks.py` | 4 | `read_params_used` returns the `train` stage's values from `dvc.lock` (the starter returns `{}`) |
| `src/week_08_prefect_flow/flows.py` | 4 | `training_flow`: `params_committed` first, a `RuntimeError` when `require_committed_params` is set and `params.yaml` is uncommitted, and the values and commit state passed to `notify` |
| `src/week_08_prefect_flow/flows.py` | 5 | `scheduled_flow` body: `pull_data`, then `training_flow(require_committed_params=True)`; no registration |
| `tests/test_flows.py` | 1–5 | the 13 skip markers removed |
| `compose.yaml` | — | `name: week08-prefect-flow` (the starter's is `week08-prefect-flow-starter`) |

## New this week, already in the starter

Provided rather than written, so students spend the week on the flow, not on standing Prefect up.

| File | Used in | What it is |
| --- | --- | --- |
| `src/week_08_prefect_flow/tasks.py` | 1, 3, 4 | the 8 tasks, including `params_committed` (asks Git whether `params.yaml` has uncommitted changes); `register_model` carries its own `retries=2` and the search-first mitigation; `notify` writes the values and the commit state |
| `src/week_08_prefect_flow/cli.py` | 1, 4, 5 | `flow` (with `--require-committed`) and `serve` subcommands |
| `src/week_08_prefect_flow/config.py` | 1 | `prefect_api_url` |
| `src/week_08_prefect_flow/tracking.py` | 1 | `prefect_available` |
| `tests/test_flows.py` | 1–5 | 16 tests; 13 shipped skipped, each marker naming its exercise; the `params_committed` test and two `notify` tests run from the start |
| `tests/test_scope.py` | — | the future-week import guard (course infrastructure) |
| `tests/conftest.py` | 3 | session-scoped `prefect_harness` |
| `compose.yaml` | 1 | a `prefect` service; a second database in the existing Postgres |
| `init-prefect-db.sh` | 1 | creates `prefectdb` on first init |
| `.env.example` | 1 | `PREFECT_DB`, `PREFECT_PORT=5520`, `PREFECT_API_URL` |
| `Makefile` | 1–5 | `flow`, `flow-register`, `flow-dvc`, `flow-retry`, `flow-committed`, `serve`, `prefect-ui`, `test-flows` |

## "We already have a DAG runner. Why a second one?"

If this is not answered in the first ten minutes the week reads as ceremony.

| | `dvc repro` | Prefect |
| :--- | :--- | :--- |
| the question it answers | **is this stale?** | **did it run, when, how many times, and what then?** |
| its graph is about | **content** — hashes | **execution** — order, state, time |
| decides | what to **skip** | what to **run**, retry, schedule, parameterise |
| knows about time | no | yes |
| knows a step failed | only that a process exited | per-task state, with history and a UI |

> **DVC tells you what is out of date. Prefect tells you what happened.**

The flow calls `dvc repro` as **one task**, because DVC already owns the graph inside it.
Splitting it into one Prefect task per stage would put two schedulers in charge of one graph, and
the one with less information would be deciding.

## Running the solution

Stop any other lab stack first (`make down` in that lab): they all share the 55xx host ports.

```bash
cp .env.example .env
make sync
make up            # FIVE services now: postgres, s3, mc, mlflow, prefect
make data-v2
make flow          # the training flow, recorded in the Prefect UI
```

Prefect UI: **http://127.0.0.1:5520**. Note the client needs `PREFECT_API_URL` with the **`/api`
suffix** — without it every call 404s against the UI, which is the most common self-hosting
mistake.

## Expected output — `make flow`

```
Beginning flow run 'obedient-wolf' for flow 'diabetes-training'
  Task run 'params_committed-700' - Finished in state Completed()
  Task run 'build_dataset-d73' - built 768 rows -> measurements.csv
  Task run 'run_pipeline-3e3' - Stage 'validate' didn't change, skipping
  ...
  Task run 'run_pipeline-3e3' - Data and pipelines are up to date.
  Task run 'read_params_used-a29' - Finished in state Completed()
  Task run 'notify-f67' - notify: GO — 13 passed, 0 failed, 4 skipped (criteria 1.0.0) | random_seed=42, train.C=1.0, train.family=logreg, train.impute_strategy=median, train.max_iter=1000, train.n_estimators=100 | params.yaml committed
Flow run 'obedient-wolf' - Finished in state Completed()
```

On a fresh clone, `run_pipeline` runs every stage instead of skipping them.

Metrics are byte-identical to Weeks 5–7. **Week 8 changes no model, no metric, no threshold.**

```
{"accuracy":0.7656,"precision":0.6964,"recall":0.5821,"f1":0.6341,"roc_auc":0.8345}
```

## Where retries belong (Exercise 3)

Read the `retries=` arguments in `tasks.py` as a **map of where this pipeline touches the
network**, because that is what they are:

| task | retries | why |
| --- | :---: | --- |
| `pull_data` | 3 | a socket. Idempotent: content-addressed. |
| `push_data` | 3 | a socket. Idempotent for the same reason. |
| `register_model` | 2 | a socket — **and not idempotent.** See below. |
| `params_committed` | — | local; asks Git |
| `build_dataset` | — | local, deterministic |
| `run_pipeline` | — | deterministic; a refusal is an answer, not a glitch |
| `read_params_used` | — | reads a file |
| `notify` | — | writes a file |

**Why `retries=3` on `train` is worse than useless:** it is deterministic and local. If it raised
once it will raise three times, and the only thing you bought is a traceback that arrives ninety
seconds later with the real bug buried under two retry lines.

**The one that is not idempotent.** `register_model` creates a *new model version* on every call.
Consider the failure retries exist for: the request reaches MLflow, MLflow commits the version,
and the *response* is lost. From the client that is indistinguishable from "it never arrived" —
and the retry registers a second, identical version. Nothing errors. You simply have versions 4
and 5 pointing at the same run. The mitigation here is the cheap one — search for an existing
version for this run id first — which narrows the window rather than closing it.

> **Idempotency is a precondition for a retry, not a consequence of one.**

### Measured, against a real outage

`docker compose stop s3`, then run the flow:

```
Retry 1/3 will start 2 second(s) from now
Retry 2/3 will start 4 second(s) from now
Retry 3/3 will start 8 second(s) from now
Retries are exhausted
  ERROR: failed to connect to s3 (dvc-storage/dvcstore/files/md5)
       - Could not connect to the endpoint URL: "http://127.0.0.1:5510/..."
```

Exponential backoff, 18.3s total, then an error naming the endpoint. Start Silo and the same
flow completes. **A retry policy that has never been observed retrying is a comment.**

## Parameters in a commit (Exercise 4)

The hyperparameters are not flow parameters. They live in `params.yaml` and change with a commit,
so someone reviews the change, Git keeps it, and `dvc.lock` records the value each stage used. The
flow parameters choose what a run does: `push`, `register_model_version` and
`require_committed_params`.

An experiment still edits `params.yaml` without a commit, and every run records what it trained
with. Measured, with `impute_strategy: mean` and no commit:

```
Task run 'run_pipeline-0e6' - Running stage 'train':
Task run 'run_pipeline-0e6' - Running stage 'evaluate':
Task run 'run_pipeline-0e6' - Running stage 'gate':
Task run 'notify-0ef' - notify: GO — 13 passed, 0 failed, 4 skipped (criteria 1.0.0) | random_seed=42, train.C=1.0, train.family=logreg, train.impute_strategy=mean, train.max_iter=1000, train.n_estimators=100 | params.yaml uncommitted
{"f1": 0.6341, "roc_auc": 0.838}      <- matches Week 6's `mean` row
```

The same change under `make flow-committed`, which starts the flow as the scheduled run does:

```
Task run 'notify-28f' - notify: FAILED — params.yaml has uncommitted changes. Commit them, or undo them with `git restore params.yaml`, before this run trains a model.
Flow run 'stoic-iguana' - Finished in state Failed(...)
```

The flow stops before `run_pipeline`, so no model is built from values nobody committed. After
`git restore params.yaml`, `train`, `evaluate` and `gate` run again and the metrics are back at
F1 0.6341, ROC AUC 0.8345.

`read_params_used` reads `dvc.lock`, not `params.yaml`: the record says what `train` used, even
if someone edits the file after the run.

## Scheduling (Exercise 5)

`make serve` starts a process that polls for scheduled runs — no work pool, no worker, no
infrastructure block. Measured with a one-minute cron:

```
Your flow 'diabetes-training-with-pull' is being served and polling for scheduled runs!
Flow run 'orange-mantis' - Beginning flow run for flow 'diabetes-training-with-pull'
  pull_data ✓  params_committed ✓  build_dataset ✓  run_pipeline ✓  read_params_used ✓
  notify: GO — 13 passed, 0 failed, 4 skipped | ... | params.yaml committed
```

The scheduled flow refuses an uncommitted `params.yaml` (Exercise 4), and it **does not register
or promote.** Two reasons, and the second matters more:
the registry needs infrastructure a scheduled run may not have, and *nobody has decided that a
model trained at 03:00, seen by no one, should reach users because a threshold said GO.* A gate
is a necessary condition for a release, not a sufficient one.

## The run history — the week's payoff

After the exercises, from the Prefect API:

```
14 flow runs   — COMPLETED 6, FAILED 8
38 task runs   — COMPLETED 31, FAILED 7
tasks that retried: pull_data x4, pull_data x4, pull_data x4
deployments: weekly-retrain, cron '* * * * *'
```

`pull_data x4` is one attempt plus three retries, **recorded**. That is the difference between a
log file and a record: a log tells you what a process printed, a history tells you what the system
did — including that it tried four times, and when, and what state it ended in.

## Testing strategy, measured

| approach | cost | use for |
| --- | ---: | --- |
| `task.fn(...)` | **0.000s** | anything about the function's logic |
| `prefect_test_harness()` setup | **~4.3s** once | session fixture |
| a flow run inside the harness | **~1.1s** | retries actually retrying, state actually recorded |
| a bare flow call, no harness | ~8s | never in a suite |

That last row is the trap: with no harness Prefect quietly starts a temporary server per process,
so a careless suite gets **slower** rather than failing — the worst possible shape for a time
budget.

Suite: **198 passed, 8 skipped** with the stack down; the 8 MLflow-link tests run with the stack
up.

## Four defects found while building this

Each is a general lesson, not a Prefect quirk.

1. **`get_run_logger()` raises outside a run context**, which broke `task.fn()` entirely — the
   free unit-test path the whole suite is built on. Fixed with a fallback logger.
   *A function that can only execute inside its framework is a function you cannot unit-test.*
2. **A flow parameter named `register` shadows a pydantic base attribute**, warning on every run.
3. **`settings: Settings` in a flow signature breaks scheduled runs only.** It works when you call
   the function directly and fails when a *deployment* validates its parameters:
   `PydanticUserError: Scheduled_FlowModel is not fully defined`. **A flow signature is a public
   API** — Prefect builds a pydantic model from it — so keep it to strings, numbers and booleans.
4. **The dvc tasks did not map Silo credentials.** The Makefile maps `S3_*` onto `AWS_*` for
   interactive use; a task that shells out has to do it again, or `dvc pull` fails to authenticate
   and the retry patiently repeats that three times. *A subprocess does not inherit your
   intentions, only your environment.* The same fix removed `--quiet`, because a retry policy is
   only as useful as the message it gives up with.

## Make targets

| Target | What it does |
| --- | --- |
| `make flow` | the training flow, recorded in the UI |
| `make flow-dvc` | the two graphs side by side (Exercise 2) |
| `make flow-retry` | prove the retry policy is real |
| `make flow-committed` | the training flow, refusing an uncommitted `params.yaml` (Exercise 4) |
| `make serve` | a scheduled deployment (`CRON=...` to override) |
| `make prefect-ui` | print the UI URL |
| `make test-flows` | just this week's tests |

Every Week 4–7 target still works, including `make ci` and both GitHub Actions workflows.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No Prefect server at ...` | stack down | `make up` |
| Every API call 404s | `PREFECT_API_URL` missing the `/api` suffix | it is in `.env.example` |
| Prefect container restarts forever | `prefectdb` missing — the init script runs **only** on first init of the volume | `make down-v && make up` |
| `PREFECT_API_DATABASE_CONNECTION_URL` does nothing | renamed | it is `PREFECT_SERVER_DATABASE_CONNECTION_URL` |
| `Scheduled_FlowModel is not fully defined` | a non-serialisable flow parameter | keep flow signatures to plain types |
| `dvc pull failed` with no detail | credentials not mapped in the subprocess | see defect 4 |
| A scheduled run fails with `params.yaml has uncommitted changes` | an experiment is still in `params.yaml` | commit the change, or `git restore params.yaml` |

## Submission

Exercises 2 and 5 ask for a written answer. Put those in a file called `answers.md` in this
directory, and commit it with your code.

```bash
git status          # answers.md must appear; .env and .venv/ must NOT
git add labs/week-08-prefect-flow/starter
git commit -m "week08: prefect flow, retries and written answers"
```
