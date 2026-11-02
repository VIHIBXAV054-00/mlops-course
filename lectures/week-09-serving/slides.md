---
theme: default
title: Week 9 — Model Serving & Deployment
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers deployment and model serving, ways to serve a model (batch, online,
  streaming, on the device), latency, a prediction service with FastAPI and the input contract, container images
  (bake or fetch), and an introduction to Kubernetes with kind.
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

# Week 9: Model Serving & Deployment

<carbon-deploy class="icon-corner" />

**Lifecycle of Artificial Intelligence Systems**

- Deploying a model
- Batch and online inference
- A prediction service
- Images and Kubernetes

<!--
Last week the pipeline produced a GO model on its own. This week someone who is not us gets to use it.
-->

---

# Recap: the pipeline so far

<carbon-flow class="icon-corner" />

<div class="middle">

What does each step guarantee?

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:8.6rem"><ph-database class="ic" /><b>Versioned data</b><small v-click="1">we know which data trained the model</small></div>
  <div class="arrow">→</div>
  <div class="node amber no-shrink" style="width:8.6rem"><ph-shield-check class="ic" /><b>Data contract</b><small v-click="2">bad rows stop before training</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:8.6rem"><ph-arrows-clockwise class="ic" /><b>Reproducible run</b><small v-click="3">same code, data and packages: same model</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:8.6rem"><ph-traffic-signal class="ic" /><b>Quality gate</b><small v-click="4">only a model that meets criteria set in advance passes</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:8.6rem"><ph-tag class="ic" /><b>Model registry</b><small v-click="5">a version for each model, an alias for the approved one</small></div>
</div>

<div v-click="6" class="flow text-sm">
  <div class="node no-shrink" style="width:46rem"><ph-clock class="ic" /><b>An orchestrator runs it on a schedule</b><small>retries what can fail for a moment, and records every run</small></div>
</div>

<div v-click="7" class="text-center" style="margin-top:1rem">

The result: an approved model with a version. **Nobody can use it yet.**

</div>

</div>

<!--
Allow about 7 minutes for the recap and opening. Weeks 4, 5, 2–3, 6, 6 and 8, left to right. Concepts only: if the room asks how a step was done, answer it there.
-->

---

# What serving builds on

<carbon-connect class="icon-corner" />

<div class="middle">

<div class="text-lg">

| **Concept** | **Means** | **Requirement** |
| --- | --- | --- |
| Reproducible environment | pinned versions of Python and every package | <span v-click="1">the server must run the versions that trained the model</span> |
| Data contract | rules every input row must pass | <span v-click="2">the request must pass the contract before the model sees it</span> |
| Model version and alias | a number for each model, a name for the approved one | <span v-click="3">a caller must be able to ask which model answered</span> |
| Quality gate | criteria a model must meet before it ships | <span v-click="4">only models passed the gate can be used</span> |

</div>

</div>

<!--
Weeks 2, 5, 3 and 6, and 6. Each row comes back today: the environment in section 1, the contract in section 3, the version and the gate in section 4.
-->

---

# Background: clients and servers

<carbon-api class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node amber no-shrink" style="width:12rem"><ph-browser class="ic" /><b>Client</b><br><small>an app, a website, another service</small></div>
  <div class="arrow-l">request<br><span class="mono">POST /predict</span> + JSON<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:12rem"><ph-hard-drives class="ic" /><b>Server</b><br><small>a service that waits for requests</small></div>
  <div class="arrow-l">response<br>status code + JSON<span class="arrow">→</span></div>
  <div class="node amber no-shrink" style="width:9rem"><ph-browser class="ic" /><b>Client</b></div>
</div>

A request fails. Who has to act?

<div class="text-sm">

| **Status** | **Means** | **Who acts** |
| --- | --- | --- |
| 2xx | it worked | <span v-click="1">nobody</span> |
| 4xx | the request is wrong: a bad value, a missing field | <span v-click="2">the client</span> |
| 5xx | the server failed, or is not ready yet | <span v-click="3">the team that runs the server</span> |

</div>

<div v-click="4" class="text-center">

Two numbers describe a server: **latency**, the time for one answer, and **throughput**, answers per second.

</div>

</div>

<!--
Students know this from web development courses; today it is the way a model gets its input. A 4xx that says which field is wrong lets the caller fix the request without asking us. Latency and throughput come back in section 2.
-->

---
layout: center
---

# **Quiz**
# A request to a prediction service timed out.
# Should the client retry it?

<v-clicks>

- **Only if a repeat is safe**: the idempotency question from Week 8.
- A prediction changes nothing, so a repeat is safe. A request that books a room or charges a card is not, unless the server detects the repeat.

</v-clicks>

<!--
Week 8 asked this about a task in a flow; the same rule holds for any client. Client libraries can retry on their own, so a service should expect repeated requests. A retry also adds load to a server that is already slow: wait longer between attempts.
-->

---
layout: section
---

# 1 · Deploying a model

<!--
About 10 minutes. From deployment in general to model serving. An optional case (Knight Capital, finance) is hidden after "What must travel with the model?".
-->

---

# What is deployment?

<carbon-deploy class="icon-corner" />

<div class="middle">

**Deployment:** installing a version of the software where its users can reach it.

<div class="flow text-sm">
  <div class="node no-shrink" style="width:9rem"><ph-code class="ic" /><b>Code</b></div>
  <div class="arrow-l">build<span class="arrow">→</span></div>
  <div class="node violet no-shrink" style="width:10rem"><ph-package class="ic" /><b>Artifact</b><br><small>a package, a binary</small></div>
  <div class="arrow-l">deploy<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:11rem"><ph-hard-drives class="ic" /><b>A running service</b><br><small>on a server</small></div>
  <div class="arrow">→</div>
  <div class="node amber no-shrink" style="width:8rem"><ph-users class="ic" /><b>Users</b></div>
</div>

<div v-click="1" class="flow text-sm">
  <div class="node no-shrink" style="width:9rem"><ph-code class="ic" /><b>Code + data</b></div>
  <div class="arrow-l">train<span class="arrow">→</span></div>
  <div class="node violet no-shrink" style="width:10rem"><ph-file class="ic" /><b>Model file</b><br><small>numbers learned from data</small></div>
  <div class="arrow-l">deploy<span class="arrow">→</span></div>
  <div class="node rose no-shrink" style="width:11rem"><b class="text-3xl">?</b></div>
  <div class="arrow">→</div>
  <div class="node amber no-shrink" style="width:8rem"><ph-users class="ic" /><b>Users</b></div>
</div>

<div v-click="2" class="text-center" style="margin-top:1rem">

A model file cannot answer anyone. It needs a program that loads it and answers: **model serving**.

</div>

</div>

<!--
Students know deployment from web development: a build makes an artifact, and a deploy installs it on servers. Training also makes an artifact, but it is data, not a program. A pickle is a Python object that only Python code can use.
-->

---

# Model serving

<carbon-application class="icon-corner" />

<div class="middle">

**Model serving:** running a model so that people or other programs get its predictions.

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-upload class="ic" /><b>Load the model</b>once, when the program starts</div>
  <div v-click class="card"><ph-sign-in class="ic" /><b>Receive inputs</b>a request, a file of rows, an event</div>
  <div v-click class="card"><ph-sign-out class="ic" /><b>Return predictions</b>a response, a table, an action</div>
</div>

</div>

<!--
The three parts hold for every way of serving in section 2: a nightly job, an HTTP service, a model inside a phone app. Sections 3 to 5 build one of them: a service, its image, and copies on a cluster.
-->

---

# What must travel with the model?

<carbon-package class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><ph-file class="ic" /><b>The model file</b>the learned numbers</div>
  <div v-click class="card"><ph-file-py class="ic" /><b>The runtime</b>the Python version</div>
  <div v-click class="card"><ph-stack class="ic" /><b>The libraries</b>at the versions that trained it</div>
  <div v-click class="card"><ph-code class="ic" /><b>The serving code</b>loads the model and answers</div>
  <div v-click class="card"><ph-shield-check class="ic" /><b>The input contract</b>what a request may contain</div>
  <div v-click class="card"><ph-tag class="ic" /><b>The metadata</b>model version, run, gate verdict</div>
</div>

<div v-click class="text-center" style="margin-top:1.5rem">

**A container image carries all of them.**

</div>

</div>

<!--
Most rooms name the model and the packages first; the contract and the metadata come last. MLflow writes `python_env.yaml` and `requirements.txt` next to every logged model for the same reason: the environment is part of the artifact.
Since Week 2 we ran other people's images (Postgres, Silo, MLflow). This week we build our own.
-->

---
hide: true
---

# Optional case · 2012: Knight Capital's eighth server

<carbon-chart-line class="icon-corner" />

<div class="middle">

Knight Capital was a US trading firm. Its router, SMARS, sent customers' stock orders to the market from **eight** servers.

- July 2012: new code for a new NYSE programme went out, server by server, copied by hand.
- A technician did not copy it to one of the eight. Nobody checked the deployment[^1][].

</div>

<!--
Optional case for section 1: what happens when nobody checks a deployment (switch `hide` on these two slides). Week 10 opens with Knight Capital: if you use it here, switch Week 10 to its Option B (Cloudflare, 2019).
Knight had no written deployment procedure and no second technician reviewing it (SEC order, paragraphs 15 and 26).
-->

