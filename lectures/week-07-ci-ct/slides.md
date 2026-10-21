---
theme: default
title: Week 7 — CI/CT Principles
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers continuous integration and continuous training, the ML test pyramid,
  GitHub Actions workflows that run the Week 5 and 6 gates, and what a model's
  version is.
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

# Week 7: CI/CT Principles

<carbon-continuous-integration class="icon-corner" />

**Lifecycle of Artificial Intelligence Systems**

- Two paths of change
- The ML test pyramid
- GitHub Actions
- Continuous training

<!--
Week 6 wrote the gates. This week they run without anyone typing a command.
-->

---

# Recap quiz

<carbon-list-numbered class="icon-corner" />

<div class="middle">

<div class="text-lg">

| **Week** | **Question** | **Answer** |
| --- | --- | --- |
| 1 | Besides the code, what changes an ML system? | <span v-click="1">**The data and the model**</span> |
| 2 | What makes a run work on another machine? | <span v-click="2">**Pinned versions**: `uv.lock`, image tags</span> |
| 3 | Which run made the model in production? | <span v-click="3">**Follow the alias**: version, run, commit</span> |
| 4 | Which data trained it? | <span v-click="4">**The data hash**, in Git and on the run</span> |
| 5 | When may data reach training? | <span v-click="5">**When it passes the contract**</span> |
| 6 | When may a model ship? | <span v-click="6">**When it passes criteria set before the run**</span> |

</div>

</div>

<!--
The fast round: the room answers each row in a word or two, about 20 seconds a row. Each answer leads to the next question: once we can find the model, we ask which data made it, then whether the data and the model were good enough.
Keep Week 2 in mind: today the checks run on "another machine", a CI runner.
-->

---

# Put the steps in order

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(6,1fr)">
  <div v-click.hide="6" class="card"><ph-tag class="ic" /><b>register</b></div>
  <div v-click.hide="3" class="card"><ph-cube class="ic" /><b>train</b></div>
  <div v-click.hide="5" class="card"><ph-stamp class="ic" /><b>gate</b></div>
  <div v-click.hide="1" class="card"><ph-shield-check class="ic" /><b>validate</b></div>
  <div v-click.hide="4" class="card"><ph-chart-bar class="ic" /><b>evaluate</b></div>
  <div v-click.hide="2" class="card"><ph-arrows-split class="ic" /><b>prepare</b></div>
</div>

<div class="flow text-sm" style="gap:0.4rem; margin-top:2.5rem">
  <div v-click="1" class="node green no-shrink" style="width:7rem"><ph-shield-check class="ic" /><b>validate</b><br><small>the data may come in</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node no-shrink" style="width:6rem"><ph-arrows-split class="ic" /><b>prepare</b><br><small>split</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node no-shrink" style="width:6rem"><ph-cube class="ic" /><b>train</b></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node violet no-shrink" style="width:7rem"><ph-chart-bar class="ic" /><b>evaluate</b><br><small>metrics and slices</small></div>
  <div v-click="5" class="arrow">→</div>
  <div v-click="5" class="node green no-shrink" style="width:7rem"><ph-stamp class="ic" /><b>gate</b><br><small>the model may go out</small></div>
  <div v-click="6" class="arrow">→</div>
  <div v-click="6" class="node sky no-shrink" style="width:7rem"><ph-tag class="ic" /><b>register</b><br><small>only with a GO</small></div>
</div>

</div>

<!--
The slow round: each click moves one card into place. Before each click, the room names the next step and says why. Validate before prepare, so a bad batch never reaches the split. Gate before register, so only a GO gets a version; in the lab, `register` and `promote` call `require_go`.
`dvc repro` (Week 4) runs these stages in this order; `train` logs to MLflow (Week 3), which runs in the Week 2 stack.
-->

---

# Spot the differences

<carbon-compare class="icon-corner" />

<div class="middle">

<div class="text-lg">

| | **Data validation** | **Model gate** |
| --- | --- | --- |
| **Guards** | <span v-click="1">the data coming in</span> | <span v-click="1">the model going out</span> |
| **Checks** | <span v-click="2">a rule for each column</span> | <span v-click="2">thresholds, baselines, every group</span> |
| **Rules from** | <span v-click="3">the domain expert and the data engineer</span> | <span v-click="3">the domain expert and the data scientist</span> |
| **On failure** | <span v-click="4">**stops the pipeline, writes a report**</span> | <span v-click="4">**stops the pipeline, writes a report**</span> |

</div>

</div>

<!--
Week 5's contract and Week 6's gate. Different objects, different rules, one mechanism: a non-zero exit code stops what comes after, and the report says why. For the data, the domain expert writes the rules and the data engineer turns them into checks; for the model, the project lead also signs the criteria.
-->

---
layout: center
---

# **Quiz**
# A new batch arrives at 03:00.
# Who runs the checks?

<v-clicks>

- Today: **nobody**, until someone types `dvc repro`.

</v-clicks>

<!--
Week 6's open question: "Who runs the gate? Today, we run `dvc repro` by hand." Both gates exist; neither runs unless a person starts the pipeline.
-->

---
layout: section
---

# 1 · Every path into production

<!--
About 12 minutes, one case: CrowdStrike, July 2024. Option B (Knight Capital, 2012) is hidden after the CrowdStrike slides.
-->

---

# 2024: CrowdStrike updates its sensor

<carbon-security class="icon-corner" />

<div class="middle">

CrowdStrike sells security software for Windows computers. It ships two kinds of update[^1][]:

<div class="flow" style="margin-top:1.5rem; gap:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-code class="ic" /><b>New sensor code</b><br><small>a release</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><ph-list-checks class="ic" /><b>Tests</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><ph-users class="ic" /><b>Staged release</b><br><small>a few computers first</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:8rem"><ph-windows-logo class="ic" /><b>Computers</b></div>
</div>

<div v-click class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-file-code class="ic" /><b>New detection rules</b><br><small>for a rapid response</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><ph-shield-check class="ic" /><b>Content Validator</b><br><small>checks the file against its definition</small></div>
  <div class="arrow-l">all at once<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:8rem"><ph-windows-logo class="ic" /><b>Computers</b></div>
</div>

</div>

[^1]: CrowdStrike, "Falcon Content Update Preliminary Post Incident Report", 24 July 2024. https://www.crowdstrike.com/en-us/blog/falcon-content-update-preliminary-post-incident-report/

<!--
CrowdStrike calls the rules "Rapid Response Content". The code's tests: unit, integration, performance and stress; the staged release goes to CrowdStrike's own staff, then early adopters, then everyone. Customers chose which sensor version they ran; they had no such choice for the rules.
This was not a cyberattack, and the sensor code did not change.
-->

---
layout: fact
class: fn-inline
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:15rem"><div class="text-5xl font-bold">04:09</div><div>19 July 2024, UTC: the new rules go out</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:15rem"><div class="text-5xl font-bold">05:27</div><div>the rules are withdrawn</div></div></div>
</div>

<div class="flex justify-center items-start gap-6 text-center" style="margin-top:2.5rem">
  <div v-click style="width:15rem"><div class="font-bold" style="color:#dc2626; white-space:nowrap; font-size:2.6rem; line-height:1.2">8.5 million</div><div>Windows computers crash</div></div>
  <div v-click style="width:15rem"><div class="font-bold" style="color:#dc2626; white-space:nowrap; font-size:2.6rem; line-height:1.2">7,000</div><div>Delta flights cancelled over five days</div></div>
  <div v-click style="width:15rem"><div class="font-bold" style="color:#dc2626; white-space:nowrap; font-size:2.6rem; line-height:1.2">&#36;5.4 billion</div><div>lost by large US companies, an estimate</div></div>
</div>

<div class="text-sm opacity-70" style="margin-top:1.5rem">

CrowdStrike[^1][] · Microsoft[^2][] · Delta[^3][] · Parametrix[^4][]

</div>

