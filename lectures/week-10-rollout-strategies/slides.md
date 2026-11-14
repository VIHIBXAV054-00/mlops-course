---
theme: default
title: Week 10 — Rollout Strategies
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers canary, blue/green and shadow releases, declarative deployment with
  KServe, a measured traffic split, smoke testing, rollback and basic load testing.
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

# Week 10: Rollout Strategies

<carbon-deploy class="icon-corner" />

**Lifecycle of Artificial Intelligence Systems**

- Rollout strategies
- Tests for serving
- Rolling out
- Rollback

<!--
Last week the model became reachable. Today we replace it on real traffic, a little at a time, with a way back. The view is the ML engineer's: what you decide, and what you hand to the team that runs the platform.
-->

---

# Recap: what do we hand over?

<carbon-package class="icon-corner" />

<div class="middle">

The pipeline ends with an approved model. What does the team that runs the service need from us?

<div class="flow">
  <div class="node amber no-shrink" style="width:9rem"><ph-database class="ic" /><b>Versioned data</b></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:9rem"><ph-flow-arrow class="ic" /><b>Pipeline</b><br><small>train, evaluate</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><ph-shield-check class="ic" /><b>Approved model</b><br><small>gate: GO</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:11rem; border-style:dashed"><span v-click="1"><ph-cube class="ic" /><b>A container image</b><br><small>one artifact they can run anywhere</small></span><span v-click.hide="1"><b>?</b></span></div>
</div>

</div>

<!--
Week 9. A model file alone is not something a DevOps or platform engineer can run: they need one artifact that starts the same way on a laptop, in CI and in the cluster.
-->

---

# What goes into the container?

<carbon-container-software class="icon-corner" />

<div class="middle">

<div style="border:2px solid #0284c7; border-radius:0.8rem; padding:1rem 1.2rem; max-width:44rem; margin:0 auto">
<div class="text-center text-sm" style="color:#0284c7; margin-bottom:0.6rem"><b>the image</b></div>
<div class="cards" style="grid-template-columns:repeat(3,1fr); margin:0">
  <div v-click class="card"><ph-file class="ic" /><b>The model file</b>the learned weights</div>
  <div v-click class="card"><ph-file-py class="ic" /><b>The runtime</b>the Python version</div>
  <div v-click class="card"><ph-stack class="ic" /><b>The packages</b>the versions that trained it</div>
  <div v-click class="card"><ph-code class="ic" /><b>The serving code</b>loads the model, answers requests</div>
  <div v-click class="card"><ph-shield-check class="ic" /><b>The input contract</b>which requests are legal</div>
  <div v-click class="card"><ph-tag class="ic" /><b>The metadata</b>model version, gate verdict</div>
</div>
</div>

</div>

<!--
Week 9's list. If any one is missing, the container starts but answers wrongly or cannot say which model it is. Today one item moves out: the model file can come from a store when the container starts, so one image serves several model versions.
-->

---

# How is the model called?

<carbon-flash class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber no-shrink" style="width:10rem"><ph-user class="ic" /><b>One request</b><br><small>one patient</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:10rem"><ph-cube class="ic" /><b>Service</b><br><small>always running</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>One prediction</b><br><small>while the caller waits</small></div>
  <div class="no-shrink" style="width:7rem"><b v-click="1">Online</b></div>
</div>

<div v-click="2" class="flow">
  <div class="node amber no-shrink" style="width:10rem"><ph-table class="ic" /><b>Many rows</b><br><small>every patient, every night</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:10rem"><ph-calendar class="ic" /><b>Scheduled job</b><br><small>runs, then stops</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><ph-rows class="ic" /><b>A table of predictions</b><br><small>read later</small></div>
  <div class="no-shrink" style="width:7rem"><b v-click="3">Batch</b></div>
</div>

</div>

<!--
Week 9. Same model, same container; what differs is who waits and when. The hospital's diabetes score could be either: online when a doctor opens a patient's record, batch when the ward is scored every night.
-->

---

# Batch or online?

<carbon-compare class="icon-corner" />

<div class="middle">

<div class="text-lg">

| | **Batch** | **Online** |
| --- | --- | --- |
| Pros | <span v-click="1">cheap · heavy models are fine · errors fixed before anyone reads</span> | <span v-click="2">fresh input · any new case</span> |
| Cons | <span v-click="3">answers hours old</span> | <span v-click="4">latency limit · runs all day</span> |

</div>

</div>

<!--
Week 9's examples: Spotify's weekly playlist and a bank's monthly churn list are batch; a card payment's fraud score and an Uber Eats delivery time are online. A bad batch table can be rebuilt before anyone reads it; a bad online answer is already with the user, which is why today's rollout matters most for online models.
-->

---

# Batch and online combined

<carbon-layers class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div v-click class="card"><ph-calendar class="ic" /><b>Batch, then online</b>heavy work at night, the last step per request</div>
  <div v-click class="card"><ph-database class="ic" /><b>A cache</b>a repeated input gets a stored answer</div>
  <div v-click class="card"><ph-lightning class="ic" /><b>Streaming features</b>online, with inputs minutes old</div>
  <div v-click class="card"><ph-device-mobile class="ic" /><b>On the device</b>the model ships inside the app</div>
  <div v-click class="card"><ph-arrows-split class="ic" /><b>Champion and challenger</b>two models answer, one answer is sent</div>
</div>

<v-click>

Each serves one approved version. Today: how a new version takes its place.

</v-click>

</div>

<!--
Week 9's architectures. Each one changes how a new model version reaches users: a cache must be cleared, an app must be updated, and champion and challenger side by side is today's shadow release.
-->

---
layout: section
---

# 1 · Rollout strategies

<!--
About 12 minutes: deploy and release, then the strategies. No case yet; the cases come once the strategies have names.
-->

---

# What is the difference between deploy and release?

<carbon-rocket class="icon-corner" />

<div class="middle text-xl">

