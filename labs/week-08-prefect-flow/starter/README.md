# Week 8 Lab — Prefect Flow

In Week 7, you used GitHub Actions to run tests and the quality gate automatically. Scheduled
training jobs also need a way to record their status and report failures. In this lab, you use
Prefect to run and schedule the training pipeline, inspect its history and configure retries.

## What you already have

The lab builds on the Compose stack, MLflow, DVC with Silo and the
`validate → prepare → train → evaluate → gate` pipeline from Weeks 1–7. It also keeps both
contracts, the quality gate, `make ci` and both GitHub Actions workflows. The model, metrics
and thresholds stay the same.

New this week:

- Prefect, the orchestrator: `prefect==3.8.2`, with a server image pinned to the same version.
- A Prefect server in `compose.yaml`. It stores its data in a second database in the existing
   Postgres container.
- `tasks.py` and `flows.py`. Most tasks are provided. You will combine them in a flow, configure
   retries and check the results.

`dvc repro` runs pipeline stages and skips those whose inputs have not changed. The Prefect flow
calls `dvc repro` as one task. It also runs network operations, manages retries and scheduling,
and records the state of each flow and task run.

## Based on (official tutorials)

- **Prefect quickstart (primary template):** https://docs.prefect.io/v3/get-started/quickstart
- **Flows and tasks:** https://docs.prefect.io/v3/concepts/flows · https://docs.prefect.io/v3/concepts/tasks
- **Retries:** https://docs.prefect.io/v3/how-to-guides/workflows/retries
- **Self-hosting a server:** https://docs.prefect.io/v3/advanced/self-hosted
- **Deployments and schedules:** https://docs.prefect.io/v3/how-to-guides/deployments/create-schedules
- **Testing flows (`prefect_test_harness`):** https://docs.prefect.io/v3/how-to-guides/workflows/test-workflows

## Prerequisites

- Weeks 1–7 working: `uv`, Docker, Git.
- If you are reusing a Postgres volume from an earlier week, it will not have the `prefectdb`
  database. See Troubleshooting.

## Setup

```bash
# Stop any other lab stack; the labs share the 55xx host ports
cd ../../week-07-ci-workflow/starter && make down; cd -

cp .env.example .env
make sync          # install all dependency groups
make up            # start postgres, s3, mc, mlflow and prefect
make data-v2       # rebuild the DVC-tracked dataset from the committed raw batches
make repro         # the Week 7 pipeline, unchanged: should end with a GO
make prefect-ui    # prints the UI address: http://127.0.0.1:5520
```

Open the Prefect UI. It has no flow runs yet.

Run `uv run pytest -q` before starting the exercises. With the stack down, the expected result is:

```
181 passed, 25 skipped
```

13 of the skipped tests are in `tests/test_flows.py`. Each has a `@pytest.mark.skip` marking
its exercise. Delete the marker when you implement the code it covers, then run the test. The
other 12 tests require infrastructure. With the stack up, the 8 MLflow-link tests among them run.

`tests/test_scope.py` checks that the code does not import tools introduced in later weeks.
Prefect installs some of those tools as dependencies; the test allows them to be installed.

## Exercises

Complete the five exercises in order. Write your answers to Exercises 2 and 5 in `answers.md`
in this directory, and commit the file with your code.

### Exercise 1 — Tasks and a flow (`make flow`)

A Prefect task is a step in a workflow. A flow calls tasks and records each run, including its
state, duration and logs. A team can use that record to find where a training run failed and
what completed before the failure. In this exercise, you combine the provided tasks into a
training flow and inspect its run in the Prefect UI.

Fill in `training_flow` in `flows.py`. The TODO lists the tasks in order. Call `notify` when the
flow fails as well as when it succeeds.

Then run `make flow` and open the run in the UI. Find the task list, each task's state and
duration, and the log lines from `dvc repro` inside `run_pipeline`.

**Check:** remove the skip markers in "The training flow" section of
`tests/test_flows.py`, and both tests pass. `make flow` ends with `Finished in state Completed()`,
the gate verdict is `GO`, `reports/last_run.txt` records it, and your metrics are byte-identical
to Week 7. The run shows up in the UI with every task in it.

### Exercise 2 — DVC and Prefect responsibilities (`make flow-dvc`) — **written**

