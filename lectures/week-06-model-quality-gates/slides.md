---
theme: default
title: Week 6 — Model Quality Gates
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers acceptance criteria, baselines and metric regression, slice-based
  evaluation, a first look at fairness checks, and a go/no-go gate.
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

# Week 6: Model Quality Gates

**Lifecycle of Artificial Intelligence Systems**

- Acceptance criteria
- Baselines and metric regression
- Slice-based evaluation
- Fairness checks
- Go/no-go gates

<!--
One new package this week: fairlearn, which scores every group in one call and computes the fairness metrics. The gate itself is a threshold, a comparison and a non-zero exit code.
-->

---
layout: center
---

# **Quiz**
# What is a data contract, and who writes its rules?

<v-clicks>

- The rules for the data, written down.
- The domain expert writes the rules.
- The data engineer turns them into checks.
- The pipeline runs the checks on every incoming batch.

</v-clicks>

<!--
One contract, two readers: people read what each column means and whom to call; the pipeline runs the checks. In our project the doctor knows that a glucose of 0 is impossible and that 0 pregnancies is normal.
-->

---
layout: center
---

# **Quiz**
# Why did our pipeline need two contracts?

<div class="flow" style="gap:0.4rem; margin-top:2rem; font-size:0.95rem">
  <div class="node amber no-shrink" style="width:6.5rem"><ph-file-csv class="ic" /><b>Batch file</b><br><small>from the clinic</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:10.5rem"><ph-shield-check class="ic" /><b>RawMeasurements</b><br><small>ingestion contract<br><span class="mono">ge=0</span>: zero allowed</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node violet no-shrink" style="width:7.5rem"><ph-arrows-clockwise class="ic" /><b>to_nullable</b><br><small>0 → missing<br>in 5 columns</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:9.5rem"><ph-shield-check class="ic" /><b>ModelInput</b><br><small>training contract<br><span class="mono">gt=0</span>: zero illegal</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node sky no-shrink" style="width:8.5rem"><ph-cube class="ic" /><b>Pipeline</b><br><small>imputer, scaler, classifier</small></div>
</div>

<!--
`RawMeasurements` (`ge=0`) at ingestion, `to_nullable`, then `ModelInput` (`gt=0, nullable=True`). The same figure as Week 5's "Two contracts, at two boundaries". The door accepts what the source really sends; the model's contract states what the model needs. Rejecting the zeros at the door would throw away every patient with one of the 652 zeros, although the other measurements are real.
-->

---
layout: center
---

# **Quiz**
# What turns a check into a gate?

<v-clicks>

- **It stops the pipeline.**
- **It writes a report.**

</v-clicks>

<!--
A non-zero exit code, so nothing after it runs; the report, written first, names the row and the rule it broke. A check that only warns lets the model train on bad data. Measured in Week 5: with `age = 250` planted, `validate` exited with 1, and `data/processed/train.csv` kept its md5 `d9eba76c…`. Warn, quarantine or stop is a decision for each rule.
-->

---
layout: center
---

# **Quiz**
# What is training-serving skew, and how do we prevent it?

<div v-click="1">
<div class="flow" style="margin:0.25rem 0">
  <div class="node amber no-shrink" style="width:10.5rem"><ph-files /> training data</div>
  <div class="arrow-l">code path A<span class="arrow">→</span></div>
  <div class="node green" style="width:10rem"><b>features</b> <small>every field filled</small><DataBatch cells="gggg gggg" /></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:7rem"><span class="mono">fit</span></div>
</div>
<div class="flow" style="margin:0.25rem 0">
  <div class="node amber no-shrink" style="width:10.5rem"><ph-globe /> a request</div>
  <div class="arrow-l fail">code path B<span class="arrow">→</span></div>
  <div class="node rose" style="width:10rem"><b>features</b> <small>some fields empty</small><DataBatch cells="g.g." /></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:7rem"><span class="mono">predict</span></div>
</div>
</div>

<div v-click="2" class="flow" style="margin-top:1rem">
  <div class="node amber no-shrink" style="width:10.5rem"><ph-files /> training data<br><ph-globe /> a request</div>
  <div class="arrow-l on">one path<span class="arrow">→</span></div>
  <div class="node violet" style="width:10rem"><ph-cube class="ic" /><b>Pipeline</b><br><small>imputer inside the model</small></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:7rem"><span class="mono">fit</span><br><span class="mono">predict</span></div>
</div>

<!--
First click: the skew, the model gets different input when it serves than when it was trained, because training and serving use two code paths. Second click: the fix, one path, with the imputer inside the model and one contract at both boundaries. Week 5's measurement: with the medians filled in `prepare` instead, a request with `glucose = 0` got a probability of 0.0068, and a missing insulin value crashed `predict`.
-->

---
layout: center
---

# **Quiz**
# The data passes every check. What can still be wrong?

<v-clicks>

- Wrong labels and plausible wrong values.
- A change compared with last month: that needs a drift check.
- **The model itself.**

</v-clicks>

<!--
A contract checks the agreed shape of one batch; drift monitoring comes in Week 12. The last answer is today's question: the data is clean, but nobody has decided yet whether the model is good enough.
-->

---

# The data is clean now. Is the model better?

<carbon-chart-line class="icon-corner" />

<div class="text-lg" style="margin-top:2rem">

| **Metric** | **Week 4**: no imputer | **Week 5**: imputer in the model | |
| --- | --- | --- | --- |
| accuracy | 0.7656 | 0.7656 | <span v-click="1">the same</span> |
| F1 | 0.6154 | 0.6341 | <span v-click="1">+0.019</span> |
| ROC-AUC | 0.8183 | 0.8345 | <span v-click="1">+0.016</span> |

</div>

<!--
Same 192 test patients, same seed. 147 of 192 answers were right in both weeks, while F1 and ROC-AUC rose. A report with only accuracy would say that nothing changed.
-->

---
layout: section
---

# 1 · What does one number hide?

<!--
About 15 minutes. Option B (speech recognition, 2020) is hidden after the face-classifier slides.
-->

---
layout: two-cols
---

# 2018: face classifiers for sale

Microsoft, IBM and Face++ sold gender classification as a cloud service: send a photo, get "male" or "female".

- Two researchers built a balanced test set: **1,270** members of parliament from six countries[^1][].
- They scored each product on it.

::right::

<div style="margin-top:6rem">
<ImageSlot id="w06-ppb" text="Example faces from the Pilot Parliaments Benchmark (Gender Shades, Figure 1)" height="260px" />
</div>

[^1]: Buolamwini and Gebru, "Gender Shades: Intersectional Accuracy Disparities in Commercial Gender Classification", PMLR 81 (FAT* 2018). https://proceedings.mlr.press/v81/buolamwini18a.html

<!--
The countries: Rwanda, Senegal and South Africa; Iceland, Finland and Sweden, chosen for a range of skin types and for many women in parliament. Buolamwini was at the MIT Media Lab, Gebru at Microsoft Research.
-->

---

# How good was IBM's classifier?

<carbon-face-activated class="icon-corner" />

<div class="flow" style="margin-top:2.5rem; margin-bottom:0">
  <div class="node sky" style="width:20rem"><ph-scan-smiley class="ic" /><b>IBM, all 1,270 faces</b><br><span class="text-4xl font-bold">87.9%</span><br><small>classified correctly</small></div>
</div>

<div v-click>
  <div class="split-stem"></div>
  <div class="split-bar" style="width:39rem"></div>
  <div class="flow" style="margin-top:0">
    <div class="node green" style="width:12rem"><b>Lighter men</b><br><span class="text-2xl font-bold">0.3%</span><br><small>wrong</small></div>
    <div class="node green" style="width:12rem"><b>Lighter women</b><br><span class="text-2xl font-bold">7.1%</span><br><small>wrong</small></div>
    <div class="node amber" style="width:12rem"><b>Darker men</b><br><span class="text-2xl font-bold">12.0%</span><br><small>wrong</small></div>
    <div class="node rose" style="width:12rem"><b>Darker women</b><br><span class="text-2xl font-bold" style="color:#dc2626">34.7%</span><br><small>wrong</small></div>
  </div>
</div>

Gender Shades, Table 4[^1][]

[^1]: Buolamwini and Gebru, PMLR 81 (2018), Table 4.

<!--
The other two: Microsoft 93.7% overall and 20.8% wrong on darker women; Face++ 90.0% overall and 34.5%. Within IBM, the gap between the best and the worst group is 34.4 percentage points.
-->

---
layout: center
---