[^1]: CrowdStrike, Preliminary Post Incident Report, 24 July 2024.
[^2]: David Weston, Microsoft blog, 20 July 2024. https://blogs.microsoft.com/blog/2024/07/20/helping-our-customers-through-the-crowdstrike-outage/
[^3]: Delta Air Lines, Form 8-K, 8 Aug 2024. https://www.sec.gov/Archives/edgar/data/27904/000168316824005369/delta_8k.htm
[^4]: Parametrix, "CrowdStrike's Impact on the Fortune 500", July 2024: US Fortune 500 without Microsoft. https://parametrixinsurance.com/reports-white-papers/crowdstrikes-impact-on-the-fortune-500

<!--
Only computers that were online in those 78 minutes received the rules. Microsoft's own words: "less than one percent of all Windows machines", but many at "enterprises that run many critical services". Do not round it up into "CrowdStrike took down the internet".
Delta put its lost revenue at $380 million and its extra costs at $170 million, and claims at least $500 million from CrowdStrike and Microsoft. Parametrix is an insurer; $5.4 billion is its estimate of direct losses only.
-->

---
layout: center
---

# The sensor code was tested.
# How did a crash get through?

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-file-text class="ic" /><b>The definition</b>says a rule has <b>21</b> input fields</div>
  <div v-click class="card"><ph-code class="ic" /><b>The sensor code</b>supplies only <b>20</b></div>
  <div v-click class="card"><ph-shield-warning class="ic" style="color:#dc2626" /><b>The Content Validator</b>checks the rules against the definition, not against the code</div>
  <div v-click class="card"><ph-list-checks class="ic" style="color:#dc2626" /><b>The tests</b>put "match anything" in field 21</div>
</div>

<v-click>

On 19 July, a rule used field 21 for the first time. The sensor read a value that was not there, and Windows crashed[^1][].

</v-click>

[^1]: CrowdStrike, "External Technical Root Cause Analysis — Channel File 291", 6 Aug 2024, findings 1, 3 and 4. https://www.crowdstrike.com/wp-content/uploads/2024/08/Channel-File-291-Incident-Root-Cause-Analysis-08.06.2024.pdf

<!--
The definition (CrowdStrike: the "IPC Template Type") shipped with sensor 7.11 in February 2024. The validator checked every new rule file against it, and the file matched it; nobody compared the definition with the 20 values the code passes in. The earlier rules also put a wildcard in field 21, so the sensor never read it. An out-of-bounds read in the sensor's Content Interpreter; it now has a bounds check.
-->

---

# What would have stopped it?

<carbon-security class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.4rem; font-size:0.95rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-code class="ic" /><b>New sensor code</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><ph-list-checks class="ic" /><b>Tests</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><ph-users class="ic" /><b>Staged release</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:7rem"><ph-windows-logo class="ic" /><b>Computers</b></div>
</div>

<div class="flow" style="gap:0.4rem; font-size:0.95rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-file-code class="ic" /><b>New detection rules</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><ph-shield-check class="ic" /><b>Content Validator</b><br><small>also checks the code's 20 values</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:9rem"><ph-list-checks class="ic" /><b>Tests</b><br><small>every new rule runs in the sensor</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:9rem"><ph-users class="ic" /><b>Staged release</b><br><small>a few computers first</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:7rem"><ph-windows-logo class="ic" /><b>Computers</b></div>
</div>

<v-click at="3">

> [!TIP]
> List every path into production. Give each one the checks your code path has.

</v-click>

</div>

<!--
CrowdStrike's own mitigations from the RCA (6 Aug 2024), findings 4 to 6. The second row now has the same steps as the first. CrowdStrike also added a bounds check in the sensor and lets customers choose when the rules arrive.
Staged release ("canary", "rings") is Week 10. Today is about the checks.
-->

---
hide: true
---

# Option B · 2012: Knight Capital updates by hand

<carbon-chart-line class="icon-corner" />

<div class="middle">

Knight Capital was a large US stock-trading firm. On 1 August 2012, new trading code went to eight servers[^1][].

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:11rem"><ph-user class="ic" /><b>A technician</b><br><small>copies the new code by hand</small></div>
  <div class="arrow">→</div>
  <div class="node green" style="width:11rem"><ph-cpu class="ic" /><b>7 servers</b><br><small>new code</small></div>
  <div v-click class="node rose" style="width:11rem"><ph-cpu class="ic" style="color:#dc2626" /><b>1 server</b><br><small>old code, never removed</small></div>
</div>

<v-click>

Nobody checked the copy: no second technician, no written procedure.

</v-click>

</div>

[^1]: US SEC, Order against Knight Capital Americas LLC, Release No. 70694, 16 Oct 2013. https://www.sec.gov/litigation/admin/2013/34-70694.pdf

<!--
Option B: use Knight Capital instead of CrowdStrike: switch `hide` on the four CrowdStrike slides and on these three. Also change: the note of "Is a new batch a code change?"; the notes of "The model was retrained at 02:30 last night." and "This week's workflows"; the CrowdStrike line on "What can a green build hide?" (use "Knight's deployment ended with no error, and one server of eight ran the old code."); the study notes' "Why this matters".
The new code reused a flag that once switched on old code ("Power Peg"), still on the eighth server.
-->

---
hide: true
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:14rem"><div class="text-5xl font-bold">45 min</div><div>of trading</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:14rem"><div class="text-5xl font-bold">4 million</div><div>trades in 154 stocks</div></div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:16rem"><div class="text-5xl font-bold" style="color:#dc2626">−&#36;460 million</div><div>Knight's loss</div></div></div>
</div>

<br>

US SEC, Release No. 70694[^1][]

[^1]: US SEC, Order against Knight Capital Americas LLC, Release No. 70694, 16 Oct 2013.

<!--
Option B, second slide. Trying to fix it, Knight removed the new code from the seven good servers, so all eight ran the old code. The SEC fined Knight $12 million.
-->

---
hide: true
---

# Option B · What would have stopped it?

<carbon-chart-line class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-code class="ic" /><b>New code</b></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:11rem"><ph-terminal class="ic" /><b>Deployment script</b><br><small>the same steps on all eight servers</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:11rem"><ph-list-checks class="ic" /><b>Check</b><br><small>every server reports its code version</small></div>
  <div v-click="2" class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-cpu class="ic" /><b>8 servers</b></div>
</div>

<v-click at="3">

The warning was there: **97** automated emails, "Power Peg disabled", before the market opened[^1][].

</v-click>

<v-click at="4">

> [!TIP]
> Automate every step that changes production, and check its result.

</v-click>

</div>

[^1]: US SEC, Order against Knight Capital Americas LLC, Release No. 70694, 16 Oct 2013, §§15 and 19.

<!--
Option B, third slide. The SEC names what was missing: "a second technician review" and "written procedures that required such a review". The script and the version check are our lesson, not the SEC's words.
The 97 emails were not designed as alerts, and nobody acted on them before or after the 9:30 open (SEC, §19).
-->

---

# Is a new batch a code change?

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-code class="ic" /><b>A code change</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:11rem"><ph-git-commit class="ic" /><b>A commit</b><br><small>a diff to read</small></div>
  <div class="arrow-l on">a reviewer<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:8rem"><ph-cube class="ic" /><b>Model</b></div>
</div>

<div v-click="1" class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-database class="ic" /><b>A new batch</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:11rem"><ph-git-commit class="ic" /><b>A commit</b><br><small>one new md5 in a <span class="mono">.dvc</span> file</small></div>
  <div class="arrow-l fail">nothing to read<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:8rem"><ph-cube class="ic" /><b>Model</b></div>
</div>

<v-click at="2">

> [!WARNING]
> In many teams new data lands in a warehouse, and a clock starts the retraining: **no commit at all**.

</v-click>

</div>

<!--
In our project, yes: since Week 4 the data's pointer is in Git, so a new batch is a commit. But a reviewer cannot judge data from its hash, so on this path the checks must be automatic: Week 5's contract and Week 6's gate. Today they run only when someone types `dvc repro`.
CrowdStrike's rules had a validator too; the checks a person would do were missing. Section 5 is the retraining with no commit.
-->

---

# Where we are: CI/CD

<div class="middle">

<Lifecycle stage="cicd" width="70%" />

Today: run the checks on every change, and on every retraining.

</div>

<!--
CI/CD joins development to operations in the Week 1 figure. Continuous training loops back from operations to build; this week stops at the gate, before deploy (Weeks 9–10).
-->

---
layout: section
---

# 2 · Continuous integration