| | **Means** | **Who decides** |
| --- | --- | --- |
| **Deploy** | <span v-click="1">the new version runs on the servers</span> | <span v-click="3">the platform team</span> |
| **Release** | <span v-click="2">users get the new version's answers</span> | <span v-click="4">for a model, the ML engineer</span> |

</div>

<!--
Week 9's new image did both at once, for every user. Kästner (Machine Learning in Production, ch. 19) and the Google SRE Workbook (ch. 16) separate the two steps; the rollout strategies of this section live between them.
-->

---

# Where we are: deploy

<Lifecycle stage="deploy" width="70%" />

Today: release the new model on real traffic, a little at a time, with a rollback plan.

<!--
Deploy, because a rollout decides which model serves which request. The smoke test and the rollback reach into operate; watching the service over time is Week 11.
-->

---
layout: center
---

# How do we check a new model version on real traffic?

<v-click>

- The old and the new version running at the same time
- A traffic split, and a check on the new version's answers

</v-click>

<!--
A Deployment converges on one image, so it cannot hold two versions: a new image replaces every pod, and the probes ask only whether the new pods are healthy. The three strategies that follow are three ways to split the traffic.
-->

---

# Canary

<carbon-chart-line class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber no-shrink" style="width:7rem"><ph-arrows-split class="ic" /> router</div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:5rem">90%<span class="arrow">→</span></div><div class="node sky no-shrink" style="width:9rem">v1, running</div></div>
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:5rem">10%<span class="arrow">→</span></div><div class="node violet no-shrink" style="width:9rem">v2, new</div></div>
  </div>
</div>

A small percentage of traffic goes to v2. If its metrics stay healthy, the percentage grows step by step[^1][].

<div v-click="1" class="proscons">
<div class="pro"><b>Pros</b><ul><li>real users, real inputs</li><li>a bad version reaches few users</li><li>rollback: set the canary percentage to 0</li></ul></div>
<div class="con"><b>Cons</b><ul><li>some users get v2's answers</li><li>a small percentage gives few answers to judge</li><li>two versions run at once</li></ul></div>
</div>

</div>

[^1]: Betsy Beyer et al. (eds.), *The Site Reliability Workbook*, O'Reilly 2018, ch. 16 "Canarying Releases". https://sre.google/workbook/canarying-releases/

<!--
Google SRE: a canary is "a partial and time-limited deployment of a change in a service and its evaluation". The book's own example: 20% errors in a canary with 5% of the traffic is 1% errors for all users. Miners took canaries into coal mines: if the bird stopped singing, the air was dangerous.
-->

---

# Canary or A/B test?

<carbon-compare class="icon-corner" />

<div class="middle">

| | **Canary** | **A/B test** |
| --- | --- | --- |
| Asks | does v2 break anything? | <span v-click="1">is v2 better?</span> |
| Watches | errors, latency, odd predictions | <span v-click="1">a business metric: clicks, sales, readmissions</span> |
| Runs for | minutes to hours | <span v-click="2">often a week or more</span> |
| Needs | a small share | <span v-click="2">enough users for a statistical test</span> |
| Ends in | promote or roll back | <span v-click="3">keep v1 or v2</span> |

<div v-click="4" class="text-center" style="margin-top:0.8rem">

First "does it work?", then "is it better?"[^1][]

</div>

</div>

[^1]: Google Cloud, *Practitioners guide to MLOps*, May 2021, pp. 25–26. https://services.google.com/fh/files/misc/practitioners_guide_to_mlops_whitepaper.pdf

<!--
Google: canary, blue/green and shadow "are often used to perform smoke testing"; online experiments are "the final criterion". Kästner: run an experiment "for at least one week".
GPT-4o's A/B test measured whether users liked the answers.
-->

---

# Blue/green

<carbon-direction-fork class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber no-shrink" style="width:7rem"><ph-arrows-split class="ic" /> router</div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:7rem">100% → 0%<span class="arrow">→</span></div><div class="node sky no-shrink" style="width:9rem">blue: v1</div></div>
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:7rem">0% → 100%<span class="arrow">→</span></div><div class="node green no-shrink" style="width:9rem">green: v2</div></div>
  </div>
</div>

Both versions run. All traffic switches at once, and can switch back.

<div v-click="1" class="proscons">
<div class="pro"><b>Pros</b><ul><li>rollback in seconds: switch back</li><li>every user gets the same version</li><li>simple to run and explain</li></ul></div>
<div class="con"><b>Cons</b><ul><li>after the switch, every user gets v2</li><li>twice the servers while both run</li><li>no small first group of users</li></ul></div>
</div>

</div>

<!--
Blue and green are just names for the two copies. The old copy stays running after the switch, which is what makes the way back fast. It fits a change that must reach everyone at the same moment, such as a new rule from 1 January.
-->

---

# Shadow

<carbon-view-off class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber no-shrink" style="width:7rem"><ph-arrows-split class="ic" /> router</div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:5rem">100%<span class="arrow">→</span></div><div class="node sky no-shrink" style="width:11rem">v1: its answer is sent</div></div>
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:5rem">a copy<span class="arrow">→</span></div><div class="node violet no-shrink" style="width:11rem; border-style:dashed">v2: its answer is stored</div></div>
  </div>
</div>

Both versions answer every request. Users see only v1's answer[^1][].

<div v-click="1" class="proscons">
<div class="pro"><b>Pros</b><ul><li>no user sees v2's answer</li><li>both models answer the same real inputs</li></ul></div>
<div class="con"><b>Cons</b><ul><li>twice the compute</li><li>needs a store to compare the answers</li><li>shows nothing about how users react</li><li>v2 must trigger no actions: no e-mails, no writes</li></ul></div>
</div>

</div>

[^1]: Kästner, *Machine Learning in Production*, ch. 19. https://mlip-cmu.github.io/book/19-testing-and-experimenting-in-production.html

<!--
Kästner: shadow releases "run two variants in parallel, but show only the predictions of the previous system or model to the user". Week 9 showed the same set-up as champion and challenger side by side. This course has no store for the shadow answers, so the lab has no shadow exercise.
-->