# Nothing was broken. What was missing?

<v-clicks>

- **Group-level metrics**: a score for each group, not one for all 1,270 faces.
- **A bar for each group** that the model must pass.

</v-clicks>

<!--
The paper (Section 4.5): taken at face value, the overall accuracies "suggest that these classifiers can be used for all populations". The metric was computed correctly; it was the wrong summary.
Week 3's Epic Sepsis Model is the same lesson: Epic's documentation gave an AUC of 0.76–0.83; on Michigan Medicine's own patients it was 0.63 (Wong et al., 2021).
-->

---

# Seven months later

<carbon-renew class="icon-corner" />

<div class="flow" style="margin-top:3rem">
  <div class="node amber" style="width:12rem"><ph-file-text class="ic" /><b>2018</b><br>the audit is published<br><small>results sent to the companies first</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node sky" style="width:12rem"><ph-cube class="ic" /><b>New versions</b><br>all three companies<br><small>release an update</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:14rem"><ph-chart-line-down class="ic" /><b>Darker women</b><br>"17.7% - 30.4% reduction in error"</div>
</div>

<v-click at="2">

Raji and Buolamwini, a second audit[^1][]

</v-click>

[^1]: Raji and Buolamwini, "Actionable Auditing: Investigating the Impact of Publicly Naming Biased Performance Results of Commercial AI Products", AIES 2019. https://www.media.mit.edu/publications/actionable-auditing-investigating-the-impact-of-publicly-naming-biased-performance-results-of-commercial-ai-products/

<!--
The 2018 figures describe 2018 products; today's versions differ. The fix came after outsiders measured per group. Our inference, not the papers': nothing in them suggests that the companies had a bar per group before the release.
-->

---

# What would have stopped it?

<carbon-security class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div class="node sky" style="width:9rem"><ph-cube class="ic" /><b>New model</b></div>
  <div class="arrow-l">evaluate<span class="arrow">→</span></div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node" style="width:15rem; padding:0.25rem 0.6rem">all faces · 87.9%</div>
    <div v-click="1" class="node" style="width:15rem; padding:0.25rem 0.6rem">lighter men · 0.3% wrong</div>
    <div v-click="1" class="node" style="width:15rem; padding:0.25rem 0.6rem">lighter women · 7.1% wrong</div>
    <div v-click="1" class="node" style="width:15rem; padding:0.25rem 0.6rem">darker men · 12.0% wrong</div>
    <div v-click="1" class="node rose" style="width:15rem; padding:0.25rem 0.6rem">darker women · 34.7% wrong</div>
  </div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:10rem"><ph-shield-check class="ic" /><b>A bar for each group</b><br><small>one group fails: no release</small></div>
</div>

<v-click at="3">

> [!TIP]
> Before a release, score the model on every group it serves, and set a bar for each group.

</v-click>

<!--
This is the practice, not what IBM did. The rest of today builds this gate for our diabetes model: written criteria, a baseline, slices and a verdict.
-->

---
hide: true
---

# Option B · 2020: speech recognition

<carbon-microphone class="icon-corner" />

Five companies sell speech-to-text: Amazon, Apple, Google, IBM and Microsoft.

- A Stanford team sent each system recorded interviews with Black and with white speakers[^1][].
- They counted the word error rate: the share of words the system got wrong.

<div class="flow" style="margin-top:2.5rem">
  <div class="node amber" style="width:12rem"><ph-microphone class="ic" /><b>Interviews</b><br><small>Black and white speakers</small></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:12rem"><ph-cube class="ic" /><b>5 systems</b><br><small>speech to text</small></div>
  <div class="arrow">→</div>
  <div class="node violet" style="width:12rem"><ph-text-aa class="ic" /><b>Word error rate</b><br><small>for each group</small></div>
</div>

[^1]: Koenecke et al., "Racial disparities in automated speech recognition", PNAS, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386/

<!--
Option B for this slot: use it instead of Gender Shades. Hide the five Gender Shades slides, from "2018: face classifiers for sale" to "What would have stopped it?", and show the five "Option B ·" slides. Change the Gender Shades line in the note of "This week's pipeline"; the study notes list both cases.
-->

---
hide: true
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:16rem"><div class="text-5xl font-bold">0.19</div><div>word error rate, white speakers</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:16rem"><div class="text-5xl font-bold" style="color:#dc2626">0.35</div><div>word error rate, Black speakers</div></div></div>
</div>

<br>

Average over the five systems, Koenecke et al.[^1][]

[^1]: Koenecke et al., PNAS, 2020.

<!--
Option B, second slide. Microsoft, the best system, had 0.15 for white and 0.27 for Black speakers; Apple, the worst, 0.23 and 0.45. The test used 19.8 hours of matched audio from 42 white and 73 Black speakers.
-->

---
hide: true
layout: center
---

# Option B · Nothing was broken. What was missing?

<v-clicks>

- **Group-level metrics**: a word error rate for each group of speakers, not one average.
- **A bar for each group** that the model must pass.

</v-clicks>

<!--
Option B, third slide. With a word error rate above 0.5 counted as unusable, 23% of the Black speakers' snippets were unusable, against 1.6% of the white speakers' (Koenecke et al., 2020).
-->

---
hide: true
---

# Option B · What did the authors ask for?

<carbon-renew class="icon-corner" />

<div class="flow" style="margin-top:3rem">
  <div class="node rose" style="width:13rem"><ph-waveform class="ic" /><b>The cause</b><br>the acoustic models<br><small>likely: too little audio from Black speakers in training</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet" style="width:12rem"><ph-database class="ic" /><b>More diverse training data</b><br><small>including African American Vernacular English</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:12rem"><ph-chart-bar class="ic" /><b>Measure every group</b><br><small>"regularly assess and publicly report"</small></div>
</div>

<br>

Koenecke et al., PNAS, 2020[^1][]

[^1]: Koenecke et al., "Racial disparities in automated speech recognition", PNAS, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386/

<!--
Option B, fourth slide. The paper reports no response from the five companies; the cause is the authors' analysis. They also ask for data on regional and non-native accents.
-->

---
hide: true
---

# Option B · What would have stopped it?

<carbon-security class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div class="node sky" style="width:9rem"><ph-cube class="ic" /><b>New model</b></div>
  <div class="arrow-l">evaluate<span class="arrow">→</span></div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node" style="width:16rem; padding:0.25rem 0.6rem">one average per product</div>
    <div v-click="1" class="node" style="width:16rem; padding:0.25rem 0.6rem">white speakers · WER 0.19</div>
    <div v-click="1" class="node rose" style="width:16rem; padding:0.25rem 0.6rem">Black speakers · WER 0.35</div>
  </div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:10rem"><ph-shield-check class="ic" /><b>A bar for each group</b><br><small>one group fails: no release</small></div>
</div>

<v-click at="3">

> [!TIP]
> Before a release, score the model on every group it serves, and set a bar for each group.

</v-click>

<!--
Option B, fifth slide. The rates are the average of the five systems. This is the practice, not what the companies did; the rest of today builds this gate for our diabetes model.
-->

---

# Where we are: before the release

<Lifecycle stage="test" width="70%" />

Today: decide whether a trained model may leave the development loop.

<!--
Why test: the gate runs after training and before anything is deployed. Week 7 runs it in CI on every change; Week 9 makes the serving image refuse a model without a GO.
-->

---

# Quiz · Which number answers which question?

<carbon-help class="icon-corner" />

<div style="display:grid; grid-template-columns:15rem 1fr; gap:2rem; align-items:center; margin-top:1rem">
<div>

<div class="cm">
  <div></div><div class="h">says no</div><div class="h">says yes</div>
  <div class="h">no diabetes</div><div class="c">108</div><div class="c bad">17</div>
  <div class="h">diabetes</div><div class="c bad">28</div><div class="c">39</div>
</div>

<div class="text-xs opacity-70 text-center">our model, 192 test patients</div>