<!--
About 10 minutes. Continuous integration as a practice, and what it costs; the tool options and GitHub Actions come in Section 4.
-->

---

# What is continuous integration?

<carbon-continuous-integration class="icon-corner" />

<div class="middle">

**Continuous integration (CI):** the team merges small changes often, and a machine checks every change automatically.

<div class="flow" style="margin-top:2rem">
  <div class="node amber" style="width:10rem"><ph-laptop class="ic" /><b>You</b><br><small>push a change</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node" style="width:11rem"><ph-cpu class="ic" /><b>A fresh machine</b><br><small>a "runner"</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:11rem"><ph-list-checks class="ic" /><b>Lint, tests, pipeline</b></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node sky" style="width:10rem"><ph-git-pull-request class="ic" /><b>✓ or ✗</b><br><small>on the pull request</small></div>
</div>

</div>

<!--
The runner is created for the job and deleted after it, so nothing from the last run is left on it.
A team with no CI tool but a strict "run `make check` before every push" rule has the practice and no enforcement: it works until someone is in a hurry.
-->

---

# Every part matters

<carbon-help class="icon-corner" />

<div class="middle">

CI checks **every change**, **automatically**, on a machine that is **not yours**.

<div class="text-lg">

| **Without** | **What breaks** |
| --- | --- |
| every change | <span v-click="1">several changes fail at once: which one broke it?</span> |
| automatically | <span v-click="2">someone forgets to run it</span> |
| not yours | <span v-click="3">it passes because of something only your laptop has</span> |

</div>

</div>

<!--
"Every change" is also why CI wants small changes: a failing run points at one small diff.
-->

---

# What is on your laptop and not in the repository?

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(4,1fr)">
  <div v-click class="card"><ph-key class="ic" /><b>A <code>.env</code> file</b>never committed,<br>on purpose</div>
  <div v-click class="card"><ph-package class="ic" /><b>A package</b>installed by hand,<br>not in <code>uv.lock</code></div>
  <div v-click class="card"><ph-database class="ic" /><b>A data file</b>pulled once,<br>months ago</div>
  <div v-click class="card"><ph-terminal class="ic" /><b>A service</b>Docker, MLflow, Silo,<br>still running</div>
</div>

<div style="height:1rem"></div>

<v-click>

> [!TIP]
> Make the build create everything it needs from the repository: the data, a default `.env`, the packages in the lock file.

</v-click>

</div>

<!--
A fresh runner has none of the four. In the lab, `make ci` copies `.env.example` when there is no `.env`, and rebuilds the data from committed batches.
-->

---

# Is CI worth it?

<carbon-chart-bar class="icon-corner" />

<div class="middle">

34,544 open-source projects on GitHub, 442 developers surveyed, 2016[^1][]:

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1rem">
  <div v-click="1" class="card"><ph-rocket-launch class="ic" style="color:#16a34a" /><div class="text-3xl font-bold">0.54</div>releases a month with CI,<br>0.24 without</div>
  <div v-click="2" class="card"><ph-git-merge class="ic" style="color:#16a34a" /><div class="text-3xl font-bold">1.6 h</div>sooner: the median pull request is accepted</div>
  <div v-click="3" class="card"><ph-hourglass class="ic" style="color:#dc2626" /><div class="text-3xl font-bold">~500 s</div>the average build</div>
  <div v-click="4" class="card"><ph-test-tube class="ic" style="color:#dc2626" /><div class="text-3xl font-bold">44%</div>of projects without CI: "Our project doesn't have automated tests"</div>
</div>


</div>

[^1]: Hilton, Tunnell, Huang, Marinov and Dig, "Usage, Costs, and Benefits of Continuous Integration in Open-Source Projects", ASE 2016, Tables 4 and 7, §4.2–4.3. https://doi.org/10.1145/2970276.2970358

<!--
A link, not proof: the same projects released 0.34 times a month before they added CI. 40% of all projects and 70% of the most popular ones used CI.
The top reason for not using CI (47%) was not knowing it. CI runs only the tests you have; which tests is the next section.
-->

---
layout: section
---

# 3 · The ML test pyramid

<!--
About 12 minutes. The students wrote all four layers in Weeks 1–6; this section names them so CI can run each one on its own.
-->

---
layout: center
---

# What can break in an ML system?

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-code class="ic" /><b>Our code</b><code>to_nullable</code> misses a column</div>
  <div v-click class="card"><ph-database class="ic" /><b>The data</b>a batch with impossible zeros</div>
  <div v-click class="card"><ph-cube class="ic" /><b>The model</b>worse than the one in production</div>
  <div v-click class="card"><ph-stack class="ic" /><b>The parts together</b>MLflow does not answer</div>
</div>

<!--
Breck et al. (Google, 2017): unlike hand-written code, an ML system's behaviour "depends on dynamic qualities of the data, and on various model configuration choices". Ordinary software tests only the first and the last card.
-->

---
class: fn-inline
---

# The ML test pyramid

<carbon-layers class="icon-corner" />

<div class="middle">

<div class="text-lg text-center" style="min-height:2rem">
<v-switch>
  <template #0>Which layer checks that <code>to_celsius(32)</code> returns 0?</template>
  <template #1>…that every row of the batch passes the ingestion contract?</template>
  <template #2>…that the new model's F1 is not lower than the champion's?</template>
  <template #3>…that a training run appears in MLflow with its data tag?</template>
  <template #4-5></template>
</v-switch>
</div>

<div class="flow" style="margin:1rem 0 0.25rem"><div v-click="4" class="node" style="width:20rem; position:relative"><b>integration</b> <small>several parts, over a real connection</small><span v-click="5" style="position:absolute; left:calc(100% + 0.75rem); top:50%; transform:translateY(-50%); white-space:nowrap; color:#dc2626; font-size:0.85rem; text-align:left">not in CI:<br>needs the Docker stack</span></div></div>
<div style="position:relative; padding:0.35rem 0">
<div class="flow" style="margin:0.25rem 0"><div v-click="3" class="node sky" style="width:27rem"><b>eval</b> <small>is the model good enough?</small></div></div>
<div class="flow" style="margin:0.25rem 0"><div v-click="2" class="node green" style="width:34rem"><b>data</b> <small>is the data what we agreed?</small></div></div>
<div class="flow" style="margin:0.25rem 0"><div v-click="1" class="node violet" style="width:41rem"><b>unit</b> <small>is our code correct?</small></div></div>
<div v-click="5" style="position:absolute; top:0; bottom:0; left:50%; width:44rem; transform:translateX(-50%); border:3px dashed #16a34a; border-radius:1rem"><span style="position:absolute; top:-0.75rem; right:1rem; background:white; padding:0 0.4rem; color:#16a34a; font-weight:700">CI runs these</span></div>
</div>

</div>

<div class="text-sm opacity-70">

The test pyramid: Mike Cohn, in Vocke[^1][] · tests for ML: Breck et al.[^2][]

</div>

[^1]: Ham Vocke, "The Practical Test Pyramid", martinfowler.com, 26 Feb 2018. https://martinfowler.com/articles/practical-test-pyramid.html
[^2]: Breck et al., "The ML Test Score", IEEE Big Data 2017. https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/

<!--
Before each click the room names the layer; the click adds it. Cohn's rule, from his book "Succeeding with Agile": the higher the level, the fewer the tests. Unit tests take milliseconds and need no data and no model.
The integration tests need the Docker stack (Postgres, Silo, MLflow), which our CI does not start: every later week's pipeline must run on a bare runner, and starting three services costs minutes and credentials on every run. Section 4's "Service containers" shows how a team that needs them would do it, for example in a nightly job. Breck et al. list 28 tests and group them differently (data, model, infrastructure, monitoring); our four layers are a simpler cut.
Some tests fit two layers: a test of the gate's own code needs no model and runs in milliseconds, but it protects the release decision. The lab's Exercise 3 asks students to choose a layer for such a test and write down why.
-->

---
layout: center
---

# **Quiz**
# CI should prove that main still works.
# Why leave the integration tests out?

<v-clicks>

- **Continuous integration vs integration test**
  - continuous integration merges every change into main
  - an integration test runs several parts together
- **Cons**
  - every push would pull and build the stack, then wait for three services
  - a slow start looks like a failing test