---

# Comparing the three

<carbon-compare class="icon-corner" />

<div class="middle text-lg">

| | **Canary** | **Blue/green** | **Shadow** |
| --- | --- | --- | --- |
| Users affected | <span v-click="1">a small share</span> | <span v-click="1">all, after the switch</span> | <span v-click="1">none</span> |
| Infrastructure cost | <span v-click="2">a few extra pods</span> | <span v-click="2">2×, while both run</span> | <span v-click="2">2×, all the time</span> |
| Rollback | <span v-click="3">canary percentage to 0</span> | <span v-click="3">switch back</span> | <span v-click="3">not needed</span> |
| What it tests | <span v-click="4">v2 with real users</span> | <span v-click="4">v2 runs in production</span> | <span v-click="4">v2 on real inputs</span> |

</div>

<!--
None of the three tells you whether v2 is better for the business: that is the A/B test. A team often combines them: shadow first, then a small canary, then a full switch.
-->

---
layout: section
---

# 2 · Tests for serving

<!--
About 12 minutes: how you know a deployed model is right before users depend on it. Probe, smoke test and load test, what each one catches, and when it runs. The lab's Exercise 4 runs the smoke test and the optional Exercise 6 the load test.
-->

---

# A bad model is deployed by accident. How do you notice?

<carbon-checkmark class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node green" style="width:9rem"><ph-cube class="ic" /><b>2/2 Running</b></div>
  <div class="node green" style="width:9rem"><ph-heartbeat class="ic" /><b>/health 200</b></div>
  <div class="node green" style="width:9rem"><ph-check-circle class="ic" /><b>every request 200</b></div>
  <div class="node green" style="width:9rem"><ph-arrows-split class="ic" /><b>10% of patients</b></div>
</div>

<v-click>

Is anything wrong?

</v-click>

<div style="display:flex; justify-content:center; align-items:flex-start; gap:2.5rem; text-align:center; margin-top:0.8rem">
  <div v-click><div style="font-size:2.2rem; font-weight:700; color:#dc2626">0 of 192</div><div>test patients flagged</div></div>
  <div v-click><div style="font-size:2.2rem; font-weight:700">0.6510</div><div>accuracy: the share of negatives</div></div>
  <div v-click><div style="font-size:2.2rem; font-weight:700">0.8407</div><div>ROC AUC, above our 0.8345</div></div>
</div>

</div>

<!--
The canary here is a `C: 0.001` model that failed the gate (3 passed, 9 failed, 4 skipped) and was published by force. Its F1 is 0.0000. The model still ranks patients well, which is why its ROC AUC is high; it never crosses the threshold.
Gate on ROC AUC alone and you would promote it.
-->

---

# Probe, smoke test, load test

<carbon-test-tool class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-heartbeat class="ic" /><b>Probe</b>Is the process alive?<br><small>every few seconds, written by the platform team</small><div v-click="1" style="margin-top:0.5rem; color:#dc2626">misses: which model, what it predicts</div></div>
  <div v-click="2" class="card"><ph-shield-check class="ic" /><b>Smoke test</b>A few requests: is this the right model, and are its answers sane?<br><small>once per release, written by the ML engineer</small><div v-click="3" style="margin-top:0.5rem; color:#dc2626">misses: many requests at once</div></div>
  <div v-click="4" class="card"><ph-gauge class="ic" /><b>Load test</b>Many requests at once: does it stay fast, without errors?<br><small>before you promise a latency</small><div v-click="5" style="margin-top:0.5rem; color:#dc2626">misses: whether real users like the answers</div></div>
</div>

</div>

<!--
"Smoke test" comes from hardware: switch the device on and see whether smoke comes out. It is short and shallow on purpose, and it runs on every release. Only the ML engineer knows what a sane answer is for this model, so they write it. What all three miss comes later today, with a case.
-->

---

# A smoke test for a model

<carbon-list-checked class="icon-corner" />

<div class="middle">

| **Check** | **Asks** |
| --- | --- |
| identity | Is this the version we released, and did it pass the gate? |
| contract | Are impossible inputs rejected, such as `glucose = 0`? |
| behaviour | Are the answers sane: a clear case positive, a clear non-case negative, not one constant answer? |
| protocol | Does every endpoint give the same answer? |

</div>

<!--
The behaviour check is the ML engineer's: only they know what a sane answer is for this model. Identity catches a pod that still runs last month's model. In the lab, `make smoke` exits non-zero when a check fails, so a rollout script can stop on it.
The "clearly ill" patient has a glucose of 183 and a BMI of 40.5.
-->

---
hide: true
---

# After the lab: `make smoke` on the canary

<carbon-list-checked class="icon-corner" />

```text {3,5,9}
    pass  identity.health                  status=ok revision=diabetes-predictor-00003 store_version=v3
    pass  identity.version                 expected v3, serving v3
    FAIL  identity.gate                      gate_verdict=NO-GO (a release needs GO)
    pass  contract.illegal_rejected        422 naming ['greater_than(0)']
    FAIL  behaviour.positive_is_positive   p=0.4751 -> 0
    pass  behaviour.negative_is_negative   p=0.2773 -> 0
    pass  behaviour.not_a_constant         probability spread 0.1978 (minimum 0.1)
    pass  protocol.v1_agrees               /predict 0 vs V1 0
  FAIL — 6 passed, 2 failed
```

<!--
Hidden: it is the result of the lab's Exercise 4. Show it after the lab, for example in the Week 11 recap. The spread check passed: the model is not a constant, it just never says yes. With only that check we would have promoted it.
-->

---

# Smoke test before traffic

<carbon-health-cross class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node violet" style="width:10rem"><ph-cube class="ic" /><b>New version</b><br><small>0% of traffic</small></div>
  <div class="arrow-l">its own address<span class="arrow">→</span></div>
  <div class="node green" style="width:10rem"><ph-shield-check class="ic" /><b>Smoke test</b></div>
  <div v-click="1" class="arrow-l">passed<span class="arrow">→</span></div>
  <div v-click="1" class="node sky" style="width:10rem"><ph-users-three class="ic" /><b>10% of patients</b></div>
