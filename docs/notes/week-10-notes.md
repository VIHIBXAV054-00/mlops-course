# Week 10 — Rollout Strategies — Study Notes

These notes go with the Week 10 lecture and lab. In Week 9 the model moved into a container, and
other people could reach it. This week a new model version reaches real users: a small share first,
with checks and a rollback plan. The view is the ML engineer's: what you decide, and what you hand to the
team that runs the platform.

## Why this matters

**GPT-4o (2025).** ChatGPT had 500 million users a week, and OpenAI updates the GPT-4o model behind it
several times a year. Before release, each update goes through offline evaluations, expert testers,
safety evaluations and a small A/B test. On 24–25 April 2025, an update went to all users that made
the model "noticeably more sycophantic": it agreed with users, praised them, and confirmed their
doubts and anger. Every check had passed. The offline evaluations "generally looked good", and the
users in the A/B test liked the model; only some expert testers said it "felt" slightly off. No check
measured sycophancy, and the A/B test measured thumbs up and thumbs down, the same signal the update
had used in training. OpenAI changed the system prompt on 27 April and started a full rollback on
28 April, which took about 24 hours. It changed three things. Behaviour problems now block a launch, an
opt-in "alpha" phase comes before release, and sycophancy evaluations are part of deployment (OpenAI, "Sycophancy in GPT-4o"
and "Expanding on what we missed with sycophancy", 2025).

### More cases from the lecture

- **AI Overviews (2024).** Google tested its AI-written search answers with red-teaming, samples of
  typical queries and tests on a share of traffic. After the US launch, rare questions such as "How
  many rocks should I eat?" got answers from satire and forum posts. A partial rollout samples typical
  traffic, not the rare questions (Liz Reid, Google blog, 30 May 2024).

## Core concepts

### Deploy and release

To **deploy** is to run the new version on the servers; usually the platform team does it. To
**release** is to give users the new version's answers; for a model, the ML engineer decides when.
Until this week both happened at once, for every user: a new image replaced every pod, and the
probes only asked whether the pods were healthy. Keeping the two steps apart lets you run the new
version, check it on a small share of real requests, and keep the old version ready.

### Rollout strategies

