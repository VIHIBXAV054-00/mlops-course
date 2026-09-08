---
theme: default
title: Week 1 — Introduction to MLOps
info: |
  A two-hour introductory lecture for the course "Lifecycle of Artificial Intelligence Systems".
class: text-left
transition: slide-left
mdc: true
# hash routing + relative base (built with --base ./) so the SPA works in a
# GitHub Pages subdirectory: slides live after the # and assets load relatively.
routerMode: hash
---

# Week 1: Introduction to MLOps

**Lifecycle of Artificial Intelligence Systems**

- Why MLOps exists
- Why ML lifecycles differ from classic software delivery
- What teams, tools, and workflows matter first

---

# Zillow Offers: a price, straight from a model

<img src="/zillow.png" class="case-shot">

---

# November 2021: a software failure with no stack trace

Zillow — one of the largest US real-estate platforms — shuts down its house-flipping business, **Zillow Offers**.

- Its pricing model (the "Zestimate" pipeline) systematically **overpaid for homes** as the market shifted
- Roughly **$300M written off in a single quarter**; ~25% of the workforce laid off
- The code had no bug. The services were up. Every request returned **HTTP 200**.

<br>

<div style="font-size: 1.6em; line-height: 1.35; font-weight: 600; margin-top: 0.5em;">
The model was wrong about the world.
</div>


---

# The dashboards were green the whole time

Classic monitoring watched: uptime ✓ latency ✓ error rate ✓

Nobody was systematically watching:

- had the input data distribution shifted since training?
- did the relationship between features and prices still hold?
- which data snapshot and which code version produced the deployed model?
- what was the rollback plan for a *statistically* failing model?

<br>

### **This course is about building the engineering systems that answer those questions.**

<!--
The same failure pattern hit credit-scoring models during COVID: inputs looked normal, predictions were wrong.
-->
---

# What you will build this semester

<img src="/mlops-cycle.svg" class="cycle cycle-sm">

<style>
.cycle { display: block; margin: 0.2rem auto 0.5rem; width: 100%; }
.cycle-sm { max-width: 800px; }
</style>

---


# What you will build this semester

| Loop stage | Weeks | What you add to the project |
| :--- | :--- | :--- |
| **Design · Build** | 1–5 | reproducible env, experiment tracking, data versioning, contracts |
| **Test** | 6–8 | evaluation gates, CI, orchestration |
| **Deploy** | 9–10 | containerised serving, canary rollout |
| **Operate · Monitor** | 11–13 | SLOs, dashboards, drift, governance |

<style>
table { font-size: 1.2rem; }
table td, table th { padding: 0.2rem 0.5rem; }
</style>

---

# Agenda

1. **Why do we need MLOps** — what breaks, and why DevOps alone does not fix it
2. **ML in research vs. in production** — the same model, two different jobs
3. **ML systems vs. traditional software** — where code and data stop being separable
4. **ML production myths** — six things people believe on the way in
5. **When to use ML** — and when a lookup table is the right answer
6. **The lifecycle** — the loop every ML system lives in, and where the friction shows up
7. **The three pillars** — reproducibility, scalability, automation
8. **Who does the work** — the roles around the loop
9. **The toolchain** — Git, Docker, MLflow, CI/CD
10. **In practice** — the anti-patterns, and today's lab

<!--
If you are short on time, sections 4 and 9 compress best (myths can be read from the notes,
the toolchain returns every week). Sections 2, 3 and 6 are the ones the rest of the
semester is hung on.
-->

---
layout: section
---

# 1 · Why do we need MLOps?

---

# Deterministic vs. probabilistic systems

Traditional software usually follows explicit rules.

ML systems learn a function from historical data and make predictions with uncertainty.

Implications:

- the same code can produce different models with different data
- “correctness” is measured statistically, not absolutely
- operational quality depends on both software and data quality

---

# DevOps solved a different problem

Classic DevOps is optimized for deterministic applications:

- source code is the main changing artifact
- builds produce stable binaries or containers
- automated tests validate expected behavior
- production health is often visible through latency, errors, and uptime

That foundation is still useful, but it is not enough for ML systems.

---

# Why MLOps became necessary

Traditional software teams ship code.