</div>

<v-click at="2">

> [!WARNING]
> 10% of traffic is 10% of real patients. They did not choose to try the new model.

</v-click>

</div>

<!--
The serving platform gives each version its own address (in KServe, a tag such as `latest-diabetes…`), so the smoke test can call v2 before it gets any share. A canary limits how many people a bad model reaches; it does not make the model safe for them.
-->

---
hide: true
---

# Declared and measured

<carbon-chart-bar class="icon-corner" />

<div class="middle">

The declaration says 10%. In the lab, a Job inside the cluster counted who answered:

<div v-click="1" style="margin-top:1.5rem">
  <div style="display:flex; align-items:center; gap:0.6rem"><div style="width:5.5rem">n = 200</div><div style="display:flex; width:36rem; height:1.8rem; color:white; font-weight:700"><div style="width:89.5%; background:#0284c7; padding-left:0.4rem">v1 · 179</div><div style="width:10.5%; background:#7c3aed; text-align:center">21</div></div><div><b>10.5%</b></div></div>
</div>
<div v-click="2" style="margin-top:0.5rem">
  <div style="display:flex; align-items:center; gap:0.6rem"><div style="width:5.5rem">n = 400</div><div style="display:flex; width:36rem; height:1.8rem; color:white; font-weight:700"><div style="width:91.8%; background:#0284c7; padding-left:0.4rem">v1 · 367</div><div style="width:8.2%; background:#7c3aed; text-align:center">33</div></div><div><b>8.2%</b></div></div>
</div>

<v-click at="3">

Is the router broken?

</v-click>

</div>

<!--
Hidden until after the lab: these are the lab's Exercise 3 results, and why the share varies is its written question (model answer in `.agents/grading/week-10.md`).
-->

---

# Load test terms

<carbon-meter class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:9rem"><ph-users-three class="ic" /><b>Requests</b></div>
  <div class="arrow">→</div>
  <div class="node violet" style="width:9rem"><ph-hourglass class="ic" /><b>Queue</b></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:9rem"><ph-cube class="ic" /><b>One worker</b></div>
</div>

<div class="text-sm">

| **Term** | **Means** |
| --- | --- |
| concurrency | requests in flight at the same time |
| throughput | requests completed per second (rps) |
| error rate | the share of requests that failed |
| p50 / p95 / p99 | the latency under which 50, 95, 99% of requests finished |

</div>

</div>

<!--
Week 9: quote percentiles, never the mean. These are the words the platform team uses when it asks "what load do you expect?". The rollout plan states the expected load in them.
-->

---
layout: center
---

# "Our model service handles 64 users."
# What do you ask?

<v-clicks>

- 64 at the same time, or 64 per second?
- With which p95?
- **With how many errors?**

</v-clicks>

<!--
Any latency number improves if the service fails faster. A p95 without an error rate beside it is not a measurement.
-->

---
hide: true
---

# Where does it stop improving?

<carbon-chart-line class="icon-corner" />

200 requests per level, from inside the cluster, one worker, one CPU:

```text {all|2-3|all}
  conc     rps  errors       p50        p95        p99
     1   123.6       0    7.20ms     9.19ms    11.13ms
     4   102.1       0   35.30ms    67.21ms    91.49ms
    16    94.1       0  100.79ms   526.69ms   775.62ms
    64    98.0       0  426.38ms  1657.05ms  1917.46ms
```

<v-clicks at="1">

- Read the rps column first.
- From concurrency 4 on, rps stays near 100 while p95 grows from 67 ms to 1.66 s.

</v-clicks>

<!--
Hidden: the lab's optional Exercise 6 result; show it after the lab, for example in the Week 11 recap.
A second run gave the same shape: 148 rps and p50 6.41 ms at concurrency 1, 106 rps and p95 1.59 s at 64. More replicas and autoscaling are the usual fix, and the platform team's job.
-->

---
layout: section
---

# 3 · Choosing a strategy

<!--
About 10 minutes: when each strategy is used, and who uses it. This is the ML engineer's main decision of the week.
-->

---

# What decides the choice

<carbon-decision-tree class="icon-corner" />

<div class="middle text-lg">

| **If the answer is yes** | **Canary** | **Blue/green** | **Shadow** |
| --- | :-: | :-: | :-: |
| Can one wrong answer harm a person? |  | <span v-click="1"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> | <span v-click="1"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> |
| Must every user get v2 at the same moment? | <span v-click="2"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> | <span v-click="2"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> | <span v-click="2"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> |
| Does the model trigger actions: e-mails, writes? |  |  | <span v-click="3"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> |
| Is compute tight? | <span v-click="4"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> | <span v-click="4"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> | <span v-click="4"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> |
| Are there few requests a day? |  |  | <span v-click="5"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> |
| Do you need to see how users react? | <span v-click="6"><ph-plus-circle-fill style="color:#16a34a; font-size:1.5em" /></span> |  | <span v-click="6"><ph-x-circle-fill style="color:#e11d48; font-size:1.5em" /></span> |

<div class="text-sm opacity-70 text-center" style="margin-top:0.6rem"><ph-plus-circle-fill style="color:#16a34a" /> fits well · <ph-x-circle-fill style="color:#e11d48" /> ruled out · empty: no effect</div>

</div>

<!--
Ask the room before each row. Harm: blue/green gives v2 to everyone at once. Side effects: a shadow v2 would send real e-mails. Few requests: a 10% canary of 300 requests a day (Hypothetical) is 30 answers, too few to judge. Not in the table: when true labels arrive late, no strategy judges accuracy in hours, so you watch proxies such as the positive rate. The ML engineer answers these from the model and the problem.
-->

---
layout: center
---