<svg v-click="5" viewBox="0 0 260 260" style="width:12rem; margin:0.75rem auto 0; display:block; font-size:16px; line-height:1">
  <path d="M40,220 L40.0,220.0 L40.0,217.0 L40.0,208.1 L43.2,208.1 L43.2,202.1 L44.8,202.1 L44.8,181.2 L46.4,181.2 L46.4,166.3 L48.0,166.3 L48.0,151.3 L49.6,151.3 L49.6,142.4 L51.2,142.4 L51.2,139.4 L52.8,139.4 L52.8,133.4 L54.4,133.4 L54.4,127.5 L57.6,127.5 L57.6,124.5 L60.8,124.5 L60.8,118.5 L62.4,118.5 L62.4,109.6 L65.6,109.6 L65.6,103.6 L67.2,103.6 L67.2,97.6 L68.8,97.6 L68.8,94.6 L70.4,94.6 L70.4,91.6 L72.0,91.6 L72.0,88.7 L73.6,88.7 L73.6,79.7 L75.2,79.7 L75.2,76.7 L80.0,76.7 L80.0,70.7 L88.0,70.7 L88.0,61.8 L92.8,61.8 L92.8,58.8 L104.0,58.8 L104.0,55.8 L105.6,55.8 L105.6,52.8 L112.0,52.8 L112.0,49.9 L113.6,49.9 L113.6,46.9 L116.8,46.9 L116.8,40.9 L121.6,40.9 L121.6,37.9 L123.2,37.9 L123.2,34.9 L139.2,34.9 L139.2,31.9 L156.8,31.9 L156.8,29.0 L177.6,29.0 L177.6,26.0 L190.4,26.0 L190.4,23.0 L217.6,23.0 L217.6,20.0 L240.0,20.0 L240,220 Z" fill="#0ea5e9" fill-opacity="0.15" />
  <line x1="40" y1="220" x2="240" y2="20" stroke="currentColor" stroke-opacity="0.4" stroke-dasharray="4 4" />
  <rect x="40" y="20" width="200" height="200" fill="none" stroke="currentColor" stroke-opacity="0.5" />
  <polyline points="40.0,220.0 40.0,217.0 40.0,208.1 43.2,208.1 43.2,202.1 44.8,202.1 44.8,181.2 46.4,181.2 46.4,166.3 48.0,166.3 48.0,151.3 49.6,151.3 49.6,142.4 51.2,142.4 51.2,139.4 52.8,139.4 52.8,133.4 54.4,133.4 54.4,127.5 57.6,127.5 57.6,124.5 60.8,124.5 60.8,118.5 62.4,118.5 62.4,109.6 65.6,109.6 65.6,103.6 67.2,103.6 67.2,97.6 68.8,97.6 68.8,94.6 70.4,94.6 70.4,91.6 72.0,91.6 72.0,88.7 73.6,88.7 73.6,79.7 75.2,79.7 75.2,76.7 80.0,76.7 80.0,70.7 88.0,70.7 88.0,61.8 92.8,61.8 92.8,58.8 104.0,58.8 104.0,55.8 105.6,55.8 105.6,52.8 112.0,52.8 112.0,49.9 113.6,49.9 113.6,46.9 116.8,46.9 116.8,40.9 121.6,40.9 121.6,37.9 123.2,37.9 123.2,34.9 139.2,34.9 139.2,31.9 156.8,31.9 156.8,29.0 177.6,29.0 177.6,26.0 190.4,26.0 190.4,23.0 217.6,23.0 217.6,20.0 240.0,20.0" fill="none" stroke="#0284c7" stroke-width="3" />
  <text x="135" y="190" fill="currentColor" font-weight="bold">AUC 0.8345</text>
  <text x="140" y="246" fill="currentColor" text-anchor="middle">false positive rate</text>
  <text x="24" y="120" fill="currentColor" text-anchor="middle" transform="rotate(-90 24 120)">true positive rate</text>
</svg>

</div>
<div class="text-sm">

| **Question** | **Metric** |
| --- | --- |
| How often is it right? | <span v-click="1">accuracy: 147 / 192 = 0.7656</span> |
| Of the patients it flags, how many have diabetes? | <span v-click="2">precision: 39 / 56 = 0.6964</span> |
| Of the patients with diabetes, how many does it find? | <span v-click="3">recall: 39 / 67 = 0.5821</span> |
| One number for both of the last two | <span v-click="4">F1, their harmonic mean: 0.6341</span> |
| Does it score patients with diabetes higher than those without? | <span v-click="5">ROC-AUC, the area under the ROC curve: 0.8345</span> |

</div>
</div>

<!--
The first four depend on the threshold: the model says yes when its probability is at least 0.5. The 28 patients with diabetes that it missed are the costly error here.
ROC-AUC needs no threshold: each threshold gives one point (false positive rate, true positive rate), and the curve joins them. 0.5 is a random order (the dashed line), 1.0 a perfect ranking. Our curve is computed from the lab solution's model.
-->

---

# A model that never says yes

<carbon-stop-sign class="icon-corner" />

One line in `params.yaml`: `train.C: 1.0 → 0.001`. The model now says "no diabetes" to all 192 test patients.

<div class="text-lg">

| **Metric** | **Our model** | **`C: 0.001`** |
| --- | --- | --- |
| accuracy | 0.7656 | <span v-click="1">0.6510</span> |
| F1 | 0.6341 | <span v-click="2">0.0000</span> |
| ROC-AUC | 0.8345 | <span v-click="3"><b style="color:#dc2626">0.8407</b></span> |

</div>

<v-click at="4">

> [!CAUTION]
> Judged by ROC-AUC alone, this model looks better than ours, yet it finds no patient with diabetes.

</v-click>

<!--
Measured in the lab (seed 42, same split); `tests/test_gates.py` asserts it. The scores still rank the patients well, but every score is below 0.5, so the model never acts on the ranking.
-->

---
layout: section
---

# 2 · What does "good enough" mean?

<!--
No new tool in this section: the criteria are one block in `params.yaml`, called `acceptance`.
-->

---

# Who decides what is good enough?

<carbon-user-multiple class="icon-corner" />

<div class="flow" style="margin-top:6rem">
  <div v-click="1" class="node amber" style="width:16rem"><ph-stethoscope class="ic" /><b>Domain expert</b><br>weighs the errors<br><small>a missed diagnosis against a false alarm</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node violet" style="width:14rem"><ph-chart-bar class="ic" /><b>Data scientist</b><br>turns them into metrics<br><small>which metric, which baseline, which groups</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green" style="width:14rem"><ph-code class="ic" /><b>ML engineer</b><br>writes the gate<br><small>a stage that runs on every model</small></div>
</div>

<div v-click="4" class="flow">
  <div class="node" style="width:46rem; border-style:dashed"><ph-user-gear /> <b>Project lead</b>: signs the criteria, and approves every later change to them</div>
</div>

<!--
Week 1's roles. A doctor can say that a missed diabetes case costs more than a false alarm; only then does the data scientist know whether recall or precision matters more.
-->

---
layout: center
---

# **Quiz**
# The team sets the F1 floor after it sees the model's F1.
# What goes wrong?

<v-clicks>

- The floor lands just below the score.
- **This model passes by design: the gate cannot refuse it.**

</v-clicks>

<div v-click>

> [!TIP]
> Write the acceptance criteria when you plan the project, and give them a version number. Raise the version with every change.

</div>

<!--
The lab has this weakness on purpose: its thresholds were chosen after measuring the shipped model, so that the lab can run. In the lab, `acceptance.criteria_version` is "1.0.0".
-->

---
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div style="width:24rem"><div class="text-6xl font-bold">0.6510</div><div><b>baseline:</b> the accuracy of a model that says "no diabetes" to every patient</div></div>
  <div v-click class="flex gap-3"><div class="text-6xl">→</div><div style="width:14rem"><div class="text-6xl font-bold" style="color:#16a34a">0.70</div><div>our accuracy floor</div></div></div>
</div>

<br>

How low is too low? 125 of our 192 test patients have no diabetes.

<!--
125 / 192 = 0.6510, the majority-class rate. A floor of 0.60 would let a model that does nothing pass.
-->

---

# Baseline options

<carbon-compare class="icon-corner" />

<div class="text-lg" style="margin-top:1.5rem">

| **Baseline** | **The question it answers** |
| --- | --- |
| the majority class | <span v-click="1">Is the model doing anything at all?</span> |
| the champion | <span v-click="2">Is the new model worse than the one we run?</span> |
| the current process | <span v-click="3">Is a model better than what we do today?</span> |

</div>

<v-click at="2">

**Champion:** the model now in production. In our registry, the alias `@champion` points to it.

</v-click>

<!--
The lab uses the first two. The third needs a study: for example, how many cases does today's screening rule find? Without it, nobody can say the model is worth deploying at all.
-->

---

# Four kinds of acceptance criteria

<carbon-list-checked class="icon-corner" />