ML teams ship **code, data assumptions, and learned model parameters**.

That creates new operational questions:

- Which dataset produced this model?
- Can we reproduce the same result tomorrow?
- What happens when the real-world input distribution changes?
- How do we test a probabilistic system that may degrade silently?

---

# Why classic DevOps is insufficient for ML

| Traditional DevOps | MLOps |
| --- | --- |
| Main artifact: code | Main artifacts: code, data, models |
| Behavior changes mostly after code changes | Behavior can change after code, data, or retraining |
| Unit and integration tests dominate | Statistical validation and data checks become essential |
| Failures are often explicit | Failures are often silent quality drops |
| Rollback is mostly binary replacement | Rollback may require model, feature, and data coordination |

---

# The triad of change

Three moving parts shape an ML system:

1. **Code** — feature logic, training logic, serving logic
2. **Data** — training snapshots, labels, schemas, distributions
3. **Model state** — learned weights or parameters

A change in any one of them can change system behavior.

---
layout: section
---

# 2 · ML in research vs. in production

---

# The same model, two different jobs

| | **Research** | **Production** |
| :--- | :--- | :--- |
| **Objectives** | model performance on a benchmark | different stakeholders want different things |
| **Computational priority** | fast training, high throughput | fast **inference**, low latency |
| **Data** | static, clean, historical | messy, shifting, historical + streaming |
| **Fairness** | "good to have" | must be considered |
| **Interpretability** | "good to have" | must be considered |