DVC and Prefect both describe workflows as graphs, but they track different information. DVC
tracks pipeline stages and their file dependencies; Prefect records flow and task runs. When a
team uses both, it needs to decide which tool manages each part of the workflow. In this exercise,
you compare the graphs and consider how to divide that work.

Run `make flow-dvc` to print the DVC graph and the address of the Prefect UI. Compare the DVC
graph's file dependencies with the tasks and run states shown by Prefect.

1. Name three capabilities Prefect provides for this lab that DVC does not, and one capability
   DVC provides that Prefect does not. Explain which problem each capability solves.
2. `run_pipeline` calls `dvc repro` as a single task. What would you lose by replacing it with
   one Prefect task per DVC stage? When might splitting the stages into separate tasks be useful?

### Exercise 3 — Configure retries (`make flow-retry`)

A network request can fail temporarily and succeed on another attempt. A retry runs the failed
task again after a delay. Exponential backoff increases that delay; jitter varies it so retries
are less likely to happen at the same time. Repeating an operation can also cause unwanted
effects, so a team must choose which tasks are safe to retry. In this exercise, you configure
and test a retry policy for the network tasks.

Set the retry policy in `NETWORK_RETRIES` at the top of the retry section in `tasks.py`: a number
of retries, an exponential backoff, and jitter. The policy is already applied to the tasks that
talk to Silo. Leave every other task without retries.

Answer two questions in one sentence each, in the comment above `NETWORK_RETRIES`:

- (a) Why might `retries=3` on `run_pipeline` be unsuitable?
- (b) Retrying is safe only if running the same operation twice does no harm. Which of the
  tasks that retry is **not** safe to repeat? What would a retry do there, and how much does the
  existing check in that task protect you?

**Check:**

- Remove the skip markers on the three retry-policy tests and the two harness tests. Then run
  `make flow-retry`. The policy tests check that only the network tasks retry, at least twice,
  with growing delays and jitter. One harness test fails twice and then succeeds. Another fails every time and still
  fails after its retries run out. Both check state and call counts, not log text.
- *(Optional, on the live stack.)* Run `docker compose stop s3`, then `make flow-register`,
  which pushes to Silo. Observe the delays between retries, then run `docker compose start s3`.

### Exercise 4 — Parameters in a commit (`make flow-committed`)

Hyperparameters affect the model produced by a training run. Recording the values helps a team
trace and compare its models. The hyperparameters are in `params.yaml`. You can edit the file
and run the pipeline while experimenting; for a scheduled run, commit the parameters so Git
records the configuration. In this exercise, each run records the values used for training,
and a run that requires committed parameters fails if `params.yaml` has uncommitted changes.

1. Implement `read_params_used` in `tasks.py`. `dvc.lock` records the parameter values each stage
   used. Return the values of the `train` stage as one dictionary.
2. Follow the Exercise 4 TODO in `training_flow`. Before any work, check `params_committed`. When
   `require_committed_params` is set and `params.yaml` has uncommitted changes, raise an error
   that says how to fix it. After the pipeline, pass the values and the commit state to `notify`.
3. Experiment: in `params.yaml`, change `impute_strategy` from `median` to `mean`, without a
   commit. Run `make flow`. `train`, `evaluate` and `gate` re-run, and `reports/last_run.txt`
   ends with `train.impute_strategy=mean` and `params.yaml uncommitted`.
4. Run `make flow-committed`. It starts the flow the way the scheduled run in Exercise 5 will.
   The flow fails before `run_pipeline` starts, and `reports/last_run.txt` says why.
5. Undo the experiment with `git restore params.yaml`, and run `make flow` again. The record says
   `train.impute_strategy=median` and `params.yaml committed`.

In a team, you can propose a parameter change for review in a pull request.

**Check:** remove the skip markers in the "Parameters in a commit" section of
`tests/test_flows.py` and on `test_notify_records_the_params_and_whether_they_were_committed`, and
the tests pass. Step 4 fails with the message from your error, and the metrics after step 5 are
the same as Week 7's.

### Exercise 5 — Schedule the flow (`make serve`) — **written**

A schedule specifies when training should start, without a person running the command each time.
The job still needs access to its data, a known configuration and a way to report its result.
A team also needs to decide what happens before a trained model is released. In this exercise,
you serve a scheduled flow and inspect a run.

Implement `scheduled_flow` in `flows.py`. It pulls the current data, then runs the training flow
with `require_committed_params=True`. It does not register or promote the model.