</v-clicks>

<v-click>

> [!TIP]
> Run the integration tests in a slower job, after a merge or every night.

</v-click>

<!--
They would check something real: our wiring to Postgres, Silo and MLflow. It changes far less often than our code, data and model, which the other three layers check on every push. In this course there is one more reason: every later week's pipeline must run on a bare runner, with no services.
-->

---

# Pytest markers

<carbon-terminal class="icon-corner" />

<div class="middle">

A marker is a label on a test[^1][]. `pytest -m unit` runs only the tests labelled `unit`.

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
<div>

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: our code is correct",
    "data: the data is what we agreed",
]
```

```bash
pytest -m unit -q
```

<v-click at="4">

```text
1 passed, 2 deselected in 0.26s
```

</v-click>

</div>
<div>

```python {all|7-9|11-14|16-17|all}
import pandas as pd
import pytest

def to_celsius(f):
    return (f - 32) * 5 / 9

@pytest.mark.unit
def test_freezing_point():
    assert to_celsius(32) == 0

@pytest.mark.data
def test_no_impossible_temperatures():
    readings = pd.DataFrame({"temp_c": [12.5, -3.0, 21.0]})
    assert readings["temp_c"].between(-90, 60).all()

def test_forgotten():
    assert True
```

</div>
</div>

</div>

[^1]: Example adapted from the pytest docs, "Working with custom markers". https://docs.pytest.org/en/stable/example/markers.html

<!--
Measured with pytest 9.1.1 (the lab's version) on these three tests. An unregistered marker, such as the typo `@pytest.mark.untt`, gives only a warning; the `strict_markers` option turns it into an error.
-->

---

# Marker types

<carbon-tag class="icon-corner" />

<div class="middle">

| **Type** | **Answers** | **Markers** | **In CI** |
| --- | --- | --- | --- |
| **layer** | what does the test check? | `unit` · `data` · `eval` · `integration` | one job per layer |
| **guard** | what does the test need to run? | `live` (the Docker stack) · `dvc` (a DVC repository) | left out: `-m "not live and not dvc"` |

<v-click>

Both are ordinary pytest markers, and a test can carry one of each. `pytestmark` at the top of a file marks every test in it. In the lab, `test_dvc_repo.py` holds data tests that need a DVC repository:

```python
pytestmark = [pytest.mark.data, pytest.mark.dvc]
```

A test with no layer runs in no CI job, so it can never fail CI: give every test a layer.

</v-click>

</div>

<!--
There is no standard name for either type; "layer" and "guard" are this course's words. Other projects use guards such as `slow` (the pytest docs' example) or `requires_db`. The guards came first (Weeks 3–4): a fixture also skips the test when the stack or the DVC files are missing. The layers are new. "Skip what needs a service" must not also skip a whole kind of check, which is why the two are separate markers.
-->

---
layout: section
---

# 4 · GitHub Actions

<!--
About 24 minutes: the tool options, then GitHub Actions. The lab's Exercises 2 and 4. The code here uses the weather readings from the markers example, not the lab's diabetes pipeline.
-->

---
class: fn-inline
---

# Tool options

<carbon-tool-box class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-github-logo class="ic" /><b>GitHub Actions</b><code>.github/workflows/*.yml</code></div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-gitlab-logo class="ic" /><b>GitLab CI/CD</b><code>.gitlab-ci.yml</code></div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-wrench class="ic" /><b>Jenkins</b><code>Jenkinsfile</code>, on a server you run</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-circle-notch class="ic" /><b>CircleCI</b><code>.circleci/config.yml</code></div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-cloud class="ic" /><b>Azure Pipelines</b><code>azure-pipelines.yml</code></div>
</div>

<div class="text-sm opacity-70">

GitHub Actions[^1][] · GitLab[^2][] · Jenkins[^3][] · CircleCI[^4][] · Azure Pipelines[^5][]

</div>

<v-click>

**We use GitHub Actions:** your repository is on GitHub.

</v-click>

</div>

[^1]: https://docs.github.com/en/actions/get-started/quickstart
[^2]: https://docs.gitlab.com/ci/
[^3]: https://www.jenkins.io/doc/book/pipeline/jenkinsfile/
[^4]: https://circleci.com/docs/guides/getting-started/getting-started/
[^5]: https://learn.microsoft.com/en-us/azure/devops/pipelines/create-first-pipeline

<!--
All five keep the pipeline in a file in the repository, so a change to the pipeline is reviewed like a change to the code. Jenkins is the one you host yourself.
The autograder is `.github/workflows/autograde.yml`; the lab's Exercise 1 reads it.
-->

---

# GitHub Actions example

<carbon-logo-github class="icon-corner" />

<div class="middle">

<div style="display:grid;grid-template-columns:0.85fr 1.15fr;gap:1.5rem;">
<div>

```yaml {1|2|3-5|6-10|all}
name: Readings CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v7
      - run: uv sync --locked
      - run: uv run pytest -m unit
```

</div>
<div class="text-sm">

| **Key** | **Means** |
| --- | --- |
| `on` | when the workflow runs |
| `jobs` | what runs; jobs run in parallel unless one `needs` another |
| `runs-on` | where: a fresh virtual machine, deleted after the job |
| `steps` | which commands, in order |

</div>
</div>

</div>

<div class="src">Adapted from GitHub Docs, "Quickstart for GitHub Actions" and "Workflow syntax". https://docs.github.com/en/actions/get-started/quickstart</div>

<!--
Nothing survives between jobs: each job checks out the code and installs the dependencies again, unless a step uploads something.
GitHub reads workflows only from `.github/workflows/` at the repository root; a workflow anywhere else does nothing, with no error and no warning. The lab keeps its workflows next to the code they test, and `make install-ci` copies them to the root as `week07-ci.yml` and `week07-ct.yml`.
The quick start's example still pins `actions/checkout@v6` (checked 16 Oct 2026); v7 is the newest major tag.
-->

---

# `uses:` and `run:`

<carbon-code class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node rose" style="width:18rem"><ph-package class="ic" /><b><code>uses: actions/checkout@v7</code></b><br><small v-click="1">someone else's program,<br>run in your job</small></div>
  <div class="node violet" style="width:18rem"><ph-terminal class="ic" /><b><code>run: make lint</code></b><br><small v-click="2">a shell command<br>from your repository</small></div>
</div>

<v-click at="3">

What can a `uses:` step do?

</v-click>

<v-clicks>

- **Read your code**, and change files in your checkout.
- **Use the job's `GITHUB_TOKEN`**, even if you never pass it[^1][].

</v-clicks>

</div>

[^1]: GitHub Docs, "Use GITHUB_TOKEN for authentication in workflows". https://docs.github.com/en/actions/tutorials/authenticate-with-github_token

<!--
Closer to `curl … | sh` with a version number than to `import`. The `permissions:` key limits what the token may do; GitHub's advice is to give actions "only the minimum access they require".
-->

---

# Pin examples

<carbon-pin class="icon-corner" />

<div class="middle">

| **Pin** | **Example** | **Means** |
| --- | --- | --- |
| a branch | `actions/checkout@main` | <span v-click="1">new code on every commit to `main`</span> |
| a major tag | `actions/checkout@v7` | <span v-click="2">new code within v7: fixes arrive by themselves</span> |
| a release tag | `astral-sh/setup-uv@v9.0.0` | <span v-click="3">one release, unless its owner moves the tag</span> |
| a commit SHA | `actions/checkout@<40 hex characters>` | <span v-click="4">never changes</span> |

<v-click at="5">

GitHub: a full-length commit SHA is "the only way to use an action as an immutable release"[^1][].

</v-click>

</div>

[^1]: GitHub Docs, "Security hardening: secure use reference". https://docs.github.com/en/actions/reference/security/secure-use

<!--
The lab pins major tags, and setup-uv to its release tag v9.0.0, because there is no v9 tag. A major tag is a compromise: security fixes arrive without an edit, and the code you run tomorrow is not the code you reviewed today. A SHA pin needs a tool (Dependabot or Renovate) to bump it, or it goes stale.
-->

---

# Our pins on 6 August 2026

<carbon-time class="icon-corner" />

<div class="middle">

| **Action** | **Pinned** | **Newest major tag** | **Behind** |
| --- | --- | --- | --- |
| `actions/checkout` (×2) | v4 | v7 | **3** |
| `astral-sh/setup-uv` | v5 | v7 | **2** |
| `actions/setup-node` | v4 | v7 | **3** |
| `actions/upload-pages-artifact` | v3 | v5 | **2** |
| `actions/deploy-pages` | v4 | v5 | **1** |

<div style="margin-top:1rem">

Nothing failed: an old major tag keeps working, so nobody noticed. We moved them by hand. `setup-uv` is now pinned to its release tag `v9.0.0`: its newest major tag is still `v7`, so `@v9` does not exist.

</div>

</div>

<!--
From `make ci-explain` on the course repository's own workflows (the autograder and the slides), 6 Aug 2026. On 16 Oct 2026, setup-uv's newest release is v10.3.0 and its newest major tag is still v7 (`git ls-remote --tags`): releases and major tags are different lists, and `@v9` failed with "unable to find version `v9`".
-->

---

# The job graph

<carbon-flow-connection class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div style="display:flex; flex-direction:column; gap:0.5rem">
    <div v-click="1" class="node green" style="width:9rem"><b>lint</b></div>
    <div v-click="2" class="node green" style="width:9rem"><b>test (unit)</b></div>
    <div v-click="2" class="node green" style="width:9rem"><b>test (data)</b></div>
    <div v-click="2" class="node green" style="width:9rem"><b>test (eval)</b></div>
  </div>
  <div v-click="3" class="arrow-l on"><code>needs</code><span class="arrow">→</span></div>
  <div v-click="3" class="node sky" style="width:12rem"><b>pipeline</b><br><small>data → validate → … → gate</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node" style="width:11rem"><ph-archive class="ic" /><b>gate report</b><br><small>on the run's page, and as a download</small></div>
</div>

<v-click at="5">

Why is `lint` a job of its own?

</v-click>

<v-clicks at="6">

- It fails in seconds.
- Nobody waits for the tests to hear about an unused import.

</v-clicks>

</div>

<!--
Times from the lab's first green run on GitHub: lint 12 s, the tests 22–36 s, the pipeline 53 s. The five jobs take 148 s of runner time, but lint and the three test jobs run side by side. The gate report is the job summary and the `gate-evidence` artifact.
The pipeline trains a model, so it waits for lint and the tests: training on a branch whose tests fail wastes a minute of runner time.
-->

---

# One job per test layer

<carbon-chart-relationship class="icon-corner" />

<div class="middle">

<div style="display:grid;grid-template-columns:1.1fr 0.9fr;gap:1.5rem">
<div>

```yaml {all|6-7|8,11|5}
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        layer: [unit, data, eval]
    name: test (${{ matrix.layer }})
    steps:
      # checkout, setup-uv, uv sync
      - run: make test-${{ matrix.layer }}