<div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; align-items:start; margin-top:1rem">
<div class="cards" style="grid-template-columns:repeat(2,1fr); margin:0">
  <div v-click class="card"><ph-ruler class="ic" /><b>Floors</b>each metric above a minimum<br><code>accuracy ≥ 0.70</code></div>
  <div v-click class="card"><ph-trophy class="ic" /><b>Regression</b>no worse than the champion<br><code>F1 drop ≤ max_drop</code></div>
  <div v-click class="card"><ph-users class="ic" /><b>Slices</b>good enough for each group<br><b>→ Section 3</b></div>
  <div v-click class="card"><ph-scales class="ic" /><b>Fairness</b>errors shared in a way we can defend<br><b>→ Section 4</b></div>
</div>
<div v-click>

```yaml
# params.yaml
acceptance:
  criteria_version: "1.0.0"
  minimum:              # floors
    accuracy: 0.70
    f1: 0.55
  regression:           # no worse than the champion
    primary_metric: f1
    max_drop: 0.01
  slice_rules:          # Section 3
    min_f1: 0.50
  fairness:             # Section 4
    max_tpr_gap: 0.20
```

</div>
</div>

<!--
Each kind catches a model the others let through: the `C: 0.001` model passes a ROC-AUC floor and fails the F1 floor.
The example is shortened from the lab's `params.yaml`, which has more rules in each block. The criteria are policy, so they live in a versioned file next to the code, not inside it; raise `criteria_version` with every change.
-->

---

# Is it worse than the champion?

<carbon-arrow-down class="icon-corner" />

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:12rem"><ph-trophy class="ic" /><b>Champion</b><br>F1 0.6341<br><small>from <span class="mono">metrics/baseline.json</span></small></div>
  <div class="arrow-l">compare<span class="arrow">↔</span></div>
  <div class="node sky" style="width:12rem"><ph-cube class="ic" /><b>New model</b><br>F1 ?</div>
  <div class="arrow">→</div>
  <div class="node green" style="width:12rem"><ph-shield-check class="ic" /><b>regression check</b><br><small>fails if the drop is larger than <span class="mono">max_drop</span></small></div>
</div>

<div class="text-sm">

| **Rule** | **Means** |
| --- | --- |
| `primary_metric` | the one metric that decides, e.g. `f1` |
| `max_drop` | the largest drop we accept, e.g. `0.01` |

</div>

How big may `max_drop` be?

<v-click>

> [!TIP]
> Set `max_drop` at least as big as the noise between two runs of the same pipeline.

</v-click>

<!--
Our pipeline is deterministic (seed 42, fixed split): two runs give the same metrics to the last digit. A GPU, another BLAS library or a reshuffled split moves the fourth decimal.
-->

---
layout: center
---

# `train.C: 1.0 → 0.01`
# Regression or improvement?

<div class="text-lg">

| **Metric** | **`C: 1.0`** | **`C: 0.01`** |
| --- | --- | --- |
| accuracy | 0.7656 | 0.7656 |
| F1 | 0.6341 | 0.6087 <span v-click="1" style="color:#dc2626">−0.0254</span> |
| ROC-AUC | 0.8345 | 0.8445 <span v-click="1" style="color:#16a34a">+0.0100</span> |

</div>

<v-clicks at="2">

- On F1: a regression. On ROC-AUC: an improvement.
- **Choose the primary metric before the run.**

</v-clicks>

<!--
Measured in the lab, same split and seed. The change also moves the slices: the F1 of patients aged 50 and over rises from 0.50 to 0.625. The lab's Exercise 4 asks the same question for `C: 0.005`. In the full gate this model also fails the age TPR gap (0.3052 against 0.25).
-->

---

# Where does the champion's score come from?

<carbon-data-base class="icon-corner" />

<div class="text-sm" style="margin-top:0.5rem">

| **Option** | **The `gate` stage gives the same result every time?** | **Always the current champion?** |
| --- | --- | --- |
| a file in Git (`baseline.json`) | <span v-click="1">yes</span> | <span v-click="2">no: a person must update it for every new champion</span> |
| the registry in MLflow (`@champion`) | <span v-click="3">no</span> | <span v-click="4">yes</span> |

</div>

<div v-click="5" class="flow" style="margin-top:0.5rem; margin-bottom:0.5rem">
  <div class="node amber" style="width:11rem"><ph-tag class="ic" /><b>@champion</b><br><small>in the registry</small></div>
  <div class="arrow-l on">copied on purpose<span class="arrow">→</span></div>
  <div class="node" style="width:12rem"><ph-file-text class="ic" /><b>baseline.json</b><br><small>committed to Git</small></div>
  <div class="arrow">→</div>
  <div class="node green" style="width:8rem"><ph-shield-check class="ic" /><b>gate</b></div>
</div>

<v-click at="6">

> [!WARNING]
> A stored score is true only for the test set it was measured on. When the test data changes, score the champion again on the new test set.

</v-click>

<!--
The lab uses the file, written only by a person running `make baseline-sync`, which loads the champion and scores it on today's test split. `dvc.lock` can then describe the stage's inputs completely; the registry answer depends on a database in another container. A score is only comparable on the same test patients: compare the champion's F1 on last month's test set with a new model's F1 on this month's, and the difference measures the data, not the model. A live test checks that the file and the alias agree when the stack is up.
-->

---

# The bar moves up

<carbon-growth class="icon-corner" />

<div class="flow" style="margin-top:1.5rem; gap:0.5rem">
  <div class="node sky no-shrink" style="width:9rem"><ph-tree class="ic" /><b>Random forest</b><br>F1 0.6452</div>
  <div class="arrow-l" style="min-width:4.5rem">gate<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:6rem"><b>GO</b><br><small>+0.0111</small></div>
  <div v-click="1" class="arrow-l" style="min-width:4.5rem">promote<span class="arrow">→</span></div>
  <div v-click="1" class="node amber no-shrink" style="width:8rem"><ph-trophy class="ic" /><b>@champion</b></div>
  <div v-click="2" class="arrow-l" style="min-width:5.5rem">baseline-sync<span class="arrow">→</span></div>
  <div v-click="2" class="node no-shrink" style="width:9rem"><ph-file-text class="ic" /><b>baseline.json</b><br>F1 0.6452</div>
</div>

<div v-click="3" class="flow" style="margin-top:1.5rem; gap:0.5rem">
  <div class="node sky no-shrink" style="width:11rem"><ph-cube class="ic" /><b>The old model</b><br>logistic regression<br>F1 0.6341</div>
  <div class="arrow-l fail" style="min-width:4.5rem">gate<span class="arrow">→</span></div>
  <div class="node rose no-shrink" style="width:7rem"><b>NO-GO</b><br><small>−0.0111</small></div>
</div>

<v-click at="4">

The old model did not change. Why is it refused now?

</v-click>

<v-click at="5">

The bar moved: it is the forest's F1 now.

</v-click>

<!--
Measured in the lab with `make ratchet`: the drop of 0.0111 is larger than `max_drop` 0.01, about one patient's worth of F1. The bar follows the champion: up with a better model, and down by up to `max_drop` each time a slightly worse one is promoted (see "Measure the noise before you set a tolerance").
-->

---
layout: section
---

# 3 · Is it good enough for every group?

<!--
The syllabus example: a model that is fine on average and wrong for older patients. A slice metric is a groupby; fairlearn's `MetricFrame` does it for any list of metrics.
-->

---
layout: center
---

# Which groups of patients should we check?

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-hourglass class="ic" /><b>Age band</b>21–29 · 30–39 · 40–49 · 50+</div>
  <div v-click class="card"><ph-scales class="ic" /><b>BMI band</b>under or normal · overweight · obese · missing</div>
  <div v-click class="card"><ph-drop class="ic" /><b>Insulin</b>measured · not measured</div>
</div>

<!--
Choosing the groups is a clinical question, so they live in `params.yaml` (block `evaluation`), where a clinician can read and change them. Bands include the lower edge: 30–39 means [30, 40).
-->

---

# Slice metrics in code

<carbon-code class="icon-corner" />

```python {1-4|5-10|11-12|all}
import pandas as pd
from fairlearn.metrics import MetricFrame, count
from sklearn.metrics import recall_score
payments = pd.read_csv("payments.csv")   # country, is_fraud, flagged
frame = MetricFrame(
    metrics={"n": count, "recall": recall_score},
    y_true=payments.is_fraud,
    y_pred=payments.flagged,
    sensitive_features=payments.country,
)
print(f"all  recall={frame.overall['recall']:.2f}")
print(frame.by_group.round(2))
```

<v-click at="4">