<div class="src">After Chip Huyen, <i>Designing Machine Learning Systems</i> (O'Reilly, 2022), Table 1-1.</div>

<style>
table { font-size: 1.2rem; }
table td, table th { padding: 0.3rem 0.6rem; }
.src { position: absolute; bottom: 1rem; left: 3rem; font-size: 0.65rem; opacity: 0.45; }
</style>

<!--
This table is the spine of the section — the next five slides each unpack one row.
-->

---

# Nobody agrees on what "better" means

<br>

<div class="personas">
  <div class="p"><div class="ico">🧪</div><div class="who">ML team</div><div class="want">a more complex model,<br>higher accuracy</div></div>
  <div class="p"><div class="ico">💰</div><div class="who">Sales</div><div class="want">recommend the<br>expensive restaurants</div></div>
  <div class="p"><div class="ico">⚡</div><div class="who">Product</div><div class="want">answer in under<br>100&nbsp;ms, or users leave</div></div>
  <div class="p"><div class="ico">🛠️</div><div class="who">Platform</div><div class="want">stop shipping models,<br>the pager is going off</div></div>
  <div class="p"><div class="ico">📈</div><div class="who">Manager</div><div class="want">maximise margin<br><i>(= fewer ML people)</i></div></div>
</div>

<style>
.personas { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.7rem; margin: 1.4rem 0 1.2rem; }
.p { text-align: center; }
.ico { font-size: 2.4rem; line-height: 1.1; }
.who { font-weight: 700; font-size: 1rem; margin-top: 0.2rem; }
.want { font-size: 0.78rem; opacity: 0.78; line-height: 1.35; margin-top: 0.2rem; }
.src { position: absolute; bottom: 1rem; left: 3rem; font-size: 0.65rem; opacity: 0.45; }
</style>

<!--
Ask the room which one is wrong. None of them are. That is the point: "the best model" is
not a technical fact, it is a negotiated definition, and somebody has to write it down.
-->

---

# Latency is a business metric

<br>

<div class="stat-row">
  <div class="stat"><div class="big">0.2–0.6%</div><div class="cap">fewer searches at <b>Google</b> when latency went 100 ms → 400 ms <span class="yr">(2009)</span></div></div>
  <div class="stat"><div class="big">0.5%</div><div class="cap">conversion lost at <b>Booking.com</b> for a 30% latency increase <span class="yr">(2019)</span></div></div>
</div>

<br>

**Research optimises throughput. Production optimises latency.**

- *Latency*: how long one prediction takes
- *Throughput*: how many predictions per second
- Batching raises both; real-time serving trades throughput away to keep latency low

<style>
.stat-row { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin: 1.2rem 0 1.4rem; }
.stat { border-left: 4px solid #4f46e5; padding-left: 0.9rem; }
.big { font-size: 2.2rem; font-weight: 800; line-height: 1; }
.cap { font-size: 1.2rem; opacity: 0.8; margin-top: 0.35rem; }
.yr { opacity: 0.6; }
</style>

<!--
-->

---

# Research data is clean because somebody cleaned it

<br>

<div class="two-col">
<div>

### Research
- clean
- static
- mostly historical
- the benchmark is the dataset

</div>
<div>

### Production
- messy
- constantly shifting
- historical + streaming
- biased, and you don't know how
- privacy and regulatory constraints

</div>
</div>

<br>

<style>
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; margin-top: 0.6rem; }
.two-col h3 { margin-bottom: 0.4rem; }
</style>

<!--
The honest version of the 80/20 claim: it is quoted everywhere, sourced to an InfoWorld
column, and has no study behind it. Say that — it models the sourcing discipline the
course asks of them.
-->

---

# Fairness and interpretability stop being optional

- **In research** they are a section you add if a reviewer asks for one
- **In production** somebody is on the receiving end of every prediction — and they can
  ask *why*
- A model that cannot be explained cannot be **appealed**, **audited**, or **defended**
- Neither can be added at the end

<div class="hook">
Suppose you have cancer and you have to choose between a black box AI surgeon that cannot
explain how it works but has a 90% cure rate, and a human surgeon with an 80% cure rate.
<b>Do you want the AI surgeon to be illegal?</b>
<div class="attr">— Geoffrey Hinton, February 2020</div>
</div>

<style>
.hook {
  position: absolute; bottom: 2.2rem; left: 3rem; right: 3rem;
  border-left: 5px solid #4f46e5; padding: 0.9rem 1.2rem;
  background: rgba(79, 70, 229, 0.06);
  font-size: 1.28rem; line-height: 1.4;
}
.attr { font-size: 0.8rem; opacity: 0.6; margin-top: 0.5rem; }
</style>


<!--
Run it as a hands-up vote before showing the quote. In Huyen's class 67% picked the AI
surgeon. It splits a room and takes ninety seconds.

Then the follow-up that matters: what would you need to see to change your vote? That is
an interpretability requirement, and it can be written into a spec.
-->

---
layout: section
---

# 3 · ML systems vs. traditional software

---

# Traditional software: separate the concerns

<div class="big-idea">Code and data are <b>separate</b>.</div>

- The input does not change the program
- You test the code; the data is somebody else's problem
- A version is a commit; a rollback is a redeploy of that commit

<style>
.big-idea { font-size: 1.5rem; font-weight: 600; margin: 1.1rem 0; }
</style>

<!--
Name the principle: separation of concerns. Every student has been taught it, and it is
exactly the thing that breaks next slide.
-->

---

# ML systems: the coupling is the problem

<div class="big-idea">Code and data are <b>tightly coupled</b>. An ML system is part code, part data.</div>

So you have to version and test **both** — and the data half is the hard part:

<div class="two-col">
<div>

### Versioning data
- line-by-line diffs do not work on a dataset
- you cannot naively keep N copies of 50 GB
- what does "merge" even mean?

</div>
<div>

### Testing data
- is it correct? does it meet the model's assumptions?
- has the distribution moved — and by how much?
- not all rows are equal (cyclists on road images)
- bad rows are an **attack surface**

</div>
</div>

<style>
.big-idea { font-size: 1.2rem; font-weight: 600; margin: 0.5rem 0 0.9rem; }
.two-col { display: grid; grid-template-columns: 1fr 1.15fr; gap: 2rem; font-size: 0.86rem; }
.two-col h3 { margin-bottom: 0.35rem; font-size: 1.1rem; }
</style>

<!--
Weeks 4 and 5 are literally these two columns: DVC answers the left, Pandera and the
contract answer the right.

The last bullet is the one to linger on — most students have never thought of a training
row as an input an attacker controls.
-->

---

# Bad rows are an attack surface

<div class="figure" role="img" aria-label="Backdoor attack: a face recognition system poisoned so that anyone wearing a specific pair of glasses is recognised as one target identity"></div>

A handful of poisoned training images installs a **physical backdoor**: wear these glasses,
be recognised as someone else.

<div class="src">Chen et al., "Targeted Backdoor Attacks on Deep Learning Systems Using Data Poisoning" (2017), Fig. 1 — reproduced for teaching.</div>

<style>
.figure { height: 300px; margin: 0.6rem auto 0.8rem; background: url('/thirdparty/data-poisoning.png') center / contain no-repeat; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
Thirty seconds, no more. The purpose is to make "test your data" feel like a security
control rather than hygiene.
-->

---

# And when it breaks, nothing goes red

<div class="figure" role="img" aria-label="Two failures side by side: a normal service showing an error page, and a mistranslated sign reading EATING CARPET STRICTLY PROHIBITED"></div>

<div class="two-col">
<div><b>Normal software fails</b> — you get a stack trace,  a red build.</div>
<div><b>ML fails</b> — you get a confident, fluent, wrong answer.</div>
</div>

<div class="src">Illustration from Chip Huyen's <i>Machine Learning Systems Design</i> lecture slides.</div>

<style>
.figure { height: 290px; margin: 0.4rem auto 0.7rem; background: url('/thirdparty/fail-silently.png') center / contain no-repeat; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; font-size: 0.95rem; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
Callback to the Zillow cold open: every request returned 200 there too.

This slide is the bridge to the monitoring half of the course — if the failure is silent,
somebody has to go looking, on purpose, on a schedule.
-->

---
layout: section
---

# 4 · ML production myths

---

# Myth 1 · "Deploying is hard"

### <v-click> Deploying is easy. </v-click>

<br>

### **<v-click> Deploying reliably is hard. </v-click>**

<!--
Week 9 is the afternoon. Weeks 10 to 13 are "reliably".
-->

---

# Myth 2 · "You only deploy one or two models"



<div v-click class="figure" role="img" aria-label="Netflix Research: a long list of ML applications running simultaneously, from content valuation to CDN caching"></div>

### **<v-click> Booking.com: 150+ models </v-click>**
### **<v-click> Uber: thousands </v-click>**

<div class="src">Netflix Research, via Chip Huyen's lecture slides.</div>

<style>
.figure { height: 250px; margin: 0.5rem auto 0.8rem; background: url('/thirdparty/netflix-many-models.png') center / contain no-repeat; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
Our course builds one model, and that is a simplification we should name out loud. The
registry in Week 3 and the rollout in Week 10 are the parts that survive multiplication.
-->

---

# Myth 3 · "If we don't touch it, performance stays the same"

<div v-click class="myth">The world moves. <b>Your model does not.</b></div>

<div v-click class="myth">The two are <b>drifting apart.</b></div>



<style>
.myth { font-size: 1.7rem; line-height: 1.35; margin: 1.2rem 0 1rem; }
</style>

<!--
-->

---

# Myth 4 · "You won't need to update models often"

<div v-click class="figure" role="img" aria-label="Weibo's machine learning platform: iteration cycle shrinking from monthly to 10 minutes across platform versions"></div>

<div v-click class="stats-list">
  <ul>
    <li>Etsy 50 deploys/day</li>
    <li>Netflix 1000s/day</li>
    <li>Weibo: every 10 minutes.</li>
    <li>AWS every 11.7 s.</li>
  </ul>
</div>

<style>
.stats-list {
  margin-top: 0.8rem;
  font-size: 1.05rem;
}
.stats-list ul {
  margin: 0;
  padding-left: 1.4rem;
  line-height: 1.8;
}
</style>

<div class="src">Qian Yu, "Machine learning with Flink in Weibo", QCon 2019, via Chip Huyen's slides.</div>

<style>
.figure { height: 265px; margin: 0.4rem auto 0.7rem; background: url('/thirdparty/weibo-iteration.png') center / contain no-repeat; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
Do not oversell this: 10 minutes is a CTR model at a social network, the extreme end. The
useful question is not "how fast can you" but "how fast could you if you had to" — and
the answer is set by your pipeline, not your model.
-->

---

# Myth 5 · "Scale is somebody else's problem"

<div v-click class="figure" role="img" aria-label="StackOverflow Developer Survey 2019: distribution of respondents by company size, with over half at companies of 100+ employees"></div>

<v-click>
Over half of developers work at companies with 100+ employees.

"Big-company problems" are most people's problems.
</v-click>

<div class="src">StackOverflow Developer Survey 2019, via Chip Huyen's slides.</div>

<style>
.figure { height: 265px; margin: 0.4rem auto 0.7rem; background: url('/thirdparty/company-size.png') center / contain no-repeat; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
The honest caveat: company size is a proxy for scale, not scale itself. A 20-person
fintech can have more traffic than a 5000-person manufacturer.
-->

---

# Myth 6 · "ML will transform the business overnight"

<div v-click class="myth">Magically: possible.<br><b>Overnight: no.</b></div>

<div v-click class="figure" role="img" aria-label="Algorithmia 2020 survey: teams with 5+ years of models in production deploy far faster than teams just getting started"></div>

<v-click>
Teams with models in production for **5+ years** deploy in days.

Teams doing it for the first time measure in months.
</v-click>

<div class="src">Algorithmia, <i>2020 State of Enterprise Machine Learning</i>, via Chip Huyen's slides.</div>

<style>
.myth { font-size: 1.5rem; line-height: 1.3; margin: 0.5rem 0 0.6rem; }
.figure { height: 215px; margin: 0.2rem auto 0.5rem; background: url('/thirdparty/deploy-time-maturity.png') center / contain no-repeat; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.62rem; opacity: 0.45; }
</style>

<!--
This is the slide that justifies the whole course to a sceptic: the difference between
the top and bottom row of that chart is not talent or model quality, it is infrastructure
that already exists.
-->

---
layout: section
---

# 5 · When to use ML

---

# What an ML solution actually is

> Machine learning is an approach to **(1) learn** **(2) complex patterns** from
> **(3) existing data** and use these patterns to make **(4) predictions** on
> **(5) unseen data**.

Five conditions:

| | **Fails when** |
| :--- | :--- |
| **Learn** — the system can learn | the relationship must be stated by hand |
| **Complex patterns** — and they exist | a lookup table would do |
| **Existing data** — available, or collectable | you have no data and no way to get it |
| **Predictions** — it is a predictive problem | you need an exact answer, not an estimate |
| **Unseen data** — shares patterns with training | tomorrow does not look like yesterday |

<div class="src">Huyen, <i>Designing Machine Learning Systems</i> (O'Reilly, 2022), ch. 1.</div>

<style>
table { font-size: 0.84rem; }
table td, table th { padding: 0.25rem 0.6rem; }
blockquote { font-size: 0.95rem; }
.src { position: absolute; bottom: 1rem; left: 3rem; font-size: 0.65rem; opacity: 0.45; }
</style>

<!--
The zip-code example is the one that lands: a lookup table is not a worse ML system, it
is the correct engineering answer, and reaching for a model there is the mistake.
-->

---

# ML shines when...

<div class="grid4">
  <div class="c"><div class="ico">🔁</div><b>It's repetitive</b><br><span>the pattern repeats often enough for a machine to learn it</span></div>
  <div class="c"><div class="ico">🪶</div><b>Wrong is cheap</b><br><span>a bad recommendation costs a click, not a life</span></div>
  <div class="c"><div class="ico">📶</div><b>It's at scale</b><br><span>the up-front cost is amortised over millions of predictions</span></div>
  <div class="c"><div class="ico">🌊</div><b>Patterns keep changing</b><br><span>hand-written rules would go stale faster than you can edit them</span></div>
</div>

<style>
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem; margin-top: 1.4rem; }
.c { font-size: 0.85rem; line-height: 1.45; }
.c .ico { font-size: 2rem; }
.c span { opacity: 0.78; }
</style>

<!--
Spam is the clean example of the fourth: today it is a Nigerian prince, tomorrow it is
something else, and no ruleset survives that on its own.
-->

---

# ...and when not to use it at all

<div class="dont">
  <div class="d"><span class="x">✕</span> <b>It's unethical</b><br><span>the fact that you can predict it does not mean you may</span></div>
  <div class="d"><span class="x">✕</span> <b>Simpler solutions do the trick</b><br><span>the first phase of model development should be a non-ML baseline</span></div>
  <div class="d"><span class="x">✕</span> <b>It's not cost-effective</b><br><span>data, compute, infrastructure and people, against the value of the prediction</span></div>
</div>

Even then: **break the problem up.** If a chatbot can't answer everything, a model that
routes "is this an FAQ?" still useful.

<style>
.dont { display: grid; gap: 0.7rem; margin: 1.1rem 0; }
.d { font-size: 0.95rem; line-height: 1.45; }
.d .x { color: #dc2626; font-weight: 800; }
.d span { opacity: 0.78; font-size: 0.85rem; }
.src { position: absolute; bottom: 1rem; left: 3rem; right: 3rem; font-size: 0.65rem; opacity: 0.45; }
</style>

<!--
The third bullet is where student projects die. Ask them, when they pick a topic in Week
2, what the non-ML baseline is — if they cannot name one, they cannot show the model
helped.

And the caution worth adding: "not cost-effective today" is not "never" — most technology
gets cheaper.
-->

<!-- ---

# Apply it to your own project

Before Week 2, check your chosen topic against the list:

1. Is there a **pattern**, and is it complex enough that you cannot write it by hand?
2. Do you **have the data** — or a realistic way to collect it?
3. Is the answer a **prediction**, not an exact computation?
4. Will next month's data **look like** this month's? If not, say so now.
5. What is the **cost of a wrong answer**, and who pays it?
6. What is the **non-ML baseline** you will have to beat?

If you cannot answer 6, you do not yet have a project — you have a dataset. -->

<!--
Turn this into the two-minute exercise that closes the section: everyone writes one
sentence for number 6. It is the single best predictor of whether their homework project
will produce a defensible result in Week 6.
-->

<!-- ---
layout: section
---

# 6 · The lifecycle

---


# The loop every ML system lives in

<img src="/mlops-cycle.svg" class="cycle cycle-lg">

Two halves joined by automation — and unlike classic DevOps, **the right half feeds the left
half data, not just bug reports.**

<style>
.cycle { display: block; margin: 0.2rem auto 0.3rem; width: 100%; }
.cycle-lg { max-width: 620px; }
</style> -->

<!--
Walk it once, slowly, and name what is ML-specific at each step:

- Design / Plan: the data has to be explored before anyone can say what is buildable
- Build: the artifact is code AND a dataset AND a trained model, not just a binary
- Test: a test suite cannot say "correct", only "good enough on this sample"
- Deploy: you ship a model whose behaviour nobody fully specified
- Operate / Monitor: the thing degrades while running perfectly

The closing arrow is the one to dwell on: monitoring output becomes next iteration's training
input, which is a feedback path a normal service does not have.
-->


---
layout: section
---

# 7 · The three pillars

---


# Pillar 1: Reproducibility

Reproducibility means a team can explain and recreate a result.

Questions reproducible teams can answer:

- Which code version produced this run?
- Which environment and dependency set was used?
- Which parameters and random seed were applied?
- Which dataset snapshot trained the model?
- Which metrics justified deployment?

---

# Reproducibility in practice

Core habits:

- version code with Git
- isolate environments with tools such as `uv`
- containerize runtime dependencies with Docker
- externalize configuration using `.env` files or typed settings
- record metrics, parameters, and artifacts in experiment tracking systems

---

# Pillar 2: Scalability

Scalability is not only about traffic.

In MLOps it also includes the ability to scale:

- from one developer to a team
- from one experiment to many runs
- from one model to multiple versions
- from local execution to automated pipelines
- from small datasets to large, evolving data assets

---

# Scalability concerns across the lifecycle

| Stage | Typical scaling concern |
| --- | --- |
| Development | standard project structure and reusable tooling |
| Training | larger datasets, longer runtimes, more experiments |
| Deployment | latency, throughput, resource isolation |
| Operations | multiple model versions, observability, governance |

Teams that scale well reduce manual steps and hidden dependencies.

---

# Pillar 3: Automation

Automation reduces fragile manual work.

Examples:

- automated dependency setup
- automated tests and linting
- automated training and evaluation workflows
- automated container builds
- automated deployment gates
- automated alerts for service or model degradation

---

# Automation does not remove engineering judgment

Automation should support, not replace, decisions.

Teams still need humans to define:

- success metrics
- acceptance thresholds
- rollback conditions
- ownership boundaries
- incident response processes

Bad automation scales mistakes faster.

---
layout: section
---

# 8 · Who does the work

---


# Who is around the loop

An ML system in production touches far more people than the "ML" job titles.

| Role | Owns |
| :--- | :--- |
| **Product owner / business** | the objective and the go/no-go |
| **Domain expert** | what the data *means*, which errors cost |
| **Data engineer** | pipelines, schemas, freshness |
| **Data scientist** | framing, experiments, offline evaluation |
| **ML engineer** | training and inference code that runs unattended |
| **MLOps / platform** | CI/CD, registry, rollout, observability |

<style>
table { font-size: 0.78rem; }
table td, table th { padding: 0.22rem 0.5rem; }
</style>

<!--
Do not read the table. Pick three rows and ask who in the room expects to be that person.

This course trains the engineering middle — ML engineer and MLOps engineer — but the rows
above and below it are where the decisions engineering cannot make actually live.
-->

---

# ...and the rest of the cast

| Role | Owns |
| :--- | :--- |
| **Software / backend engineer** | the product the model is embedded in |
| **SRE / on-call** | availability, incident response, the pager |
| **Security & privacy** | access, PII, retention, supply chain |
| **Legal / compliance / risk** | documentation, auditability, regulatory duty |
| **QA / test** | acceptance testing, release evidence |
| **End users / operators** | the decisions the output feeds |

In a small team **one person holds five of these rows...**

<style>
table { font-size: 0.78rem; }
table td, table th { padding: 0.22rem 0.5rem; }
</style>

<!--
The last line is the one that matters for a student heading into a startup: they will *be*
the security row and the QA row, whether or not anybody says so.

Weeks 6 and 13 deliberately touch the product-owner, domain-expert and compliance rows —
fairness slices, the model card, the kill switch. Flag that now so it does not look like
scope creep later.
-->

---
layout: section
---

# 9 · The toolchain

---


# Tooling overview: Git

Git matters because it gives teams:

- versioned history of source code
- collaboration through branches and pull requests
- traceability between changes and outcomes
- the baseline coordination layer for later CI workflows

For ML, Git is necessary but not sufficient because data and model artifacts often exceed normal source-control patterns.

---

# Tooling overview: Docker

Docker helps teams create repeatable runtimes.

Benefits:

- reduces “works on my machine” failures
- aligns local, CI, and deployment environments
- packages system-level dependencies cleanly
- creates a stable base for later training and serving workflows

Week 1 uses Docker as a runtime foundation, not yet as a complex platform.

---

# Tooling overview: MLflow

MLflow introduces structure around experimentation.

Typical uses:

- log parameters
- log metrics
- save artifacts
- compare runs
- register and promote model versions

Later weeks build on this to connect experimentation with team-level governance.

---

# Tooling overview: CI/CD

CI/CD extends good local practice into shared automation.

CI examples:

- run tests on every pull request
- verify training code still works
- check evaluation thresholds

CD examples:

- build containers
- publish validated artifacts
- promote approved models or services

<!-- ---
layout: section
---

# 10 · In practice -->

<!-- ---


# Typical anti-patterns in early ML projects

Watch for:

- notebooks as the only source of truth
- hidden manual preprocessing steps
- local paths hard-coded into training scripts
- dependencies installed ad hoc without pinning
- no shared definition of metrics or acceptance criteria
- no separation between secrets and code -->

<!-- ---

# Configuration management basics

Week 1 starts with a simple pattern:

- keep defaults in code
- override environment-specific values via `.env`
- commit `.env.example`, never real secrets
- document required variables clearly

This is a lightweight entry point into more robust configuration systems used later. -->

<!-- ---

# Today's lab: train the semester's model

You will train a **diabetes prediction model** on real diagnostic data from 768 patients — the exact pipeline this course will version, validate, deploy, and monitor until Week 14.

1. Clone the repository, create a reproducible environment with `uv`
2. Run the baseline training pipeline and verify you get **identical metrics to everyone else**
3. Then change one number — the random seed — and watch accuracy move by ~5 points

<br>

> Same code. Same data file. Different model.
>
> That experiment *is* the triad of change — and it is why "it works on my machine" is a much stranger claim in ML than in classic software. -->