```

</div>
<div class="text-sm">

| **Key** | **Means** |
| --- | --- |
| `matrix` | one copy of the job per value: `test (unit)`, `test (data)`, `test (eval)` |
| `matrix.layer` | the value in this copy |
| `fail-fast: false` | when one copy fails, the others still finish |

</div>
</div>

<v-click at="4">

A red `test (data)` names the layer that failed; one job for all tests says only "tests failed".

</v-click>

</div>

<div class="src">The matrix syntax: GitHub Docs, "Running variations of jobs in a workflow". https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations</div>

<!--
From the lab's `ci.yml`. The same key runs one job on several Python versions or operating systems, the usual example in the docs (Astral's uv guide uses `python-version`). The default `fail-fast: true` cancels the other copies, so you would not learn whether the others are broken too.
The cost: each copy installs the dependencies again.
-->

---

# One pipeline definition

<carbon-direction-merge class="icon-corner" />

<div class="middle">

<div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem">
<div>

**Two copies**

<div class="flow" style="flex-direction:column; gap:0.4rem">
  <div class="node violet" style="width:17rem"><ph-file-code /> <b>Makefile</b><br><small>lint · tests · <code>dvc repro</code> · <b>gate</b></small></div>
  <div class="node rose" style="width:17rem"><ph-github-logo /> <code>ci.yml</code> lists its own steps<br><small>lint · tests · <code>dvc repro</code> · <b>no gate</b></small></div>
</div>

<v-click at="1">

You add the gate to the Makefile and forget `ci.yml`. CI never runs the gate, and stays green.

</v-click>

</div>
<div v-click="2">

**One definition**

<div class="flow" style="flex-direction:column; gap:0.4rem">
  <div class="node amber" style="width:17rem"><ph-laptop /> your laptop → <code>make ci</code></div>
  <div class="node amber" style="width:17rem"><ph-github-logo /> <code>ci.yml</code> → <code>make ci</code></div>
  <div class="node green" style="width:17rem"><ph-file-code /> <b>Makefile</b><br><small>lint · tests · <code>dvc repro</code> · gate</small></div>
</div>

</div>
</div>

</div>

<!--
With two copies, every change to the pipeline must be made twice, and the copy nobody runs locally falls behind without a sound.
The lab enforces one definition: a test reads every `run:` line of both workflows and fails if one calls `src/main.py` directly. A rule with a test outlives a rule in a README. `ct.yml` calls `make ct-local` the same way.
It is not about `make`: a shell script or a task runner works too, as long as there is one definition.
-->

---

# Service containers

<carbon-container-software class="icon-corner" />

<div class="middle">

A job can start a database next to it, for its tests to use[^1][]:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16.3
        ports: ["5432:5432"]
```

<v-clicks>

- **Pro:** the integration tests can run in CI.
- **Con:** every run starts the service and waits for it; a slow start looks like a failing test.
- **We do not use them:** our CI needs no service at all.

</v-clicks>

</div>

[^1]: GitHub Docs, "Workflow syntax", `jobs.<job_id>.services`: "Used to host service containers for a job in a workflow." https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

<!--
This is the usual answer for a job that needs a database, a queue or an object store. Our pipeline would need three: Postgres, Silo and MLflow, plus their credentials.
-->

---

# What our CI does not need

<carbon-checkmark-outline class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div class="card"><ph-cube class="ic" style="color:#dc2626" /><b>Docker</b></div>
  <div class="card"><ph-flask class="ic" style="color:#dc2626" /><b>MLflow</b></div>
  <div class="card"><ph-database class="ic" style="color:#dc2626" /><b>Silo</b></div>
  <div class="card"><ph-key class="ic" style="color:#dc2626" /><b>Secrets</b></div>
  <div class="card"><ph-cloud-arrow-down class="ic" style="color:#dc2626" /><b><code>dvc pull</code></b></div>
</div>

<v-click>

`make ci` trains, evaluates and gates on a bare runner. It cannot register or promote a model: that needs the tracking server.

</v-click>

<v-click>

> [!TIP]
> Design the pipeline so that it runs on a bare machine, from the first week of the project.

</v-click>

</div>

<!--
How: the dataset rebuilds from batches committed to Git (Week 4); `train` skips the run log when MLflow does not answer (Week 4); the contracts read committed files (Week 5); the gate is a pure function, numbers in and verdict out (Week 6).
The principle is common practice under the name "hermetic" builds and tests (Bazel docs, "Hermeticity"; Google Testing Blog, "Hermetic Servers", 2012). Measured in the lab: `make ci` from a clean checkout, stack down, about 19 s, with metrics byte-identical to Weeks 5 and 6.
-->

---
hide: true
---

# A red build you can read

<carbon-report class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1rem">
  <div v-click="1" class="card"><ph-warning class="ic" style="color:#dc2626" /><b>Annotation</b>one line at the top of the run<br><code style="white-space:normal">echo "::error title=Forecast too far off::MAE 3.1"</code></div>
  <div v-click="2" class="card"><ph-file-text class="ic" /><b>Job summary</b>Markdown on the run page<br><code style="white-space:normal">echo "| MAE | 3.1 |" >> "$GITHUB_STEP_SUMMARY"</code></div>
  <div v-click="3" class="card"><ph-archive class="ic" /><b>Artifact</b>the files, to download<br><code style="white-space:normal">uses: actions/upload-artifact@v7</code></div>
</div>

<div v-click="4" class="text-sm" style="margin-top:1rem">