```text
all  recall=0.75
            n  recall
country
AT        4.0    0.00
DE       10.0    1.00
HU        6.0    0.67
```

</v-click>

<!--
A toy file of 20 card payments, not our patients: the lab writes the diabetes version, `group_scores`. `MetricFrame` takes any scikit-learn metric; `overall` is the whole file, `by_group` one row per country. Output measured with fairlearn 0.14.0 and scikit-learn 1.9.0, the lab's versions.
-->

---

# Which group would you worry about?

<carbon-user-multiple class="icon-corner" />

<div class="text-lg" style="margin-top:1.5rem">

| **Age band** | **n** | **with diabetes** | **F1** | **ROC-AUC** |
| --- | --- | --- | --- | --- |
| all patients | 192 | 67 | 0.6341 | 0.8345 |
| 21–29 | 94 | 21 | 0.6316 | 0.8656 |
| 30–39 | 48 | 22 | 0.5946 | 0.7832 |
| 40–49 | 31 | 17 | 0.7500 | 0.8571 |
| 50+ | <span v-mark.circle.red="2">19</span> | 7 | 0.5000 | <span v-mark.circle.red="1">0.6071</span> |

</div>

<!--
Our model on the lab's test split. The false-positive rate of the 50+ group is 0.4167: two in five healthy older patients get flagged, against 0.0685 for the under-30s.
-->

---

# How many patients make a slice?

<carbon-rule class="icon-corner" />

<div class="flow" style="margin-top:0; margin-bottom:0">
  <div class="node amber" style="width:13rem"><ph-credit-card class="ic" /><b>AT in the toy file</b><br>4 payments, 1 fraud</div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:13rem"><b>recall</b><br>0.00 or 1.00<br><small>nothing in between</small></div>
</div>

<div class="text-sm">

| **Rule** | **Means** |
| --- | --- |
| `min_support` | a group needs at least this many rows |
| `min_positives` | a group needs at least this many positive cases |

</div>

<v-click>

> [!WARNING]
> A group can have many rows and almost no positive cases.

</v-click>

<v-click>

> [!TIP]
> When a group does not meet `min_support` or `min_positives`, skip its check, and say so in the report.

</v-click>

<!--
Questions for the room: why two rules? And when a group is too small to judge, does its check pass or fail? Neither: it is skipped. Call a skip a pass, and the report says "everything checked" when the group we worried about was never scored. Call it a fail, and every model with a small group is refused.
The lab uses 20 rows and 10 positives. Lower `min_support` to 15 alone, and the 50+ group is still not scored: now its 7 positives are too few.
-->

---

# Always check what was skipped

<carbon-report class="icon-corner" />

```text {1|3-7|all}
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)

  SKIPPED (not checked — read these before you trust the verdict):
    slice.age_band.50+                       support 19 < min_support 20
    slice.bmi_band.under_normal              positives 1 < min_positives 10
    slice.bmi_band.overweight                positives 9 < min_positives 10
    slice.bmi_band.missing                   support 2 < min_support 20
```

<v-click at="3">

> [!TIP]
> Put the count of skipped checks in the verdict's first line, and give each skip its reason with the numbers.

</v-click>

<!--
Real output of `make gate` on the lab solution. The 50+ group, the one with the lowest ROC-AUC, is among the four that were not checked.
-->

---

# Which BMI group is a patient with no BMI in?

<carbon-data-error class="icon-corner" />

The gate groups patients by BMI: **under 25** · **25 to 29** · **30 and over (obese)** · **missing**.

<div class="flow" style="margin-top:3rem">
  <div class="node amber" style="width:11rem"><b>2 test patients</b><br><span class="mono">bmi = 0</span><br><small>never measured</small></div>
  <div class="arrow-l">slice the raw data<span class="arrow">→</span></div>
  <div class="node green" style="width:14rem"><b>missing</b> · 2 patients<br><DataBatch cells=".." :cols="2" /></div>
</div>

<div v-click class="flow">
  <div class="node amber" style="width:11rem"><b>the same 2</b><br><span class="mono">bmi = 32.4</span><br><small>the training median</small></div>
  <div class="arrow-l fail">slice after the imputer<span class="arrow">→</span></div>
  <div class="node rose" style="width:14rem"><b>obese</b> · 112 → 114 patients<br><small>F1 0.6792 → 0.6729</small><DataBatch cells="gggggg.." :cols="8" /></div>
</div>

<v-click>

> [!TIP]
> Give missing values their own group: cut the groups from the raw data, before the imputer.

</v-click>

<!--
The first way is the right one. Measured in the lab. After the imputer, the `missing` group no longer exists, and `obese` reports a number partly about two patients whose BMI nobody knows. So the lab cuts the slices from the raw test data, before the imputer.
-->

---
layout: section
---

# 4 · Group fairness metrics

<!--
A first look at fairness: three rates, three gaps, and why they disagree. Week 13 comes back to it with Model Cards. Option B for the Obermeyer case (pneumonia risk, mid-1990s) is hidden after its slides.
-->

---
class: fn-inline
---

# Group fairness: compare the groups

<carbon-scales class="icon-corner" />

<div class="flow" style="margin-top:1.5rem">
  <div class="node" style="width:16rem"><ph-users class="ic" /><b>Section 3: slices</b><br>Is each group above the floor?<br><small>one group against a fixed bar</small></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet" style="width:16rem"><ph-scales class="ic" /><b>Section 4: fairness</b><br>Do the groups get the same rates?<br><small>groups against each other</small></div>
</div>

<v-clicks at="2">

- The groups come from a **sensitive feature**: age, sex, ethnicity[^1][].
- Two harms to look for:
  - an **allocation harm** withholds an opportunity or a resource
  - a **quality-of-service harm** means the model works worse for some people

</v-clicks>

[^1]: fairlearn, "Fairness in machine learning". https://fairlearn.org/main/user_guide/fairness_in_machine_learning.html

<!--
fairlearn: a sensitive feature is one "the system designer should be sensitive to" when assessing fairness. In our case, a missed diagnosis is a quality-of-service harm, and a referral for extra tests that one group does not get is an allocation harm.
-->

---

# Three rates for each group

<carbon-chart-column class="icon-corner" />

<div style="display:grid; grid-template-columns:15rem 1fr; gap:2rem; align-items:center; margin-top:1rem">
<div>

<div class="cm">
  <div></div><div class="h">says no</div><div class="h">says yes</div>
  <div class="h">no diabetes</div><div class="c">TN</div><div class="c bad">FP</div>
  <div class="h">diabetes</div><div class="c bad">FN</div><div class="c">TP</div>
</div>

</div>
<div class="text-sm">

| **Rate** | **Computed as** | **Means** |
| --- | --- | --- |
| selection rate | (TP + FP) / all | <span v-click="1">how often we act</span> |
| TPR (= recall) | TP / (TP + FN) | <span v-click="2">whom we catch</span> |
| FPR | FP / (FP + TN) | <span v-click="3">whom we alarm</span> |

</div>
</div>

<!--
TPR and recall are the same number; papers use both names. Our model on all 192 patients: selection rate 56/192 = 0.2917, TPR 0.5821, FPR 17/125 = 0.1360.
-->

---
class: fn-inline
---

# Three fairness metrics

<carbon-scales class="icon-corner" />

<div class="text-sm">

| **Metric** | **Equal in every group** | **The question it asks** |
| --- | --- | --- |
| demographic parity | selection rate | <span v-click="1">Is every group flagged as often?</span> |
| equal opportunity | TPR | <span v-click="2">Of the patients with diabetes, is every group found as often?</span> |
| equalized odds | TPR **and** FPR | <span v-click="3">Are both errors the same in every group?</span> |

</div>

<v-click at="4">

Each is measured as a **difference**: the highest group's rate minus the lowest group's.
In fairlearn, each is one function: `demographic_parity_difference`,
`equal_opportunity_difference`, `equalized_odds_difference`.

</v-click>

Definitions and names: fairlearn user guide[^1][]

[^1]: fairlearn, "Common fairness metrics". https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html

<!--
For equalized odds, the difference is the larger of the TPR gap and the FPR gap. Tip for the room: choose the metric by the harm that a wrong decision causes, and write the reason next to the rule. fairlearn: demographic parity "seeks to mitigate allocation harms"; equalized odds and equal opportunity are a diagnostic for both kinds. So: equal opportunity when a missed case costs most, demographic parity when the decision gives out a resource. Our case: a missed diagnosis is the costly error, so equal opportunity is the natural first choice. fairlearn has no minimum group size: a group of two patients can set the gap. The lab leaves groups under 5 rows out before it calls these functions.
-->

