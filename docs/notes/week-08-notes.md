# Week 8 — Orchestration — Study Notes

These notes go with the Week 8 lecture and lab. Week 7 put our checks on a schedule: on every
commit, and every Monday at 03:00. Week 8 answers the question this raises and leaves open:
**how do you know it ran?**

## Why this matters

**Toy Story 2 (Pixar).** Pixar makes animated films. During the production of *Toy Story 2*,
every character, set and shot was a file on one shared server. A delete command started at the
top folder of the project and worked its way down. Oren Jacob was then an associate technical
director. He tells how his colleague Larry Cutler looked at a folder that "had like 40 files". He
looked again, and it had four. The team went to the backup on tape. The backup file had reached its 4 GB
limit. The error log that would have told the administrators was on the same full volume, at zero
bytes: "no-one at Pixar knew this yet". At the time, Pixar did not test its backups continuously.

The film survived because Galyn Susman, the supervising technical director, had a workstation at
home while she was on maternity leave. Its copy was incomplete. The restore also used older
backups and copies the animators had made. Afterwards, the administrators brought a new backup
plan to the production meeting, and today Pixar tests its backups continuously. (Sources: Taylor
McCloud, *Newsweek*, 16 Feb 2022; Matthew Panzarino, *The Next Web*, 21 May 2012, from an
interview with Jacob. Retellings disagree on the dates and the details; these two are the ones
the lecture uses.)

The backup ran without a person, and it reported nothing. The team believed it had backups. Nobody
could check that belief until the day they needed them. Every automated job this week has the
same risk. Once a job runs on its own, nobody sees it run, so it needs a record and an owner.

**GitLab.com (2017)** (the teacher may use it instead). GitLab.com is an online service where
developers keep their Git projects. On 31 January 2017, during an incident, an engineer meant to
clean the secondary database server and deleted the database folder on the primary, about 300 GB.
The team went to the backups. The `pg_dump` backups should have been in an S3 bucket, but "the S3
bucket was empty". Disk snapshots were not switched on for the database servers, and replication
was broken. What saved the service was a manual snapshot taken six hours earlier. About six hours
of data were lost: about 5,000 projects, 5,000 comments and 700 new user accounts.