Run `make serve` to serve the flow on a cron schedule. The default is every 5 minutes; set
`CRON='* * * * *'` to run it every minute. Leave it running until at least one scheduled run
starts. Check the run in the UI, then stop the process with Ctrl-C. Record the flow-run name and
its final state.

**Check:** remove the skip marker in "The scheduled flow" section of `tests/test_flows.py`, and
the test checks all three.

1. Is passing the quality gate enough to release a model trained by a scheduled job? What other
   checks or approvals would you require before it reaches users?
2. What should be notified, and to whom?
3. What should happen on the **second** failure in a row that should not happen on the first?
4. Which scheduled-job failure would these checks and notifications still miss?

### Finish — commit your work

```bash
git status          # include answers.md; exclude .env and .venv/
git add labs/week-08-prefect-flow/starter
git commit -m "week08: prefect flow, retries and written answers"
```

Commit your code and `answers.md`. At the top of `answers.md`, put the name and final state of
the scheduled run from Exercise 5. If `git status` shows `params.yaml` as modified, an experiment
from Exercise 4 is still in it. Undo it with `git restore params.yaml` before you commit.

## Make targets

| Target | What it does |
| --- | --- |
| `make flow` | the training flow, recorded in the Prefect UI (Exercise 1) |
| `make flow-dvc` | the two graphs side by side (Exercise 2) |
| `make flow-retry` | runs the retry tests (Exercise 3) |
| `make flow-committed` | the training flow, refusing an uncommitted `params.yaml` (Exercise 4) |
| `make serve` | a scheduled deployment. `CRON=...` to override (Exercise 5) |
| `make flow-register` | the flow with `dvc push` and registration, against the live stack |
| `make prefect-ui` | print the UI address |
| `make test-flows` | run this week's flow tests |

Every Week 4–7 target still works, including `make ci`, `make repro`, `make gate` and both
GitHub Actions workflows.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No Prefect server at ...` | stack down | `make up` |
| Every API call returns 404 | `PREFECT_API_URL` is missing the `/api` suffix | copy it from `.env.example` |
| Prefect container restarts in a loop | `prefectdb` is missing. The init script only runs when the Postgres volume is **first** created | `make down-v && make up` (this also wipes MLflow's data) |
| `PREFECT_API_DATABASE_CONNECTION_URL` has no effect | the setting was renamed | use `PREFECT_SERVER_DATABASE_CONNECTION_URL` |
| `Scheduled_FlowModel is not fully defined` | a flow parameter Prefect cannot serialise | keep flow signatures to strings, numbers and booleans, as the `training_flow` docstring explains |
| `dvc pull failed` with no detail | Silo credentials were not passed to the subprocess | see `_dvc_env` in `tasks.py` |
| A scheduled run fails with `params.yaml has uncommitted changes` | an experiment is still in `params.yaml` | commit the change, or undo it with `git restore params.yaml` |
| `data/measurements.csv is missing` | a fresh clone. The dataset is DVC-tracked, not committed | `make data-v2` |
| A flow test takes about 8 seconds instead of 1 | it runs a flow without the harness, so Prefect starts a temporary server | use the `prefect_harness` fixture, or `task.fn(...)` |
| Port already in use | another week's stack is running | `make down` in that lab first |

## Submission

Submit the commit from Finish. It contains your code and `answers.md`, with the scheduled run's
name and state at the top. Do not include `.env` or `.venv/`. Push the commit, open it on
GitHub (`https://github.com/<you>/<repo>/commit/<hash>`), and upload that URL to Moodle.

## Deviations from the tutorials

1. **The flow calls `dvc repro`.** The quickstart builds a flow out of
   plain Python tasks. The existing DVC pipeline tracks inputs and skips stages that are up to
   date, so the flow calls it rather than replacing its stages.
2. The lab uses a self-hosted server with the existing Postgres container. The script
   `init-prefect-db.sh` creates a second database when the Postgres volume is first created.
3. The lab uses `.serve()` for scheduled runs. It runs in one process and does not need a work
   pool, worker or infrastructure block.
4. The retries exercise asks you to choose which tasks should retry, as well as configuring the
   retry policy.
5. Tests use `prefect_test_harness` for flow runs and `task.fn(...)` where they can test the
   underlying function without starting a flow.

The settings in `.env.example` include the `/api` suffix in `PREFECT_API_URL` and use
`PREFECT_SERVER_DATABASE_CONNECTION_URL` for the server database connection.