[^1]: US SEC, Order against Knight Capital Americas LLC, Release No. 34-70694, 16 Oct 2013, paragraph 15. https://www.sec.gov/files/litigation/admin/2013/34-70694.pdf

---
hide: true
---

# Optional case · 45 minutes on 1 August 2012

<carbon-time class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node green no-shrink" style="width:10rem"><b>7 servers</b><br><small>new code: orders handled correctly</small></div>
  <div class="node rose no-shrink" style="width:10rem"><b>1 server</b><br><small>old code, reused flag: an endless stream of orders</small></div>
</div>

<div class="flex justify-center gap-10 text-center" style="margin-top:1.5rem">
  <div v-click><div class="text-4xl font-bold">397 million</div><div>shares traded in about 45 minutes</div></div>
  <div v-click><div class="text-4xl font-bold" style="color:#dc2626">−&#36;460 million</div><div>Knight's loss on those positions</div></div>
</div>

<br>

</div>

SEC order against Knight Capital, paragraphs 16–17[^1][]

<!--
Optional case, second slide. The SEC: "a simple double-check of the deployment" could have found the missed server (para. 41). Knight paid $12 million and hired a consultant to review its deployment controls (para. 51, IV.C).
The practice: deploy by a script, then ask every server which version it runs, as `/health` does this week.
-->

[^1]: US SEC, Release No. 34-70694, 16 Oct 2013, paragraphs 16–17.

---

# Where we are: deployment

<div class="middle">

<Lifecycle stage="deploy" width="70%" />

</div>

<!--
The stage is deploy: this week the model becomes reachable. Week 10 finishes deployment (replacing a model safely); keeping it healthy and correct is Weeks 11–12.
-->

---
layout: section
---

# 2 · Batch and online inference

<!--
About 15 minutes. The two main types first, then the other ways (Huyen, Designing Machine Learning Systems, Chapter 7), then the case: Booking.com (travel). Option B: a slower Google search (web search), hidden after the Booking.com number.
-->

---
layout: center
---

# A hospital wants a diabetes risk score.
# When does it need the answer?

<div class="grid grid-cols-2 gap-12 text-center" style="margin-top:2rem">
<div>
  <div class="flow" style="margin:0"><div class="node amber" style="font-size:1.2rem; flex:1">Every morning, for the whole ward</div></div>
  <div v-click="1">
    <div style="font-size:2.2rem; color:#64748b; margin:0.4rem 0">↓</div>
    <div style="font-size:2.4rem; font-weight:700; color:#d97706">Batch inference</div>
  </div>
</div>
<div>
  <div class="flow" style="margin:0"><div class="node sky" style="font-size:1.2rem; flex:1">While a nurse admits a patient</div></div>
  <div v-click="2">
    <div style="font-size:2.2rem; color:#64748b; margin:0.4rem 0">↓</div>
    <div style="font-size:2.4rem; font-weight:700; color:#0284c7">Online inference</div>
  </div>
</div>
</div>

<!--
The ward list exists the evening before; the new patient at the door does not. Same model, two ways to ask it: these are the two main types of serving, and the next two slides show where each is used.
-->

---

# Batch inference

<carbon-calendar class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.5rem; margin:0.2rem 0">
  <div class="node amber no-shrink" style="width:10rem"><b>On a schedule</b><br><small>every night, every week</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><b>Model</b><br><small>all rows at once</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:10rem"><b>Stored predictions</b><br><small>a table, a key-value store</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>An app reads them</b><br><small>when someone looks</small></div>
</div>


<div class="text-sm tight">

| **Where** | **The model predicts** | **Computed** |
| --- | --- | --- |
| <span>Spotify, Discover Weekly</span> | <span>a playlist of new songs for each user</span> | <span>every Monday</span> |
| <span>Netflix</span> | <span>recommendations for each member</span> | <span>offline, stored for the app[^1][]</span> |
| <span>A bank</span> | <span>which customers are likely to leave, for the retention team</span> | <span>every month</span> |
| <span>A hospital ward</span> | <span>diabetes risk for every patient</span> | <span>every night</span> |

</div>
<br>

> [!TIP]
> Choose batch when the inputs are known in advance and an answer some hours old is good enough.

</div>

[^1]: Xavier Amatriain and Justin Basilico, "System Architectures for Personalization and Recommendation", Netflix Technology Blog, March 2013. https://netflixtechblog.com/system-architectures-for-personalization-and-recommendation-e081aa94b5d8

<style>
.tight td, .tight th { padding-top: 0.3rem; padding-bottom: 0.3rem; }
</style>

<!--
A batch job is the Week 8 flow with one more task: score every row and write the results. Nobody waits for it, so a slow model only makes the job longer. Netflix's post describes offline computation with no limit on the amount of data or the time it takes; the results are stored and served later.
-->

---

# Online inference

<carbon-flash class="icon-corner" />

<div class="flow text-sm" style="gap:0.5rem; margin:0.2rem 0">
  <div class="node amber no-shrink" style="width:10rem"><b>A request</b><br><small>one new input</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:11rem"><b>Service</b><br><small>the model loaded, waiting</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><b>One answer</b><br><small>while the caller waits</small></div>
</div>


<div class="text-sm tight">

| **Where** | **The model predicts** | **Answer within** |
| --- | --- | --- |
| <span>Card payments</span> | <span>the risk that this payment is fraud, before it is approved</span> | <span>under 100 ms at Stripe[^1][]</span> |
| <span>Uber Eats[^2][]</span> | <span>when the meal will arrive, as the customer orders</span> | <span>while the order page loads</span> |
| <span>Booking.com, web search</span> | <span>the order of the results for this search</span> | <span>while the results page loads</span> |
| <span>Online ads</span> | <span>the chance that this user clicks this ad, in each auction</span> | <span>80–1,000 ms at Google[^3][]</span> |

</div>
<br>

> [!TIP]
> Choose online when the input exists only when someone asks, or the answer must be fresh.

[^1]: Stripe newsroom, 30 April 2025. https://stripe.com/newsroom/news/radar-for-ach-sepa
[^2]: Hermann and Del Balso, "Meet Michelangelo", Uber Engineering blog, September 2017. https://www.uber.com/blog/michelangelo-machine-learning-platform/
[^3]: Google Authorized Buyers, RTB guide, updated 17 September 2026. https://developers.google.com/authorized-buyers/rtb/start

<style>
.tight td, .tight th { padding-top: 0.3rem; padding-bottom: 0.3rem; }
</style>

<!--
Nobody can score this payment, this order or this query the night before: the input does not exist yet. The last column gives a rough size, not a target. A payment waits for the fraud score, so its budget is tight; a delivery estimate can take a little longer. Google sets the deadline per auction and drops a bid that arrives after it. Latency comes back later in this section.
-->

---

# Batch or online?

<carbon-compare class="icon-corner" />

<div class="middle">

<div class="text-lg">

| | **Batch** | **Online** |
| --- | --- | --- |
| Optimises | throughput: rows per second | latency: time for one answer |
| The answer is computed | before anyone asks | when someone asks |
| The input | known in advance, may be hours old | arrives with the request |
| Must keep running | a scheduled job, for minutes | a service, all the time |
| A failure looks like | a late or missing table | a slow or failed request |

</div>

</div>

<!--
Fill it in with the room before you comment on it. Costs differ too: a batch job uses machines for minutes a day; a service holds them all day, even at night with no requests. A bad batch table can be rebuilt before anyone reads it; a bad online answer is already with the user.
-->

---

# Streaming inference

<carbon-flow-stream class="icon-corner" />

Online inference that also uses **streaming features**: features computed from the latest events, minutes old, instead of from last night's data.[^1][]

<div class="flex items-center justify-center gap-2 text-sm" style="margin-top:1rem">
<div class="flex flex-col gap-2">
<div class="flow" style="margin:0"><div class="node amber no-shrink" style="width:17rem"><b>Batch feature</b><br><small>computed every night from history:<br>a restaurant's mean prep time, last 7 days</small></div></div>
<div class="flow" style="margin:0"><div class="node violet no-shrink" style="width:17rem"><b>Streaming feature</b><br><small>updated from a stream of events:<br>the same restaurant, last hour</small></div></div>
</div>
<div class="flow" style="margin:0"><div class="arrow">→</div><div class="node sky no-shrink" style="width:10rem"><b>Model</b><br><small>called per request</small></div><div class="arrow">→</div><div class="node green no-shrink" style="width:9rem"><b>Answer</b><br><small>delivery time</small></div></div>
</div>

<div class="text-sm" style="margin-top:0.5rem">

</div>
<br>
<div v-click class="tradeoffs" style="margin-top:1rem">
<div><div class="font-bold" style="color:#475569"><ph-list-bullets /> Examples</div><ul><li>Uber Eats: a restaurant's prep time, last hour</li><li>card payments: payments from this card, last 10 minutes</li></ul></div>
<div><div class="font-bold" style="color:#16a34a"><ph-thumbs-up /> Gains</div><ul><li>the answer reacts to the last minutes</li><li>a busy evening or a burst of fraud shows at once</li></ul></div>
<div><div class="font-bold" style="color:#e11d48"><ph-warning /> Watch out for</div><ul><li>streaming job monitoring</li><li>feature implementation consistency</li></ul></div>
</div>


[^1]: Hermann and Del Balso, "Meet Michelangelo", Uber Engineering blog, September 2017. https://www.uber.com/blog/michelangelo-machine-learning-platform/