| **Condition** | **The step runs** |
| --- | --- |
| no `if:` | only when every step before it passed |
| `if: failure()` | only when a step before it failed |
| `if: always()` | always, even after a failure |

</div>

GitHub Docs[^1][]

</div>

[^1]: GitHub Docs, "Workflow commands for GitHub Actions". https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

<!--
Hidden: the lab's Exercise 4 README and the study notes cover it. Three readers: the annotation is for someone scanning the pull request, the summary for someone deciding whether to care, the artifact for someone debugging. A red cross that makes you open the logs is the one people learn to ignore.
Same rule as Week 5's gate: write the report first, then stop.
-->

---
hide: true
---

# The red build, measured

<carbon-stop-sign class="icon-corner" />

<div class="middle">

`train.C: 1.0 → 0.005`, pushed to GitHub:

| Job | Result | Time |
| --- | --- | --- |
| `lint` | pass | 19 s |
| `test (unit)` | pass | 36 s |
| `test (data)` | pass | 30 s |
| `test (eval)` | pass | 28 s |
| `pipeline` | **fail**, at the gate | 43 s |

```text
NO-GO. 4 acceptance criteria failed: minimum.f1, regression.f1,
slice.age_band.30-39, fairness.age_band.tpr_gap.
```

</div>

<!--
Hidden: it answers the lab's Exercise 6 written questions. Show it after the lab deadline, for example in the Week 8 recap.
The job times and the artifact `gate-evidence` (4,425 bytes, uploaded although the job failed) are from the August run on GitHub. The verdict is from `make ci-fail` on 16 Oct 2026, after Week 6 added the age-band TPR gap to the gate.
-->

---
layout: section
---

# 5 · Continuous training

<!--
About 12 minutes. The second path from Section 1, with the same commands. The lab's Exercise 5. Option B for the fly-book case (Zillow, 2021) is hidden after it.
-->

---

# Continuous training

<carbon-time class="icon-corner" />

<div class="middle">

Retraining started by a person, a clock or new data, with no code change.

```yaml
on:
  workflow_dispatch:            # a person, from the Actions tab
    inputs:
      note: {required: false}
  schedule:
    - cron: "30 2 * * *"        # every day, 02:30 UTC
```

<div class="flow" style="margin-top:1rem">
  <div class="node amber" style="width:11rem"><ph-git-pull-request /> push, pull request</div>
  <div class="arrow">→</div>
  <div class="node" style="width:7rem"><code>ci.yml</code></div>
  <div class="arrow">→</div>
  <div class="node violet" style="width:8rem"><b>Makefile</b></div>
  <div class="arrow">←</div>
  <div v-click class="node" style="width:7rem"><code>ct.yml</code></div>
  <div v-click class="arrow">←</div>
  <div v-click class="node amber" style="width:11rem"><ph-clock /> a person, a clock</div>
</div>

</div>

<!--
A CT workflow must not run on `push`, or it is a slower copy of CI. An input such as `note` lets the person say why they started the run, and the run can print it into its log.
New data can also start it, for example a new batch arriving in storage.
-->

---
layout: center
---

# The model was retrained at 02:30 last night.
# Who checked it?

<div class="flow text-sm" style="gap:0.4rem; margin-top:2rem">
  <div class="node amber no-shrink" style="width:5rem"><ph-file-csv class="ic" /><b>Batch</b></div>
  <div class="arrow">→</div>
  <div :class="$clicks >= 1 ? 'node green no-shrink' : 'node no-shrink'" style="width:7rem"><ph-shield-check class="ic" /><b>validate</b><br><small>the data contract</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6.5rem"><ph-cube class="ic" /><b>prepare, train</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6.5rem"><ph-chart-bar class="ic" /><b>evaluate</b></div>
  <div class="arrow">→</div>
  <div :class="$clicks >= 1 ? 'node green no-shrink' : 'node no-shrink'" style="width:7rem"><ph-stamp class="ic" /><b>gate</b><br><small>GO or NO-GO</small></div>
</div>

<v-click at="1">

The checks inside the pipeline: **the data contract and the gate**. A person reads the gate report in the morning.

</v-click>

<!--
No one waits for the run, there is no diff to review, and nobody approved the new data: the CrowdStrike content path again. Everything a reviewer checks by eye on the code path has to become an automatic check on this one.
-->

---

# 2011: two booksellers set prices by program

<carbon-shopping-cart class="icon-corner" />

<div class="middle">

Two Amazon sellers offered *The Making of a Fly*, a biology book[^1][]:

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:13rem"><ph-storefront class="ic" /><b>profnath</b><br><small>price = 0.9983 × the other's</small></div>
  <div class="arrow-l">every day<span class="arrow">⇄</span></div>
  <div class="node amber" style="width:13rem"><ph-storefront class="ic" /><b>bordeebook</b><br><small>price = 1.270589 × the other's</small></div>
</div>

<v-click>

What was missing between the program and the price?

</v-click>

</div>

[^1]: Michael Eisen, "Amazon's $23,698,655.93 book about flies", *it is NOT junk*, 22 April 2011 (archived). https://web.archive.org/web/2011/http://www.michaeleisen.org/blog/?p=358

<!--
0.9983 × 1.270589 is about 1.27, so both prices grew by about 27% a day. Eisen's guess: bordeebook did not own the book, and would buy it from profnath if someone ordered it.
-->

---
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:27rem"><div class="text-5xl font-bold" style="color:#dc2626">&#36;23,698,655.93</div><div>the highest price, 18 April 2011</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:14rem"><div class="text-5xl font-bold">&#36;106.23</div><div>the next day</div></div></div>
</div>

<br>

<v-click>

Eisen: no "built-in sanity check on the prices"[^1][]

</v-click>

[^1]: Michael Eisen, *it is NOT junk*, 22 April 2011.

<!--
Plus $3.99 shipping. Someone noticed: on 19 April, profnath's price dropped to $106.23, and bordeebook followed.
-->

---

# What would have stopped the loop?

<carbon-shopping-cart class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:13rem"><ph-storefront class="ic" /><b>profnath</b><br><small>0.9983 × the other's</small></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:12rem"><ph-shield-check class="ic" /><b>Maximum price</b><br><small>a gate before the listing</small></div>
  <div v-click="1" class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-tag class="ic" /><b>Listing</b></div>
</div>

<div class="flow" style="margin:0"><div class="arrow-l">reads the other's listing, every day<span class="arrow">⇅</span></div></div>

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:13rem"><ph-storefront class="ic" /><b>bordeebook</b><br><small>1.270589 × the other's</small></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:12rem"><ph-shield-check class="ic" /><b>Maximum price</b><br><small>a gate before the listing</small></div>
  <div v-click="1" class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-tag class="ic" /><b>Listing</b></div>
</div>

</div>

<!--
Both programs did what they were told. The maximum price is a gate between the loop and the result, the same job as Week 6's gate; in CT, the gate is that line.
-->

---
hide: true
---

# Option B · 2021: Zillow buys houses

<carbon-home class="icon-corner" />

<div class="middle">

Zillow runs a large US property website. Its Zillow Offers business bought homes from sellers and sold them again. Each offer needed a forecast of the home's price "three to six months into the future"[^1][].

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:11rem"><ph-chart-line-up class="ic" /><b>Price forecast</b></div>
  <div class="arrow">→</div>
  <div class="node violet" style="width:11rem"><ph-handshake class="ic" /><b>Offer</b><br><small>to the seller</small></div>
  <div v-click class="arrow">→</div>
  <div v-click class="node sky" style="width:11rem"><ph-house class="ic" /><b>9,680 homes</b><br><small>bought in Q3 2021</small></div>
  <div v-click class="arrow">→</div>
  <div v-click class="node rose" style="width:11rem"><ph-house class="ic" style="color:#dc2626" /><b>3,032 homes</b><br><small>sold in Q3 2021</small></div>
</div>

<v-click>

What was missing between the forecast and the purchase?

</v-click>

</div>

[^1]: Zillow Group, Q3 2021 Shareholder Letter, 2 Nov 2021. https://www.sec.gov/Archives/edgar/data/1617640/000161764021000085/exhibit993.htm