---

# Is the model fair to both groups?

<carbon-help class="icon-corner" />

Split our 192 test patients by whether an insulin value was ever recorded:

<div class="text-lg">

| **Group** | **n** | **selection rate** | **TPR** |
| --- | --- | --- | --- |
| insulin measured | 104 | 0.2885 | 0.5238 |
| insulin not measured | 88 | 0.2955 | 0.6800 |

</div>

<br>

<v-clicks>

- Demographic parity: gap 0.0070. **Yes.**
- Equal opportunity: gap 0.1562. **No.**

</v-clicks>

<!--
Same model, same patients. The base rates differ too: 40% of patients with an insulin value have diabetes, 28% of those without one.
-->

---
layout: center
class: fn-inline
---

# Can a model satisfy all three at once?

<v-click>

**Base rate:** the share of a group that really has diabetes.

</v-click>

<div class="fair-grid">
  <div></div><div class="h">insulin measured<br><small>40% have diabetes</small></div><div class="h">not measured<br><small>28% have diabetes</small></div><div></div>
  <div v-click="2" class="h">a perfect model</div>
  <div v-click="2"><div class="pgrid"><span v-for="(c, i) in 'TTTTTTTTTTNNNNNNNNNNNNNNN'" :key="i" :class="'p' + c" /></div></div>
  <div v-click="2"><div class="pgrid"><span v-for="(c, i) in 'TTTTTTTNNNNNNNNNNNNNNNNNN'" :key="i" :class="'p' + c" /></div></div>
  <div v-click="2" class="res">flags 40% and 28%<br><b style="color:#dc2626">selection rates differ</b></div>
  <div v-click="3" class="h">equal selection rates</div>
  <div v-click="3"><div class="pgrid"><span v-for="(c, i) in 'TTTTTTTTTMNNNNNNNNNNNNNNN'" :key="i" :class="'p' + c" /></div></div>
  <div v-click="3"><div class="pgrid"><span v-for="(c, i) in 'TTTTTTTFFNNNNNNNNNNNNNNNN'" :key="i" :class="'p' + c" /></div></div>
  <div v-click="3" class="res">flags 36% and 36%<br><b style="color:#dc2626">1 missed · 2 false alarms</b></div>
</div>

<div class="legend"><span class="pT"></span> found <span class="pM"></span> missed <span class="pF"></span> false alarm <span class="pN"></span> healthy, not flagged</div>

<v-click at="4">

**So no model gets all three**, unless the base rates are equal or the model is no better than chance[^1][].

</v-click>

<v-click at="5">

> [!TIP]
> Choose one criterion, and write the reason down in the acceptance criteria.

</v-click>

[^1]: Barocas, Hardt and Narayanan, *Fairness and Machine Learning*, Chapter 3 "Classification", section "Relationships between criteria", Proposition 3 (independence versus separation). https://fairmlbook.org/classification.html

<!--
Base rates from the lab's test split: 42 of 104 patients with an insulin value have diabetes, 25 of 88 without one. Each square is one of 25 patients per group (10 and 7 with diabetes). The second model flags 9 in each group: in the first group it must miss one patient with diabetes, in the second it must flag two healthy ones. The book calls demographic parity "independence" and equalized odds "separation". Calibration and equal error rates cannot both hold either: Chouldechova (2017, arXiv:1703.00056) on US recidivism scores, and Kleinberg, Mullainathan and Raghavan (2016, arXiv:1609.05807).
-->

---

# Which groups get a fairness gate?

<carbon-security class="icon-corner" />

Our model, all three gaps. Which should stop a release?

<div class="text-sm">

| **Groups** | **Selection rate**<br><small>demographic parity</small> | **TPR**<br><small>equal opportunity</small> | **TPR or FPR**<br><small>equalized odds</small> |
| --- | --- | --- | --- |
| age band | 0.3030 <span v-click="1">· report</span> | 0.2059 <span v-click="1">· **gate ≤ 0.25**</span> | 0.3482 <span v-click="1">· report</span> |
| insulin measured or not | 0.0070 <span v-click="2">· **gate ≤ 0.10**</span> | 0.1562 <span v-click="2">· **gate ≤ 0.20**</span> | 0.1562 <span v-click="2">· report</span> |

</div>

<br>
<v-clicks at="3">

- Age: diabetes really is more common with age (22% under 30, 55% at 40–49), so unequal selection rates are expected. But a patient with diabetes should be found as often at any age.
- Insulin: whether the test was ordered is about access to care, not about the body.

</v-clicks>
<br>
<v-click at="5">

> [!TIP]
> Gate a gap only where equal rates are what you expect. Report the others, and document why.

</v-click>

<!--
Measured with `make fairness` on the lab solution; the lab's `params.yaml` gates `max_selection_rate_gap: 0.10` and `max_tpr_gap: 0.20` on the insulin axis, and the TPR gap at 0.25 on the age axis. The age TPR limit is looser than the insulin one because the age groups are small: 17 to 22 patients with diabetes per band (7 at 50+), so one patient found or missed moves a group's TPR by about 0.05. The age gaps come from the 30-39 band (TPR 0.5000) and the 40-49 band (0.7059). Which gap matters is a judgement about the world, not a property of the model: the domain expert decides it.
-->

---

# 2019: who gets extra care?

<carbon-hospital class="icon-corner" />

US hospitals run care programmes for patients with complex health needs: dedicated nurses, extra doctor appointments. Places are expensive, so an algorithm picks who gets one[^1][].

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:11rem"><ph-heartbeat class="ic" /><b>Who is sickest?</b><br><small>they gain most from the programme</small></div>
  <div v-click="1" class="arrow-l">hard to measure<span class="arrow">→</span></div>
  <div v-click="1" class="node violet" style="width:11rem"><ph-currency-dollar class="ic" /><b>Next year's cost</b><br><small>predicted by the algorithm</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node sky" style="width:9rem"><ph-cube class="ic" /><b>Risk score</b><br><small>risk ∼ cost</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:10rem"><ph-first-aid class="ic" /><b>Extra care</b><br><small>top 3% enrolled automatically</small></div>
</div>

[^1]: Obermeyer, Powers, Vogeli and Mullainathan, "Dissecting racial bias in an algorithm used to manage the health of populations", *Science* 366 (2019). https://www.science.org/doi/10.1126/science.aax2342

<!--
The counter-case of the week: the model predicts its label well, and still harms patients. From the paper: patients above the 97th percentile of the score are enrolled automatically, those above the 55th are referred to their doctor; by industry estimates, such tools are applied to about 200 million people in the US each year. The abstract calls the algorithm "typical of this industry-wide approach".
-->

---

# What went wrong?

<carbon-search class="icon-corner" />

<div class="flow" style="margin-top:1.5rem">
  <div v-click="1" class="node rose" style="width:14rem"><ph-heartbeat class="ic" /><b>The same risk score</b><br>Black patients were sicker<br><small>4.8 against 3.8 chronic illnesses at the enrolment line</small></div>
  <div v-click="2" class="arrow-l">why?<span class="arrow">→</span></div>
  <div v-click="2" class="node amber" style="width:14rem"><ph-currency-dollar class="ic" /><b>The same illness</b><br>less money spent on Black patients<br><small>$1,801 less a year: unequal access to care</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node violet" style="width:12rem"><ph-chart-line-down class="ic" /><b>Lower cost</b><br>lower score<br><small>fewer Black patients chosen</small></div>
</div>

<div v-click="4" class="flex justify-center items-start gap-3 text-center" style="margin-top:1.5rem">
  <div style="width:16rem"><div class="text-5xl font-bold">17.7%</div><div>of the patients chosen were Black</div></div>
  <div class="text-5xl">→</div>
  <div style="width:16rem"><div class="text-5xl font-bold" style="color:#16a34a">46.5%</div><div>if they were chosen by health</div></div>
</div>

Obermeyer et al., *Science* 2019, pp. 1–4[^1][]

[^1]: Obermeyer, Powers, Vogeli and Mullainathan, *Science* 366 (2019). https://www.science.org/doi/10.1126/science.aax2342

<!--
The bias here: at the same score, one group is sicker, so the score under-ranks that group's need. "Chronic illnesses" is the number of active chronic conditions; the line is the 97th percentile, where patients are enrolled automatically (26.3% more illness for Black patients). The authors' words on the cause: "unequal access to care means that we spend less money caring for Black patients than for White patients". 46.5% is their simulation: swap healthier White patients above the line for sicker Black patients below it until both are equally healthy.
-->

