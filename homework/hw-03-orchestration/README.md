# HW 3: Orchestration

| | |
| --- | --- |
| **Released** | Week 9 |
| **Due** | 23:59 (Budapest) on Sunday of **Week 12** (29 November) |
| **Estimated effort** | 6–10 hours |
| **Builds on** | HW 1 and HW 2 (your project repository), Week 8 (Prefect) |

---

## Objective

Run your training pipeline with an orchestrator, so that it runs on a schedule without you and
records what happened. When a run fails, you can identify the failed task, see how many times it
was tried, and inspect its logs.

This extends the repository you submitted for HW 2. Do not start a new project.

Use only the tools from Labs 1–8. Serving, containers for deployment and Kubernetes are not part
of this assignment, and a REST API earns no marks. The assignment comes out in the week of the
serving lab. First make the pipeline run reliably on its own; HW 4 puts an endpoint in front of
it.

---

## Requirements

The grader runs commands and reads your evidence as shown in the grading table.

### R1 — A flow over the training chain (14 points)

Your pipeline already validates data, trains a model and checks its quality. A Prefect flow
brings these steps together and records each task run, so you can see where a run stopped.

- Create a Prefect flow that covers your pipeline from start to end. Include at least validate →
  prepare → train → evaluate → gate, or the same steps in your project's order.
- Use `@task` for the tasks and `@flow` for the flow.
- Add a self-hosted Prefect server to `compose.yaml`. Pin the client to the version of the
  server image. Store the server's data in a database that survives a restart, for example a
  second database in your Postgres container, as in the Week 8 lab.
- Set `PREFECT_API_URL` in `.env.example`, with the `/api` suffix.

If your pipeline uses DVC, you can call `dvc repro` as one task, as in the lab. Its DVC stages do
not each need a Prefect task. Explain your choice in `docs/hw3.md`. If you split the stages into
separate tasks, explain why that is better for your project.

### R2 — Retry policy (16 points)

A network request can fail temporarily and succeed on a second attempt. Other failures, such as
invalid data, will not improve with a retry. Repeating an operation can also create an unwanted
result, such as a duplicate model version.

Choose which tasks should retry. In `docs/hw3.md`, explain your decision for every task, including
those without retries.

- Add retries only to tasks that can fail temporarily and then succeed.
- Use exponential backoff and jitter for at least one task.
- Include a table of every task, whether it retries, and one line explaining why.
- Identify at least one operation that is **not idempotent**: repeating it can create an unwanted
  result. Explain what a retry would do and either make the operation safe to retry or explain why
  you have not.

Retries on every task score zero for this requirement.

### R3 — Parameters in a commit (14 points)

When a scheduled run trains a model, the team needs to know which hyperparameters it used.
Git records the configuration for scheduled runs; you can still try an uncommitted change in a
manual experiment.

- Keep hyperparameters in a configuration file in Git, such as `params.yaml`. Your Git history
  must show at least one commit that changes them.
- Each run that trains records the values the pipeline used, from `dvc.lock`, the MLflow run or
  your own record. It also records whether the configuration file had uncommitted changes.
- The scheduled entry point refuses to train if the configuration file has staged or unstaged
  changes. Its error message says how to fix the problem. A manual run may use an uncommitted
  file, but its record must say so.
- Use flow parameters to choose what a run does, such as pushing data, registering a model or
  selecting a data window. They must not change how the model is built.
- In `docs/hw3.md`, document the manual command and the command that runs the same entry point
  and settings as the schedule. Show this demonstration:
  1. Change a hyperparameter without a commit and run the flow manually. The record says
     "uncommitted".
  2. Run the scheduled entry point with the same settings as the deployment. It refuses before
     training.
  3. Commit the change and run again. The record shows the new value and "committed".

The grader runs these steps in a disposable fresh clone. Document any local Git identity needed
for the demonstration commit. Restore files changed by the runs and finish with a clean `git status`;
the demonstration commit may remain in that clone.

### R4 — A schedule (10 points)

A schedule can start training without a person running the flow each time. It still needs a
process that can execute the run, and a stopped process may leave no failed run to inspect.

- Create a deployment with a cron schedule. In `docs/hw3.md`, document the command to create it
  and start the process that executes its runs, such as `serve` from the Week 8 lab.
- Show evidence from your run history that a **scheduled** run started: its name, state and
  start time. A started run counts even if it failed; a deployment that has never started a
  scheduled run does not count.
- Explain what happens if the schedule stops starting runs, and who would notice.

### R5 — Record failures (10 points)

When a run fails, a team needs a record it can find without watching the terminal. The record
should help identify the failure and the work that ran before it.