<!--
Huyen (Chapter 7) calls this streaming prediction: online prediction that uses batch features and streaming features. Uber publishes events to Kafka, a stream job computes the one-hour average, and the result is stored for the service to read. The model is the same; what changes is how fresh its inputs are. The two fraud and video features are examples of the kind, not quotes from a company.
-->

---

# Inference on the device

<carbon-mobile class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-camera class="ic" /><b>Input</b><br><small>camera, keyboard, sensor</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:12rem"><ph-device-mobile class="ic" /><b>Model in the app</b><br><small>on the phone or in the car</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><ph-check-circle class="ic" /><b>Answer</b><br><small>no network needed</small></div>
</div>
<br>
<div v-click class="tradeoffs" style="margin-top:1.5rem">
<div><div class="font-bold" style="color:#475569"><ph-list-bullets /> Examples</div><ul><li>Face ID unlocking an iPhone</li><li>next-word suggestions in a phone keyboard</li><li>lane detection in a car's driver assistance</li></ul></div>
<div><div class="font-bold" style="color:#16a34a"><ph-thumbs-up /> Gains</div><ul><li>works without a network</li><li>no network latency</li><li>the data stays on the device</li></ul></div>
<div><div class="font-bold" style="color:#e11d48"><ph-warning /> Watch out for</div><ul><li>the model must fit the device's memory and battery</li><li>a new version reaches users only when they update the app</li><li>you cannot easily see the inputs it gets</li></ul></div>
</div>

</div>

<!--
Also called edge inference. It works without a network, adds no network latency, and the data stays on the device, which matters for faces and typed text. A new model version reaches users only when they update the app, so a bad version is hard to take back.
-->

---

# Batch and online together

<carbon-layers class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-calendar class="ic" /><b>Batch, every night</b><br><small>the heavy work: a list of candidates for each user</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:9rem"><ph-database class="ic" /><b>Stored</b><br><small>candidates per user</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:11rem"><ph-lightning class="ic" /><b>Online, per request</b><br><small>the last step: rank them with the current context</small></div>
</div>
<br>
<div v-click class="tradeoffs" style="margin-top:1.5rem">
<div><div class="font-bold" style="color:#475569"><ph-list-bullets /> Examples</div><ul><li>Netflix: offline, nearline and online steps, combined</li><li>an online shop: candidate products per user every night, ranked by the current basket</li></ul></div>
<div><div class="font-bold" style="color:#16a34a"><ph-thumbs-up /> Gains</div><ul><li>the heavy work has time and runs once</li><li>the answer still uses the request's context</li></ul></div>
<div><div class="font-bold" style="color:#e11d48"><ph-warning /> Watch out for</div><ul><li>two paths that must compute the same features the same way</li><li>two places that can fail</li></ul></div>
</div>

<div class="text-sm" style="margin-top:0.8rem">

</div>

</div>

[^1]: Amatriain and Basilico, "System Architectures for Personalization and Recommendation", Netflix Technology Blog, March 2013. https://netflixtechblog.com/system-architectures-for-personalization-and-recommendation-e081aa94b5d8

<!--
Most large recommenders work like this: batch gives the model time for heavy work, online adds what only exists at request time, such as the device or the last click. Netflix's nearline step computes in response to user events, close to streaming. If the two paths compute a feature differently, the online answer is wrong without any error.
-->

---

# A cache in front of the model

<carbon-data-base class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="display:grid; grid-template-columns:8rem 3rem 10rem 4rem 10rem; justify-content:center; align-items:center; gap:0.3rem 0.5rem">
  <div class="node amber"><b>A request</b></div>
  <div class="arrow text-center">→</div>
  <div class="node violet"><ph-database class="ic" /><b>Cache</b><br><small>seen this input?</small></div>
  <div class="arrow-l on" style="min-width:0"><span>yes</span><div class="arrow">→</div></div>
  <div class="node green"><b>Stored answer</b><br><small>no model call</small></div>
  <div></div><div></div>
  <div class="arrow-l" style="min-width:0"><span>no</span><div class="arrow">↓</div></div>
  <div></div><div></div>
  <div></div><div></div>
  <div class="node sky"><b>Model</b><br><small>computes the answer</small></div>
  <div class="arrow-l" style="min-width:0"><span>store</span><div class="arrow">→</div></div>
  <div class="node green"><b>New answer</b><br><small>saved in the cache</small></div>
</div>

<div v-click class="tradeoffs" style="margin-top:1.2rem">
<div><div class="font-bold" style="color:#475569"><ph-list-bullets /> Examples</div><ul><li>results for a popular search query</li><li>"similar products" on a product page, the same for every visitor</li></ul></div>
<div><div class="font-bold" style="color:#16a34a"><ph-thumbs-up /> Gains</div><ul><li>a repeated input costs no model call</li><li>fast and cheap</li></ul></div>
<div><div class="font-bold" style="color:#e11d48"><ph-warning /> Watch out for</div><ul><li>an answer can be out of date</li><li>a new model version must clear the cache</li><li>helps only when inputs repeat</li></ul></div>
</div>

</div>

<!--
A cache only helps when the same input repeats. It is the same freshness question as batch: how old can an answer be before it is wrong? A new model version must clear the cache, or users keep getting the old model's answers.
-->

---

# Champion and challenger side by side

<carbon-compare class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="display:grid; grid-template-columns:7rem 2rem 9rem 2rem 10rem 2rem 7rem; justify-content:center; align-items:center; gap:0.4rem 0.3rem">
  <div class="node amber">Request</div>
  <div class="arrow text-center">→</div>
  <div class="node violet"><b>Service</b><br><small>sends a copy to both</small></div>
  <div class="arrow text-center">→</div>
  <div class="node green"><b>Champion</b><br><small>its answer goes back</small></div>
  <div class="arrow text-center">→</div>
  <div class="node amber">User</div>
  <div></div><div></div><div></div>
  <div class="arrow text-center">↘</div>
  <div class="node sky"><b>Challenger</b><br><small>its answer is logged, never sent</small></div>
  <div class="arrow text-center">→</div>
  <div class="node"><b>Compare</b><br><small>later, same inputs</small></div>
</div>

<div v-click class="tradeoffs" style="margin-top:1.2rem">
<div><div class="font-bold" style="color:#475569"><ph-list-bullets /> Examples</div><ul><li>a new fraud model scores real payments before it may block one</li><li>our challenger from Week 6 next to the champion</li></ul></div>
<div><div class="font-bold" style="color:#16a34a"><ph-thumbs-up /> Gains</div><ul><li>real traffic, and no user sees the challenger's answer</li><li>both models answer the same inputs</li></ul></div>
<div><div class="font-bold" style="color:#e11d48"><ph-warning /> Watch out for</div><ul><li>twice the compute</li><li>both answers must be stored and compared</li><li>the challenger must not act: no emails, no writes</li></ul></div>
</div>

</div>

<!--
This is called shadow mode or shadow deployment (Huyen, Designing Machine Learning Systems, Chapter 9). Champion and challenger are the registry aliases from Week 6. Here it is a way of serving two models; Week 10 uses it as one of the ways to release a new model, next to canary and blue/green.
-->

---

# Booking.com: 150 models

<div class="middle">

Booking.com is an online travel agent: millions of guests book a stay from millions of properties.

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-magnifying-glass class="ic" /><b>A guest searches</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:13rem"><ph-cube class="ic" /><b>ML models</b><br><small>about 150 customer-facing models across the site</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><ph-list class="ic" /><b>Search results</b></div>
</div>

Each model was tested on real users in an A/B test[^1][]. How much does a slower page cost?

</div>

[^1]: Bernardi, Mavridis and Estevez, "150 Successful Machine Learning Models: 6 Lessons Learned at Booking.com", KDD 2019. https://doi.org/10.1145/3292500.3330744

<!--
The models predict, for example, a user's travel preferences or how many people travel together, and choose which images and reviews to show.
-->

---
layout: fact
---

<div class="text-center" style="margin-top:2rem; font-size:2.2rem; line-height:1.2">How much does a slower page cost?</div>

<div class="flex justify-center items-start gap-3 text-center" style="margin-top:3rem">
  <div style="width:16rem"><div class="text-5xl font-bold" style="color:#d97706">+30%</div><div>latency, about</div></div>
  <div class="flex gap-3"><div class="text-5xl">→</div><div style="width:18rem"><div class="text-5xl font-bold" style="color:#dc2626">−0.5%</div><div>conversion rate (share of visitors who book), or worse</div></div></div>
</div>

<br>

Booking.com, KDD 2019, Section 5: "Deployment: Time is money"[^1][]

[^1]: Bernardi, Mavridis and Estevez, KDD 2019. https://doi.org/10.1145/3292500.3330744

<!--
One experiment: four arms with added synthetic latency, plus a control group. The paper says more than 0.5%, "a relevant cost for our business". In other experiments, removing latency raised conversion.
-->

---
hide: true
---

# Option B · 2009: a slower Google search

<carbon-search class="icon-corner" />

<div class="middle">

Google's web search team ran an experiment: for some users, the results page came back **100 to 400 ms** later, on purpose[^1][].