The backup job had been failing on every run: it used `pg_dump` 9.2 against a PostgreSQL 9.6
database. Cron sent an e-mail on each failure, but the e-mails failed DMARC, an e-mail
authentication check, and the receiving server rejected them. "We were never aware of the backups
failing, until it was too late." Afterwards GitLab added automated restore tests, monitoring for
backups, and "an owner for data durability" (GitLab, "Postmortem of database outage of January
31", 10 Feb 2017). A failure notification is a job too, and it can fail without anyone noticing.
So make a run fail on purpose, and check that a person hears about it.

### More cases from the lecture

- **AWS, December 2021.** Amazon Web Services runs cloud services for other companies. AWS's own
  services (monitoring, internal DNS, parts of EC2's control plane) run on an internal network;
  customer applications run on the main network, and network devices link the two. On
  7 December 2021 at 07:30 (Pacific time), an automated job added capacity to a service on the main
  network. Many clients on the internal network opened connections at once, and the network devices
  were overwhelmed. The clients had back-off, but a latent issue stopped it working, so the delays
  caused "even more connection attempts and retries". Customers could not launch new EC2 machines
  from 07:33 to 14:40; all network devices had recovered by 14:22. AWS switched the scaling job off and fixed the back-off (AWS,
  "Summary of the AWS Service Event in the Northern Virginia (US-EAST-1) Region", 10 Dec 2021).
- **AWS DynamoDB, September 2015** (the teacher may use it instead). DynamoDB is AWS's database
  service. Its storage servers ask a metadata service which part of the data they hold. On
  20 September 2015 the answers became too slow, and "unavailable servers continued to retry
  requests for membership data, maintaining high load on the metadata service". Error rates stayed
  high for about five hours. AWS added capacity and made the storage servers ask less often. It also
  split the metadata service into many smaller ones (AWS, "Summary of the Amazon DynamoDB Service
  Disruption and Related Impacts in the US-East Region", Sept 2015).

## Core concepts

### Why an orchestrator

`dvc repro` already runs a graph of steps. It compares the hashes of each stage's inputs with the
last run and skips the stages that are not stale. It keeps no history: `dvc.lock` records the
state after the last successful run, not the attempts, the failures or the times. An
**orchestrator** is a tool that runs a graph of steps and records every run. It knows when a run
happened, how each step ended and how many attempts it took. It can also retry a step or start a
run on a schedule. It has no idea of content hashes, so it cannot decide what is stale.

A cron gives you only the trigger: it starts a job at a time, and nothing more. The tools on the
market include Apache Airflow, Dagster, Prefect, Kubeflow Pipelines and Argo Workflows. The course
uses Prefect: a flow is a Python function, it runs in tests without a server, and its server fits
in our Compose stack. Airflow is the one you are most likely to meet at work. It needs a
scheduler, a Dag processor, an API server and a metadata database, so a platform team often runs
it for many teams.

Lecture: "2 · Orchestration" · Lab: Exercise 2

### Tasks, flows and the run record

A **task** (`@task`) is one step; a **flow** (`@flow`) is the function that calls the steps. When
you call a flow, Prefect creates a **flow run**, and a **task run** for each step. Each has a name,
a start time, a duration, a state and a number of attempts. With no server configured, Prefect
starts a temporary one for the run and stops it afterwards. The lab points the client at its own
server, `PREFECT_API_URL=http://127.0.0.1:5520/api`, so the record stays in Postgres and the UI
shows it.

`daily_mean.fn(...)` calls the plain Python function inside a task and leaves no record. In
Prefect 3, calling the task itself outside a flow, `daily_mean(...)`, also creates a task run.

```python
from prefect import flow, task

@task
def daily_mean(readings: list[float]) -> float:
    return sum(readings) / len(readings)

@flow(log_prints=True)
def weather_report(station: str = "A") -> float:
    mean = daily_mean([12.5, 13.1, 11.8])
    print(f"station {station}: mean {mean:.1f} °C")
    return mean
```

Lecture: "3 · Tasks, flows and run states" · Lab: Exercise 1

### States and partial failure

A run moves through **Scheduled**, **Pending**, **Running** and **Completed**. A failed attempt
with retries left goes through **AwaitingRetry** and **Retrying**. An exception with no retries
left ends **Failed**; a run killed from outside (out of memory, a stopped container) ends
**Crashed**. A scheduled run whose start time has passed, and which has not started, is **Late**.

Failed and Crashed send you to different places. A Failed task raised an exception: read it, the
cause is usually in your code. A Crashed task was killed, so its last log line is not the cause:
look at the machine. When a task fails, the tasks after it never start and get no task run. The
record shows what ran, not what should have run.

Report how every run ends, also when it fails: what ran, where it stopped, and why. In the
lecture's weather flow, a `try`/`except` around the tasks calls `notify` on the failure path. It
then raises the error again, so the flow run stays Failed in the record. Where a notification is delivered
(e-mail, chat, a pager) is Week 11.

Lecture: "3 · Tasks, flows and run states" · Lab: Exercise 1

### Retries and idempotency

Without retries, one dropped connection fails the whole run. In the lecture, `fetch_readings`
raised a `ConnectionError` and the flow run ended Failed. The weather server answered again a
second later. A **retry** runs a failed task again after a delay. It helps only when the
same call may succeed next time: a network that drops for a second, a service that is restarting
(503), or a rate limit (429). A refused permission (403) or a task that runs out of memory gives
the same result on the next try. So does a failed validation: bad data gives the same exception
on every try. In the lecture, `check_readings` with `retries=3, retry_delay_seconds=2` failed four
times on the same bad reading, and the flow failed 6 seconds later than it needed to. Put retries
on the tasks that cross a network, and only where a repeat is safe.

You could write the retry loop yourself, with `try`/`except` and `time.sleep`. Then you write and
test it in every task, and the record shows one task run with no failed attempt. With
`@task(retries=3, retry_delay_seconds=2)` the orchestrator retries the task, and the record keeps
every attempt.

With a **fixed delay**, clients that failed at the same moment retry at the same moment, as often
as before. **Exponential backoff** doubles the delay after each failed attempt, so a restarting
service has time to come back. **Jitter** adds a random part to each delay, so tasks that failed together do not retry
together. The AWS outage of 2021 shows what happens when back-off does not work: retries keep the
overload going.

```python
from prefect.tasks import exponential_backoff

@task(retries=3,
      retry_delay_seconds=exponential_backoff(backoff_factor=1),   # 1, 2, 4 s
      retry_jitter_factor=0.2)                                      # up to 20% longer
def fetch_readings(station: str) -> list[float]: ...
```

An operation is **idempotent** if running it twice has the same effect as running it once. Check
this before you add a retry. Suppose a request reaches the server and the server acts on it, but
the response is lost. The client cannot tell this from a request that never arrived, so it retries.
The action happens twice: a second charge on a card, a second record, a second e-mail. The fix
is an idempotency key: the client sends the same key with each attempt, and the server ignores a
key it has already seen. Not every service offers one.

Check that a retry policy works: stop the service it protects, run the flow, and watch the delays
in the log. Then start the service again and see the same flow complete.

Retries also hide problems. With `retries=5` on every task, fewer runs fail, but the problems
stay. A service needs more attempts each week, a bug is reported six attempts late, a create call
runs twice. The run record keeps every attempt, so read the attempt counts, and
open a ticket when a service needs retries on most runs. Prefect's `retry_condition_fn` can limit
retries to chosen exceptions, such as a connection error.

Lecture: "4 · Retries" and "7 · Red flags and good practices" · Lab: Exercise 3

### Time limits

A call that hangs never fails. The server accepts the connection and never answers. The task
stays **Running**, and nobody is told. A retry does not help, because there is no failure to
retry. `timeout_seconds` gives the task a time limit:

```python
@task(timeout_seconds=5)
def fetch_readings(station: str) -> list[float]: ...
```

In the lecture, a task that slept for 60 s ended after 5 s in the state **TimedOut**, and so did
its flow run. TimedOut is a kind of Failed, so the flow's failure path runs and can tell someone.
Set a timeout on every task that waits for something outside: the network, another service, a
lock. Pick the limit from the run history, a few times the usual duration, so a slow but healthy
run is not stopped.

Lecture: "7 · Red flags and good practices" · Lab: not in the lab (you would add one to the
Silo tasks of Exercise 3)

### Parameters: in a commit or in the run

The pipeline's parameters live in `params.yaml`, and `dvc repro` hashes that file: when a value
changes, the stages that use it, and the stages after them, run again. A flow can also take
parameters, like `station` in the weather flow. It is tempting to make `C` one of them, so that
anyone can try a value from the UI without a commit. That causes three problems:

- **DVC does not see it.** The stages are commands that read `params.yaml`. A value in the
  flow's memory never reaches them: `train` is skipped, and the run ends Completed with the
  previous model. So the flow would have to write the value into `params.yaml` first.
- **No commit.** The model then comes from a `params.yaml` that is not in Git, and nobody
  reviewed the change.
- **Two runs, one file.** Two runs at the same time overwrite each other's value.

So change a hyperparameter (`train.C`, `impute_strategy`, the gate's thresholds) with a commit to
`params.yaml`: the change is reviewed, Git keeps it, and `dvc.lock` records the value each stage
used. Keep flow parameters for what a run does (`push`, `register_model_version`), which the flow
run's record keeps. To try many values without a commit each, DVC has
`dvc exp run -S train.C=0.01`; it brings DVC's experiments system, which this course does not
teach.

Lecture: "5 · Parameters" · Lab: Exercise 4

### Scheduling

A **deployment** is a flow registered on the Prefect server with its parameters and a schedule,
such as the cron `0 6 * * 1` (Monday 06:00). The server plans the next runs ahead: at least
three, at most 100, and at most 100 days ahead. Give a cron schedule a time zone
(`Europe/Budapest`), so a daily run moves with daylight saving time. The server only plans a run;
another process must start it.

With `.serve()`, that process is the script itself. `weekly_flow.serve(name=..., cron=...)`
creates the deployment, asks the server for due runs every 10 seconds, and runs each one in a
subprocess on the same machine. The flow run then talks to the other services (in the lab, Silo
and MLflow) and reports its states to the server. Stop the process, and Prefect pauses the
schedule and deletes the planned runs: no run starts, and no run fails. It also needs a real
server: with the temporary one, Prefect warns "Cannot schedule flows on an ephemeral server".

With a **work pool**, the server keeps a queue of due runs and the settings for where they run
(an image, CPU, memory). A **worker** is a long-running process on your infrastructure. It asks
its pool for due runs and starts each one on new infrastructure. A Docker worker starts a
container, and a Kubernetes worker starts a job. Start with `.serve()` on a machine that stays
on, and move to a work pool when runs need their own containers or machines.

On a work pool, every run starts in a new container, and the container is removed when the run
ends. The next run finds only what the last one pushed to storage outside the container. In the
lab, that is the data and model in Silo (`dvc push`) and the runs in MLflow. Files on the local
disk, such as `models/model.pkl` or a changed `dvc.lock`, are gone. With `.serve()` on one
machine, the files stay between runs. So a flow that depends on them works in the lab and breaks
later on a work pool. Prefect's own results have the same limit. By default they are saved to
`~/.prefect/storage/`, and a new container "cannot access results saved to the local filesystem
of the original container" (Prefect docs, "Results"). Pass small values, such as a verdict or a
run ID, between tasks; push data and models to storage, and pass their path or hash.

Before you put a flow on a schedule, test it the way the scheduler calls it. Prefect builds a
Pydantic model from the flow's signature and checks the parameters of every run, also the ones the
server sends as JSON. If Pydantic cannot find a type named in an annotation, the run fails before
the first task with `PydanticUserError: ... is not fully defined`. This happens with postponed
annotations (`from __future__ import annotations`) and a type imported only under `TYPE_CHECKING`
or inside a function. A dataclass or Pydantic model defined at module level works. Call
`flow.validate_parameters({...})` in a test, or run the flow once through its deployment. Strings,
numbers and booleans as parameters avoid the problem and are easy to type in the UI.

Lecture: "6 · Scheduling" · Lab: Exercise 5

### One ML system, several pipelines

Our lab orchestrates one pipeline: training. A system in production usually has three
(Dowling, 2023). A **feature pipeline** turns raw data into features. A **training pipeline**
turns features into a model. An **inference pipeline** uses features and a model to make
predictions. Each has its own schedule and owner: features daily, training weekly, batch predictions
nightly. They do not call each other. They meet in storage with versions: features in a table
or a feature store, models in the registry. So one pipeline can fail without stopping the
others. If Monday's training fails, the nightly predictions still run with the model that the
registry alias points to. The cost is that the predictions may come from an old model, so
someone must notice the failed training (Week 11's alerts). In our lab, the features are
computed inside the model's own `Pipeline` (imputer and scaler), so training and prediction
cannot compute them differently. Week 9 adds the inference side.

Lecture: "6 · Scheduling"

### How do you know it ran?

A **log** is what a process printed while it was alive to print it. A **run history** is the
record of which runs existed, each task's state, attempts and times. We ran the weather
flow four times. The server's history then held 4 flow runs (3 Completed, 1 Failed) and 15 task
runs (14 Completed, 1 Failed). It also showed that `fetch_readings` needed 3 attempts in one run. No log file gives you that count after the process has ended. A run history is also
evidence for an audit (Week 13).

When a weekly schedule stops, the record shows it in one of two ways. If the server still
schedules runs, the run that did not start becomes **Late**. If the scheduler itself is gone,
there is no run and no row, so a dashboard of failed runs shows nothing. The lab's set-up gives
the second case. With `.serve()`, stopping the process pauses the schedule (`pause_on_shutdown=True`
by default) and deletes the runs already scheduled: no Late run, no row. Late appears when the
schedule stays active but nothing picks the run up. Examples are a work pool whose workers are
down, or a `.serve()` process that was killed before it could pause the schedule. Alert when an expected run
has not completed in time, as well as when a run fails. For the Toy Story 2 backup, that check
would read "no successful backup in 48 hours".

Lecture: "6 · Scheduling" · Lab: Exercises 1 and 5

### When an orchestrator is worth it

An orchestrator is one more system to run. Prefect needs a server and a database, which someone
must run, back up and upgrade. In this course that is one more service in Compose and a second
Postgres database. Without a configured server, every flow run starts a temporary one, about 8 s,
and the test harness adds about 4.3 s per test session.

It is worth it when the pipeline has many steps, calls over the network, runs on a schedule, and
several people read its runs. It is too much for one script on one schedule: a cron and a check on
the last successful run do the job. Start with those. Add an orchestrator when you need retries,
parameters or a history of many steps. If your company already runs Airflow or
Prefect for other pipelines, one more flow costs little.

Lecture: "6 · Scheduling" · Lab: Exercise 2

### Keep the framework at the edges

Most tests should not need Prefect. `task.fn(...)` runs the plain function and costs nothing.
`prefect_test_harness()` sets up a test database once per session, about 4.3 s in the lab. A flow
run with no harness starts a temporary server, about 8 s. `get_run_logger()` raises an error
outside a run, so a task that calls it cannot run as `task.fn(...)`. Put the logic in plain
functions, and keep the decorators at the edges.

Lecture: "7 · Red flags and good practices" · Lab: Exercise 3

## Commands

```bash
uv add prefect                                  # install Prefect in a project
prefect server start                            # a local Prefect server and UI
export PREFECT_API_URL=http://127.0.0.1:5520/api   # the lab's server; note the /api
```

```python
weather_report()                                         # one flow run
daily_mean.fn([12.5, 13.1, 11.8])                        # the plain function, no record
weather_report.serve(name="daily-weather", cron="0 6 * * *")   # a deployment on a schedule
weather_report.validate_parameters({"station": "B"})     # check parameters as the scheduler does
```

In the lab: `make up` starts the stack (Prefect UI on port 5520), `make flow` runs the training
flow, and `make serve` serves it on a cron schedule.

## Key terms

- **Orchestrator** — a tool that runs a graph of steps and records every run.
- **Flow / task** — the function that calls the steps, and one step; each call creates a *run*.
- **Flow run / task run** — the record of one call: its state, attempts and times.
- **State** — Scheduled, Pending, Running, Completed, AwaitingRetry, Retrying, Failed, Crashed,
  and Late for a scheduled run that did not start on time.
- **Retry / fixed delay / exponential backoff / jitter** — try again; wait the same time before each attempt; double the wait after each failed attempt; add a random part to each wait.
- **Timeout** — the longest a task may run (`timeout_seconds`); a task that takes longer ends
  **TimedOut**, a kind of Failed.
- **Idempotent** — running it twice has the same effect as running it once.
- **Idempotency key** — a key sent with each attempt so the server can ignore a repeat.
- **Flow parameter** — an input for one run, such as `push`. Prefect checks it with a Pydantic
  model built from the flow's signature. Hyperparameters stay in `params.yaml`.
- **Deployment** — a flow plus how and when it should run.
- **`.serve()`** — a process that starts the scheduled runs of a deployment.
- **Work pool** — a queue of runs on the server, with the settings for where they run.
- **Worker** — a long-running process that takes runs from a work pool and starts each one on new
  infrastructure.
- **Feature / training / inference pipeline** — the three pipelines of an ML system: raw data to
  features, features to a model, features and a model to predictions.
- **Run history** — what the system did, as opposed to what a process printed.
- **Partial failure** — some steps ran, some never started, and the state is in between.

## How this connects to the lab

Exercise 1 wires the tasks into a flow and runs it against the self-hosted Prefect server.
Exercise 2 is written: what Prefect and DVC each give you, and what would happen if you split
`dvc repro` into several tasks. Exercise 3 sets the retry policy and asks you to defend it.
Exercise 4 records in each run which values `train` used (from `dvc.lock`) and whether
`params.yaml` was committed. You try a value without a commit, and the run a schedule would start
refuses it. Exercise 5 puts the flow on a cron and asks what must happen before a model trained
at 03:00 reaches users.

The model does not change this week: the metrics stay the same as in Weeks 5–7 (F1 0.6341,
ROC AUC 0.8345). Check this rather than assume it.

## Recommended reading

- **Prefect: quickstart, retries, self-hosting** — short, and the primary references.
  https://docs.prefect.io/v3/get-started/quickstart ·
  https://docs.prefect.io/v3/how-to-guides/workflows/retries ·
  https://docs.prefect.io/v3/advanced/self-hosted
- **Apache Airflow: architecture overview** — the most common alternative, and the one you are most
  likely to meet at work.
  https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html
- **Jim Dowling, "From MLOps to ML Systems with Feature/Training/Inference Pipelines"**
  (Hopsworks, 2023) — one ML system as three pipelines that meet in storage.
  https://www.hopsworks.ai/post/mlops-to-ml-systems-with-fti-pipelines
- **Testing workflows** — `prefect_test_harness` and `task.fn`.
  https://docs.prefect.io/v3/how-to-guides/workflows/test-workflows
- **Sculley et al., "Hidden Technical Debt in Machine Learning Systems"** (NeurIPS 2015) —
  pipeline jungles and configuration debt.
  https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf
- **Matthew Panzarino, "How Pixar's Toy Story 2 was deleted twice"** (*The Next Web*, 2012) — the
  backup story, from an interview with Oren Jacob.
  https://thenextweb.com/news/how-pixars-toy-story-2-was-deleted-twice-once-by-technology-and-again-for-its-own-good
- **AWS, "Summary of the AWS Service Event in the Northern Virginia (US-EAST-1) Region"** (2021) —
  the retry case. https://aws.amazon.com/message/12721/
- **GitLab, "Postmortem of database outage of January 31"** (2017) — backups that failed, and
  failure e-mails nobody received.
  https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/
- Huyen, *Designing Machine Learning Systems*, Ch. 10 — workflow orchestration in context.

## Check yourself

1. A colleague adds `retries=5` to every task "to make the pipeline more reliable", and the
   failure rate drops. What has changed, what is now hidden, and which operation in your project
   could run twice?
2. A colleague wants `training_flow` to take `C` as a parameter, so that anyone can try a value
   from the UI. Give two problems this causes, and say where `C` should change instead.
3. One run is Late; in another, a task Crashed. Where do you look first in each case, and why
   are the two places different?
4. Your weekly retrain stops firing. Why will neither a dashboard of failed runs nor a failure
   notification tell you? Describe something that would.
5. Your team's weekly retrain is served with `.serve()` from a colleague's laptop. What happens to
   Monday's run when the laptop is shut down on Friday, and what would you change?
6. A colleague's flow has been in the Running state for nine hours; it usually takes twenty
   minutes. No retry has run. Why not, and what would you change in the flow?
7. A team has one nightly script that exports a table to a file. Would you put it in an
   orchestrator? What is the smallest thing that would tell them it stopped working?
8. Your flow moves from `.serve()` to a Docker work pool. The second run fails because
   `models/model.pkl` is missing, although the first run wrote it. Why, and what should the first
   run have done?
9. The weekly training pipeline fails on Monday. Should Tuesday's batch predictions stop? What
   connects the two pipelines, and what does someone still have to notice?