# Which strategy?

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1rem">
  <div class="card"><ph-currency-dollar class="ic" /><b>A credit-scoring model</b>a wrong answer refuses a loan<div v-click="1" style="margin-top:0.5rem"><b>→ shadow, then a small canary</b></div></div>
  <div class="card"><ph-shopping-cart class="ic" /><b>A shop's recommender</b>a million requests a day<div v-click="2" style="margin-top:0.5rem"><b>→ canary, then an A/B test</b></div></div>
  <div class="card"><ph-calendar class="ic" /><b>A tax model</b>a new law applies to everyone from 1 January<div v-click="3" style="margin-top:0.5rem"><b>→ blue/green</b></div></div>
  <div class="card"><ph-envelope class="ic" /><b>A model that picks who gets a discount e-mail</b>every answer sends an e-mail<div v-click="4" style="margin-top:0.5rem"><b>→ canary: shadow would send the e-mails</b></div></div>
  <div class="card"><ph-image class="ic" /><b>A photo app's auto-tagger</b>a wrong tag is easy to fix<div v-click="5" style="margin-top:0.5rem"><b>→ any of the three: canary is the simplest</b></div></div>
  <div class="card"><ph-chat-circle-text class="ic" /><b>A support chatbot's new LLM</b>answers in free text<div v-click="6" style="margin-top:0.5rem"><b>→ shadow to compare answers, or a canary: both work</b></div></div>
</div>

<!--
Ask the room before each click. The last two have more than one good answer: low stakes means the cheapest strategy wins, and the chatbot depends on whether the team can judge free-text answers without users. The lab asks the same question for our diabetes model.
-->

---
class: fn-inline
---

# Who uses which strategy?

<carbon-enterprise class="icon-corner" />

<div class="text-base" style="margin-top:0.5rem">

| **Team, model** | **Before everyone gets a new version** |
| --- | --- |
| Tesla, driver assistance | <span v-click="1">"shadow mode": runs in the car, does not take the controls[^1][]</span> |
| Uber, pricing and ETAs | <span v-click="2">shadow by default, then a small slice, automatic rollback[^2][]</span> |
| Booking.com, ~150 models | <span v-click="3">A/B tests on business metrics[^3][]</span> |
| GitHub Copilot, LLM | <span v-click="4">4,000+ offline tests, then staff first, "similar to canary testing"[^4][]</span> |
| Anthropic, Claude | <span v-click="5">spot checks, then small "canary" groups[^5][]</span> |

</div>

[^1]: Fred Lambert, Electrek, 16 Jan 2017. https://electrek.co/2017/01/16/tesla-enhanced-autopilot-shadow-mode/
[^2]: J. Wang, S. Wang and J. Li, Uber blog, 30 Oct 2025. https://www.uber.com/blog/raising-the-bar-on-ml-model-deployment-safety/
[^3]: L. Bernardi et al., "150 Successful Machine Learning Models", KDD 2019. https://doi.org/10.1145/3292500.3330744
[^4]: C. Adams and K. Finley, GitHub blog, 17 Jan 2025. https://github.blog/ai-and-ml/generative-ai/how-we-evaluate-models-for-github-copilot/
[^5]: Anthropic, 17 Sep 2025. https://www.anthropic.com/engineering/a-postmortem-of-three-recent-issues

<!--
Tesla: Musk called it a "non-actuating mode to assess reliability". Uber: shadow testing is part of over 75% of critical online use cases, and a rollback triggers when error rates, latency or CPU/GPU use cross a threshold. Booking.com: a better model offline did not always bring more business value, so each model is judged by an experiment. No team goes from the test set straight to all users.
-->

---
layout: section
---

# 4 · Rolling out

<!--
About 15 minutes. One case from the decision to the file: our diabetes model v2 as a canary. The lab's Exercises 1–3 do the same steps.
-->

---

# Use case: diabetes model

<carbon-health-cross class="icon-corner" />

<div class="middle text-lg">

We want to replace v1 with v2.

| | **Strategy** |
| --- | --- |
| Can one wrong answer harm a person? | <span v-click="1">yes → not blue/green</span> |
| Does the model trigger actions, like e-mails or writes? | <span v-click="2">no → shadow is possible</span> |
| Can the platform store and compare shadow answers? | <span v-click="3">not right now → not shadow</span> |

<div v-click="4" class="text-center text-xl" style="margin-top:1rem">

**→ canary**

</div>

</div>

<!--
The decision table from Section 3, applied to our model. The best fit would be shadow first, but our platform has nothing that stores and compares shadow answers, so the platform limits the choice. At work this is common: you choose from what the platform supports, and you say what you would need for the better option.
-->

---

# What the ML engineer hands over

<carbon-user-multiple class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.8rem">
  <div style="display:flex; flex-direction:column; gap:0.5rem">
    <div class="node sky no-shrink" style="width:16rem"><ph-cube class="ic" /><b>The container image</b><br><small>code, packages, runtime</small></div>
    <div v-click="1" class="node violet no-shrink" style="width:16rem"><ph-folder class="ic" /><b>The model version</b><br><small>v2 from the model store, gate: GO</small></div>
    <div v-click="2" class="node amber no-shrink" style="width:16rem"><ph-file-text class="ic" /><b>The rollout plan</b><br><small>strategy, checks, when to promote or roll back</small></div>
  </div>
  <div class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:16rem"><ph-users-three class="ic" /><b>The platform team</b><br><small>runs the cluster, splits the traffic, runs the rollback</small></div>
</div>

</div>

<!--
The ML engineer decides what the model needs. The platform team decides how the cluster does it. Kästner (ch. 13): "collaboration between operators, developers, and data scientists is essential". Load and latency targets are agreed together.
-->

---

# Recap: Kubernetes

<carbon-kubernetes class="icon-corner" />

<div class="middle">

Kubernetes runs containers on a group of machines, a **cluster**, and keeps them in the state you declare[^1][].

<div class="text-sm">

| | **Is** |
| --- | --- |
| **Pod** | the smallest unit Kubernetes runs: containers with one network address |
| **Deployment** | declares which image and how many pods, and keeps them running |
| **Service** | a stable address that sends each request to a ready pod |
| **Probe** | a request to each pod, such as `GET /health`: no answer, no traffic |