<div class="flow" style="margin-top:2rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-magnifying-glass class="ic" /><b>A search</b></div>
  <div class="arrow">→</div>
  <div class="node rose no-shrink" style="width:11rem"><ph-hourglass class="ic" /><b>+400 ms</b><br><small>added on the server</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:11rem"><ph-list class="ic" /><b>The same results</b></div>
</div>

<div class="text-center" style="margin-top:1.5rem">Would you notice? Would you search less?</div>

</div>

[^1]: Jake Brutlag (Google), "Speed Matters", Google Research blog, 23 June 2009. https://research.google/blog/speed-matters/

<!--
Option B for this slot: use it instead of "Booking.com: 150 models" and the number slide after it (switch `hide` on those two slides and on these two). "How does Booking keep predictions fast?" stays: introduce Booking.com there in one line, as an online travel agent with about 150 models.
-->

---
hide: true
layout: fact
---

<div class="text-center" style="margin-top:2rem; font-size:2.2rem; line-height:1.2">Would you search less?</div>

<div class="flex justify-center items-start gap-6 text-center" style="margin-top:3rem">
  <div style="width:13rem"><div class="text-5xl font-bold" style="color:#d97706">−0.44%</div><div>searches per user, weeks 1–3, with +400 ms</div></div>
  <div style="width:13rem"><div class="text-5xl font-bold" style="color:#dc2626">−0.76%</div><div>weeks 4–6, same delay</div></div>
  <div style="width:13rem"><div class="text-5xl font-bold" style="color:#dc2626">−0.21%</div><div>in the five weeks after the delay was removed</div></div>
</div>

<br>

Google Research, "Speed Matters", 2009[^1][]

[^1]: Jake Brutlag, "Speed Matters", Google Research blog, 23 June 2009. https://research.google/blog/speed-matters/

<!--
Option B, second slide. With +200 ms the drop was 0.22%, then 0.36%. The post: users who saw the longer delay "take time to return to their previous usage level".
-->

---

# How does Booking.com keep predictions fast?

<carbon-meter class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-table class="ic" /><b>Precomputation and caching</b>store all predictions in a key-value store</div>
  <div class="card"><ph-copy class="ic" /><b>Model redundancy</b>copies of each model across a cluster</div>
  <div class="card"><ph-lightning class="ic" /><b>A fast linear prediction engine</b>written in-house</div>
  <div class="card"><ph-cube class="ic" /><b>Sparse models</b>fewer parameters, less computation</div>
  <div class="card"><ph-stack class="ic" /><b>Bulking</b>many requests sent as one</div>
  <div class="card"><ph-gear class="ic" /><b>Minimum feature transformations</b>less work per request</div>
</div>

</div>

Booking.com, KDD 2019, Section 5[^1][]

[^1]: Bernardi, Mavridis and Estevez, KDD 2019. https://doi.org/10.1145/3292500.3330744

<!--
The paper's point: "Even mathematically simple models have the potential of introducing relevant latency", because a page can call several models, each on thousands of hotels.
Model redundancy comes back later today: a Deployment keeps several copies of the model running.
-->

---

# Batch versus online in the lab

<carbon-chart-evaluation class="icon-corner" />

<div class="middle">

<div class="flow" style="margin-top:2rem">
  <div v-click="1" class="node green no-shrink" style="width:14rem"><ph-table class="ic" /><b>Batch: one model call</b><br>0.0095 s<br><small>20,236 rows per second</small></div>
  <div v-click="1" class="node amber no-shrink" style="width:14rem"><ph-globe class="ic" /><b>Online: 192 sequential requests</b><br>0.8875 s<br><small>216 rows per second</small></div>
</div>

<div v-click="2" class="text-center" style="margin-top:1rem">
  <div class="text-6xl font-bold" style="color:#dc2626">93×</div>
  <div>the time, in this test</div>
</div>

</div>

<!--
The lab's `make bench` (Exercise 3), 2 Nov 2026: three runs gave 104×, 72× and 93×. Both modes score the same 192 patients, with the sentinel zeros sent as missing values, and every online request answered 200. FastAPI's in-process TestClient sends each request; there is no network or concurrent load. The request also builds a dataframe and calls the model once per row. The ratio depends on the workload and machine.
-->

---

# Latency metrics

<carbon-chart-histogram class="icon-corner" />

<div style="display:grid; grid-template-columns:20rem 1fr; gap:2rem; align-items:end; margin-top:1rem">
<div>
<div class="flex items-end justify-center gap-1" style="height:11rem">
  <div class="text-center" v-for="[ms, n] in [[3,11],[4,178],[5,3]]" :key="ms">
    <div :style="{ height: (n / 178 * 10) + 'rem', width: '2.4rem', background: '#0284c7', borderRadius: '3px 3px 0 0' }"></div>
    <div class="text-xs">{{ ms }}</div>
  </div>
</div>
<div class="text-center text-xs">latency of each of 192 requests, in whole ms</div>
</div>
<div v-click class="text-sm">

| **Metric** | **Here** | **Means** |
| --- | --- | --- |
| mean | 4.40&nbsp;ms | the average: a few slow requests pull it up |
| p50, median | 4.39&nbsp;ms | half of the requests were faster |
| p95 | 4.80&nbsp;ms | one request in 20 was slower |
| max | 5.22&nbsp;ms | the slowest request |

A percentile *pN*: N% of the requests were faster.<br>Uber reports p95 under 10 ms for its online predictions[^1][].

</div>
</div>
<br>
<v-click>

> [!TIP]
> Report latency as p50 and p95, and name the percentile you quote.

</v-click>


[^1]: Hermann and Del Balso, "Meet Michelangelo", Uber Engineering blog, September 2017. https://www.uber.com/blog/michelangelo-machine-learning-platform/

<!--
Measured on 2 Nov 2026 with the lab's solution: the 192 test patients through FastAPI's TestClient, after 20 warm-up requests, each request timed; all 192 answered 200. In one process, one request at a time, the tail is short. Through a network it grows: Week 11 measures p50 8.79 ms and p95 22.97 ms from the host to the container.
Percentiles of two services cannot be averaged into the percentile of both.
-->

---
layout: section
---

# 3 · A prediction service

<!--
About 12 minutes. MLflow's model server first, then our own with FastAPI; the lab follows the same order (Exercises 1 and 2).
-->

---

# The MLflow model server

<carbon-api class="icon-corner" />

<div class="middle">

```bash
mlflow models serve -m "models:/diabetes-classifier@champion" --env-manager local -p 5540
```

<div class="flow" style="margin-top:2.5rem">
  <div class="node amber no-shrink" style="width:12rem"><ph-globe class="ic" /><b>POST /invocations</b><br><small><span class="mono">{"dataframe_records": [ … ]}</span></small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:12rem"><ph-cube class="ic" /><b>The champion model</b><br><small>loaded from the registry</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:12rem"><ph-check-circle class="ic" /><b>Response</b><br><small><span class="mono">{"predictions": [1]}</span></small></div>
</div>

</div>

<!--
The lab's model was logged without a signature, so the columns must arrive in the training order: scikit-learn refuses any other. Port 5540 in the lab.
`--env-manager local` uses the Python you are in instead of rebuilding the model's environment from `python_env.yaml`: the risk of a server with other package versions, accepted on purpose.
-->

---
layout: center
---

# We send it a patient with glucose = 0.
# What happens?

<v-clicks>

- `{"predictions": [0]}`: scored.
- **MLflow does not know about the contract.**

</v-clicks>

<!--
Measured against the lab's champion in August 2026 and again on 29 Oct 2026. Week 5 made glucose 0 illegal in `ModelInput`; this server has never seen that contract.
What it does check is Exercise 1's written question, graded: the other bad requests and the reason are kept for the lab.
-->

---
class: fn-inline
---

# Tool options for serving

<carbon-tool-box class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-lightning class="ic" /><b>FastAPI</b>a web framework built on Python type hints</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-flask class="ic" /><b>Flask</b>"a lightweight WSGI web application framework"</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-cube class="ic" /><b>mlflow models serve</b>a REST server for a logged model, no code</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-package class="ic" /><b>BentoML</b>a Python library for online serving systems</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-cpu class="ic" /><b>NVIDIA Triton</b>inference server for PyTorch, ONNX, TensorRT…</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-kubernetes class="ic" /><b>KServe</b>model serving on Kubernetes<br><b>→ Week 10</b></div>
</div>

<div class="text-sm opacity-70">

FastAPI[^1][] · Flask[^2][] · MLflow[^3][] · BentoML[^4][] · Triton[^5][] · KServe[^6][]

</div>

<v-click>

**We use FastAPI:** the request is a typed Python class.

</v-click>

</div>

[^1]: https://fastapi.tiangolo.com/
[^2]: https://flask.palletsprojects.com/en/stable/
[^3]: https://mlflow.org/docs/latest/deployment/deploy-model-locally/
[^4]: https://github.com/bentoml/BentoML
[^5]: https://github.com/triton-inference-server/server
[^6]: https://kserve.github.io/website/

<!--
Flask and FastAPI are general web frameworks; BentoML, Triton and KServe are built for models. Triton earns its set-up on GPUs and deep learning models, not on a logistic regression.
-->

---
class: fn-inline
---