- Record flow failures in a file, a log line in a fixed format, or a webhook. The reporting must
  run when the flow fails, not only when it succeeds.
- In `docs/hw3.md`, document a demonstration that makes the pipeline fail **inside** the flow.
  Show which Prefect tasks ran, which never started, and the failure record. If one task runs
  `dvc repro`, use its logs to show which DVC stages ran or did not run.
- Restore everything the demonstration changed, including rebuilt data and updated DVC pointers.
  Check with `git status`.

### R6 — Keep the quality gate (8 points)

Prefect runs the pipeline; the quality gate from HW 2 still decides whether a model passes.
Adding a flow must not allow a refused model to reach the registry or be promoted.

- Ensure the flow does not register or promote a model that the gate refused.
- In `docs/hw3.md`, demonstrate a refusal. For example, make the model worse with an uncommitted
  hyperparameter change and run the flow manually. Show the gate verdict and evidence that no
  model was registered or promoted. Restore the files changed by the demonstration afterwards.

### R7 — Run history (10 points)

After the demonstrations, use your Prefect server to find out what the pipeline has been doing.
In `docs/hw3.md`, record:

- how many flow runs there were, and in which states
- how many task runs there were, and in which states
- at least one task that **retried**, with its number of attempts
- your deployment and its schedule

Screenshots are fine. Include a task that actually retried, not only one with retries configured.

### R8 — `docs/hw3.md` (12 points)

Put your decisions and evidence in one document so another person can inspect the runs and
repeat the demonstrations. Include the R2 retry table, the R3 demonstration, the R4 schedule
evidence, the R5 failure transcript, the R6 gate demonstration and the R7 history.

End with **what your orchestrator cannot tell you**. Give specific limits for your project; this
section is graded on its content, not its length.

### R9 — Tests (6 points)

Tests should check the flow without starting the project services. Keep the work in plain
functions and the Prefect decorators at the edges, as in the Week 8 lab.

- Write at least four tests of your flow logic that pass with **Docker stopped** and no running
  external Prefect server. `prefect_test_harness` may start a temporary local server.
- At least one test must run a task and check its number of attempts when it retries, not only
  its retry setting. `task.fn(...)` calls the underlying function without Prefect's retries;
  use a task run, for example with `prefect_test_harness`, to test retries.

---

## Submission

Push to your project repository and submit **the URL of the commit** you want graded in the
HW 3 assignment in Moodle.

| Path | What |
| --- | --- |
| `src/.../flows.py`, `tasks.py` | the flow and its tasks |
| `compose.yaml`, `.env.example` | the Prefect server and its settings |
| `docs/hw3.md` | all the written work |
| `tests/` | including the flow tests |

**Do not commit:** `.env`, `.prefect/`, `prefect.db`, `*.db-wal`, `*.db-shm`, `.dvc/cache/`,
`.venv/`, your data file, or model files outside the DVC cache.

### The commands the grader will run

From a **fresh clone** of your submitted commit, the grader follows your setup instructions:

```bash
uv sync --locked --all-groups
uv run --frozen pytest -q             # with Docker stopped; must pass
cp .env.example .env
<your documented .env setup, if needed>
docker compose up -d --wait           # Prefect must start and be healthy
<your documented data setup command>   # for example, dvc pull
<your flow command>                   # must finish, or stop at the gate
```

Document how the grader can obtain the data and any required credentials without access to your
private files or services. Do not commit secrets. Then the grader runs the R3 and R5
demonstrations from your `docs/hw3.md`, as written, in the disposable clone.

---

## Grading

| Requirement | Points | How |
| --- | --- | --- |
| R1 flow over the training chain | 14 | running |
| R2 retry policy | 16 | reading + running |
| R3 parameters in a commit | 14 | running + reading |
| R4 a schedule that started a run | 10 | reading |
| R5 record failures | 10 | running |
| R6 keep the quality gate | 8 | running |
| R7 run history | 10 | reading |
| R8 `docs/hw3.md` | 12 | reading |
| R9 tests | 6 | running |
| **Total** | **100** | |

**Automatic deductions:**

These deductions apply in addition to points lost in the requirements. Retries on every task
score zero for R2. The retry deduction also applies if those retries include tasks whose
failures cannot be transient and no reason is given.

| | |
| --- | --- |
| −10 | retries on tasks whose failures cannot be transient, with no reason given |
| −10 | a run trains from an uncommitted configuration and nothing records it |
| −8 | the failure path does not report |
| −8 | a demonstration that leaves the repository with uncommitted changes |
| −5 | client and server versions not pinned together |
| −5 | Prefect state or `.env` committed |
| −5 | a deployment that has never started a run |