</div>

<v-click>

You write YAML files with the state you want. Kubernetes restarts, replaces and routes until the cluster matches them.

</v-click>

</div>

[^1]: Kubernetes docs, "Overview". https://kubernetes.io/docs/concepts/overview/

<!--
Week 9. The key idea is declarative: you do not tell Kubernetes to start a container, you write down what should be running, and its controllers keep that true. That is why a pod you delete by hand comes back.
-->

---

# What a Deployment cannot do

<carbon-kubernetes class="icon-corner" />

<div class="middle">

In plain Kubernetes, the Service sends each request to any ready pod. The traffic split is the ratio of pods.

<div class="flow" style="gap:0.3rem; margin-top:1rem">
  <div class="no-shrink" style="width:9rem"><b>10% to v2</b><br><small>10 pods</small></div>
  <div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node violet no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v2</small></div>
</div>

<div v-click="1" class="flow" style="gap:0.3rem">
  <div class="no-shrink" style="width:9rem"><b>3 pods</b><br><small>33% to v2</small></div>
  <div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node sky no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v1</small></div><div class="node violet no-shrink" style="width:2.6rem; padding:0.3rem 0"><small>v2</small></div>
</div>

<v-clicks at="2">

- One Deployment holds one version: a new image replaces every pod.
- The model is inside the image: a new model means a new image.

</v-clicks>

</div>

<!--
The Kubernetes docs show this canary with two Deployments behind one Service, the replica counts as the split. Our model needs 1 or 2 pods for its traffic, so 10% would mean running 10 pods only to get the split. This is a limit of plain Kubernetes, not of the model. Tools built for rollouts set the split in a router instead, independent of the number of pods.
-->

---
class: fn-inline
---

# KServe

<carbon-kubernetes class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-file-code class="ic" /><b>InferenceService</b><br><small>one YAML file per model</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:9rem"><ph-arrows-split class="ic" /><b>router</b></div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:4rem">90%<span class="arrow">→</span></div><div class="node sky no-shrink" style="width:9rem">revision 1: v1</div></div>
    <div class="flow" style="margin:0"><div class="arrow-l" style="min-width:4rem">10%<span class="arrow">→</span></div><div class="node sky no-shrink" style="width:9rem">revision 2: v2</div></div>
  </div>
  <div class="arrow">←</div>
  <div class="node green no-shrink" style="width:8rem"><ph-database class="ic" /><b>model store</b></div>
</div>

<div v-click>

- KServe runs on Kubernetes and serves models[^1][].
- Each change makes a new **revision**. The previous one keeps running.
- `canaryTrafficPercent` sets the traffic split.
- The model comes from a store: a new version is a new folder, not a new image.

<div class="text-sm opacity-70">

Other tools for the same job: Argo Rollouts[^2][] and Flagger[^3][] for any service on Kubernetes, SageMaker[^4][] on AWS.

</div>

</div>

</div>

[^1]: KServe docs (0.20), "Canary Rollout". https://kserve.github.io/website/docs/model-serving/predictive-inference/rollout-strategies/canary
[^2]: https://argoproj.github.io/argo-rollouts/
[^3]: https://docs.flagger.app/
[^4]: AWS, "Deployment guardrails". https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html

<!--
KServe 0.20.0 (released 6 Aug 2026) is the version the lab installs. Behind it the platform team runs cert-manager, Istio, Knative and KServe: 15 pods, about 2.3 GiB of memory. At work the platform team usually picks the tool. The ML engineer needs to know what it can do: two versions at once, a split by percentage, a rollback by changing one field.
-->

---

# Our canary in one file

<carbon-document-tasks class="icon-corner" />

<div class="middle">

```yaml {all|6|9|12|all}
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: diabetes
spec:
  predictor:
    canaryTrafficPercent: 10
    containers:
      - image: diabetes-api:local
        env:
          - name: STORAGE_URI
            value: pvc://diabetes-models/v2
```

<v-click at="4">

Only the model and the percentage change. The image stays the same, so a failure points to the model.

</v-click>

</div>

<!--
Shortened from the lab's file: the probes, resources and container name are left out. Applying this file is the deploy. Changing `canaryTrafficPercent` is the release. Setting it to 0 is the rollback. A canary that also changed the image would leave two suspects when it fails.
-->

---

# The rollout plan

<carbon-document class="icon-corner" />

<div class="middle">

A checklist in a YAML file, kept in Git next to the model's code.

<div class="text-sm">

| **Item** | **Example** |
| --- | --- |
| strategy | canary: v2 replaces v1 on 10% of requests |
| before any traffic | the smoke test passes on v2 |
| promote when | 24 hours with errors under 1%, positive rate within 5 points of v1 |
| roll back when | any smoke check fails, or errors above 1% for 5 minutes |
| expected load | 20 requests per second, p95 under 300 ms |

</div>

</div>

<!--
Every line is a decision the platform team cannot make for you. With the rollback criteria written down, whoever is on call at 3 a.m. can roll back without a meeting. A rollout without a written plan is decided in a meeting during the incident. The smoke test and the load test read their limits from this file. In the lab it is `release.yaml`, written in Exercise 2.
-->

---
layout: section
---

# 5 · Online evaluation