# Route to the model

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:8rem"><ph-globe class="ic" /><b>Client</b><br><small>POST /predict, JSON</small></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node violet no-shrink" style="width:9.5rem"><ph-plug class="ic" /><b>Uvicorn</b><br><small>web server: listens on a port, handles HTTP</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node sky no-shrink" style="width:9.5rem"><ph-signpost class="ic" /><b>FastAPI</b><br><small>web framework: sends the request to your function</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:9.5rem"><ph-shield-check class="ic" /><b>Pydantic</b><br><small>checks the JSON against your class</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node sky no-shrink" style="width:8.5rem"><ph-cube class="ic" /><b>Your function</b><br><small>calls the model</small></div>
</div>

<div class="text-sm" style="margin-top:1.5rem">

| | **Is** | **We write** |
| --- | --- | --- |
| <span v-click="1">Uvicorn[^1][]</span> | <span v-click="1">an ASGI web server</span> | <span v-click="1">nothing: `uvicorn app:app --port 8000`</span> |
| <span v-click="2">FastAPI[^2][]</span> | <span v-click="2">a web framework for APIs, based on Python type hints</span> | <span v-click="2">the route: `@app.post("/predict")`</span> |
| <span v-click="3">Pydantic[^3][]</span> | <span v-click="3">a data validation library</span> | <span v-click="3">the contract: a class with types and limits</span> |
| <span v-click="4">Your function</span> | <span v-click="4">our code</span> | <span v-click="4">load the model once, call `predict`</span> |

</div>

</div>

[^1]: https://www.uvicorn.org/
[^2]: https://fastapi.tiangolo.com/
[^3]: https://docs.pydantic.dev/latest/

<!--
Three packages, three jobs. Uvicorn knows HTTP and nothing about our model; FastAPI knows routes and nothing about ports; Pydantic knows types and limits. ASGI is the interface between the server and the app, so another ASGI server could run the same app. We install FastAPI and Uvicorn; FastAPI brings Pydantic with it.
-->

---

# FastAPI quick start

<carbon-terminal class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:3fr 2fr; gap:1rem">
<div>

```python {all|5-9|11-12|14-18|all}
import joblib
from fastapi import FastAPI
from pydantic import BaseModel, Field

class Flower(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float = Field(gt=0)
    petal_width: float = Field(gt=0)

app = FastAPI()
model = joblib.load("iris.pkl")   # once, at startup

@app.post("/predict")
def predict(flower: Flower):
    x = [[flower.sepal_length, flower.sepal_width,
          flower.petal_length, flower.petal_width]]
    return {"species": int(model.predict(x)[0])}
```

</div>
<div v-click="5">

```text
$ uvicorn app:app --port 8000

$ curl -X POST localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"sepal_length": 5.1,
         "sepal_width": 3.5,
         "petal_length": 1.4,
         "petal_width": 0.2}'

{"species":0}
```

</div>
</div>

</div>

<!--
Run on 3 Oct 2026 with the lab's versions (FastAPI 0.141.1, pydantic 2.13.4, uvicorn 0.52.1). `iris.pkl` is `LogisticRegression(max_iter=1000)` fitted on scikit-learn's `load_iris`; species 0 is setosa.
Loading the model inside `predict` would also work, and would add the load time to every request.
-->

---

# What does Pydantic check for you?

<carbon-security class="icon-corner" />

<div class="middle">

The `Flower` class is a data contract.

We write the rules, Pydantic checks each request, and FastAPI answers 422 when a check fails.

<div class="text-sm" style="margin-top:1rem">

| **The request** | **The response** |
| --- | --- |
| no `petal_width` | <span v-click="1">422 `missing`: "Field required"</span> |
| `sepal_length = "five"` | <span v-click="2">422 `float_parsing`</span> |
| `petal_length = 0` | <span v-click="3">422 `greater_than`: "Input should be greater than 0"</span> |
| `sepal_length = 51`, sent in mm | <span v-click="4">200 `{"species": 1}`</span> |

</div>

</div>

<!--
Measured with the quick-start app. The 422s come before `predict` runs. Pydantic checks types, presence and the limits we wrote, such as `gt=0`; it cannot know what we did not write.
51 mm is 5.1 cm: a valid float, a plausible number, and a different species. Week 5's unit-change fault, over HTTP.
-->

---

# Pandera or Pydantic?

<carbon-data-check class="icon-corner" />
<br>
<div class="flow text-sm" style="gap:0.5rem; margin:0.4rem 0">
  <div class="text-xs" style="width:5rem">Week 5:<br>training</div>
  <div class="node amber no-shrink" style="width:9rem"><b>Data sources</b><br><small>a table, many rows</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>Pandera</b><br><small>checks a DataFrame</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:8rem"><b>Training</b></div>
</div>
<div class="flow text-sm" style="gap:0.5rem; margin:0.4rem 0">
  <div class="text-xs" style="width:5rem">Week 9:<br>serving</div>
  <div class="node amber no-shrink" style="width:9rem"><b>A client</b><br><small>JSON, one patient</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>Pydantic</b><br><small>checks one request</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:8rem"><b>Model</b></div>
</div>
<br>
<div v-click="1" class="text-sm" style="margin-top:0.8rem">

| **Question** | **Answer** |
| --- | --- |
| Why not Pydantic for training data? | Pandera checks a whole table at once: columns, types, values. |
| Why not Pandera for serving? | FastAPI reads Pydantic classes: it parses the JSON and answers 422. |
| How do the rules stay the same? | Write each rule once... |

</div>


<!--
Ask the room the three questions before you click. Both are data contracts: Week 5's checks data from our sources before training, and a request is a second path into the same model. If glucose > 0 is written in both tools, someone will change one and forget the other.
-->

---

# Data checks

<carbon-security class="icon-corner" />

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:8rem"><b>Request</b><br><small>JSON, one patient</small></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:10rem"><b>Pydantic</b><br><small>types and presence</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:11rem"><b>Pandera: PredictionInput</b><br><small>allowed values</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node sky no-shrink" style="width:10rem"><b>predict_proba</b><br><small>the model</small></div>
</div>

<div class="text-sm" style="margin-top:0.4rem">

| | **Written from** | **Checks** |
| --- | --- | --- |
| <span v-click="1">Pydantic: `PredictionRequest`</span> | <span v-click="1">the field names of `PredictionInput`, and which may be null; a test checks they agree</span> | <span v-click="1">types and presence</span> |
| <span v-click="2">Pandera: `PredictionInput`</span> | <span v-click="2">Week 5's `ModelInput` without the label</span> | <span v-click="2">allowed values: the training rules</span> |

</div>
<br>
<v-click at="3">

```text
POST /predict  {"glucose": 0, …}
422  … "failures": {"greater_than(0)": 1} …
```

</v-click>

<br>

<v-click at="5">

> [!TIP]
> Check each request with the contract that trained the model, return the failed checks in the 422.

</v-click>


<!--
Ask the room what each check is before you click. Measured on 3 Oct 2026 with the lab's solution: age 250 with BMI 336 fails `less_than_or_equal_to(120)` and `less_than_or_equal_to(100.0)`. `PredictionInput` is `ModelInput` without the label, written in Week 5 for this moment: we add the training contract as a second layer, called inside the endpoint. In the lab, Pydantic lists only the fields and their types; the value rules stay in Pandera, and a test checks that the two field lists agree. The 422 also names the contract version, so the caller knows which rules it broke.
-->

---

# A request's path

<carbon-flow-connection class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:7rem"><b>Client</b><br><small>JSON, one patient</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:7rem"><b>Uvicorn</b><br><small>HTTP on port 8000</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:7rem"><b>FastAPI</b><br><small>POST /predict</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:7rem"><b>Pydantic</b><br><small>types, presence</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:7rem"><b>Pandera</b><br><small>allowed values</small></div>
</div>

<div class="flow text-sm" style="gap:0.4rem; justify-content:flex-end; margin-right:1.5rem">
  <div class="text-xl" style="color:#64748b">↓</div>
</div>

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:7rem"><b>Client</b><br><small>uses the answer</small></div>
  <div class="arrow">←</div>
  <div class="node violet no-shrink" style="width:23rem; text-align:left"><b>Response, 200</b><br><span class="mono" style="font-size:0.75rem">{"prediction": 1, "probability": 0.7173,<br>&nbsp;"model_version": "1", "schema_version": "1.0.0"}</span></div>
  <div class="arrow">←</div>
  <div class="node sky no-shrink" style="width:9rem"><b>Model</b><br><small>predict_proba, loaded once</small></div>
</div>

</div>

<!--
Walk the whole path once before we package it. Measured on 3 Oct 2026 with the lab's solution: Week 5's first patient scores 0.7173. The response carries the model version and the contract version, so the caller can report which model answered.
-->

---

# When the request is not enough

<carbon-data-base class="icon-corner" />

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:9rem"><b>Request</b><br><small>a patient ID and today's values</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:10rem"><b>Look up</b><br><small>stored features, from a feature store</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:10rem"><b>Compute</b><br><small>features from both</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:7rem"><b>Model</b></div>
</div>
<br>
<div class="text-sm" style="margin-top:1rem">

| **The service** | **Example** |
| --- | --- |
| <span v-click="1">gets every feature in the request</span> | <span v-click="1">the client sends all necessary values</span> |
| <span v-click="2">looks up stored features by ID</span> | <span v-click="2">the patient's earlier glucose readings</span> |
| <span v-click="3">computes a feature from both</span> | <span v-click="3">the change in glucose since the last visit</span> |

</div>
<br>
<v-click at="4">

> [!WARNING]
> A feature computed differently in serving than in training gives wrong answers without an error.