---

# Which check would have caught it?

<carbon-warning-alt class="icon-corner" />

<div class="flow text-sm" style="margin-top:0.5rem; margin-bottom:0.25rem">
  <div class="node" style="width:12rem; padding:0.3rem">check against the <b>label</b> (cost)</div>
  <div class="arrow">→</div>
  <div class="node green" style="width:17rem; padding:0.3rem"><b>pass</b> · the same costs at the same score</div>
</div>

<div v-click="1" class="flow text-sm" style="margin-top:0; margin-bottom:0.5rem">
  <div class="node" style="width:12rem; padding:0.3rem">check against <b>health</b></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:17rem; padding:0.3rem"><b>fail</b> · Black patients sicker at the same score</div>
</div>

<v-click at="2">

> [!WARNING]
> If the label measures the wrong thing, every check can pass.

</v-click>

<v-click at="3">

> [!NOTE]
> Combining predicted health with cost cut the bias by 84%[^1][].

</v-click>

[^1]: Obermeyer et al., *Science* 366 (2019), pp. 3 and 7.

<!--
The authors on the first check: "By this metric, one could call the algorithm unbiased." Only someone who asks what the label means catches this: the domain expert from Week 1. The fix: the manufacturer replicated the result on its own data of 3,695,943 patients; with the combined label, the excess chronic illnesses among Black patients at the same score fell from 48,772 to 7,758.
-->

---
hide: true
---

# Option B · Mid-1990s: who goes to hospital?

<carbon-hospital class="icon-corner" />

A research study trained models to predict which patients with pneumonia would die[^1][]. The plan: admit the high-risk patients, treat the low-risk ones at home.

<div class="flow" style="margin-top:1.5rem">
  <div class="node amber" style="width:11rem"><ph-heartbeat class="ic" /><b>Risk without hospital</b><br><small>what the decision needs</small></div>
  <div v-click="1" class="arrow-l">not in the data<span class="arrow">→</span></div>
  <div v-click="1" class="node violet" style="width:12rem"><ph-first-aid class="ic" /><b>Death after the care they got</b><br><small>the label it learnt</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node sky" style="width:9rem"><ph-cube class="ic" /><b>Risk score</b></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green" style="width:9rem"><ph-hospital class="ic" /><b>Admit or send home</b></div>
</div>

[^1]: Caruana et al., "Intelligible Models for HealthCare: Predicting Pneumonia Risk and Hospital 30-day Readmission", KDD 2015, Sections 1 and 3. https://doi.org/10.1145/2783258.2788613

<!--
Option B for this slot: use it instead of Obermeyer. One of the study's datasets had 14,199 patients. Hide "2019: who gets extra care?", "What went wrong?" and "Which check would have caught it?"; show the three "Option B ·" slides after them. The study notes already list both cases.
-->

---
hide: true
layout: center
---

# Option B · What did the model learn about asthma?

<v-clicks>

- "HasAsthma(x) ⇒ LowerRisk(x)"
- Patients with asthma usually went straight to intensive care, and that care lowered their death rate.
- **Sent home, they have a much higher risk.**

</v-clicks>

<!--
Option B, second slide. A rule-based model showed the rule, so the neural nets had surely learnt it too. The team used logistic regression, whose asthma weight could be corrected, although the neural nets had a higher AUC (0.86 against 0.77 on one dataset).
-->

---
hide: true
---

# Option B · Which check would have caught it?

<carbon-warning-alt class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div class="node rose" style="width:12rem"><ph-first-aid class="ic" /><b>Label: death after care</b><br><small>the wrong target</small></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:9rem"><ph-cube class="ic" /><b>Model</b></div>
  <div class="arrow">→</div>
  <div class="node green" style="width:15rem"><ph-shield-check class="ic" /><b>Floors, slices, fairness gaps</b><br><small>all computed against the label</small></div>
</div>

<v-click>

> [!WARNING]
> Every check in this lecture compares predictions with the label. If the label measures the wrong thing, every check can pass.

</v-click>

<!--
Option B, third slide. The rule was found because the rule-based model was readable. The paper: models trained on real-world data must be validated before they are used on patients.
-->

---
layout: section
---

# 5 · The go/no-go gate

<!--
The lab's Exercises 3 and 4 build this. No new tool: the gate is a function and a DVC stage.
-->

---

# From evidence to a verdict

<carbon-flow class="icon-corner" />

<div class="flow" style="margin-top:1.5rem; gap:0.5rem">
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node amber no-shrink" style="width:10rem; padding:0.3rem"><span class="mono">metrics.json</span></div>
    <div class="node amber no-shrink" style="width:10rem; padding:0.3rem"><span class="mono">slices.json</span></div>
    <div class="node amber no-shrink" style="width:10rem; padding:0.3rem"><span class="mono">baseline.json</span></div>
    <div class="node amber no-shrink" style="width:10rem; padding:0.3rem"><span class="mono">acceptance</span> rules</div>
  </div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet no-shrink" style="width:10rem"><ph-function class="ic" /><b>evaluate_gate</b><br><small>a pure function</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node green no-shrink" style="width:8rem; padding:0.3rem">pass · 13</div>
    <div class="node rose no-shrink" style="width:8rem; padding:0.3rem">fail · 0</div>
    <div class="node no-shrink" style="width:8rem; padding:0.3rem; border-style:dashed">skipped · 4</div>
  </div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node sky no-shrink" style="width:12rem"><ph-stamp class="ic" /><b>GO</b> if nothing failed<br><b>NO-GO</b> otherwise<br><small>the skip count stays in the headline</small></div>
</div>

<!--
`evaluate_gate` takes four plain dicts: no files, no model, no network. That is why `tests/test_gates.py` can test every rule with nothing running. The counts are our shipped model's verdict.
-->

---

# The gate in the pipeline

<carbon-flow-connection class="icon-corner" />

<div class="flow" style="margin-top:2rem; gap:0.4rem">
  <div class="node green no-shrink" style="width:7rem"><b>validate</b><br><small>Week 5</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6.5rem"><b>prepare</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6rem"><b>train</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:7rem"><b>evaluate</b><br><small>+ slices</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9rem"><b>gate</b><br><small>writes <span class="mono">gate.json</span></small></div>
</div>

<div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; align-items:start">
<div>

<v-clicks>

- On a NO-GO, `gate` writes the report and exits with code 1, so `dvc repro` fails.
- `make register` and `make promote` read the report and refuse without a GO.

</v-clicks>

</div>
<div v-click="1">

```json
// reports/gate.json
{
  "verdict": "GO",
  "criteria_version": "1.0.0",
  "summary": {"passed": 13, "failed": 0,
              "skipped": 4}
}
```

</div>
</div>

<v-click>

> [!TIP]
> Make every command that publishes a model (register, promote, build an image) read the gate report and refuse without a GO.

</v-click>

<!--
Week 9 adds a third reader: `make image` refuses to build a serving image for a model without a GO.
-->

---

# Inspect the report

<carbon-document class="icon-corner" />

<div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem">
<div>

```json
{
  "verdict": "GO",
  "criteria_version": "1.0.0",
  "summary": {"passed": 13, "failed": 0,
              "skipped": 4},
  "checks": [
    {"id": "regression.f1",
     "baseline": 0.6341, "observed": 0.6341,
     "delta": 0.0, "max_drop": 0.01,
     "status": "pass"}, ...
  ]
}
```

</div>
<div>

**Two copies of the report:**

<v-clicks>

- **In Git**, next to the code that made it: `make register` and CI read it without MLflow.
- **In the MLflow run**, next to the model: for tracing the model later.

</v-clicks>

</div>
</div>

<v-click>

> [!NOTE]
> The report has no timestamp: the same run gives the same file, so a Git diff shows only real changes.

</v-click>

<!--
`reports/gate.json` is a `cache: false` DVC output, so it is committed with the code, `params.yaml` and `dvc.lock`. Week 7's CI runs on a runner with no MLflow, and it still has to read the verdict; that is why the Git copy exists. The next slide shows the MLflow copy. The JSON is shortened from the lab's real report.
-->

---

# Why was this model allowed out?

<carbon-tag class="icon-corner" />