<!--
About 10 minutes: one case where every check before the release passed and users still saw the problem. Option B (Google's AI Overviews) is hidden after it.
-->

---

# GPT-4o, April 2025

<carbon-warning-alt class="icon-corner" />

<div class="middle">

An update made ChatGPT "noticeably more sycophantic": it praised users and agreed with everything[^1][].

<div class="flow">
  <div class="node green no-shrink" style="width:10rem"><ph-list-checks class="ic" /><b>Offline evaluations</b><br><small>passed</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><ph-arrows-split class="ic" /><b>A/B test</b><br><small>users liked it</small></div>
  <div class="arrow">→</div>
  <div class="node rose no-shrink" style="width:10rem"><ph-globe class="ic" /><b>All users</b><br><small>24–25 April</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:10rem"><ph-arrow-counter-clockwise class="ic" /><b>Rollback</b><br><small>from 28 April</small></div>
</div>

<div style="text-align:center; margin-top:1.2rem">
  <div style="font-size:2.4rem; font-weight:700; color:#dc2626">about 4 days</div>
  <div>with every check green, before the rollback started</div>
</div>

</div>

[^1]: OpenAI, "Sycophancy in GPT-4o: what happened and what we're doing about it" and "Expanding on what we missed with sycophancy", 2025. https://openai.com/index/sycophancy-in-gpt-4o/ · https://openai.com/index/expanding-on-sycophancy/

<!--
The update reached users on 24–25 April; OpenAI started the full rollback on 28 April, and it took about 24 hours. A team with excellent ML engineers and many evaluations still needed days, because users noticed the problem before any metric did. ChatGPT had 500 million users a week. Sycophantic: flattering, agreeing with everything (Hungarian: hízelgő). Expert testers said it "felt" slightly off. OpenAI changed the system prompt on 27 April as a first step, and calls the launch "the wrong call".
-->

---

# Why did every check pass?

<carbon-search class="icon-corner" />

<div class="middle">

<v-click>

- No check measured sycophancy.
- The A/B test measured what users liked: thumbs up and thumbs down.
- The update used the same signal in training.

</v-click>

<div v-click class="text-sm" style="margin-top:1rem">

| **OpenAI's changes** |
| --- |
| behaviour problems block a launch, even when the A/B test looks good |
| an opt-in "alpha" phase with users who want to give feedback |
| sycophancy evaluations in the deployment process |

</div>

<v-click>

> [!TIP]
> An online test sees only the metrics you give it. Write down which failures each check covers, and let a failing qualitative check block the release.

</v-click>

</div>

<!--
OpenAI: "our A/B tests didn't have the right signals to show how the model was performing on that front". Users' thumbs up "can sometimes favor more agreeable responses": the metric the model was trained on was also the metric that judged the release.
-->

---
hide: true
layout: two-cols
---

# Option B · AI Overviews, May 2024

Google Search started to show AI-written answers, "AI Overviews", above the results for US users[^1][].

- Before launch: red-teaming, evaluations on "samples of typical user queries", and "tests on a proportion of search traffic".
- After launch: answers that told people to eat rocks and to put glue on pizza.

::right::

<div style="margin-top:2.5rem">
<ImageSlot id="w10-overviews" text="An illustration: a search results page with an AI answer box above the links (an illustration, not a real screenshot)" height="220px" />
</div>

[^1]: Liz Reid, "AI Overviews: About last week", Google blog, 30 May 2024. https://blog.google/products/search/ai-overviews-update-may-2024/

<!--
Option B: use it instead of the GPT-4o case (switch `hide` on the two GPT-4o slides and on these two). Google: "there's nothing quite like having millions of people using the feature with many novel searches."
-->

---
hide: true
---

# Option B · Typical queries, rare questions

<carbon-search class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node green" style="width:13rem"><ph-list-checks class="ic" /><b>Tested</b><br><small>typical queries, a share of traffic</small></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:13rem"><ph-question class="ic" /><b>Failed</b><br><small>"How many rocks should I eat?"</small></div>
</div>

<v-clicks>

- Almost nobody had asked that question before: a "data void".
- The answers came from satire and from "troll-y" forum posts.
- Google's fixes: detect nonsensical queries, use less forum content, show no AI answer for some query types.

</v-clicks>

</div>

<!--
Option B, second slide. A partial rollout samples typical traffic; the rare questions that go viral are not in the sample. Google says it found content-policy violations on "less than one in every 7 million unique queries" with an AI Overview.
-->

---

# Offline and online evaluation

<carbon-chart-evaluation class="icon-corner" />

<div class="middle text-sm">

| | **Offline** | **Online** |
| --- | --- | --- |
| Data | a held-out test set | real requests |
| When | before the release | after the release |
| True labels | known | late, or never |
| A wrong answer reaches | nobody | real users |

<div v-click class="text-center" style="margin-top:0.8rem">What can only online evaluation show?</div>

<div v-click class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-question class="ic" /><b>New inputs</b>requests nobody put in the test set</div>
  <div class="card"><ph-users class="ic" /><b>User reactions</b>what people do with the answers</div>
  <div class="card"><ph-globe class="ic" /><b>Today's world</b>not the world of the training data</div>
</div>

</div>

<!--
Kästner (Machine Learning in Production, ch. 19): production data is "the ultimate unseen and representative test data". This is why every check passed for GPT-4o. Week 6's gate is offline evaluation: it compares the candidate with criteria on old data. It stays necessary, but it is not enough. For the diabetes model the true label (a diagnosis) arrives months after the prediction.
-->

---

# What do you watch in the first hour?

<carbon-view class="icon-corner" />

<div class="middle">

A new diabetes model gets 10% of patients.

<div class="cards" style="grid-template-columns:repeat(4,1fr); margin-top:1rem">
  <div v-click class="card"><ph-warning class="ic" /><b>Errors and latency</b>as for any service</div>
  <div v-click class="card"><ph-chart-bar class="ic" /><b>Positive rate</b>next to the old model's</div>
  <div v-click class="card"><ph-arrows-out class="ic" /><b>Unusual inputs</b>values outside the training data</div>
  <div v-click class="card" style="border-color:#e11d48; background:#fff1f2; color:#4c0519"><ph-hourglass class="ic" /><b>True diagnosis</b>arrives months later: not in the first hour</div>
</div>

</div>

<!--
The first three need no labels, so they work on day one. Comparing with the old model on the same traffic is what a canary or a shadow makes possible. Week 11 turns these into metrics and alerts. Week 12 watches the inputs (drift).
-->

---
layout: section
---

# 6 · Rollback

<!--
About 8 minutes. The lab's Exercise 5 rolls back and looks at what the rollback left behind.
-->

---

# Rollback by strategy

<carbon-undo class="icon-corner" />

<div class="middle">

The error rate stays above 1% for 5 minutes. The rollout plan says: roll back. What do you do?

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1rem">
  <div v-click class="card"><ph-sliders class="ic" /><b>Canary</b>set the canary percentage to 0<div style="margin-top:0.5rem"><small>v1 gets 100% again, in about 1.5 s in the lab</small></div></div>
  <div v-click class="card"><ph-arrows-left-right class="ic" /><b>Blue/green</b>switch the router back to blue<div style="margin-top:0.5rem"><small>blue kept running, so nothing has to start</small></div></div>
  <div v-click class="card"><ph-eye-slash class="ic" /><b>Shadow</b>nothing to roll back<div style="margin-top:0.5rem"><small>no user saw v2: stop sending it copies</small></div></div>
</div>

<v-click>

Roll back by changing the declaration, with the same field you deploy with.

</v-click>

</div>

<!--
Measured in the lab: the route reported 100/0 about 1.5 s after the patch, and the bad version keeps running at 0%, ready for debugging. Deleting the bad version by hand does not work in KServe: the declaration still names it, so the controller recreates it.
-->

---

# Test the rollback

<carbon-undo class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber" style="width:16rem"><ph-git-branch class="ic" /><b>Deploy</b><br><small>canary: 10%</small></div>
  <div class="node amber" style="width:16rem"><ph-arrow-counter-clockwise class="ic" /><b>Roll back</b><br><small>canary: 0%</small></div>
</div>

<v-click>

Remember *Toy Story 2*: Pixar had a backup, but nobody had tested it, and it did not hold the film when it was needed[^1][].

</v-click>

<v-click>

> [!TIP]
> Write the rollback steps into the rollout plan, and run them on a test cluster before the release.

</v-click>

</div>

[^1]: Matthew Panzarino, "How Pixar's Toy Story 2 was deleted twice, once by technology and again for its own good", *The Next Web*, 21 May 2012. https://thenextweb.com/news/how-pixars-toy-story-2-was-deleted-twice-once-by-technology-and-again-for-its-own-good

<!--
The Pixar case from the orchestration lecture: "Pixar, at the time, did not continuously test their backups." A rollback is the same kind of safety net. A rollback that uses the deploy mechanism is run at every release; "rebuild the old image and redeploy" runs only on the worst day.
-->

---
layout: section
---

# 7 · Wrap-up

<!--
About 5 minutes: the release in one diagram, takeaways, open questions, the lab, and the questions students can now answer.
-->

---

# This week's release

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.4rem">
  <div class="node sky no-shrink" style="width:7rem"><b>v1</b><br><small>100%</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet no-shrink" style="width:8rem"><b>publish v2</b><br><small>gate: GO</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node amber no-shrink" style="width:8.5rem"><b>rollout plan</b><br><small>in Git</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:8rem"><b>smoke test</b><br><small>at 0%</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node amber no-shrink" style="width:8rem"><b>canary</b><br><small>90 / 10, counted</small></div>
  <div v-click="5" style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flow" style="margin:0"><div class="arrow">→</div><div class="node violet no-shrink" style="width:7rem"><b>promote</b></div></div>
    <div class="flow" style="margin:0"><div class="arrow">→</div><div class="node rose no-shrink" style="width:7rem"><b>roll back</b></div></div>
  </div>
</div>

</div>

<!--
The ML engineer writes the second, third and fourth boxes; the platform runs the arrows.
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<div class="middle">

<v-clicks>

- Deploying runs the new version. Releasing gives users its answers. Keep them apart.
- Offline evaluation is necessary and not enough: real traffic shows what the test set lacks.
- Choose the strategy from the model and the problem: the cost of a wrong answer, the traffic, the labels.
- Hand over a written rollout plan: the model, the checks, when to promote, when to roll back.
- Roll back by changing the declaration, and test the rollback before you need it.

</v-clicks>

</div>

<!--
If time is short, ask which takeaway the room would drop for a model that is retrained once a year.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><carbon-dashboard class="ic" /><b>Who notices at 3 a.m.?</b>Every number today came from a command someone typed.<br><br><b>→ Week 11:</b> metrics, SLOs and alerts</div>
  <div v-click class="card"><carbon-chart-line class="ic" /><b>When should a new model roll out?</b>Nothing here sees the world change.<br><br><b>→ Week 12:</b> drift, the signal to retrain</div>
  <div v-click class="card"><carbon-policy class="ic" /><b>Who records what happened?</b>The rollout lives in the cluster, not in Git.<br><br><b>→ Week 13:</b> governance and incident reports</div>
</div>

</div>

<!--
Week 11 turns the rollback table into alerts: Prometheus and Grafana for latency, rps and error rate. Week 12 supplies the signal that would start this week's rollout.
-->

---
hide: true
---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **#** | **Exercise** | **What you show** |
| --- | --- | --- |
| 1 | Publish a model version | the store refuses a NO-GO model |
| 2 | Write the rollout plan | `release.yaml`, with your reasons (written) |
| 3 | Run a canary | smoke-tested at 0%, then the split counted (written) |
| 4 | Stop a bad canary | the smoke test blocks a healthy pod (written) |
| 5 | Roll back | what the rollback did not restore (written) |
| 6 | Load test (optional) | rps, errors, p50/p95/p99 against your request |

</div>

Keep the Compose stack down. Homework 2 is due on Sunday 15 November.

</div>

<!--
The installer pulls about 2.5 GB of images; ask students to run `make kind-up` and `make kserve-install` before the lab session if they can. Written answers go in `answers.md`, committed with the code.
-->

---
hide: true
---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

<div class="middle">

- What is the difference between deploying and releasing a model?
- What can online evaluation show that offline evaluation cannot?
- Which rollout strategy fits a given model, and why?
- How does a canary differ from an A/B test?
- What does an ML engineer hand over to the platform team before a release?
- What can a smoke test catch that a readiness probe cannot?
- When do you roll back, who decides, and how?

</div>

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