</v-click>

<!--
A feature store is a database of features that training and serving both read. Every lookup adds latency: Uber reports p95 under 5 ms without the Cassandra lookup and under 10 ms with it. The difference between training and serving features is called training-serving skew.
-->

---

# From probability to decision

<carbon-decision-tree class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.6rem">
  <div class="node sky no-shrink" style="width:10rem"><b>Model</b><br><small>probability 0.80</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:10rem"><b>Threshold 0.7</b><br><small>chosen in evaluation</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>Decision</b><br><small>high risk: call the patient</small></div>
</div>

<div v-click style="margin-top:1.2rem">

```json
POST /predict  →  200
{"probability": 0.80, "threshold": 0.7, "decision": "high risk",
 "model_version": "1"}
```

</div>

<v-click>

> [!TIP]
> Store the threshold with the model version, and return both the probability and the decision.

</v-click>

</div>

<!--
The threshold is a decision about costs: a missed patient against a needless call. It is chosen during evaluation, so it must travel with the model like any other artifact: a service that calls `predict` uses 0.5, whatever the team chose. The lab returns `prediction` (0.5) and `probability`. In Week 6, threshold 0.3 found 54 of the 67 test patients with diabetes and 0.7 found 26.
-->

---

# Everything the service needs

<carbon-package class="icon-corner" />

<div class="middle">

<div class="cards text-sm" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-code class="ic" /><b>Python 3.12</b>the runtime</div>
  <div class="card"><ph-lock class="ic" /><b>Packages</b>from <span class="mono">uv.lock</span>, as in training</div>
  <div class="card"><ph-file-code class="ic" /><b>Serving code</b>the FastAPI app, the contracts</div>
  <div class="card"><ph-cube class="ic" /><b>The model</b>and its threshold</div>
  <div class="card"><ph-tag class="ic" /><b>Metadata</b>model version, run, gate verdict</div>
  <div class="card"><ph-play class="ic" /><b>Start command</b><span class="mono">uvicorn app:app --port 8000</span></div>
</div>

<div v-click class="text-center" style="margin-top:1.5rem">

It runs on our laptop. **How do we run the same service on another server?**

</div>

</div>

<!--
The list from "What must travel with the model?" in section 1, now built, plus the command that starts it. The next section packages all six into one file that runs the same everywhere.
-->

---
layout: section
---

# 4 · Container images

<!--
About 12 minutes. The service runs on our laptop; this section packages it so it runs the same on any server. The lab's Dockerfile is written for students (Exercise 4); they read it and build it.
-->

---

# What is a container?

<carbon-container-software class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:1fr 1fr; gap:2.5rem; align-items:end">
<div class="text-center">
<div class="flow" style="flex-direction:column; gap:0.3rem; margin:0">
  <div class="flex gap-2">
    <div class="node sky no-shrink text-sm" style="width:8.5rem"><b>Container A</b><br><small>Python 3.12, packages, code, model</small></div>
    <div class="node sky no-shrink text-sm" style="width:8.5rem"><b>Container B</b><br><small>another program, its own packages</small></div>
  </div>
  <div class="node violet no-shrink text-sm" style="width:17.5rem"><b>Docker</b> <small>builds images, runs containers</small></div>
  <div class="node amber no-shrink text-sm" style="width:17.5rem"><b>Host: one Linux kernel</b></div>
</div>
<div class="text-xs" style="margin-top:0.4rem">containers share the host's kernel</div>
</div>
<div class="text-center">
<div class="flow" style="flex-direction:column; gap:0.3rem; margin:0">
  <div class="flex gap-2">
    <div class="node rose no-shrink text-sm" style="width:8.5rem"><b>VM A</b><br><small>a whole OS with its own kernel</small></div>
    <div class="node rose no-shrink text-sm" style="width:8.5rem"><b>VM B</b><br><small>a whole OS with its own kernel</small></div>
  </div>
  <div class="node violet no-shrink text-sm" style="width:17.5rem"><b>Hypervisor</b></div>
  <div class="node amber no-shrink text-sm" style="width:17.5rem"><b>Host</b></div>
</div>
<div class="text-xs" style="margin-top:0.4rem">virtual machines each boot an OS</div>
</div>
</div>

<div v-click class="text-sm" style="margin-top:1.5rem">

| | |
| --- | --- |
| **Image** | a package of files: OS libraries, Python, packages, our code, the model |
| **Container** | a running program started from an image, separated from other programs |

</div>

</div>

<!--
Section 1 asked what must travel with the model; an image is the box that carries all of it, and a container is the box running. Because a container shares the host's kernel, it starts in seconds; a virtual machine boots a whole OS and takes minutes. The same image runs the same way on a laptop, in CI and in a cluster.
-->

---

# Dockerfile, image, container

<carbon-container-services class="icon-corner" />

<div class="middle">

<div class="flow" style="margin-top:1rem">
  <div class="node amber no-shrink" style="width:10rem"><ph-file-code class="ic" /><b>serve.Dockerfile</b><br><small>the recipe</small></div>
  <div class="arrow-l">docker build<span class="arrow">→</span></div>
  <div class="node violet no-shrink" style="width:12rem"><ph-package class="ic" /><b>Image</b><br><small><span class="mono">diabetes-api:local</span></small></div>
  <div class="arrow-l">docker run<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:10rem"><ph-shipping-container class="ic" /><b>Container</b><br><small>the running copy</small></div>
</div>

</div>

<!--
`docker build` reads the Dockerfile and the files it copies, and writes an image; `docker run` starts a container from it. In the lab, `make image` and `make run-image` wrap the two commands.
-->

---

# Building the image, layer by layer

<carbon-layers class="icon-corner" />

<div class="middle">

<div style="display:flex; flex-direction:column; align-items:center; gap:0.25rem; margin-top:0" class="flow">
  <div v-click="6" class="node green no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">6 · Set the start command</b><br><span class="mono">CMD uv run uvicorn week_09_serving.api:app …</span></div>
  <div v-click="5" class="node sky no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">5 · Add the model</b><br><span class="mono">COPY models/model.pkl</span></div>
  <div v-click="4" class="node violet no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">4 · Label it: model version, run, gate verdict</b><br><span class="mono">ARG MODEL_VERSION</span> · <span class="mono">LABEL …</span></div>
  <div v-click="3" class="node violet no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">3 · Copy the code, install the environment</b><br><span class="mono">COPY src</span> · <span class="mono">RUN uv sync --locked --no-dev</span></div>
  <div v-click="2" class="node violet no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">2 · Copy the environment files</b><br><span class="mono">COPY pyproject.toml uv.lock</span></div>
  <div v-click="1" class="node amber no-shrink text-sm" style="width:32rem; padding:0.3rem 0.8rem"><b style="font-size:1.15rem">1 · Select a base image</b><br><span class="mono">FROM python:3.12-slim</span></div>
</div>

<div v-click="7" class="text-center" style="margin-top:0.8rem">The lab's image: <b>1.04 GB</b></div>

</div>

<!--
From the lab's `serve.Dockerfile`, bottom layer first, shortened: it also copies `uv`, `params.yaml` and the data file, and writes `baked.json` from the build arguments. The base image gives Debian and Python 3.12. Docker rebuilds a changed layer and every layer above it, so what changes most often goes last. A new model version changes the build arguments and `model.pkl`; `uv sync` stays cached, and the rebuild took under a second (30 Oct 2026).
`--locked` refuses a stale lock, as in CI: the image cannot get package versions that training did not have.
-->

---

# Where does the model come from?

<carbon-direction-fork class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node no-shrink" style="width:7rem"><b>Bake</b></div>
  <div class="node amber no-shrink" style="width:9rem"><ph-file class="ic" /><b>Local model</b><br><small>and gate report</small></div>
  <div class="arrow-l">docker build<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:10rem"><ph-shipping-container class="ic" /><b>Image</b><br><small>code + model</small></div>
  <div class="arrow-l">start<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:9rem"><b>Container</b><br><small>needs nothing else</small></div>
</div>

<div v-click="1" class="flow">
  <div class="node no-shrink" style="width:7rem"><b>Fetch</b></div>
  <div class="node sky no-shrink" style="width:10rem"><ph-shipping-container class="ic" /><b>Image</b><br><small>code only</small></div>
  <div class="arrow-l">start<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:9rem"><b>Container</b></div>
  <div class="arrow-l">download<span class="arrow">←</span></div>
  <div class="node amber no-shrink" style="width:9rem"><ph-database class="ic" /><b>Registry</b><br><small>at every start</small></div>
</div>

</div>

<!--
If two pods fetch the champion and the alias moves between their starts, they serve different versions; fetching a fixed version avoids this. If the registry is down at startup, a fetching container cannot load the model. With suitable rollout settings, the update stalls while old pods keep serving.
-->

---

# Bake or fetch

<carbon-scales class="icon-corner" />

<div class="middle">

<div class="text-sm" style="margin-top:1rem">

| | **Bake at build** | **Fetch at startup** |
| --- | --- | --- |
| Two containers from one image | <span v-click="1">always serve the same model</span> | <span v-click="1">may serve different models</span> |
| Registry needed at container start | <span v-click="2">no</span> | <span v-click="2">yes</span> |
| A new model needs | <span v-click="3">a new image</span> | <span v-click="3">a restart</span> |
| One image for many models | <span v-click="4">no</span> | <span v-click="4">yes</span> |