<div class="flow" style="gap:0.5rem; margin-top:2rem">
  <div class="node sky no-shrink" style="width:7rem"><span class="mono">@staging</span></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:6rem">version</div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:5rem">run</div>
  <div class="arrow">→</div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node amber no-shrink text-sm" style="width:20rem"><span class="mono">dvc_md5</span> · which data</div>
    <div class="node green no-shrink text-sm" style="width:20rem"><span class="mono">data_validation</span> · Week 5's verdict</div>
    <div v-click="1" class="node green no-shrink text-sm text-left" style="width:20rem; border-width:3px"><span class="mono">gate: GO</span><br><span class="mono">gate_criteria_version: 1.0.0</span><br><span class="mono">gate_checks_failed: 0</span><br><span class="mono">gate_checks_skipped: 4</span></div>
  </div>
</div>

<v-click at="2">

The `gate` stage tags the training run, and logs `gate.json` and `slices.json` with it. `make trace` prints the whole chain.

</v-click>

<!--
The run is tagged on a NO-GO too: a run that failed its gate is the one you want to find later. Week 13's Model Card cites these tags.
-->

---
layout: section
---

# 6 · Red flags and good practices

<!--
Each of these happens at work with any metric and any tool. The lab-specific traps are on a hidden slide; show them at the start of the lab session.
-->

---
hide: true
---

# Traps you will meet in the lab

<carbon-debug class="icon-corner" />

<div class="text-sm">

| **Trap** | **What you see** | **What is wrong** |
| --- | --- | --- |
| `roc_auc_score` on the predicted classes | ROC AUC 0.7230, not 0.8345 | score `y_prob`, the probabilities |
| slicing the imputed features | the `missing` BMI group is gone | pass the raw test frame to `slice_report` |
| a patient outside every band | group sizes do not add up to 192 | give that patient a visible label |
| a two-patient group in the fairness gaps | a TPR gap set by two patients | leave groups under 5 rows out |
| `No module named 'fairlearn'` | the package is new this week | `uv sync --locked --all-groups` |
| `dvc repro` says "up to date" after an edit | you changed a comment, not a value | `dvc params diff` |

</div>

<!--
Hidden: lab-specific. Show it at the start of the lab session instead.
-->

---

# Make sure every rule can fire

<carbon-rule class="icon-corner" />

<div class="flow" style="margin-top:3.5rem">
  <div class="node sky" style="width:11rem"><b>all patients</b><br>F1 0.6341</div>
  <div class="arrow-l">a group's F1 is at least<span class="arrow">→</span></div>
  <div class="node green" style="width:10rem"><b>min_f1</b><br>0.50</div>
  <div class="arrow-l">so a group's gap to all patients is at most<span class="arrow">→</span></div>
  <div class="node" style="width:9rem"><b>0.1341</b></div>
</div>

<div class="text-sm text-center">

`max_f1_gap`: all patients' F1 minus a group's F1

</div>

<div v-click class="flow">
  <div class="node rose" style="width:22rem"><b><span class="mono">max_f1_gap: 0.15</span></b><br><small>can never fail: a gap that large is already a failed <span class="mono">min_f1</span></small></div>
</div>

<v-click>

> [!TIP]
> For each rule, make a model that should fail it, and check that the gate says NO-GO.

</v-click>

<!--
Found while building this lab: a test that expected a gap failure got a pass. The lab now uses 0.10. A floor below the majority-class rate (0.6510) is the same mistake.
-->

---

# Measure the noise before you set a tolerance

<carbon-chart-bar class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(2,1fr); margin-top:2rem">
  <div class="card"><ph-question class="ic" style="color:#dc2626" /><b><code>max_drop: 0.01</code>, a guess</b>a real drop of 0.009 passes for ever</div>
  <div class="card"><ph-chart-line-up class="ic" style="color:#16a34a" /><b><code>max_drop</code> from a measurement</b></div>
</div>

<v-click>

> [!TIP]
> Train the same model several times, with different seeds or on different machines, and set `max_drop` just above the spread you measure.

</v-click>

<!--
Our pipeline gives the same F1 on every run, so the lab's 0.01 is a choice, not a measurement. Weeks of "only 0.009 worse" add up to a model that is much worse than the champion it replaced.
-->

---

# Change a threshold in a reviewed commit

<carbon-version class="icon-corner" />

The model misses the F1 floor by 0.003, the day before a release. What do you do?

<div class="flow" style="margin-top:4rem">
  <div class="node rose" style="width:16rem"><ph-pencil-simple class="ic" /><b>Edit <span class="mono">params.yaml</span></b><br><small>0.55 → 0.54, no review, version unchanged</small></div>
  <div v-click="1" class="arrow-l">instead<span class="arrow">→</span></div>
  <div v-click="1" class="node green" style="width:18rem"><ph-git-commit class="ic" /><b>A reviewed commit</b><br><small>the reason, an approver, <span class="mono">criteria_version</span> 1.0.0 → 1.1.0</small></div>
</div>

<!--
`criteria_version` is tagged on every MLflow run, so an old verdict still names the rules it was issued under. A threshold lowered without a trace makes every later GO mean less.
A threshold may go down for a good reason, for example a new test set that is harder. Then the commit message says so.
-->

---
layout: section
---

# 7 · Wrap-up

<!--
About 10 minutes: the whole pipeline, takeaways, open questions, the lab, and the questions students can now answer.
-->

---

# This week's pipeline

<carbon-flow class="icon-corner" />

<div class="flow text-sm" style="gap:0.4rem; margin-top:6rem">
  <div class="node amber no-shrink" style="width:5rem"><ph-file-csv class="ic" /><b>Batch</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:7rem"><ph-shield-check class="ic" /><b>validate</b><br><small>the data may come in</small></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:6.5rem"><ph-cube class="ic" /><b>prepare, train</b></div>
  <div v-click="1" class="arrow">→</div>
  <div v-click="1" class="node violet no-shrink" style="width:7rem"><ph-chart-bar class="ic" /><b>evaluate</b><br><small>metrics and slices</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node green no-shrink" style="width:7rem"><ph-stamp class="ic" /><b>gate</b><br><small>the model may go out</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node sky no-shrink" style="width:7rem"><ph-tag class="ic" /><b>register</b><br><small>only with a GO</small></div>
</div>

<!--
Two gates now: one at the start of the pipeline for the data, one at the end for the model. Back to Gender Shades: the `gate` box is the bar for each group from "What would have stopped it?".
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<v-clicks>

- Write down what "good enough" means before the run.
- Compare with a model that does nothing, and with the model in production.
- Score every group you serve, and report how many patients each score rests on.
- Fairness criteria can disagree: choose one, and write down why.
- A gate stops a release and leaves its evidence in Git.

</v-clicks>

<!--
If time is short, ask which takeaway a team with a single, well-understood model and one user group could drop, and why.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><carbon-automatic class="ic" /><b>Who runs the gate?</b>Today, we run <code>dvc repro</code> by hand.<br><br><b>→ Week 7:</b> CI on every change</div>
  <div v-click class="card"><carbon-chart-line class="ic" /><b>Does the model stay good?</b>The gate judges one test set, once.<br><br><b>→ Weeks 11–12:</b> monitoring and drift</div>
  <div v-click class="card"><carbon-document class="ic" /><b>What did we not check?</b>Skipped groups, groups we never recorded, a wrong label.<br><br><b>→ Week 13:</b> Model Cards</div>
</div>

<!--
Our data has no sex, ethnicity, income or clinic column, and every patient is a woman of Pima heritage aged 21 or more: those groups cannot be scored at all. Week 13's Model Card must print the skipped checks next to the GO.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="text-sm">

| # | Exercise | What you show |
| --- | --- | --- |
| 1 | Slice the test set | `metrics/slices.json`: every group with its `n` and positives |
| 2 | Read the slice table (written) | the worst group, and a group with F1 0.0000 and ROC-AUC 1.0000 |
| 3 | Write the acceptance criteria | `make gate` prints GO, with every check |
| 4 | The gate as a stage (written) | with `C: 0.005`, `dvc repro` stops and `register` and `promote` refuse |
| 5 | Fairness checks (written) | three gaps per axis, one axis gated |
| 6 | The ratchet | a better champion, and the old model refused |

</div>

Written answers go in `answers.md`, committed with your code. Homework 2, out in Week 7, applies this gate to your own project.

<!--
Stop the Week 5 stack before the lab: every lab uses the same ports.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

- Why can one metric not decide a release?
- Which four kinds of acceptance criteria are there, and who should write them?
- Which baselines should a model beat?
- How do you score a model per group, and when is a group too small to score?
- What do demographic parity and equal opportunity measure, and why can they disagree?
- How does a gate stop a release, and what does it leave behind?
- What can a passing gate not tell you?

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
