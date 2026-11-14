---
theme: default
title: Week 8 — Orchestration
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers workflow orchestration with Prefect: tasks, flows and run states,
  retries and idempotency, parameters, schedules, and knowing that
  an automated run happened.
class: text-left
transition: slide-left
mdc: true
# hash routing + relative base (built with --base ./) so the SPA works in a
# GitHub Pages subdirectory: slides live after the # and assets load relatively.
routerMode: hash
# Shared course components (Lifecycle, ImageSlot). The path is resolved from
# lectures/, so './_shared' means lectures/_shared.
addons:
  - ./_shared
duration: 80min
---

# Week 8: Orchestration

<carbon-flow-stream class="icon-corner" />

**Lifecycle of Artificial Intelligence Systems**

- Run records
- Prefect tasks and flows
- Retries and idempotency
- Parameters and schedules

<!--
Homework 1 is due this Sunday, 1 November. Homework 3 (a Prefect flow for the student's own project) comes out next week.
-->

---

# Recap: CI and CT

<carbon-continuous-integration class="icon-corner" />

<div class="middle">

<div class="text-lg">

| | **Continuous integration** | **Continuous training** |
| --- | --- | --- |
| **Starts on** | <span v-click="1">a push, a pull request</span> | <span v-click="1">a schedule, a person, new data</span> |
| **What changed** | <span v-click="2">the code</span> | <span v-click="2">the data</span> |
| **Checks** | <span v-click="3">lint, tests, the pipeline with its gates</span> | <span v-click="3">the data contract and the model gate</span> |
| **Result** | <span v-click="4">**✓ or ✗ on the pull request:** may the change merge?</span> | <span v-click="4">**a new model and its verdict:** may it be registered?</span> |

</div>

</div>

<!--
-->

---

# Recap: Model quality gates

<carbon-task-approved class="icon-corner" />

<div class="middle">

<div class="text-lg">

| **Question** | **Answer** |
| --- | --- |
| F1 is above its floor.<br>Can the verdict still be NO-GO? | <span v-click="1">**Yes:** one group below its limit, or a drop against the champion</span> |
| Which groups do teams usually score? | <span v-click="2">**Age, sex, region, clinic.**<br>Lab: age, BMI, insulin measured or not.</span> |
| The gate says NO-GO.<br>What happens next? | <span v-click="3">**The pipeline stops.** Nothing is registered, the report shows the failed criteria.</span> |

</div>

</div>

<!--
-->

---

# A missing scheduled run

<carbon-time class="icon-corner" />

<div class="middle">

```yaml
on:
  schedule:
    - cron: '0 8 * * 1'     # Mondays, 08:00 UTC
```

Monday, 08:05. You open the Actions tab to check the run, and it is not there. **What could cause it?**

<v-click>

What GitHub's documentation says[^1][]:

</v-click>

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><ph-hourglass-medium class="ic" /><b>Delayed</b>at high load, for example at the start of every hour</div>
  <div v-click class="card"><ph-trash class="ic" style="color:#dc2626" /><b>Dropped</b>"some queued jobs may be dropped"</div>
  <div v-click class="card"><ph-power class="ic" style="color:#dc2626" /><b>Disabled</b>in a public repository, after 60 days with no activity</div>
</div>

</div>

[^1]: GitHub Docs, "Events that trigger workflows", `schedule` (checked 3 Oct 2026). https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

<!--
-->

---
layout: section
---

# 1 · To infinity and back up

<!--
About 10 minutes, one case. The title plays on Buzz Lightyear's "To infinity and beyond!"; if you switch to Option B, rename the section "1 · The GitLab backups". Option B (GitLab.com, 2017) is hidden after the Pixar slides. Both are backups, not ML pipelines: a scheduled job that fails without telling anyone is the same problem whatever the job does.
-->

---

# Toy Story 2

<carbon-video class="icon-corner" />

<div class="middle">

Every character, set and shot of *Toy Story 2* was kept on one shared server[^1][], with a backup on tape[^2][].

<div class="flow" style="margin-top:2.5rem">
  <div class="node amber" style="width:10rem"><ph-users-three class="ic" /><b>Animators</b><br><small>change files every day</small></div>
  <div class="arrow">→</div>
  <div class="node" style="width:12rem"><ph-hard-drives class="ic" /><b>Asset server</b><br><DataBatch cells="gggggggg gggggggg" :cols="8" /></div>
  <div class="arrow-l">backup job<span class="arrow">→</span></div>
  <div class="node" style="width:10rem"><ph-archive class="ic" /><b>Backup</b><br><small>on tape</small></div>
</div>

</div>

[^1]: Taylor McCloud, "'Lightyear' Producer Credited With Saving 'Toy Story 2' After Deletion", *Newsweek*, 16 Feb 2022, quoting Oren Jacob. https://www.newsweek.com/lightyear-producer-credited-saving-toy-story-2-after-deletion-1680072
[^2]: Matthew Panzarino, "How Pixar's Toy Story 2 was deleted twice, once by technology and again for its own good", *The Next Web*, 21 May 2012, from an interview with Oren Jacob. https://thenextweb.com/news/how-pixars-toy-story-2-was-deleted-twice-once-by-technology-and-again-for-its-own-good

<!--
Oren Jacob was an associate technical director on Toy Story 2 and later Pixar's CTO. Retellings disagree on the date and the details; the four slides of this case keep to these two sources.
-->

---

# Files deleted

<carbon-trash-can class="icon-corner" />

<div class="middle">

Someone deleted files from the asset server by mistake.

<div class="flow" style="margin-top:2.5rem">
  <div class="node amber" style="width:10rem"><ph-users-three class="ic" /><b>Animators</b></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:12rem"><ph-hard-drives class="ic" /><b>Asset server</b><br><DataBatch cells="g......g ...g...." :cols="8" /></div>
  <div class="arrow-l">backup job<span class="arrow">→</span></div>
  <div class="node" style="width:10rem"><ph-archive class="ic" /><b>Backup</b></div>
</div>

About **90%** of the film was gone.

</div>

<!--
A size check on the film's folder showed 10% of the size it should have been.
Jacob tells how a colleague watched a folder of about 40 files shrink to four.
-->

---

# What was in the backup?

<carbon-data-backup class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:10rem"><ph-users-three class="ic" /><b>Animators</b></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:12rem"><ph-hard-drives class="ic" /><b>Asset server</b><br><DataBatch cells="g......g ...g...." :cols="8" /></div>
  <div :class="$clicks >= 1 ? 'arrow-l fail' : 'arrow-l'">backup job<span class="arrow">→</span></div>
  <div v-click="1" class="node rose" style="width:12rem"><ph-archive class="ic" /><b>Backup on tape</b><br><DataBatch cells="rrrr rrrr" /></div>
</div>

<v-clicks at="2">

- The backup reached the tape's **4 GB file-size limit**. After that, new data pushed older files off, so the tape no longer held the whole film.
- The error log was on the same full disk, so it stayed **empty**: nobody was warned.

</v-clicks>

</div>

<!--
TNW: "as the files hit 4 gigabytes in size, the maximum size of the file was met", and new data was "pushing" the older files off; it gives no more detail. "Pixar, at the time, did not continuously test their backups."
-->

---

# Maternity leave for the rescue

<carbon-home class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node rose" style="width:11rem"><ph-hard-drives class="ic" /><b>Asset server</b><br><DataBatch cells="g......g ...g...." :cols="8" /></div>
  <div class="arrow">←</div>
  <div class="node amber" style="width:15rem"><ph-house class="ic" /><b>A home computer</b><br><small>a technical director on maternity leave had a copy</small></div>
</div>

> [!NOTE]
> Afterwards, Pixar changed its backup plan, and today it tests its backups continuously.

</div>

<!--
Galyn Susman, supervising technical director, later the producer of Lightyear (2022). Pixar gave her a workstation at home while she was on maternity leave. Her copy was incomplete and up to a couple of weeks old; the restore also used older backups and copies the animators had made (TNW).
-->

---

# How would you catch it?

<carbon-security class="icon-corner" />

<div class="middle">

The backup job runs every night. How do you find out that it fails?

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin:2rem 0 1.5rem">
  <div v-click class="card"><ph-terminal-window class="ic" /><b>Exit status</b>record how every run ends: success or error, and when</div>
  <div v-click class="card"><ph-bell-ringing class="ic" /><b>Alert</b>notify the job's owner on failure, and when no run has succeeded for a day</div>
  <div v-click class="card"><ph-arrow-counter-clockwise class="ic" /><b>Restore test</b>restore from the backup on a schedule, and check the files</div>
</div>

<v-click>

> [!TIP]
> Record the exit status of every scheduled job, and alert its owner when a run fails or does not happen.

</v-click>

</div>

<!--
-->

---
hide: true
---

# Option B · 2017: GitLab.com loses its database

<carbon-data-base class="icon-corner" />

<div class="middle">

On 31 January 2017, during an incident, an engineer at GitLab.com deleted the database folder on the wrong server[^1][].

<div class="flow" style="margin-top:2rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-user class="ic" /><b>An engineer</b><br><small>meant to clean the secondary</small></div>
  <div class="arrow-l fail">delete<span class="arrow">→</span></div>
  <div class="node rose no-shrink" style="width:12rem"><ph-database class="ic" /><b>Primary database</b><br><small v-click="1">about 300 GB removed</small></div>
  <div v-click="2" class="arrow-l">restore<span class="arrow">←</span></div>
  <div v-click="2" class="node no-shrink" style="width:10rem"><ph-archive class="ic" /><b>Backups</b><br><small>?</small></div>
</div>

</div>

[^1]: GitLab, "Postmortem of database outage of January 31", 10 Feb 2017. https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/

<!--
Option B for the cold open: use it instead of Toy Story 2 (switch `hide` on the five Pixar slides and on these three GitLab slides). The note of "Running the schedule with `.serve()`" also refers to Toy Story 2; use GitLab's rejected e-mails there instead.
The postmortem names nobody. It blames the missing ownership: "nobody was responsible for testing this procedure".
-->

---
hide: true
---

# Option B · What was in the backups?

<carbon-data-backup class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(4,1fr)">
  <div v-click class="card"><ph-file-sql class="ic" style="color:#dc2626" /><b><code>pg_dump</code> backups</b>"The S3 bucket was empty"</div>
  <div v-click class="card"><ph-camera-slash class="ic" style="color:#dc2626" /><b>Disk snapshots</b>not switched on for the database servers</div>
  <div v-click class="card"><ph-copy class="ic" style="color:#dc2626" /><b>Replication</b>broken, and the secondary wiped too</div>
  <div v-click class="card"><ph-camera class="ic" style="color:#16a34a" /><b>A manual snapshot</b>taken 6 hours earlier: it worked</div>
</div>

<v-click>

About 6 hours of data lost: about 5,000 projects, 5,000 comments and 700 new user accounts.

</v-click>

</div>

<!--
Option B, second slide. The backup job ran `pg_dump` 9.2 against a PostgreSQL 9.6 database. The version difference made it stop with an error on every run.
-->

---
hide: true
---

# Option B · Why did nobody know?

<carbon-security class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node no-shrink" style="width:9rem"><ph-archive class="ic" /><b>Backup job</b><br><small>stops with an error</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><ph-envelope-simple class="ic" /><b>Failure e-mail</b><br><small>sent by cron</small></div>
  <div v-click="1" class="arrow-l fail">rejected<span class="arrow">→</span></div>
  <div v-click="1" class="node rose no-shrink" style="width:10rem"><ph-tray class="ic" /><b>Mail server</b><br><small>never delivered</small></div>
</div>

<v-click at="2">

"We were never aware of the backups failing, until it was too late."

</v-click>

<v-click at="3">

> [!TIP]
> Test the alert as well as the job: make a run fail on purpose, and check that a person hears about it.

</v-click>

</div>

<!--
Option B, third slide. The e-mails failed DMARC, an e-mail authentication check, so the receiving server rejected them. GitLab's actions afterwards: automated restore tests, monitoring for backups, and "an owner for data durability".
-->

---

# Where we are: running the pipeline

<div class="middle">

<Lifecycle stage="build,cicd" width="70%" />

Today: run the training pipeline automatically, and know what each run did.

</div>

<!--
Why build and CI/CD: the flow wraps the pipeline we built in Weeks 4–6 and runs it without a person, from a commit, a schedule or new data. Week 7 added the trigger; this week adds the record of each run.
-->

---
layout: section
---

# 2 · Orchestration

<!--
-->

---
layout: center
---

# We already run a graph with `dvc repro`.
# Why add another tool?

<div class="cards" style="grid-template-columns:repeat(2,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-fingerprint class="ic" /><b><code>dvc repro</code></b>Is this stale?</div>
  <div v-click class="card"><ph-clock-counter-clockwise class="ic" /><b>An orchestrator</b>Did it run, when, and how did it end?</div>
</div>

<!--
DVC's graph is about files: it compares hashes and skips what has not changed. An orchestrator's graph is about time: attempts, states, durations, schedules.
-->

---

# What is an orchestrator?

<carbon-flow class="icon-corner" />

<div class="middle">

**Orchestrator:** a tool that runs a graph of steps and records every run.

What do we have already?

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1.5rem">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-flow-arrow class="ic" /><b>Order</b>runs the steps one after another, or side by side<br><small v-click="1"><b>we have it:</b> <code>dvc repro</code></small></div>
  <div :class="$clicks >= 2 ? 'card picked' : 'card'"><ph-alarm class="ic" /><b>Triggers</b>a schedule, new data, a person, an API call<br><small v-click="2"><b>we have it:</b> cron</small></div>
  <div class="card"><ph-arrow-clockwise class="ic" /><b>Retries</b>tries a failed step again, after a delay<br><small v-click="3" style="color:#dc2626"><b>missing</b></small></div>
  <div class="card"><ph-list-checks class="ic" /><b>Record</b>the state, time and attempts of each step<br><small v-click="3" style="color:#dc2626"><b>missing</b></small></div>
</div>

<v-click at="4">

An orchestrator does all four. We keep `dvc repro` for what it does better: knowing which stages are stale.

</v-click>

</div>

<!--
Week 7's `ct.yml` is a cron: it starts one workflow on a schedule. It does not retry a step, and the only record is the Actions log, which GitHub keeps for a limited time. `dvc repro` orders the stages, but a failed stage stops it, and `dvc.lock` keeps only the last successful state.
-->

---

# `dvc repro` vs an orchestrator

<carbon-compare class="icon-corner" />

<div class="middle">

| **Question** | **`dvc repro`** | **An orchestrator** |
| --- | :---: | :---: |
| Has `params.yaml` changed since the last run? | <span v-click="1"><carbon-checkmark-filled style="color:#16a34a; font-size:1.3em" /></span> | <span v-click="1"><carbon-close-filled style="color:#dc2626; font-size:1.3em" /></span> |
| Which stages can it skip? | <span v-click="2"><carbon-checkmark-filled style="color:#16a34a; font-size:1.3em" /></span> | <span v-click="2"><carbon-close-filled style="color:#dc2626; font-size:1.3em" /></span> |
| Did last Monday's scheduled run happen? | <span v-click="3"><carbon-close-filled style="color:#dc2626; font-size:1.3em" /></span> | <span v-click="3"><carbon-checkmark-filled style="color:#16a34a; font-size:1.3em" /></span> |
| Should a failed upload try again? | <span v-click="4"><carbon-close-filled style="color:#dc2626; font-size:1.3em" /></span> | <span v-click="4"><carbon-checkmark-filled style="color:#16a34a; font-size:1.3em" /></span> |
| How long did each step take, and how many attempts? | <span v-click="5"><carbon-close-filled style="color:#dc2626; font-size:1.3em" /></span> | <span v-click="5"><carbon-checkmark-filled style="color:#16a34a; font-size:1.3em" /></span> |

</div>

<!--
`dvc.lock` records the state after the last successful run; it keeps no history of attempts or failures. The orchestrator has no idea of content hashes, so it cannot decide what is stale.
-->

---

# A pipeline inside a pipeline

<carbon-chart-relationship class="icon-corner" />

<div class="middle">

<div style="border:2px dashed #0284c7; border-radius:0.75rem; padding:0.5rem 1rem 0.2rem; width:38rem; margin:0 auto">
<div class="text-sm" style="color:#0284c7"><b>The flow:</b> the orchestrator runs every step</div>
<div class="flow" style="gap:0.5rem; margin:0.5rem 0">
  <div class="node amber no-shrink" style="width:9rem"><ph-cloud-arrow-down class="ic" /><b>pull data</b><br><small>from the object store</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:9rem"><ph-graph class="ic" /><b>dvc repro</b><br><small>one step</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-tag class="ic" /><b>register</b><br><small>in MLflow</small></div>
</div>
</div>

<div v-click>
  <div class="split-stem"></div>
  <div class="split-bar" style="width:36rem"></div>
  <div class="flow" style="margin-top:0; gap:0.4rem; font-size:0.85rem">
    <div class="node violet" style="width:6rem">validate</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">prepare</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">train</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">evaluate</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">gate</div>
  </div>
</div>

<v-click>

The orchestrator runs the whole pipeline; `dvc repro` is one of its steps. Inside that step, DVC decides which stages run.

</v-click>

</div>

<!--
The steps at the edges talk to other services over the network; the stages inside `dvc repro` read and write local files.
-->

---
class: fn-inline
---

# Tool options

<carbon-tool-box class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-wind class="ic" /><b>Apache Airflow</b>workflows as Python DAGs: develop, schedule, monitor</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-cube class="ic" /><b>Dagster</b>a data orchestrator built around assets</div>
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-flow-arrow class="ic" /><b>Prefect</b>build, deploy, run and monitor pipelines: Python functions with decorators</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-boat class="ic" /><b>Kubeflow Pipelines</b>ML workflows in containers on Kubernetes</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-git-fork class="ic" /><b>Argo Workflows</b>parallel jobs in containers on Kubernetes</div>
</div>

<div class="text-sm opacity-70">

Airflow[^1][] · Dagster[^2][] · Prefect[^3][] · Kubeflow Pipelines[^4][] · Argo Workflows[^5][]

</div>

<v-click>

**We use Prefect:** a flow is a Python function, it runs in tests without a server, and its server fits in our Compose stack.

</v-click>

</div>

[^1]: https://airflow.apache.org/docs/apache-airflow/stable/index.html
[^2]: https://dagster.io/docs
[^3]: https://docs.prefect.io/v3/get-started/quickstart
[^4]: https://www.kubeflow.org/docs/components/pipelines/overview/
[^5]: https://argo-workflows.readthedocs.io/en/latest/

<!--
Kubeflow Pipelines and Argo run every step in its own container on Kubernetes, which Week 9 introduces. Prefect Cloud is Prefect's hosted service; this course self-hosts the open-source server and never needs an account.
-->

---
hide: true
---

# Prefect or Airflow?

<carbon-compare class="icon-corner" />

<div class="middle">

<div style="font-size:0.8rem">

| | **Prefect** | **Apache Airflow** |
| --- | --- | --- |
| A workflow is | a Python function with `@flow`, its steps `@task` functions | a Dag, defined in a Python file |
| It starts | when you call it, or on a schedule through a deployment | when the scheduler triggers it |
| You need | nothing for one call; a server and a database for schedules | a scheduler, a Dag processor, an API server and a metadata database |
| Choose it when | one team writes, tests and runs its own pipeline | a platform team already runs it for many teams' batch workflows |

</div>

<div class="text-sm opacity-70">

Prefect docs[^1][] · Airflow 3.3 docs[^2][]

</div>

</div>

[^1]: Prefect docs, "Prefect server" (checked 9 Oct 2026). https://docs.prefect.io/v3/concepts/server
[^2]: Airflow docs, "Architecture Overview" (checked 9 Oct 2026). https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html

<!--
Hidden: an optional comparison. Show it if the room asks which tool they will meet at work.
Databases: Prefect uses SQLite by default and recommends PostgreSQL for production; Airflow's metadata database is "usually PostgreSQL or MySQL". Airflow calls itself "a platform for orchestrating batch workflows"; many teams students join will already run it, and the practices of this week (retries, parameters, a record of each run) carry over unchanged.
-->

---
layout: section
---

# 3 · Tasks, flows and run states

<!--
The code examples use weather readings from a station, not our patients: the lab writes the diabetes flow, so the lecture does not give it away.
-->

---

# Prefect quick start

<carbon-terminal class="icon-corner" />

<div class="middle">

```bash
uv add prefect
```

```python {1|3-9|11-15|17|all}
from prefect import flow, task

@task
def fetch_readings(station: str) -> list[float]:
    return [12.5, 13.1, 11.8]

@task
def daily_mean(readings: list[float]) -> float:
    return sum(readings) / len(readings)

@flow(log_prints=True)
def weather_report(station: str = "A") -> float:
    mean = daily_mean(fetch_readings(station))
    print(f"station {station}: mean {mean:.1f} °C")
    return mean

weather_report()
```

</div>

<!--
Adapted from the Prefect quickstart (https://docs.prefect.io/v3/get-started/quickstart).
A task is one step; a flow is the function that calls the steps.
-->

---

# Prefect quick start

<carbon-terminal class="icon-corner" />

<div class="middle">

<div class="code-lg">

```text {all|2-3|1,4-5|all}
Flow run 'wondrous-fennec' - Beginning flow run 'wondrous-fennec' for flow 'weather-report'
Task run 'fetch_readings-808' - Finished in state Completed()
Task run 'daily_mean-09b' - Finished in state Completed()
Flow run 'wondrous-fennec' - station A: mean 12.5 °C
Flow run 'wondrous-fennec' - Finished in state Completed()
```

</div>

<v-click at="1">

**Two task runs**, one for each `@task`.

</v-click>

<v-click at="2">

**One flow run**, with a generated name, that printed the result for station A.

</v-click>

</div>

<!--
With no server configured, Prefect starts a local one for the run.
-->

---

# A function call, or a flow run?

<carbon-data-table class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node no-shrink" style="width:17rem"><span class="mono" style="font-size:0.75rem; white-space:nowrap">daily_mean.fn([12.5, 13.1, 11.8])</span></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:5rem"><b>12.47</b></div>
  <div style="width:23.5rem"></div>
</div>
<div v-click class="flow">
  <div class="node no-shrink" style="width:17rem"><span class="mono" style="font-size:0.75rem">weather_report(station="A")</span></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:5rem"><b>12.47</b></div>
  <div class="arrow">+</div>
  <div class="node green no-shrink text-sm" style="width:21rem; text-align:left"><b>a record in the server</b><br>flow run <span class="mono">charcoal-owl</span>: Completed<br>parameters <span class="mono">{'station': 'A'}</span>, 0.04 s<br>2 task runs: Completed, 1 attempt each</div>
</div>

<v-click>

> [!TIP]
> Run the pipeline as a flow to leave a record in the server.

</v-click>

</div>

<!--
-->

---

# The states of a run

<carbon-flow-data class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem; font-size:0.9rem">
  <div style="display:flex; flex-direction:column; align-items:center; gap:0.3rem">
    <div style="height:4.6rem"></div>
    <div class="node no-shrink" style="width:7rem"><b>Scheduled</b></div>
    <div v-click="3" class="arrow" style="transform:rotate(90deg)">→</div>
    <div v-click="3" class="node amber no-shrink" style="width:7rem"><b>Late</b><br><small>start time passed</small></div>
  </div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6rem"><b>Pending</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:6rem"><b>Running</b></div>
  <div class="arrow">→</div>
  <div style="display:flex; flex-direction:column; gap:0.45rem">
    <div class="node green no-shrink" style="width:13rem"><b>Completed</b></div>
    <div v-click="1" class="node violet no-shrink" style="width:13rem"><b>AwaitingRetry → Retrying</b><br><small>waits, then runs again</small></div>
    <div v-click="1" class="node rose no-shrink" style="width:13rem"><b>Failed</b></div>
    <div v-click="2" class="node rose no-shrink" style="width:13rem"><b>Crashed</b></div>
  </div>
</div>

</div>

Prefect docs, "States"[^1][]

[^1]: Prefect docs, "States" (checked 3 Oct 2026). https://docs.prefect.io/v3/concepts/states

<!--
Every task run and every flow run has a state, and the server keeps each change with its time. Late is a Scheduled run whose start time has passed and that has not started; by default after 15 seconds. Also in the docs: Cancelled, Paused, Cached, TimedOut.
-->

---
layout: center
---

# **Failed** or **Crashed**:
# what is the difference?

<v-clicks>

- **Failed:** your code raised an exception. Read it, and fix the code.
- **Crashed:** something outside stopped the run: out of memory, a stopped container, a lost machine. The code may be fine.

</v-clicks>

<!--
A crashed task was killed from outside, so its last log line is not the cause.
-->

---

# One task fails. What happens to the rest?

<carbon-warning-alt class="icon-corner" />

<div class="middle">

<div :style="$clicks >= 4 ? 'border:2px solid #dc2626; background:rgba(220,38,38,0.06)' : 'border:2px dashed #94a3b8'" style="border-radius:0.75rem; padding:0.5rem 1rem 0.8rem; width:44rem; margin:0 auto">
<div :class="$clicks >= 4 ? 'text-sm text-red-600' : 'text-sm opacity-70'"><b>flow run</b><span v-click="4">: Failed</span></div>
<div class="flow" style="gap:0.5rem; margin:0.5rem 0 0">
  <div :class="$clicks >= 1 ? 'node green no-shrink' : 'node no-shrink'" style="width:9rem"><b>fetch_readings</b><br><small v-click="1">Completed</small></div>
  <div class="arrow">→</div>
  <div :class="$clicks >= 2 ? 'node rose no-shrink' : 'node no-shrink'" style="width:10.5rem"><b>check_readings</b><br><small>finds −9999.0</small><small v-click="2"> · Failed</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" :style="$clicks >= 3 ? 'opacity:0.4; border-style:dashed' : ''" style="width:8.5rem"><b>write_report</b><br><small v-click="3">never started</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" :style="$clicks >= 3 ? 'opacity:0.4; border-style:dashed' : ''" style="width:8rem"><b>publish</b><br><small v-click="3">never started</small></div>
</div>
</div>

</div>

<!--
-->

---

# Report on the failure path too

<carbon-notification class="icon-corner" />

<div class="middle">

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem" class="text-sm">
<div>

```python
@task
def check_readings(readings: list[float]):
    if min(readings) < -90:
        raise ValueError(
            f"impossible temperature: {min(readings)}")
    return readings

@task
def notify(message: str) -> None:
    print(f"to the station owner: {message}")
```

</div>
<div>

```python
@flow(log_prints=True)
def weather_report(station: str = "A"):
    try:
        check_readings(fetch_readings(station))
        notify(f"station {station}: report ready")
    except Exception as error:
        notify(f"station {station}: FAILED, {error}")
        raise
```

</div>
</div>

<v-click>

```text
Task run 'check_readings-b44' - Finished in state Failed(...)
Task run 'notify-cac' - to the station owner: station A: FAILED, impossible temperature: -9999.0
Flow run 'thundering-oriole' - Finished in state Failed(...)
```

</v-click>

<v-click>

> [!TIP]
> Report how every run ended, also when it fails: what ran, where it stopped, and why.

</v-click>

</div>

<!--
-->

---

# The failed run in the Prefect UI

<carbon-dashboard class="icon-corner" />

<div class="middle">

The same run, the next morning, without the terminal:

<img src="/prefect-ui-failed-run.png" alt="Prefect UI: flow run audacious-dove, Failed, 3 task runs: fetch_readings and notify green, check_readings red" style="width:100%; max-height:270px; object-fit:contain; border-radius:0.5rem" />

<div class="src">The failure-path flow, run on a local Prefect server (Prefect 3.8.2, 22 Oct 2026)</div>

<div class="flow text-sm" style="gap:0.6rem; margin-top:0.8rem">
  <div v-click class="node rose no-shrink" style="width:12rem"><b>Failed</b><br><small>when it ran, how long</small></div>
  <div v-click class="node no-shrink" style="width:12rem"><b>3 task runs</b><br><small>the state of each</small></div>
  <div v-click class="node green no-shrink" style="width:12rem"><b>notify</b><br><small>ran on the failure path</small></div>
</div>

</div>

<!--
The point: the record is in the server, so anyone can read it later, also when nobody watched the terminal. The red band on the timeline is the time after the failure.
-->

---
layout: section
---

# 4 · Retries

<!--
-->

---

# A network call can fail

<carbon-cloud-offline class="icon-corner" />

<div class="middle">

`fetch_readings` asks the weather server for the readings, and the server does not answer:

```python
@task
def fetch_readings(station: str) -> list[float]:
    ...  # the weather server does not answer
```

<v-click>

```text
Task run 'fetch_readings-7af' - Task run failed with exception: ConnectionError('weather server
    did not answer')
Task run 'fetch_readings-7af' - Finished in state Failed(...)
Flow run 'grateful-scallop' - Finished in state Failed(...)
```

</v-click>

<v-click>

One second later, the server answers again. **Should the flow have waited?**

</v-click>

</div>

<!--
-->

---

# Who should handle the retry?

<carbon-renew class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:1.25fr 1fr; gap:1.5rem; align-items:start">
<div>

```python
@task
def fetch_readings(station: str) -> list[float]:
    for attempt in range(4):
        try:
            return ask_weather_server(station)
        except ConnectionError:
            time.sleep(2)
    raise ConnectionError("no answer")
```

<div v-click="1" class="text-sm" style="margin-top:0.6rem">You write and test this loop in every task. The record shows <b>one</b> task run, and no failed attempt.</div>

</div>
<div v-click="2">

```python
@task(retries=3, retry_delay_seconds=2)
def fetch_readings(station: str) -> list[float]:
    return ask_weather_server(station)
```

<div class="text-sm" style="margin-top:0.6rem">The orchestrator retries the task. The record shows <b>every</b> attempt.</div>

</div>
</div>

</div>

<!--
-->

---

# `retries`

<carbon-renew class="icon-corner" />

<div class="middle">

```python {1}
@task(retries=3, retry_delay_seconds=2)
def fetch_readings(station: str) -> list[float]:
    ...  # the weather server does not answer twice, then it does
```

<v-click>

```text
Task run 'fetch_readings-e22' - Task run failed with exception: ConnectionError('weather server
    did not answer') - Retry 1/3 will start 2 second(s) from now
Task run 'fetch_readings-e22' - Task run failed with exception: ConnectionError('weather server
    did not answer') - Retry 2/3 will start 2 second(s) from now
Task run 'fetch_readings-e22' - Finished in state Completed()
Flow run 'pearl-goat' - Finished in state Completed()
```

</v-click>

</div>

<!--
-->

---
layout: center
---

# Which of these may succeed on a second try?

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1.5rem">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-hard-drives class="ic" /><b><code>dvc pull</code></b><br>503 Service Unavailable</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-lock-key class="ic" /><b><code>dvc pull</code></b><br>403 Forbidden</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-memory class="ic" /><b><code>train</code></b><br>runs out of memory</div>
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-gauge class="ic" /><b>MLflow</b><br>429 Too Many Requests</div>
</div>

<v-click at="2">

A retry helps only when the same call may succeed a little later.

</v-click>

<!--
503 and 429 say "not now": wait and ask again. 403 says "not you": the credentials will not fix themselves. Out of memory on the same machine with the same data happens again; a bigger machine is a different fix. A rejection from `validate` is the same kind: asking again gets the same answer.
-->

---

# Retrying a failed validation

<carbon-data-error class="icon-corner" />

<div class="middle">

`check_readings` with `retries=3, retry_delay_seconds=2`, on the reading −9999.0:

<div class="flow" style="gap:0.4rem">
  <div class="node rose no-shrink" style="width:8rem"><b>attempt 1</b><br><small>ValueError</small></div>
  <div class="arrow-l">2 s<span class="arrow">→</span></div>
  <div v-click="1" class="node rose no-shrink" style="width:8rem"><b>attempt 2</b><br><small>ValueError</small></div>
  <div v-click="1" class="arrow-l">2 s<span class="arrow">→</span></div>
  <div v-click="1" class="node rose no-shrink" style="width:8rem"><b>attempt 3</b><br><small>ValueError</small></div>
  <div v-click="1" class="arrow-l">2 s<span class="arrow">→</span></div>
  <div v-click="1" class="node rose no-shrink" style="width:8rem"><b>attempt 4</b><br><small>ValueError</small></div>
</div>

<v-click at="2">

The same error, four times. The flow failed **6 seconds** later than it needed to.

</v-click>

</div>

<!--
-->

---

# The 2021 AWS outage

<carbon-cloud class="icon-corner" />

<div class="middle">

Amazon Web Services (AWS) runs cloud services for other companies.

AWS's own services run on an internal network, customer applications run on the main network[^1][].

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber no-shrink" style="width:12rem"><ph-buildings class="ic" /><b>Internal network</b><br><small>monitoring, internal DNS, parts of EC2's control</small></div>
  <div class="arrow-l">connections<span class="arrow">↔</span></div>
  <div class="node no-shrink" style="width:10rem"><ph-network class="ic" /><b>Network devices</b><br><small>link the two networks</small></div>
  <div class="arrow-l">connections<span class="arrow">↔</span></div>
  <div class="node sky no-shrink" style="width:12rem"><ph-cloud class="ic" /><b>Main network</b><br><small>most AWS services, all customer applications</small></div>
</div>

</div>

[^1]: AWS, "Summary of the AWS Service Event in the Northern Virginia (US-EAST-1) Region", 10 Dec 2021. https://aws.amazon.com/message/12721/

<!--
EC2 is AWS's virtual-machine service; its control plane is the part that starts, stops and lists machines. The event was in US-East-1, AWS's region in Northern Virginia.
-->

---

# 2021: AWS clients that kept retrying

<carbon-cloud-offline class="icon-corner" />

<div class="middle">

7 December 2021, 07:30: an automated job added capacity to a service on the main network.

<div class="flow" style="margin-top:1.5rem">
  <div :class="$clicks >= 3 ? 'node rose no-shrink' : 'node amber no-shrink'" style="width:12rem"><ph-buildings class="ic" /><b>Internal network</b><br><small>{{ $clicks >= 3 ? 'clients retry' : ($clicks >= 1 ? 'many clients connect at once' : 'monitoring, internal DNS, parts of EC2\'s control') }}</small></div>
  <div :class="$clicks >= 1 ? 'arrow-l fail' : 'arrow-l'" style="line-height:0.9">
    <span style="line-height:1.2">{{ $clicks >= 3 ? 'even more connections' : ($clicks >= 1 ? 'a surge of connections' : 'connections') }}</span>
    <span class="arrow">→</span>
    <span v-click="1" class="arrow">→</span>
    <span v-click="1" class="arrow">→</span>
    <span v-click="3" class="arrow">→</span>
    <span v-click="3" class="arrow">→</span>
  </div>
  <div :class="$clicks >= 2 ? 'node rose no-shrink' : 'node no-shrink'" style="width:10rem"><ph-network class="ic" /><b>Network devices</b><br><small>{{ $clicks >= 2 ? 'overwhelmed: slow answers, errors' : 'link the two networks' }}</small></div>
  <div :class="$clicks >= 4 ? 'arrow-l fail' : 'arrow-l'">{{ $clicks >= 4 ? 'errors' : 'connections' }}<span class="arrow">↔</span></div>
  <div :class="$clicks >= 4 ? 'node rose no-shrink' : 'node sky no-shrink'" style="width:12rem"><ph-cloud class="ic" /><b>Main network</b><br><small>{{ $clicks >= 4 ? 'customers get errors from AWS services' : 'most AWS services, all customer applications' }}</small></div>
</div>

<div v-click="4" style="margin-top:1.5rem; text-align:center">
  <span style="font-size:2.4rem; font-weight:700; color:#dc2626">07:33 → 14:40</span><br>
  <span>customers could not launch new EC2 machines (US Pacific time)</span>
</div>

</div>

<!--
AWS: the delays caused "even more connection attempts and retries". The clients had "well tested request back-off behaviors", but "a latent issue prevented these clients from adequately backing off". The devices recovered at 14:22; API Gateway at 16:37. AWS switched the scaling job off and fixed the back-off.
-->

---
hide: true
---

# Option B · 2015: DynamoDB's servers keep asking

<carbon-data-base class="icon-corner" />

<div class="middle">

DynamoDB is AWS's database service. Its storage servers ask a metadata service which part of the data they hold. On 20 September 2015 the answers became too slow, and the servers timed out[^1][].

<div class="flow">
  <div class="node amber no-shrink" style="width:11rem"><ph-hard-drives class="ic" /><b>Storage servers</b><br><small>"which data is mine?"</small></div>
  <div :class="$clicks >= 1 ? 'arrow-l fail' : 'arrow-l'">ask again<span class="arrow">→</span></div>
  <div :class="$clicks >= 1 ? 'node rose no-shrink' : 'node no-shrink'" style="width:11rem"><ph-database class="ic" /><b>Metadata service</b><br><small v-click="1">kept under high load</small></div>
</div>

<v-click at="2">

"Unavailable servers continued to retry requests for membership data, maintaining high load on the metadata service."[^1][]

</v-click>

</div>

[^1]: AWS, "Summary of the Amazon DynamoDB Service Disruption and Related Impacts in the US-East Region", Sept 2015. https://aws.amazon.com/message/5467D2/

<!--
Option B for the retry case: use it instead of the AWS 2021 case (switch `hide` on the two AWS 2021 slides and on the two DynamoDB slides; the second one sits after "Exponential backoff"). The event started at 02:19 PDT; at 07:10 error rates were low enough for most customers, about five hours.
-->

---

# The problem with a fixed delay

<carbon-time class="icon-corner" />

<div class="middle">

`retries=3, retry_delay_seconds=2` on three clients that failed at the same moment:

<div class="flow" style="display:grid; grid-template-columns:5rem repeat(4,6.5rem); gap:0.5rem 1.6rem; align-items:center; justify-content:center; margin-top:1.2rem; padding:0">
  <span></span><small class="text-center opacity-70">0 s</small><small class="text-center opacity-70">2 s</small><small class="text-center opacity-70">4 s</small><small class="text-center opacity-70">6 s</small>
  <small>client 1</small>
  <div class="node rose text-center text-sm">attempt 1</div><div class="node rose text-center text-sm">attempt 2</div><div class="node rose text-center text-sm">attempt 3</div><div class="node rose text-center text-sm">attempt 4</div>
  <small v-click="1">client 2</small>
  <div v-click="1" class="node rose text-center text-sm">attempt 1</div><div v-click="1" class="node rose text-center text-sm">attempt 2</div><div v-click="1" class="node rose text-center text-sm">attempt 3</div><div v-click="1" class="node rose text-center text-sm">attempt 4</div>
  <small v-click="1">client 3</small>
  <div v-click="1" class="node rose text-center text-sm">attempt 1</div><div v-click="1" class="node rose text-center text-sm">attempt 2</div><div v-click="1" class="node rose text-center text-sm">attempt 3</div><div v-click="1" class="node rose text-center text-sm">attempt 4</div>
</div>

<v-click at="2">

> [!WARNING]
> The server gets every retry at the same moment, as often as the first try.

</v-click>

</div>

<!--
Before the next slide: which other retry strategies do they know? Answers you may hear: a growing delay (backoff), a random part in each delay (jitter), a retry budget per minute, a circuit breaker that stops calling a failing service, and the server's Retry-After header. Prefect offers the first two.
-->

---

# Exponential backoff

<carbon-time class="icon-corner" />

<div class="middle">

After each failed attempt, wait twice as long as before.

```python
from prefect.tasks import exponential_backoff

@task(retries=3,
      retry_delay_seconds=exponential_backoff(backoff_factor=1),
      retry_jitter_factor=0.2)
def fetch_readings(station: str) -> list[float]: ...
```

<div class="flow" style="margin-top:1.5rem; gap:0.4rem">
  <div class="node rose no-shrink" style="width:6rem"><small>attempt 1</small></div>
  <div class="arrow-l no-shrink" style="width:3rem; min-width:0">1 s<span style="display:flex; align-items:center; width:100%"><span style="flex:1; height:2px; background:#64748b"></span><span style="font-size:0.7rem">▶</span></span></div>
  <div class="node rose no-shrink" style="width:6rem"><small>attempt 2</small></div>
  <div class="arrow-l no-shrink" style="width:6rem; min-width:0">2 s<span style="display:flex; align-items:center; width:100%"><span style="flex:1; height:2px; background:#64748b"></span><span style="font-size:0.7rem">▶</span></span></div>
  <div class="node rose no-shrink" style="width:6rem"><small>attempt 3</small></div>
  <div class="arrow-l no-shrink" style="width:12rem; min-width:0">4 s<span style="display:flex; align-items:center; width:100%"><span style="flex:1; height:2px; background:#64748b"></span><span style="font-size:0.7rem">▶</span></span></div>
  <div class="node no-shrink" style="width:6rem"><small>attempt 4</small></div>
</div>

<v-clicks>

- **Backoff:** a restarting service has more time to come back.
- **Jitter:** each delay gets a random part, so tasks that failed together do not retry together[^1][].

</v-clicks>

</div>

[^1]: Prefect docs, "Configure task retries". https://docs.prefect.io/v3/how-to-guides/workflows/retries

<!--
`exponential_backoff(backoff_factor=1)` gives the delays [1, 2, 4] (Prefect 3.8.2); with `retry_jitter_factor=0.2` each delay is random, at most 20% longer, and about the same on average. The lab picks its own values in Exercise 3.
-->

---
hide: true
---

# Option B · What did AWS change?

<carbon-renew class="icon-corner" />

<div class="middle">

What AWS's summary says[^1][]:

<div class="cards" style="grid-template-columns:repeat(3,1fr); ">
  <div v-click class="card"><ph-arrow-fat-lines-up class="ic" /><b>More capacity</b>for the metadata service</div>
  <div v-click class="card"><ph-timer class="ic" /><b>Ask less often</b>storage servers request membership data more slowly</div>
  <div v-click class="card"><ph-squares-four class="ic" /><b>Split it</b>many metadata services, each for part of the fleet</div>
</div>

</div>

[^1]: AWS, DynamoDB service disruption summary, Sept 2015.

<!--
Option B, second slide. Asking less often is a back-off on the client side; splitting the service limits how many clients can retry against one instance at the same time.
-->

---

# Not every task is safe to retry

<carbon-repeat class="icon-corner" />

<div class="middle">

<div class="flow" style="display:grid; grid-template-columns:12rem 13rem 12rem; gap:0.6rem 0.5rem; align-items:center; justify-content:center; margin-top:1rem">
  <div class="node amber text-center"><ph-receipt class="ic" /><b>charge_customer</b></div>
  <div></div>
  <div class="node sky text-center"><ph-credit-card class="ic" /><b>Payment service</b></div>
  <small class="text-center">attempt 1</small>
  <div class="text-center text-sm" style="color:#4338ca; font-weight:700">charge €49 →</div>
  <small class="text-center">charged: €49</small>
  <small v-click="1" class="text-center">no answer: charged or not?</small>
  <div v-click="1" class="text-center text-sm text-red-600" style="font-weight:700">← response lost</div>
  <small v-click="1"></small>
  <small v-click="2" class="text-center">attempt 2</small>
  <div v-click="2" class="text-center text-sm" style="color:#4338ca; font-weight:700">charge €49 again →</div>
  <small v-click="2" class="text-center text-red-600"><b>charged again: €98 in total</b></small>
</div>

<v-click at="3">

**Idempotent:** running it twice has the same effect as running it once. `charge_customer` is not.

</v-click>

<v-click at="4">

> [!TIP]
> Before you add retries to a task, check that running it twice is safe.

</v-click>

</div>

<!--
From the client, "charged, but the answer was lost" looks the same as "never arrived". Other operations with this shape: creating a record, appending a row, sending an e-mail.
The fix is an idempotency key: the client sends the same key with each attempt, and the server ignores a key it has already seen. Stripe's payment API offers one (Stripe API docs, "Idempotent requests"); not every service does.
-->

---
hide: true
---

# Which of our tasks get a retry?

<carbon-flow-connection class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.35rem; font-size:0.85rem">
  <div class="node no-shrink" style="width:6.2rem"><b>pull_data</b><br><small v-click="1">3 retries<br>network</small></div>
  <div class="node no-shrink" style="width:6.2rem"><b>params_committed</b><br><small v-click="2">none<br>local Git</small></div>
  <div class="node no-shrink" style="width:6.2rem"><b>build_dataset</b><br><small v-click="2">none<br>local files</small></div>
  <div class="node no-shrink" style="width:6.2rem"><b>run_pipeline</b><br><small v-click="2">none<br>deterministic</small></div>
  <div class="node no-shrink" style="width:6.2rem"><b>push_data</b><br><small v-click="1">3 retries<br>network</small></div>
  <div class="node no-shrink" style="width:6.6rem"><b>register_model</b><br><small v-click="3">2 retries<br>not idempotent</small></div>
  <div class="node no-shrink" style="width:5.5rem"><b>notify</b><br><small v-click="2">none<br>local file</small></div>
</div>

<v-click at="4">

> [!TIP]
> Put retries only on calls over the network, and check first that a repeat is safe.

</v-click>

</div>

<!--
Hidden: it is the answer to lab Exercise 3. Show it after the lab deadline, or when the solution is released.
`pull_data` and `push_data` are safe to repeat because DVC moves content by hash (Week 4): the same hash gives the same data. `register_model` is not idempotent: a lost response and a retry register the same model twice, so it needs a check for an existing version first.
-->

---
layout: section
---

# 5 · Parameters

<!--
-->

---

# Flow and Pipeline

<carbon-chart-relationship class="icon-corner" />

<div class="middle">

<div style="border:2px dashed #0284c7; border-radius:0.75rem; padding:0.5rem 1rem 0.2rem; width:38rem; margin:0 auto">
<div class="text-sm" style="color:#0284c7"><b>The flow</b><span v-click="1" style="color:#d97706"> · flow parameters?</span></div>
<div class="flow" style="gap:0.5rem; margin:0.5rem 0">
  <div class="node amber no-shrink" style="width:9rem"><ph-cloud-arrow-down class="ic" /><b>pull data</b></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:9rem"><ph-graph class="ic" /><b>dvc repro</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-tag class="ic" /><b>register</b></div>
</div>
</div>

<div>
  <div class="split-stem"></div>
  <div class="split-bar" style="width:36rem"></div>
  <div class="flow" style="margin-top:0; gap:0.4rem; font-size:0.85rem">
    <div class="node violet" style="width:6rem">validate</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">prepare</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">train</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">evaluate</div><div class="arrow">→</div>
    <div class="node violet" style="width:6rem">gate</div>
  </div>
  <div v-click="1" class="text-sm text-center" style="color:#d97706; margin-top:0.3rem"><b>pipeline parameters?</b></div>
</div>

</div>

<!--
-->

---

# Where are the pipeline parameters?

<carbon-settings-adjust class="icon-corner" />

<div class="middle">

<v-click>

<div class="code-lg">

```yaml
# params.yaml
train:
  family: logreg
  C: 1.0
  impute_strategy: median
```

</div>

</v-click>

<div class="flow" style="gap:0.4rem; margin-top:1.2rem">
  <div v-click="2" class="node no-shrink" style="width:8.5rem; padding:0.5rem"><small>pipeline</small><div class="mini"><span class=""></span><span class=""></span><span class=""></span></div></div>
  <div v-click="2" class="arrow-l" style="min-width:6rem"><code>dvc repro</code> finds the change<span class="arrow">→</span></div>
  <div v-click="2" class="node no-shrink" style="width:8.5rem; padding:0.5rem"><small>changed</small><div class="mini"><span class=""></span><span class="changed"></span><span class=""></span></div></div>
  <div v-click="3" class="arrow-l" style="min-width:6rem">the stages after it too<span class="arrow">→</span></div>
  <div v-click="3" class="node no-shrink" style="width:8.5rem; padding:0.5rem"><small>must re-run</small><div class="mini"><span class=""></span><span class="rerun"></span><span class="rerun"></span></div></div>
  <div v-click="4" class="arrow-l" style="min-width:6rem">runs only these<span class="arrow">→</span></div>
  <div v-click="4" class="node no-shrink" style="width:8.5rem; padding:0.5rem"><small>running</small><div class="mini"><span class="cached"></span><span class="rerun"><ph-arrows-clockwise /></span><span class="rerun"><ph-arrows-clockwise /></span></div></div>
</div>

</div>

<!--
-->

---

# Flow parameters

<carbon-settings-adjust class="icon-corner" />

<div class="middle">

The flow can pass its parameters to its steps: with `training_flow(C=0.01)`, anyone could start a run with another `C` from the UI.

<v-click at="1">

**Should a flow parameter change the pipeline?**

</v-click>

<br>

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:0.6rem">
  <div v-click="2" class="card"><ph-eye-slash class="ic" /><b>DVC does not see it</b>The stages read <code>params.yaml</code>, so the flow must write the value into the file first.</div>
  <div v-click="3" class="card"><ph-git-commit class="ic" /><b>No commit</b>The model comes from a <code>params.yaml</code> that is not in Git, and nobody reviewed the change.</div>
  <div v-click="4" class="card"><ph-copy class="ic" /><b>Two runs, one file</b>Two runs at the same time overwrite each other's value.</div>
</div>

<v-click at="5">

</v-click>

</div>

<!--
-->

---

# Parameter Separation

<carbon-commit class="icon-corner" />

<div class="middle">

<div class="label-col">

| | `params.yaml`, in a commit | Flow parameters |
| --- | --- | --- |
| Controls | how the model is built: `train.C`, `impute_strategy`, the gate's thresholds | what this run does: `push`, `register_model_version`, `station` |
| Changed by | <span v-click="1">a commit, reviewed in a pull request</span> | <span v-click="1">a person in the UI, or a schedule, when the run starts</span> |
| Recorded in | <span v-click="2">Git and `dvc.lock`</span> | <span v-click="2">the flow run's record</span> |

</div>

<br>

<v-click at="3">

> [!TIP]
> Change hyperparameters only with a commit to `params.yaml`.

</v-click>

</div>

<!--
To try many values without a commit each, DVC has `dvc exp run -S train.C=0.01`: it runs an experiment with that value and records it. It brings DVC's experiments system.
-->

---
layout: section
---

# 6 · Scheduling

<!--
-->

---

# Scheduling a flow

<carbon-calendar class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem; margin-top:1rem">
  <div class="node violet no-shrink" style="width:12rem"><ph-flow-arrow class="ic" /><b>Deployment</b><br><small>the flow, its parameters<br>and a schedule:<br><span class="mono" style="white-space:nowrap">0 6 * * 1</span></small></div>
  <div v-click="1" class="arrow-l no-shrink">plans the next runs<span class="arrow">→</span></div>
  <div v-click="1" class="node green no-shrink" style="width:13rem"><ph-hard-drives class="ic" /><b>Prefect server</b><br><small>Scheduled runs:<br>Mon 2 Nov, 06:00<br>Mon 9 Nov, 06:00<br>Mon 16 Nov, 06:00</small></div>
  <div v-click="2" class="arrow-l no-shrink">at 06:00<span class="arrow">→</span></div>
  <div v-click="2" class="node amber no-shrink" style="width:9rem"><ph-question class="ic" /><b>Who starts the run?</b></div>
</div>

</div>

<!--
A deployment is a flow registered on the server, so that a schedule, the UI or the API can start it. `0 6 * * 1` is cron for Monday 06:00. The server keeps 3 to 100 runs planned, up to 100 days ahead. Give a cron schedule a time zone, so a daily run moves with daylight saving time.
-->

---

# Running the schedule with `.serve()`

<carbon-laptop class="icon-corner" />

<div class="middle">

<div class="flow" style="display:grid; grid-template-columns:18rem 11rem 16rem; grid-template-rows:1.8rem auto 2.6rem auto 0.6rem; align-items:center; justify-items:center; justify-content:center; gap:0; margin-top:0.5rem">
  <div style="grid-column:1; grid-row:1 / 6; align-self:stretch; justify-self:stretch; border:2px dashed #d97706; border-radius:0.75rem"></div>
  <div class="text-sm" style="grid-column:1; grid-row:1; color:#d97706"><b>Your machine</b></div>
  <div class="node amber" style="grid-column:1; grid-row:2; width:15rem"><ph-terminal-window class="ic" /><b><code>.serve()</code> process</b><br><small>runs until you stop it</small></div>
  <div v-click="2" class="arrow-l" style="grid-column:1; grid-row:3">starts a subprocess<span class="arrow">↓</span></div>
  <div v-click="2" class="node violet" style="grid-column:1; grid-row:4; width:15rem"><ph-flow-arrow class="ic" /><b>flow run</b><br><small>pull data → dvc repro → register</small></div>
  <div v-click="1" class="arrow-l" style="grid-column:2; grid-row:2">asks for due runs<span class="arrow">⇄</span></div>
  <div v-click="3" class="arrow-l" style="grid-column:2; grid-row:4">data, model, states<span class="arrow">→</span></div>
  <div style="grid-column:3; grid-row:1 / 6; align-self:stretch; justify-self:stretch; border:2px dashed #16a34a; border-radius:0.75rem"></div>
  <div class="text-sm" style="grid-column:3; grid-row:1; color:#16a34a"><b>Our Compose stack</b></div>
  <div class="node green" style="grid-column:3; grid-row:2; width:13rem"><ph-hard-drives class="ic" /><b>Prefect server</b><br><small>deployment, schedule, records</small></div>
  <div class="node sky" style="grid-column:3; grid-row:4; width:13rem"><ph-database class="ic" /><b>MLflow, Silo</b><br><small>and Postgres under both</small></div>
</div>

<v-click at="4">

> [!WARNING]
> Stop the `.serve()` process, and Prefect pauses the schedule: no run starts, and no run fails.

</v-click>

</div>

<!--
`.serve()` asks the server for due runs every 10 s and runs each one in a subprocess. Stopping it also deletes the planned runs.
-->

---

# Running the schedule with a work pool

<carbon-server-proxy class="icon-corner" />

<div class="flow" style="display:grid; grid-template-columns:14rem 7.5rem 11rem 6.5rem 10rem; grid-template-rows:1.6rem auto 2.6rem auto 0.4rem; align-items:center; justify-items:center; justify-content:center; gap:0; margin-top:0.5rem">
  <div style="grid-column:1; grid-row:1 / 6; align-self:stretch; justify-self:stretch; border:2px dashed #16a34a; border-radius:0.75rem"></div>
  <div class="text-sm" style="grid-column:1; grid-row:1; color:#16a34a"><b>Prefect server</b></div>
  <div class="node violet" style="grid-column:1; grid-row:2; width:12rem"><ph-flow-arrow class="ic" /><b>Deployment</b><br><small>flow, parameters, schedule</small></div>
  <div v-click="1" class="arrow-l" style="grid-column:1; grid-row:3">due runs<span class="arrow">↓</span></div>
  <div v-click="1" class="node green" style="grid-column:1; grid-row:4; width:12rem"><ph-queue class="ic" /><b>Work pool</b><br><small>a queue of runs, and where to run them</small></div>
  <div v-click="2" class="arrow-l" style="grid-column:2; grid-row:4">asks for due runs<span class="arrow">⇄</span></div>
  <div v-click="2" style="grid-column:3 / 6; grid-row:1 / 6; align-self:stretch; justify-self:stretch; border:2px dashed #0284c7; border-radius:0.75rem"></div>
  <div v-click="2" class="text-sm" style="grid-column:3 / 6; grid-row:1; color:#0284c7"><b>Your infrastructure</b></div>
  <div v-click="2" class="node amber" style="grid-column:3; grid-row:4; width:10rem"><ph-terminal-window class="ic" /><b>Worker</b><br><small>a long-running process</small></div>
  <div v-click="3" class="arrow-l" style="grid-column:4; grid-row:2; min-width:5rem">starts<span class="arrow">↗</span></div>
  <div v-click="3" class="arrow-l" style="grid-column:4; grid-row:4; min-width:5rem">starts<span class="arrow">→</span></div>
  <div v-click="3" class="node sky" style="grid-column:5; grid-row:2; width:9rem"><ph-cube class="ic" /><b>flow run</b><br><small>new container</small></div>
  <div v-click="3" class="node sky" style="grid-column:5; grid-row:4; width:9rem"><ph-cube class="ic" /><b>flow run</b><br><small>new container</small></div>
</div>

<div class="src">Prefect docs, "Work pools" and "Workers" (checked 26 Oct 2026): https://docs.prefect.io/v3/concepts/work-pools · https://docs.prefect.io/v3/concepts/workers</div>

<!--
The work pool lives on the server and holds each run's settings: image, CPU, memory. The worker runs where the runs should run. A worker only polls pools of its own type: a Docker worker starts containers, a Kubernetes worker starts jobs. Push pools need no worker: the run goes straight to a cloud service.
-->

---

# Every run in a new container

<carbon-container-software class="icon-corner" />

<div class="middle">

With a work pool, each run starts in a new container and the container is removed at the end.

<div class="flow" style="margin-top:1.5rem">
  <div class="node sky no-shrink" style="width:14rem"><ph-cube class="ic" /><b>Run 1</b><br><small>writes <span class="mono">data/</span>, <span class="mono">models/model.pkl</span>, <span class="mono">dvc.lock</span></small></div>
  <div class="arrow-l">container removed<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:14rem"><ph-cube class="ic" /><b>Run 2</b><br><small>starts from the image</small></div>
</div>

<div class="text-center" style="margin-top:1.5rem">

**What does run 2 find from run 1?**

<v-click>

Only what run 1 pushed to storage outside the container.

</v-click>

</div>

</div>

<!--
With `.serve()` on one machine, files stay between runs, so a flow that depends on them works in the lab and breaks later on a work pool. The same holds for a retry from the UI: Prefect's docs warn that a new container "cannot access results saved to the local filesystem of the original container" (Prefect docs, "Results").
-->

---

# `.serve()` or a work pool?

<carbon-compare class="icon-corner" />

<div class="middle">

<div class="label-col">

| | `.serve()` | Work pool and worker |
| --- | --- | --- |
| Runs on | <span v-click="1">a subprocess on the serving machine</span> | <span v-click="1">new infrastructure for each run:<br>a container, a Kubernetes job</span> |
| Keep running | <span v-click="2">one process per flow script</span> | <span v-click="2">one worker per pool</span> |
| Code and libraries | <span v-click="3">already installed on that machine</span> | <span v-click="3">in the image each run starts from</span> |
| Fits | <span v-click="4">one machine, a few flows: our lab</span> | <span v-click="4">many flows and teams,<br>runs that must not share a machine</span> |

</div>

</div>

<!--
The platform team usually owns the server, the pools and the workers; the ML engineer owns the flow and its deployment.
-->

---

# One ML system, several pipelines

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.4rem; margin-top:0.5rem">
  <div class="node violet no-shrink" style="width:9rem"><ph-table class="ic" /><b>Feature pipeline</b><br><small>raw data → features<br>daily</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:7rem"><ph-database class="ic" /><b>Feature store</b></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet no-shrink" style="width:9rem"><ph-brain class="ic" /><b>Training pipeline</b><br><small>features → model<br>weekly</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node no-shrink" style="width:7rem"><ph-package class="ic" /><b>Model registry</b></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node violet no-shrink" style="width:9rem"><ph-robot class="ic" /><b>Batch inference</b><br><small>features + model → predictions<br>nightly</small></div>
</div>

<v-click at="3">

<div class="text-center" style="margin-top:1.5rem">

Each pipeline has its own schedule and owner. They meet in storage, not in function calls.[^1][]

</div>

</v-click>

</div>

[^1]: Jim Dowling, "From MLOps to ML Systems with Feature/Training/Inference Pipelines", Hopsworks, 13 Sep 2023. https://www.hopsworks.ai/post/mlops-to-ml-systems-with-fti-pipelines (checked 26 Oct 2026)

<!--
Dowling: "Each FTI pipeline can be operated independently." Google's MLOps level 2 has the same split. Our lab has only the training pipeline: the features are computed inside the model's own `Pipeline` (imputer, scaler), so training and prediction cannot compute them differently. Week 9 adds the inference side: batch and online.
-->

---

# Is an orchestrator worth it?

<carbon-scales class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><ph-coins class="ic" /><b>The cost</b>a server and its database to run and upgrade; a temporary server adds about 8 s to every bare flow run</div>
  <div v-click class="card"><ph-check-circle class="ic" style="color:#16a34a" /><b>Worth it</b>many steps, calls over the network, a schedule, several people who read the runs</div>
  <div v-click class="card"><ph-x-circle class="ic" style="color:#dc2626" /><b>Too much</b>one script on one schedule: a cron and a check on the last success do the job</div>
</div>

<v-click>

> [!TIP]
> Start with a cron and a check on the last successful run. Add an orchestrator when you need retries, parameters or a history of many steps.

</v-click>

</div>

<!--
Many teams already run Airflow or Prefect for other pipelines; then the cost of one more flow is small.
-->

---
layout: section
---

# 7 · Red flags and good practices

<!--
-->

---
hide: true
---

# Traps you will meet in the lab

<carbon-debug class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **Trap** | **What you see** | **What is wrong** |
| --- | --- | --- |
| `PREFECT_API_URL` without `/api` | every API call returns 404 | add the `/api` suffix |
| `PREFECT_API_DATABASE_CONNECTION_URL` | no effect | renamed: `PREFECT_SERVER_DATABASE_CONNECTION_URL` |
| a Postgres volume from an earlier week | the Prefect container restarts in a loop | `prefectdb` is created only on the volume's first start: `make down-v && make up` |
| a flow parameter named `register` | a warning on every run | it shadows a pydantic attribute; pick another name |
| a flow called in a test without the harness | the test takes about 8 s | use the `prefect_harness` fixture or `task.fn(...)` |
| `dvc` called from a task | `dvc pull failed`, no detail | the subprocess needs the Silo credentials as `AWS_*` |
| a flow parameter type imported under `TYPE_CHECKING` | `PydanticUserError`: the model "is not fully defined" | Prefect builds a pydantic model from the signature: import the type at module level, or use plain types |
| `get_run_logger()` in a task called as `task.fn(...)` | `MissingContextError` | there is no run; the lab's `_log()` falls back to a normal logger |

</div>

</div>

<!--
Hidden: lab-specific. Show it at the start of the lab session instead. All eight were found while building the lab.
-->

---

# Count the retries

<carbon-renew class="icon-corner" />

<div class="middle">

A colleague adds `retries=5` to every task. Next month, fewer runs fail. **What did the team stop seeing?**

<div class="flow" style="margin-top:2rem">
  <div v-click="1" class="node rose no-shrink" style="width:13rem"><ph-eye-slash class="ic" /><b>A failing service</b><br><small>it needs more attempts each week</small></div>
  <div v-click="2" class="node rose no-shrink" style="width:13rem"><ph-bug class="ic" /><b>A bug</b><br><small>reported six attempts later</small></div>
  <div v-click="3" class="node rose no-shrink" style="width:13rem"><ph-copy class="ic" /><b>A duplicate</b><br><small>a create call that ran twice</small></div>
</div>

<v-click at="4">

> [!TIP]
> Read the attempt count of each task in the run record, and open a ticket when a service needs retries on most runs.

</v-click>

</div>

<!--
The number of failed runs went down; the number of problems did not. The record keeps every attempt, so the signal is there for anyone who reads it. Prefect's `retry_condition_fn` can retry only on chosen exceptions, such as a connection error.
-->

---

# Give every task a time limit

<carbon-timer class="icon-corner" />

<div class="middle">

A call that hangs never fails.

```python {1}
@task(timeout_seconds=5)
def fetch_readings(station: str) -> list[float]:
    ...  # the server accepts the connection and never answers
```

<v-click>

```text
Task run 'fetch_readings-920' - Task run exceeded timeout of 5.0 second(s)
Task run 'fetch_readings-920' - Finished in state TimedOut('Task run exceeded timeout of
    5.0 second(s)', type=FAILED)
Flow run 'rebel-sponge' - Finished in state TimedOut(..., type=FAILED)
```

</v-click>
<br>
<v-click>

> [!TIP]
> Set a timeout on every task that waits for an outside service.

</v-click>

</div>

<!--
Pick the limit from the run history: a few times the usual duration.
-->

---
hide: true
---

# Let one tool own each graph

<carbon-chart-relationship class="icon-corner" />

<div class="middle">

The tempting design: one Prefect task per DVC stage, each running `dvc repro -s <stage>`.

<div class="flow" style="gap:0.4rem">
  <div class="node violet" style="width:7rem">validate</div><div class="arrow">→</div>
  <div class="node violet" style="width:7rem">prepare</div><div class="arrow">→</div>
  <div class="node violet" style="width:7rem">train</div><div class="arrow">→</div>
  <div class="node violet" style="width:7rem">evaluate</div>
</div>

Two tools now decide the order of one graph, and the one that cannot see the hashes decides.

<br>

> [!TIP]
> Call the build system once, and split only when steps need different machines.

</div>

<!--
Hidden: it answers lab Exercise 2's second question. Show it after the lab deadline, or when the solution is released.
If one stage needs a GPU and another a large-memory machine, splitting is right: then the orchestrator knows something DVC cannot see.
-->

---
layout: section
---

# 8 · Wrap-up

<!--
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<div class="middle">

<v-clicks>

- For every automated job, record each run and alert its owner if it fails.
- The build system decides what is stale; the orchestrator decides what runs, when, and how often.
- Retry only failures that may go away, on operations that are safe to repeat.
- Change hyperparameters with a commit; keep flow parameters for what a run does.

</v-clicks>

</div>

<!--
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><carbon-api class="ic" /><b>Can anyone else use the model?</b>It is a file in the registry.<br><b>→ Week 9:</b> serving, containers</div>
  <div v-click class="card"><carbon-deploy class="ic" /><b>How does a GO model reach users safely?</b>The scheduled flow does not release anything.<br><b>→ Week 10:</b> rollout strategies</div>
  <div v-click class="card"><carbon-notification-new class="ic" /><b>Who notices a run that never happened?</b>A record has no row for it.<br><b>→ Week 11:</b> alerts</div>
  <div v-click class="card"><carbon-chart-line class="ic" /><b>When should the model retrain?</b>A schedule knows nothing about the data.<br><b>→ Week 12:</b> drift monitoring</div>
</div>

</div>

<!--
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

<div class="middle">

- Why does a project with `dvc repro` need an orchestrator, and what does each one decide?
- What does a flow run record that a function call does not?
- What is the difference between Failed, Crashed and Late?
- When does a retry help, and when does it hide bad data or create a duplicate?
- Which values belong in `params.yaml`, and which in a flow parameter?
- Who starts a scheduled run with `.serve()`, and who with a work pool?
- What does a run on a work pool find from the previous run?
- Why does an ML system have several pipelines, and what connects them?
- What does an orchestrator cost, and when is a cron with a check enough?

</div>

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->

---
layout: section
hide: true
---

# Backup · Orchestration beyond one flow

<!--
Draft slides for ideas that other courses teach and this deck leaves out (MLOps Zoomcamp, Made With ML, Google's MLOps levels, Airflow's best practices). Each block stands alone: move it into a section, or leave it here for questions.
-->

---
hide: true
---

# Re-running Monday's run

<carbon-recently-viewed class="icon-corner" />

<div class="middle">

A daily job runs at 06:00 and builds features from yesterday's data: `date.today() - 1`.

<div class="flow" style="margin-top:1.5rem">
  <div class="node rose no-shrink" style="width:12rem"><ph-calendar-x class="ic" /><b>Mon 06:00</b><br><small>should process Sunday<br>Failed: a service was down</small></div>
  <div class="arrow-l">fixed on Wednesday<span class="arrow">→</span></div>
  <div class="node amber no-shrink" style="width:12rem"><ph-play class="ic" /><b>Wed 10:00</b><br><small>someone re-runs Monday's run</small></div>
  <div v-click="1" class="arrow-l">reads<span class="arrow">→</span></div>
  <div v-click="1" class="node rose no-shrink" style="width:12rem"><ph-files class="ic" /><b>Tuesday's data</b><br><small>today − 1</small></div>
</div>

<div class="text-center" style="margin-top:1.5rem">

**Which day does the re-run process?**

<v-click at="2">

Sunday is never processed, and Tuesday is processed twice.

</v-click>

</div>

</div>

<!--
The same happens when a model is retrained "on the latest data": a re-run months later trains on different data, so it cannot rebuild the model an incident is about. Airflow's best practices say a task "should never" call `now()` and should read a fixed data interval instead (Airflow docs, "Best Practices").
-->

---
hide: true
---

# A run reads a fixed window of data

<carbon-calendar-heat-map class="icon-corner" />

<div class="middle">

<div class="label-col">

| | Depends on when it starts | Same result on every re-run[^1][] |
| --- | --- | --- |
| Daily features | `date.today() - 1` | <span v-click="1">the day as a run parameter, set by the schedule</span> |
| Weekly retrain | the data in the bucket now | <span v-click="2">a data version: a commit with its `dvc.lock` (Week 4)</span> |
| A missed week | re-run and hope | <span v-click="3">a backfill: one run for each missing window</span> |

</div>

<v-click at="4">

> [!TIP]
> Pass the data window or the data version to the run as a parameter, so a re-run of last Monday's run gives last Monday's result.

</v-click>

</div>

[^1]: Apache Airflow docs, "Best Practices": tasks "should produce the same outcome on every re-run". https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html (checked 26 Oct 2026)

<!--
This is idempotency of a whole run, not of one call (Section 4). A Prefect run can read its planned time from `prefect.runtime.flow_run.scheduled_start_time`. Prefect 3.8.2 has no backfill command: create one run per window with `prefect deployment run --param day=...`. Airflow and Kestra have backfills built in.
-->

---
hide: true
---

# Store large data, pass its name

<carbon-data-share class="icon-corner" />

<div class="middle">

<div class="label-col">

| What | Where it lives[^1][] | What tasks pass to each other |
| --- | --- | --- |
| Small values | <span v-click="1">the task's return value</span> | <span v-click="1">a verdict, a run ID, a metric</span> |
| Data and models | <span v-click="2">object storage: Silo with `dvc push`, MLflow</span> | <span v-click="2">a path, a hash, a model version</span> |
| Code and libraries | <span v-click="3">the image the run starts from</span> | <span v-click="3">nothing</span> |

</div>

<v-click at="4">

> [!TIP]
> Push what a later run needs before the run ends. Pass names and hashes, not local files.

</v-click>

</div>

[^1]: Apache Airflow docs, "Best Practices": "you should not store any file or config in the local filesystem". https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html (checked 26 Oct 2026)

<!--
Prefect results go to `~/.prefect/storage/` unless `result_storage` names remote storage (Prefect docs, "Results"). In the lab, `training_flow` has `push=False` by default: fine with `.serve()`, but in a container the new DVC outputs would be lost. The same rule applies when one step needs a GPU: it becomes its own deployment, and its inputs and outputs go through storage.
-->

---
hide: true
---

# When should training run?

<carbon-event class="icon-corner" />

<div class="middle">

Google's list of triggers for retraining[^1][]:

<div class="cards" style="grid-template-columns:repeat(5,1fr); margin-top:1rem">
  <div v-click class="card"><ph-hand-pointing class="ic" /><b>On demand</b>a person starts it</div>
  <div v-click class="card"><ph-clock class="ic" /><b>On a schedule</b>new labelled data comes every week<br><b>→ this week</b></div>
  <div v-click class="card"><ph-files class="ic" /><b>On new data</b>data comes at no fixed time</div>
  <div v-click class="card"><ph-chart-line-down class="ic" /><b>On worse performance</b>the model's metrics drop<br><b>→ Week 12</b></div>
  <div v-click class="card"><ph-arrows-split class="ic" /><b>On data drift</b>the inputs change<br><b>→ Week 12</b></div>
</div>

</div>

[^1]: Google Cloud, "MLOps: Continuous delivery and automation pipelines in machine learning", last updated 28 Aug 2024. https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning (checked 26 Oct 2026)

<!--
The list is Google's, for retraining. A schedule is the simplest and the only one that needs no other system; the others need something that notices: a file arriving, a metric, a drift test. In Prefect, a deployment can start on an event instead of a schedule: `.serve(triggers=[DeploymentEventTrigger(...)])` (Prefect docs, "How to create deployment triggers").
-->

---
hide: true
---

# When runs overlap

<carbon-time class="icon-corner" />

<div class="middle">

A daily job usually takes 2 hours. Today it takes 26. **What should happen to tomorrow's run?**[^1][]

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1rem">
  <div v-click class="card"><ph-play class="ic" /><b>Start it in parallel</b>both write the same outputs</div>
  <div v-click class="card"><ph-hourglass class="ic" /><b>Let it wait</b>it starts late, and the delay grows</div>
  <div v-click class="card"><ph-skip-forward class="ic" /><b>Cancel it</b>its data waits for a backfill</div>
</div>

<v-click>

> [!TIP]
> Set a concurrency limit of 1 on every deployment that writes shared outputs, and decide whether the next run waits or is cancelled.

</v-click>

</div>

[^1]: Alex Strick van Linschoten, "The Hidden Complexity of ML Pipeline Schedules", ZenML blog, 23 Jan 2026. https://www.zenml.io/blog/the-hidden-complexity-of-ml-pipeline-schedules (checked 26 Oct 2026)

<!--
Pinterest's Pinball scheduler stored an overrun policy with every schedule: abort the running run, run in parallel, or delay. Prefect: a deployment's `concurrency_limit=1` with `collision_strategy` `ENQUEUE` (wait) or `CANCEL_NEW` (Prefect docs, "Deployments", "Concurrency limiting"). For our weekly retrain, two runs would write the same `dvc.lock` and model files, so it should wait.
-->

---
hide: true
---

# Training failed. Do the predictions stop?

<carbon-parent-child class="icon-corner" />

<div class="middle">

Monday's training run fails. The nightly batch inference runs on Tuesday.

<div class="flow" style="margin-top:1.5rem">
  <div class="node rose no-shrink" style="width:11rem"><ph-brain class="ic" /><b>Training</b><br><small>Mon: Failed, no new version</small></div>
  <div class="arrow-l">registry<span class="arrow">→</span></div>
  <div class="node no-shrink" style="width:11rem"><ph-package class="ic" /><b>Model registry</b><br><small>last week's version stays current</small></div>
  <div v-click="1" class="arrow-l">loads it<span class="arrow">→</span></div>
  <div v-click="1" class="node green no-shrink" style="width:11rem"><ph-robot class="ic" /><b>Batch inference</b><br><small>Tue: Completed with last week's model</small></div>
</div>

<v-click at="2">

> [!TIP]
> Connect pipelines through versioned storage, such as a registry or a table, so one can fail without stopping the others.

</v-click>

</div>

<!--
If inference called the training flow directly, a failed training would also stop the predictions. The registry alias (Week 3) is the contract between the two pipelines. The cost: the predictions may come from an old model, so someone must notice the failed training (Week 11's alerts).
-->

---
hide: true
---

# Graphs that are not a line

<carbon-tree-view-alt class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-arrow-right class="ic" /><b>A line</b>pull data → train → register<br><small>our flow</small></div>
  <div v-click class="card"><ph-git-fork class="ic" /><b>Fan-out, fan-in</b>train each model family in parallel, then keep the best</div>
  <div v-click class="card"><ph-warning class="ic" /><b>A failure branch</b>a step that runs only when another fails: clean up, alert</div>
</div>

<br>

<v-click>

**We want `logreg` and `rf` trained on every run. Should Prefect or `dvc.yaml` run the two branches?**

</v-click>

<v-click>

> [!TIP]
> Put the fan-out in the build system when the branches run on one machine; DVC then skips the branches whose inputs did not change. Put it in the orchestrator when branches need different machines.

</v-click>

</div>

<!--
Prefect runs a fan-out with `task.map(...)` or `task.submit(...)`; a failure branch is an `on_failure` hook or an `except` (Section 3). DVC has `foreach` and `matrix` stages for a fan-out inside `dvc.yaml`. Made With ML teaches these shapes with Airflow, where a "trigger rule" decides when a step runs (all parents succeeded, one failed, and so on).
-->

---
hide: true
---

# Run tasks, or keep assets up to date?

<carbon-data-structured class="icon-corner" />

<div class="middle">

<div class="label-col">

| | Task-centred | Asset-centred[^1][] |
| --- | --- | --- |
| You declare | <span v-click="1">steps and their order</span> | <span v-click="1">data and models, and what each is built from</span> |
| It records | <span v-click="2">which task ran, and its state</span> | <span v-click="2">which inputs each asset was built from</span> |
| Examples | <span v-click="3">Airflow, Prefect flows</span> | <span v-click="3">Dagster, `dvc repro`, Prefect `@materialize`</span> |

</div>

<v-click at="4">

Our design uses both: Prefect runs the tasks and keeps the run history; DVC keeps the data and the model up to date.

</v-click>

</div>

[^1]: Dagster docs, "Concepts": an asset is "a logical unit of data such as a table, dataset, or machine learning model". https://dagster.io/docs/getting-started/concepts (checked 26 Oct 2026)

<!--
An asset-centred tool can answer "which data built this model?" from its own records; a task-centred one answers "did Monday's run succeed?". In ML, both questions come up in an incident. In our lab, the first is answered by `dvc.lock` and the MLflow tags (Week 4), the second by Prefect. Prefect 3 also has assets: "any outcome or output of your Prefect workflows" (Prefect docs, "Assets").
-->

---
hide: true
---

# Test the flow the way the scheduler runs it

<carbon-test-tool class="icon-corner" />

<div class="middle">

Three levels, as in Airflow's testing advice[^1][]:

<div class="flow" style="gap:0.5rem; margin-top:1rem">
  <div v-click="1" class="node green no-shrink" style="width:13rem"><ph-check-circle class="ic" /><b>It loads</b><br><small>import the flow; check its parameters as JSON: <span class="mono">validate_parameters</span></small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:13rem"><ph-test-tube class="ic" /><b>Each task works</b><br><small>unit tests on <span class="mono">task.fn(...)</span>, no server</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:13rem"><ph-flask class="ic" /><b>A whole run works</b><br><small>a test server, then a staging run before production</small></div>
</div>

<v-click at="4">

> [!TIP]
> Before you put a flow on a schedule, test that its parameters load from JSON, as the scheduler sends them.

</v-click>

</div>

[^1]: Apache Airflow docs, "Best Practices", "Testing a DAG". https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html (checked 26 Oct 2026)

<!--
Airflow lists the same three levels: a loader test, unit tests, and a staging environment for the complete run. Our costs, measured with Prefect 3.8.2: `task.fn` 0.000 s, `prefect_test_harness` setup about 4.3 s once per session, a flow run in the harness about 1.1 s. While building the lab, a dataclass parameter failed with `PydanticUserError` (the traps slide).
-->