| Strategy | Means |
| --- | --- |
| canary | a small percentage of traffic goes to v2. If its metrics stay healthy, the percentage grows step by step |
| blue/green | both versions run. All traffic switches at once, and can switch back |
| shadow | v2 gets a copy of every request. Its answers are compared and never sent (Week 9's champion and challenger side by side) |

| | Canary | Blue/green | Shadow |
| --- | --- | --- | --- |
| Pros | real users and inputs, a bad version reaches few users | rollback in seconds, everyone gets the same version | no user sees v2's answer, both models answer the same inputs |
| Cons | some users get v2's answers, a small share gives few answers to judge | after the switch every user gets v2, twice the servers | twice the compute, needs a store to compare answers, v2 must trigger no actions |
| Infrastructure cost | a few extra pods | 2× while both run | 2× all the time |
| Rollback | set the share to 0 | switch back | not needed |

Google's SRE workbook defines a canary as "a partial and time-limited deployment of a change in a
service and its evaluation". Teams that ship models do this in stages. Tesla ran new driver-assistance
software in cars in "shadow mode": active, but without taking the controls. Uber shadow-tests new
models by default, then sends a small share of traffic, with automatic rollback. Booking.com judges
its models with A/B tests on business metrics. GitHub Copilot runs more than 4,000 offline tests, then
switches some staff to a new model first, "similar to canary testing". A canary and an **A/B test** look alike but answer different questions.
A canary asks "does v2 break anything?", watches errors, latency and odd predictions, and runs for
minutes to hours. An A/B test asks "is v2 better?", watches a business metric, and needs enough users
for a statistical test, often for a week or more. Google's MLOps guide puts them in that order: the
technical check first, then the online experiment.

The choice depends on the model and the problem, which is why the ML engineer makes it:

| If the answer is yes | Canary | Blue/green | Shadow |
| --- | :-: | :-: | :-: |
| Can one wrong answer harm a person? | | ruled out | fits well |
| Must every user get v2 at the same moment? | ruled out | fits well | ruled out |
| Does the model trigger actions (e-mails, writes)? | | | ruled out |
| Is compute tight? | fits well | fits well | ruled out |
| Are there few requests a day? | | | fits well |
| Do you need to see how users react? | fits well | | ruled out |

One question has no column: when true labels arrive late, no strategy judges accuracy in hours, so
you watch proxies such as the positive rate.

### Tests for serving

A deployed model can be wrong while every server looks healthy. Three tests answer different
questions:

| Test | Asks | Runs | Cannot see |
| --- | --- | --- | --- |
| probe | Is the process alive? | every few seconds, the cluster acts on it | which model, what it predicts |
| smoke test | A few requests: is this the right model, and are its answers sane? | once per release, a script decides | many requests at once |
| load test | Many requests at once: does it stay fast, without errors? | before you promise a latency | whether real users like the answers |

A smoke test for a model has four checks. Identity: is this the version we released, and did it
pass the gate? Contract: are impossible inputs rejected, such as `glucose = 0`? Behaviour: are the
answers sane, a clear case positive, a clear non-case negative, not one constant answer? Protocol:
does every endpoint give the same answer?

In the lab, a `C: 0.001` model that failed the gate runs as a canary: `2/2 Running`, every request
answered with 200, and it flags 0 of 192 test patients while its ROC AUC, 0.8407, is above our
model's 0.8345. The smoke test fails it on identity and behaviour, and exits with a non-zero code so
a deployment script stops. Run the smoke test on the new version's own address before it gets any
traffic: 10% of traffic is 10% of real patients. Keep a test that runs the smoke test against a
model that must fail it: a check that never failed may check nothing.

A declared traffic split is a claim: count which version answered, from inside the cluster, and
report the count with the number of requests you sent.

### Basic load testing

| Term | Means |
| --- | --- |
| concurrency | requests in flight at the same time |
| throughput | requests completed per second (rps) |
| error rate | the share of requests that failed |
| p50 / p95 / p99 | the latency under which 50, 95 or 99% of the requests finished |

Report every result with its concurrency, its percentiles and its error rate, and never the mean.
A latency number without an error rate can always be improved by failing faster. When someone says
"our service handles 64 users", ask: 64 at the same time, or 64 per second? With which p95? With how
many errors?

### Rolling out our model

Take the diabetes model: v1 serves the hospital's online score, and v2 passed the gate. A wrong
answer can harm a patient, so blue/green is out. The model triggers no actions (no e-mails, no writes), so shadow would fit, but
the platform has nothing that stores and compares shadow answers. The choice: a canary at 10%,
smoke-tested at 0% first. At work you often choose from what the platform supports, and say what
you would need for the better option.

The ML engineer hands over three things: the **container image** (Week 9: code, packages,
runtime), the **model version** in the model store with its gate verdict, and the **rollout plan**.
The platform team runs the cluster, splits the traffic and runs the rollback. Load and latency
targets are agreed together.

Week 9's Kubernetes **Deployment** cannot run this canary well. It holds one version, and a new
image replaces every pod. It splits traffic only by the number of pods, so 10% needs 9 old pods and
1 new one. And it does not know what a model is, because the model is inside the image.
**KServe** runs on Kubernetes and serves models. Its **InferenceService** is one YAML file per
model. Each change makes a new **revision** while the previous one keeps running,
`canaryTrafficPercent` sets the traffic split, and the model is loaded from a store, so a new
version is a new folder, not a new image. Argo Rollouts and Flagger do the same for any service on
Kubernetes, and managed endpoints such as SageMaker offer it on a cloud. The platform team usually
picks the tool.

Let the canary differ from the running version only in the model and the percentage. If a canary
also changes the image and fails, there are two suspects.

The **rollout plan** is a short file in Git, written by the ML engineer before the rollout. It names
the candidate and the version it replaces, the strategy and percentage, the check before any
traffic, when to promote, when to roll back, and what load to expect. With the rollback criteria
written down, whoever is on call can roll back without a meeting.

### Offline and online evaluation

**Offline evaluation** scores the model on a held-out test set before the release (Week 6's gate).
**Online evaluation** watches the model on real requests after the release. Only online evaluation
shows inputs nobody put in the test set, how users react, and the world today instead of the world
of the training data. Its difficulty: true labels arrive late or never. A diabetes diagnosis comes
months after the prediction. So in the first hour you watch what needs no label: errors and latency,
the share of positive predictions next to the old model's, and input values outside the training
data. An online test also sees only the metrics you give it, as GPT-4o showed.

### Rollback

Decide the rollback before the release: which signal (a failed smoke check, the error rate, p95
latency, the positive rate), which threshold, and who acts. Then the engineer on call rolls back from
a table, without a meeting. AWS SageMaker's deployment guardrails automate this: a watching period
with alarms, and a rollback when one fires.

Each strategy has its own rollback. For a canary, set the canary percentage to 0: in the lab the old
revision had 100% again about 1.5 s later, and the bad version kept running at 0%, ready for
debugging. For blue/green, switch the router back to blue, which kept running. For shadow there is
nothing to roll back, because no user saw v2: stop sending it copies. In each case you change the
declaration, with the same field you deploy with. Deleting the bad revision by hand does not work:
the declaration still names it, and the controller recreates it in about 20 s.

Test the rollback before you need it. Pixar had a backup of *Toy Story 2*, but nobody had tested
it, and it did not hold the film when it was needed. Write the rollback steps into the rollout plan
and run them on a test cluster before the release. OpenAI's full rollback of GPT-4o took about 24
hours.

## Commands

```bash
make model-publish VERSION=v2                     # publish a model to the store, if the gate said GO
make release-check                                # is release.yaml complete?
make smoke-local VERSION=v3                       # the smoke test in-process, no cluster
kubectl get isvc diabetes                         # the declared split and the revisions
kubectl get revision                              # every revision KServe keeps
make split-measure N=200                          # count which version answered
make smoke VERSION=v2                             # the smoke test against the newest revision
make rollback                                     # canaryTrafficPercent: 0
```

## Key terms

- **Deploy / release**: run the new version; give users its answers.
- **Offline / online evaluation**: scores on a held-out test set before the release; checks on real
  requests after it.
- **Canary / blue-green / shadow**: a small share first; two versions live and one switch; a copy of
  the traffic whose answers are never sent.
- **A/B test**: an experiment that compares two versions on a business metric, with enough users for
  a statistical test.
- **Sycophancy**: a model agreeing with and flattering the user (Hungarian: *hízelgés*).
- **Rollout plan**: the ML engineer's written decisions for a rollout: versions, strategy, checks,
  promotion and rollback criteria, expected load.
- **Provenance**: the record of where a model came from: version, run, data, gate verdict.
- **`InferenceService`**: KServe's object for one served model, with revisions and traffic.
- **Revision**: an unchanging snapshot of the configuration. Two can be live at once.
- **`canaryTrafficPercent`**: the share of the traffic the newest ready revision gets.
- **Promotion / rollback**: remove `canaryTrafficPercent` (100% to the new revision); set it to 0
  (100% to the old one).
- **Smoke test**: a check after deployment that the right model is served and behaves.
- **Load test**: throughput, error rate and latency percentiles at a stated concurrency.
- **p50 / p95 / p99**: the median and the tail latency.

## How this connects to the lab

Exercise 1 publishes three model versions to a store the cluster reads, and makes the store refuse a
model the gate rejected. Exercise 2 writes the rollout plan, `release.yaml`, and the smoke test's
behaviour check, and runs the smoke test in-process against all three versions. Exercise 3 deploys
v1 and a canary with v2 at 0%, smoke-tests it, gives it its canary percentage and counts the split
from inside the cluster. Exercise 4 deploys the rejected model as the canary and sees the smoke test stop it on a
healthy pod. Exercise 5 gives it traffic without the check, rolls back and times it, and asks what the
rollback did not restore and which rollback steps are still untested. Exercise 6 (optional) runs a load
test against the limits of the rollout plan.

## Recommended reading

- **Kästner, *Machine Learning in Production*, ch. 19 "Testing and Experimenting in Production"**:
  offline and online evaluation, A/B tests, canaries and shadow releases.
  https://mlip-cmu.github.io/book/19-testing-and-experimenting-in-production.html
- **Kästner, ch. 13 "Planning for Operations"**: what the model team and the operators need from
  each other. https://mlip-cmu.github.io/book/13-planning-for-operations.html
- **Google Cloud, *Practitioners guide to MLOps* (May 2021), pp. 25–26**: progressive delivery and
  online experiments.
  https://services.google.com/fh/files/misc/practitioners_guide_to_mlops_whitepaper.pdf
- **Google SRE workbook, ch. 16 "Canarying Releases"**: what a canary is and how to evaluate it.
  https://sre.google/workbook/canarying-releases/
- **OpenAI, "Expanding on what we missed with sycophancy"** (2025): how a model update passed every
  check. https://openai.com/index/expanding-on-sycophancy/
- **KServe: canary rollout example**.
  https://kserve.github.io/website/docs/model-serving/predictive-inference/rollout-strategies/canary-example

## Check yourself

1. A fraud model, a news recommender and a model that must apply a new regulation to everyone from
   1 March each need a release. Which rollout strategy fits each one, and why?
2. A canary and an A/B test both send part of the traffic to v2. Give two differences in what they
   measure, and say which one comes first.
3. Your team's new model passed the gate and a two-day A/B test. What could still be wrong that
   neither check would show? Use the GPT-4o case.
4. Your `InferenceService` declares `canaryTrafficPercent: 10`. You send 50 requests and 9 of them
   come back from the new revision. Is the split wrong? Show the arithmetic.
5. Your canary's pod is `2/2 Running`, its readiness probe passes, and every request returns HTTP
   200. Name three things that could still be badly wrong, and the check that would catch each.
6. List what an ML engineer should write into a rollout plan, and say for two of the items why
   the platform team cannot decide them alone.
7. A colleague rolls back a bad model with `kubectl delete revision my-model-00007`. What happens,
   and why? What should they have done instead?