<!--
Option B: use Zillow instead of the fly book: switch `hide` on the three fly-book slides and on these three. Also change the fly-book paragraph in the study notes' "Why this matters".
Zillow: "Higher-than-anticipated conversion rates during Q3 resulted in the purchase of 9,680 homes", and it expected to buy close to 9,000 more in Q4.
-->

---
hide: true
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:16rem"><div class="text-5xl font-bold" style="color:#dc2626">−&#36;304 million</div><div>write-down on the homes it owned, Q3 2021</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:15rem"><div class="text-5xl font-bold">closed</div><div>Zillow Offers wound down</div></div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:14rem"><div class="text-5xl font-bold">25%</div><div>of Zillow's staff to go</div></div></div>
</div>

<br>

<v-click>

Zillow: "unable to accurately forecast future home prices at different times in both directions"

</v-click>

Zillow Q3 2021 letter[^1][] · press release[^2][]

[^1]: Zillow Group, Q3 2021 Shareholder Letter, 2 Nov 2021.
[^2]: Zillow Group, "Zillow Group Reports Third-Quarter 2021 Financial Results & Shares Plan to Wind Down Zillow Offers Operations", 2 Nov 2021. https://www.sec.gov/Archives/edgar/data/1617640/000161764021000085/q32021991.htm

<!--
Option B, second slide. The write-down came from "unintentionally purchasing homes at higher prices than our current estimates of future selling prices".
-->

---
hide: true
---

# Option B · What would have stopped the buying?

<carbon-home class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-chart-line-up class="ic" /><b>Price forecast</b></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:10rem"><ph-handshake class="ic" /><b>Offer</b><br><small>to the seller</small></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:13rem"><ph-shield-check class="ic" /><b>Limit</b><br><small>on purchases without a person</small></div>
  <div v-click="1" class="arrow">→</div>
  <div class="node sky no-shrink" style="width:10rem"><ph-house class="ic" /><b>Purchase</b></div>
</div>

</div>

<!--
Option B, third slide. The letter does not say which checks the buying had. A limit on what the loop may buy without a person is our reading, not Zillow's words.
-->

---

# Can a clock be trusted?

<carbon-alarm class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><ph-hourglass class="ic" /><b>It can run late, or be dropped</b>under high load, for example at the start of every hour</div>
  <div v-click class="card"><ph-calendar-x class="ic" style="color:#dc2626" /><b>It can stop</b>in a public repository, after 60 days with no activity</div>
</div>

<div class="text-sm opacity-70">

GitHub Docs[^1][]

</div>

<v-click>

> [!WARNING]
> You will not notice a run that never happened.

</v-click>

</div>

[^1]: GitHub Docs, "Events that trigger workflows", `schedule`. https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

<!--
GitHub: "If the load is sufficiently high enough, some queued jobs may be dropped." GitHub's advice: "schedule your workflow to run at a different time of the hour". That is why the example runs at 02:30, not at 02:00.
Knowing that a scheduled run happened, and retrying it, is Week 8.
-->

---

# What can a green build hide?

<carbon-warning-alt class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1rem">
  <div v-click class="card"><ph-pencil-simple class="ic" /><b>A missing check</b>green means the tests you wrote passed</div>
  <div v-click class="card"><ph-ruler class="ic" /><b>A threshold set too low</b>the model met the bar you chose</div>
  <div v-click class="card"><ph-skip-forward class="ic" /><b>A skipped test</b>skipped counts as green</div>
  <div v-click class="card"><ph-eye-slash class="ic" /><b>A workflow that never ran</b>no run, no red</div>
</div>

<v-click>

CrowdStrike's Content Validator **ran**, and **passed** the file that affected 8.5 million Windows devices.

</v-click>

<v-click>

> [!TIP]
> After every incident, find the check that was missing, and add it to CI.

</v-click>

</div>

<!--
"Why did CI not catch it?" has an answer: CI checked what it was told to.
A workflow that never ran: one outside the root `.github/workflows/`, or a schedule GitHub switched off after 60 days. Week 6's gate gave "skipped" its own status for the same reason a skipped test is dangerous.
-->

---
layout: section
---

# 6 · Versioning

<!--
About 8 minutes. CT makes new models without a commit, so a release tag alone no longer names the model. Branching options are here because this is where the team chooses one. A model is code and data, so the same commit retrained on new data gives a new model.
-->

---

# What identifies a model?

<carbon-version class="icon-corner" />

<div class="middle">

<div class="flow" style="margin-bottom:0"><div class="node sky" style="width:16rem"><ph-cube class="ic" /><b>One model in production</b></div></div>

<div v-click>
  <div class="split-stem"></div>
  <div class="split-bar" style="width:50rem"></div>
  <div class="flow" style="margin-top:0; gap:0.5rem">
    <div class="node violet no-shrink" style="width:12rem"><ph-git-commit class="ic" /><b>Git commit</b><br><small>which code · Week 3</small></div>
    <div class="node green no-shrink" style="width:12rem"><ph-database class="ic" /><b>Data md5</b><br><small class="mono">a8fd7b4f…</small><small>which data · Week 4</small></div>
    <div class="node amber no-shrink" style="width:12rem"><ph-sliders class="ic" /><b>Params</b><br><small>which settings · Week 3</small></div>
    <div class="node sky no-shrink" style="width:12rem"><ph-tag class="ic" /><b>Registry version</b><br><small>which file · Week 3</small></div>
  </div>
</div>

<v-click>

The lab's `make trace` prints all four for the model behind an alias.

</v-click>

</div>

<!--
Ordinary software needs one of these; a trained model needs four. Week 6 added the gate verdict and `criteria_version` to the same trace.
-->

---
class: fn-inline
clicks: 1
---

# Branching options

<carbon-branch class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-git-commit class="ic" /><b>Trunk-based development</b>everyone merges into <code>main</code> at least once a day<br><small>fits: small changes and a fast CI</small></div>
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-git-pull-request class="ic" /><b>GitHub flow</b>a branch and a pull request for each change, then merge<br><small>fits: one version in production</small></div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-git-fork class="ic" /><b>Git flow</b><code>develop</code>, feature, release and hotfix branches<br><small>fits: several released versions in use at once</small></div>
</div>

Our model service has one version in production. Which one fits?

<div class="text-sm opacity-70">

GitHub Docs[^1][] · Driessen[^2][]

</div>

</div>

[^1]: GitHub Docs, "GitHub flow". https://docs.github.com/en/get-started/using-github/github-flow
[^2]: Vincent Driessen, "A successful Git branching model", 2010, note of 5 March 2020. https://nvie.com/posts/a-successful-git-branching-model/

<!--
Driessen, who wrote Git flow, added in 2020: a team that delivers continuously should use a simpler workflow "like GitHub flow". Trunk-based development: DORA, "Capabilities: Trunk-based development", and trunkbaseddevelopment.com.
A retrain needs no branch: a scheduled workflow runs on the newest commit of the default branch.
-->

---

# Which model made this prediction?

<carbon-branch class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:9rem"><ph-git-branch class="ic" /><b>A short branch</b></div>
  <div class="arrow-l">pull request, CI<span class="arrow">→</span></div>
  <div class="node violet" style="width:8rem"><ph-git-commit class="ic" /><b><code>main</code></b></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:10rem"><ph-tag class="ic" /><b><code>v1.4.0</code></b><br><small>a release tag: the code</small></div>
</div>

<div v-click="1" class="flow" style="gap:0.5rem">
  <div class="node amber" style="width:9rem"><ph-clock class="ic" /><b>Nightly retrain</b><br><small>on <code>v1.4.0</code></small></div>
  <div class="arrow">→</div>
  <div class="node" style="width:8rem"><b>version 7</b><br><small>Monday</small></div>
  <div class="node" style="width:8rem"><b>version 8</b><br><small>Tuesday</small></div>
  <div class="node" style="width:8rem"><b>version 9</b><br><small>Wednesday</small></div>
</div>

<v-click at="2">

A user reports a bad prediction from Tuesday. The tag cannot say which model made it.

</v-click>

<v-click at="3">

**Version 8**: the one `@champion` pointed to on Tuesday (its `promoted_at` tag). Its run holds the commit, the data md5 and the params.

</v-click>

</div>