</div>

<div class="flow" style="margin-top:1.5rem">
  <div v-click="5" class="node green no-shrink" style="width:15rem"><b>This week: bake</b><br><small>the cluster runs with the MLflow stack down</small></div>
  <div v-click="6" class="node sky no-shrink" style="width:15rem"><b>Next week: fetch</b><br><small>KServe loads the model at startup</small></div>
</div>

</div>

<!--
A 16 GB laptop cannot run the stack and cluster together. `make image` can build with the stack down, but cannot identify the champion's version. Once loaded, this fetching design can serve without the registry until the next start.
-->

---

# Which model is in this container?

<carbon-tag class="icon-corner" />

<div class="middle">

```json
GET /health
{"status": "ok", "model_version": "1",
 "run_id": "ea06d98fbd9d4130aa1bb0e7f19a1ffe",
 "gate_verdict": "GO", "schema_version": "1.0.0",
 "model_source": "registry champion"}
```

<v-click>

```text
make trace
2. Version      : 1  (aliases: ['champion', 'staging'])
3. Run          : ea06d98fbd9d4130aa1bb0e7f19a1ffe
5. Data version : a8fd7b4f0d6d1bc4e378a8f76c5fff0c
8. Gate         : GO  (criteria v1.0.0, 0 failed, 4 skipped)
```

</v-click>

<v-click>

`/health` reports the build metadata. It does not verify the model file.

</v-click>

</div>

<!--
`make image` compares the local run ID with the champion's run ID before recording the version. The health endpoint reads that recorded claim; it does not compare the model's contents with the registry.
Built with the stack down, the same image says `"model_version": "unknown"` and `"model_source": "local models/model.pkl"`: it does not claim what it cannot know.
-->

---

# Keeping a NO-GO model out of deployment

<carbon-locked class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.3rem">
  <div class="node amber no-shrink" style="width:6rem"><b>Train</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:6rem"><ph-shield-check class="ic" /><b>Gate</b><br><small>GO or NO-GO</small></div>
  <div class="arrow-l on" style="min-width:2.6rem"><span>GO?</span><span class="arrow">→</span></div>
  <div class="node no-shrink" style="width:6rem"><b>Register</b><br><small>Week 6</small></div>
  <div class="arrow-l on" style="min-width:2.6rem"><span>GO?</span><span class="arrow">→</span></div>
  <div class="node no-shrink" style="width:6rem"><b>Promote</b><br><small>Week 6</small></div>
  <div v-click="1" class="arrow-l on" style="min-width:2.6rem"><span>GO?</span><span class="arrow">→</span></div>
  <div v-click="1" class="node sky no-shrink" style="width:6rem"><b>Build image</b><br><small>Week 9</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node no-shrink" style="width:6rem"><b>Deploy</b><br><small>Week 10</small></div>
</div>

<v-click at="2">

```text
$ make image
REFUSING to build: the recorded gate verdict is 'NO-GO'.
```

There are always bypasses: A direct `docker build` bypasses this check.

</v-click>

<v-click at="3">

> [!TIP]
> Check the gate verdict in every path that can ship a model.

</v-click>

</div>

<!--
Every step that moves the model closer to users checks the verdict again: register and promote since Week 6, and now `make image`. The lab's Make target checks the recorded verdict before it calls Docker. A production release process needs an enforced gate, for example in CI with release permissions restricted to that path.
Week 10 adds a fourth: the model store that KServe reads.
-->

---
layout: center
---

# One container serves the model.
# What can go wrong?

<v-click>

- It crashes, and nobody starts it again.
- More requests arrive than one copy can answer.
- A new version means stopping the old one.

</v-click>

<v-click>

- **Run several copies, and let a program keep them running.**

> [!TIP]
> Hand the containers to an orchestrator, as Week 8 handed the pipeline's tasks to Prefect.

</v-click>

<!--
Booking.com's "model redundancy": copies of each model across a cluster. Orchestration is the idea from Week 8: a program starts the work, watches it and acts when something fails. Prefect orchestrates runs that finish; Kubernetes orchestrates services that must keep running. Docker Compose (Week 2) restarts containers on one machine; it does not spread copies over several.
-->

---
hide: true
---

# Optional case · 2016: Pokémon GO's launch

<carbon-rocket class="icon-corner" />

<div class="middle">

Pokémon GO is a mobile game by Niantic. It launched in July 2016, on Google's Kubernetes service (GKE)[^1][].

<div class="flex justify-center gap-3 text-center" style="margin-top:3.5rem">
  <div style="width:10rem"><div class="text-5xl font-bold">1×</div><div>the traffic Niantic planned for</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:10rem"><div class="text-5xl font-bold" style="color:#d97706">5×</div><div>the worst case they expected</div></div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:10rem"><div class="text-5xl font-bold" style="color:#dc2626">50×</div><div>the traffic that came</div></div></div>
</div>

</div>

[^1]: Luke Stone (Google), "Bringing Pokémon GO to life on Google Cloud", 30 Sept 2016. https://cloud.google.com/blog/products/containers-kubernetes/bringing-pokemon-go-to-life-on-google-cloud

<!--
Optional case for the Kubernetes section, with "Before Japan: more copies": show both after "One container serves the model. What can go wrong?". No other slide refers to it.
Traffic passed Niantic's expectations within 15 minutes of the launch in Australia and New Zealand.
-->

---
hide: true
---

# Before Japan: more copies

<carbon-rocket class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node rose no-shrink" style="width:12rem"><ph-users-three class="ic" /><b>US launch</b><br><small>50× the planned traffic</small></div>
  <div v-click="1" class="arrow-l">GKE upgrade<span class="arrow">→</span></div>
  <div v-click="1" class="node violet no-shrink" style="width:12rem"><ph-copy class="ic" /><b>The cluster</b><br><small>room for more than a thousand extra nodes</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:12rem"><ph-check-circle class="ic" /><b>Japan launch</b><br><small>3× the US sign-ups, without incident</small></div>
</div>

<v-click at="3">

> [!TIP]
> Plan capacity above your worst-case estimate, and make adding copies a change to one number.

</v-click>

</div>

Google Cloud blog, 30 Sept 2016[^1][]

[^1]: Luke Stone (Google), "Bringing Pokémon GO to life on Google Cloud", 30 Sept 2016. https://cloud.google.com/blog/products/containers-kubernetes/bringing-pokemon-go-to-life-on-google-cloud

<!--
Optional case, second slide. The team also replaced the network load balancer with Google's HTTP/S load balancer. The worst case was off by ten times: an estimate is not a measurement, and Week 10 load-tests the service.
-->

---
layout: section
---

# 5 · Kubernetes

<!--
About 15 minutes. Only Pod, Deployment, Service and probes; Ingress, autoscaling and Helm stay out of the course.
-->

---

# What is Kubernetes?

<carbon-kubernetes class="icon-corner" />

<div class="middle">

Kubernetes runs containers on a group of machines, a **cluster**, and keeps them in the state you declare[^1][].

<div class="flow text-sm" style="margin-top:1.2rem; gap:0.5rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-file-code class="ic" /><b>YAML files</b><br><small>the state you want: "two copies of this image"</small></div>
  <div class="arrow-l">kubectl apply<span class="arrow">→</span></div>
  <div class="node violet no-shrink" style="width:10rem"><ph-gear class="ic" /><b>Control plane</b><br><small>stores the wanted state; controllers compare and fix</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:10rem"><ph-hard-drives class="ic" /><b>Nodes</b><br><small>the machines that run the containers</small></div>
</div>

<div v-click class="cards text-sm" style="grid-template-columns:repeat(4,1fr); margin-top:1.2rem">
  <div class="card"><b>Restarts</b>a container that fails</div>
  <div class="card"><b>Spreads</b>copies over the machines</div>
  <div class="card"><b>Routes</b>requests to healthy copies</div>
  <div class="card"><b>Replaces</b>a version step by step</div>
</div>

</div>

[^1]: Kubernetes docs, "Overview". https://kubernetes.io/docs/concepts/overview/

<!--
The docs call it "a portable, extensible, open source platform for managing containerized workloads and services". The key idea is declarative: you do not tell Kubernetes to start a container, you write down what should be running, and it keeps that true. Docker Compose (Week 2) runs containers on one machine and does not spread copies over several.
-->

---

# A simple Kubernetes architecture

<carbon-kubernetes class="icon-corner" />

<div class="flow" style="gap:0.6rem">
  <div v-click="3" class="node amber no-shrink" style="width:8rem"><b>Request</b></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:11rem"><b>Service</b></div>
  <div v-click="2" class="arrow">→</div>
  <div style="display:flex; flex-direction:column; gap:0.5rem">
    <div class="node sky no-shrink" style="width:11rem"><b>Pod</b><br><small><span class="mono">app: diabetes-api</span></small></div>
    <div v-click="1" class="node sky no-shrink" style="width:11rem"><b>Pod</b><br><small><span class="mono">app: diabetes-api</span></small></div>
  </div>
  <div v-click="1" class="arrow">←</div>
  <div v-click="1" class="node violet no-shrink" style="width:11rem"><b>Deployment</b><br><small><span class="mono">replicas: 2</span></small></div>
</div>

<div class="text-sm" style="margin-top:1rem">

| | **Is** |
| --- | --- |
| **Pod** | the smallest unit Kubernetes runs: containers with one network address |
| <span v-click="1">**Deployment**</span> | <span v-click="1">declares which image and how many pods; keeps them running</span> |
| <span v-click="2">**Service**</span> | <span v-click="2">a stable address; sends each request to a ready pod, found by label</span> |
| <span v-click="4">**Probe**</span> | <span v-click="4">a request to each pod, here `GET /health`; no answer, no traffic</span> |

</div>


<!--
A pod can hold several containers that share a network address; ours holds one. Pods come and go and change address; the Service stays.
A probe is not an object of its own: it is a few lines in the container's part of the Deployment.
-->

---
layout: center
---

# You delete one of the two pods by hand.
# What happens?

<div v-click class="flow" style="margin-top:1.5rem">
  <div class="node violet no-shrink" style="width:11rem"><b>Declared</b><br><span class="mono">replicas: 2</span></div>
  <div class="arrow-l fail">differs<span class="arrow">≠</span></div>
  <div class="node rose no-shrink" style="width:11rem"><b>Running</b><br>1 pod</div>
  <div class="arrow-l">controller<span class="arrow">→</span></div>
  <div class="node sky no-shrink" style="width:11rem"><b>A new pod</b><br><small>starts within seconds</small></div>
</div>

<div v-click class="text-center" style="margin-top:1.5rem">

The Deployment says what should be true. A controller keeps making it true.

</div>

<v-click>

> [!TIP]
> Do not restart containers by hand: let the controller do it.

</v-click>

<!--
This is the idea that makes the rest of Kubernetes readable: a loop compares the declared state with the running state and acts on the difference. Week 10's KServe is the same idea one level up.
-->

---
class: fn-inline
---

# Local cluster options

<carbon-kubernetes class="icon-corner" />

<div class="middle">

In production, Kubernetes runs on many machines, usually from a cloud provider or a platform team. A **local cluster** runs the same Kubernetes on one laptop: the same API and YAML files, for learning and testing.

<div class="cards" style="grid-template-columns:repeat(4,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><ph-shipping-container class="ic" /><b>kind</b>"local Kubernetes clusters using Docker container 'nodes'"</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-laptop class="ic" /><b>minikube</b>a local cluster on macOS, Linux and Windows</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><ph-shipping-container class="ic" /><b>k3d</b>k3s, a minimal Kubernetes, in Docker</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'" style="opacity:0.45"><ph-globe class="ic" /><b>A cloud cluster</b>GKE, EKS, AKS<br><small>not in this course</small></div>
</div>

<div class="text-sm opacity-70">

kind[^1][] · minikube[^2][] · k3d[^3][]

</div>

<v-click>

Any of the three would do. **We use kind:** Week 10 installs KServe on the same kind cluster.

</v-click>

</div>

[^1]: https://kind.sigs.k8s.io/
[^2]: https://minikube.sigs.k8s.io/docs/
[^3]: https://k3d.io/stable/

<!--
kind "was primarily designed for testing Kubernetes itself". The lab uses kind v0.32.0 and kubectl; `kind create cluster` took about 60 seconds.
-->

---

# A Deployment and a Service

<carbon-document class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem">
<div>

```yaml {all|7|8-9|10-16|all}
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iris-api
spec:
  replicas: 2
  selector:
    matchLabels: {app: iris-api}
  template:
    metadata:
      labels: {app: iris-api}
    spec:
      containers:
        - name: api
          image: iris-api:local
```

</div>
<div>

```yaml {all|7|8-10|all}
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: iris-api
spec:
  selector: {app: iris-api}
  ports:
    - port: 80
      targetPort: 8000
```

<v-click>

```bash
kubectl apply -f deployment.yaml -f service.yaml
```

</v-click>

</div>
</div>

</div>

<!--
The quick-start app as manifests. Checked as YAML on 3 Oct 2026; not applied to a cluster in this lecture. The lab's manifests add `imagePullPolicy`, ports by name and the two probes.
The label `app: iris-api` appears three times: in the Deployment's selector, in the pod template's labels and in the Service's selector. All three must match.
-->

---

# Is the pod ready?

<carbon-health-cross class="icon-corner" />

<div class="middle">

<div class="flow">
  <div class="node green no-shrink" style="width:9rem"><ph-plug class="ic" /><b>Service</b></div>
  <div style="display:flex; flex-direction:column; gap:0.5rem">
    <div class="flow" style="margin:0; justify-content:flex-start">
      <div class="arrow-l">traffic<span class="arrow">→</span></div>
      <div class="node sky no-shrink" style="width:13rem"><b>Pod A</b><br><small>ready: gets traffic</small></div>
    </div>
    <div class="flow" style="margin:0; justify-content:flex-start">
      <div class="arrow-l fail">no traffic<span class="arrow" style="color:#e11d48">⇢</span></div>
      <div class="node rose no-shrink" style="width:13rem"><b>Pod B</b><br><small>still loading the model</small></div>
    </div>
  </div>
</div>

<div v-click class="text-sm">

| **Probe** | **Asks** | **When it fails** |
| --- | --- | --- |
| Readiness | may this pod get traffic? | the pod leaves the Service's endpoints and keeps running |
| Liveness | is this container broken? | the kubelet restarts the container |

</div>

<div v-click class="text-sm text-center">

Both call an endpoint of the app, here `GET /health`[^1][].

</div>

</div>

[^1]: Kubernetes docs, "Liveness, Readiness, and Startup Probes" (opened 3 Oct 2026). https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/

<!--
The probe checks that a model is loaded; it does not check prediction quality. The same docs warn that a badly set liveness probe can restart containers under load and cause cascading failures.
-->

---
layout: section
---

# 6 · Wrap-up

<!--
About 6 minutes: the week's system, takeaways, open questions, the lab, and the questions students can now answer.
-->

---

# This week's system

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node green no-shrink" style="width:9rem"><ph-shield-check class="ic" /><b>GO model</b><br><small>Week 6 gate</small></div>
  <div v-click="1" class="arrow-l">make image<span class="arrow">→</span></div>
  <div v-click="1" class="node sky no-shrink" style="width:11rem"><ph-shipping-container class="ic" /><b>Image</b><br><small>model baked in<br>lock file, labels</small></div>
  <div v-click="2" class="arrow-l">kind load<span class="arrow">→</span></div>
  <div v-click="2" class="node violet no-shrink" style="width:12rem"><ph-copy class="ic" /><b>Deployment</b><br><small>2 pods, probes on <span class="mono">/health</span></small></div>
</div>

<div v-click="3" class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:7rem"><ph-globe class="ic" /><b>Request</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:7rem"><ph-plug class="ic" /><b>Service</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:8rem"><b>Pydantic</b><br><small>types</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>Pandera</b><br><small>values, or a 422</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><b>predict_proba</b><br><small>p50 and p95</small></div>
</div>

</div>

<!--
Inside each pod, every request passes the same two checks as on the laptop. The image carries the Python version and the lock file, so the server runs the laptop's environment.
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<div class="middle">

<v-clicks>

- A model file is supported only in the environment that wrote it: ship the two together.
- Choose how to serve by when the input exists and how fresh the answer must be; batch is the simplest when it is fresh enough.
- Report latency as percentiles, measured on your own system.
- Check every request with the contract that trained the model.
- Every path that ships a model must check the gate.
- Declare how many ready copies should run, and let a controller keep them running.

</v-clicks>

</div>

<!--
A model that scores a table once a night needs the first takeaway and the gate, but no service and no cluster. Week 10 asks the next question: how to replace the model in those copies safely.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><carbon-renew class="ic" /><b>How do we replace the model safely?</b>A new image reaches every user at once. Nothing checks whether the new model is better.<br><b>→ Week 10:</b> canary, shadow, rollback, load tests</div>
  <div v-click class="card"><carbon-meter class="ic" /><b>Is the service healthy right now?</b>We measured latency once, on a laptop.<br><b>→ Week 11:</b> metrics, SLOs, alerts</div>
</div>

</div>

<!--
Week 10 also finishes the bake-or-fetch story: KServe fetches the model, and one image serves several versions. Our 192 sequential requests were not a load test: no concurrency, no sustained rate.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="middle">

<div class="text-sm">

| **#** | **Exercise** | **What you show** |
| --- | --- | --- |
| 1 | The MLflow model server | `mlflow models serve`: what it scores and what it refuses |
| 2 | Your own service | `POST /predict` with the Week 5 contract, `GET /health` |
| 3 | Batch versus online in the lab | wall clock, throughput, p50 and p95 |
| 4 | A container image with the model in it | `/health` in the container matches `make trace` |
| 5 | A Deployment, a Service and probes | `ErrImagePull` first, then two ready pods on kind |

</div>

Exercises 1, 3 and 4 have written answers. HW 3 is out this week.

</div>

<!--
Stop the Week 8 stack before the lab. Only Exercise 1 and `make image` need the Compose stack; never run it together with the kind cluster on a 16 GB laptop.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

<div class="middle">

- What must travel with a model when it leaves the training machine?
- When does a use case need batch, online, streaming or on-device serving?
- Why do we report latency as p50 and p95, and not as a mean?
- What does Pydantic check in a request, and what does the Week 5 contract add?
- What is the trade-off between baking the model into an image and fetching it at startup?
- What do a Pod, a Deployment and a Service do, and what happens when a probe fails?

</div>

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