<!--
The branch, the pull request and the release tag are ordinary software practice; the second row is what ML adds. Today's `@champion` may not be the model that made the prediction. In Week 9, the service returns the model version with every prediction, which closes this gap.
-->

---
layout: section
---

# 7 · Red flags and good practices

<!--
Each of these happens at work with any CI tool. The lab-specific traps are on a hidden slide; show them at the start of the lab session.
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
| workflow inside the lab folder | you push, and nothing runs | `make install-ci` copies it to the root |
| `astral-sh/setup-uv@v9` | `unable to find version v9` | pin `@v9.0.0` |
| no `.env` on the runner | `./.env: No such file or directory` | `make ci` copies `.env.example` |
| a test with no layer marker | it never runs in CI | `pytest -m "not unit and not data and not eval and not integration"` must select 0 |
| no `paths:` filter | every commit in the repository starts a build | scope the trigger to the lab |
| `actions/checkout` default | only the last commit is fetched | `git rev-parse` works; anything using history does not |

</div>

</div>

<!--
Hidden: lab-specific. Show it at the start of the lab session instead.
`actions/checkout` defaults to `fetch-depth: 1`.
-->

---

# Pin the linter and its rules

<carbon-rule class="icon-corner" />

<div class="middle">

The same code, two rule sets of ruff 0.16.1:

<div class="flow" style="margin-top:1.5rem">
  <div class="node rose" style="width:16rem"><ph-warning class="ic" /><b>ruff's default today</b><br><span class="text-3xl font-bold">22</span><small>findings, 10 rules</small></div>
  <div class="node green" style="width:16rem"><ph-check-circle class="ic" /><b><code>select = ["E4", "E7", "E9", "F"]</code></b><br><span class="text-3xl font-bold">2</span><small>findings, both unused imports</small></div>
</div>

<v-click>

> [!TIP]
> Pin the version of every tool CI runs, and list the linter's rules explicitly, so a build fails only when your code changes.

</v-click>

</div>

<!--
Measured on 16 Oct 2026 on the Week 6 lab's solution, the code Week 7 starts from. Older ruff releases selected only `E4, E7, E9, F`; the docs' "Default rules" page now lists a much wider set, so an unpinned linter can fail a build on a day you changed nothing. The lab pins `ruff==0.16.1` in a `lint` group.
-->

---

# Key the cache on the lock file

<carbon-archive class="icon-corner" />

<div class="middle">

CI saves the installed packages between runs, to install faster. Then `uv.lock` changes:

<div class="flow" style="margin-top:1rem">
  <div class="node rose" style="width:12rem"><b>key = branch name</b></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:22rem">same key, the old cache is reused<br><small>CI tests last month's packages</small></div>
</div>

<div v-click class="flow">
  <div class="node green" style="width:12rem"><b>key = hash of <code>uv.lock</code></b></div>
  <div class="arrow">→</div>
  <div class="node green" style="width:22rem">new key, a fresh install<br><small>CI tests the packages in the lock file</small></div>
</div>

<v-click>

> [!TIP]
> Key every cache on a hash of the files that define its contents.

</v-click>

</div>

<!--
setup-uv's `enable-cache: true` does this by default: its key includes a hash of `uv.lock`, `pyproject.toml` and requirements files (its README, `cache-dependency-glob`). The cache only saves the download; `uv sync --locked` still decides what is installed.
When CI fails and your laptop does not, clear the cache before you debug.
-->

---

# Make switching a check off visible

<carbon-view-off class="icon-corner" />

<div class="middle">

The gate says NO-GO every week, and the team is tired of red builds. Someone adds one line to `ci.yml`:

```yaml
pipeline:
  continue-on-error: true    # the run is green even when this job fails
```

<div v-click class="flow">
  <div class="node rose" style="width:12rem"><ph-stamp class="ic" /><b>gate: NO-GO</b></div>
  <div class="arrow-l fail">continue-on-error<span class="arrow">→</span></div>
  <div class="node green" style="width:12rem"><ph-check-circle class="ic" /><b>the run: green</b><br><small>nobody reads the gate</small></div>
</div>

<v-click>

> [!TIP]
> Weaken a check only in a reviewed pull request, with a reason, an owner, and a date to look at it again.

</v-click>

</div>

<!--
GitHub Docs: `continue-on-error` "prevents a workflow run from failing when a job fails". The same move exists everywhere: `|| true`, a skipped test, a threshold lowered to the last score.
-->

---
layout: section
---

# 8 · Wrap-up

<!--
About 8 minutes. The lab's solution is released at the Week 8 lecture; the hidden "The red build, measured" can be shown then.
-->

---

# This week's workflows

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-git-pull-request class="ic" /><b>push, PR</b></div>
  <div class="arrow">→</div>
  <div v-click="1" style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node green no-shrink" style="width:9rem"><b>lint</b></div>
    <div class="node green no-shrink" style="width:9rem"><b>tests</b><br><small>unit · data · eval</small></div>
  </div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node sky no-shrink" style="width:11rem"><b>pipeline</b><br><small>contract … gate</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node no-shrink" style="width:8rem"><b>evidence</b><br><small>summary, artifact</small></div>
</div>

<div v-click="4" class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-clock class="ic" /><b>a person, a clock</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:11rem"><b>retrain</b><br><small>the same contract and gate</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:8rem"><b>evidence</b></div>
</div>

</div>

<!--
Both workflows stop at the gate: they do not register, promote or deploy. The lab's Exercise 5 asks why.
Back to CrowdStrike: the second row is the content path, now with the checks of the first.
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<div class="middle">

<div class="text-xl">

<v-clicks>

- Every path into production needs the same checks, and a retrained model is one of them.
- CI runs the checks on every change, automatically, on a separate machine.
- ML adds tests for the data and the model; give every test a layer.
- Keep one definition of the pipeline, and let every workflow call it.
- Continuous training has no reviewer: the data contract and the gate do that job.

</v-clicks>

</div>

</div>

<!--
None of these takeaways needs GitHub: the lab's `make ci-local` runs the same pipeline definition on a laptop.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><carbon-alarm class="ic" /><b>Did the scheduled run happen?</b>A cron can run late, or stop, and tell nobody.<br><b>→ Week 8:</b> orchestration, retries, run history</div>
  <div v-click class="card"><carbon-application class="ic" /><b>How does the model reach users?</b>CI stops at the gate.<br><b>→ Week 9:</b> serving the model</div>
  <div v-click class="card"><carbon-deployment-pattern class="ic" /><b>Should a GO model ship by itself?</b>And to whom first?<br><b>→ Week 10:</b> staged rollout</div>
  <div v-click class="card"><carbon-chart-line class="ic" /><b>Is it still good next month?</b>CI tests one model on one test set.<br><b>→ Weeks 11–12:</b> monitoring and drift</div>
</div>

</div>

<!--
Week 8's line: cron in a CI system runs one workflow on a clock; an orchestrator owns a graph of work, its state, its retries and its history.
Week 13 uses this week's artifacts as evidence for the Model Card.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **#** | **Exercise** | **What you show** |
| --- | --- | --- |
| 1 | The autograder workflow | what `autograde.yml` is for, and what it runs |
| 2 | One pipeline definition | `make ci` runs lint, tests, pipeline and gate, with the stack down |
| 3 | Sort the tests into layers | the unmarked check selects 0 |
| 4 | The code path | `ci.yml`, a green run on GitHub, its summary and artifact |
| 5 | Continuous training | `ct.yml`, started by hand with a reason |
| 6 | Inspect a failed build (optional) | a failed run on GitHub, and what it told you |

</div>

Exercises 1, 5 and 6 have written answers, in `answers.md`; Exercise 6 is optional. Homework 2 is out this week.

</div>

<!--
Students need Actions enabled on their own copy of the repository (Settings → Actions → General). The stack is needed only for the `live` tests.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

<div class="middle">

- Why does a retrained model need the same checks as a code change?
- What does CI add to the tests you can run on your laptop, and what does it cost?
- Which test layers does ML add, and how does CI run one layer at a time?
- What does a `uses:` step run, and what can it do?
- Why pin an action, and how can a pin fail?
- What identifies a model's version, and what does a release tag name?
- Which branching model fits a team with one version in production?
- What can a green build hide?

</div>

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
