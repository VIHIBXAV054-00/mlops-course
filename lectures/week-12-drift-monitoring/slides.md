---
theme: default
title: Week 12 — Drift and Degradation
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers data drift and concept drift, the prediction log, reference and current
  windows, drift statistics as a written policy with Evidently, proxy metrics, drift
  alerts, and reaction protocols (retraining triggers, rollbacks).
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

# Week 12: Drift and Degradation

<carbon-chart-line class="icon-corner" />

<div class="middle">

**Lifecycle of Artificial Intelligence Systems**

- Data drift and concept drift
- Measuring drift
- Signals without labels
- Reacting to drift

</div>

<!--
Last week we learnt to notice when the service fails. Today the service is healthy and the model can still be wrong.
-->

---

# Recap: the test set

<carbon-calendar class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-database class="ic" /><b>Dataset</b></div>
  <div class="arrow-l">split<span class="arrow">→</span></div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="node green no-shrink" style="width:9rem; margin:0"><b>Training set</b><br><small>fit the model</small></div>
    <div class="node violet no-shrink" style="width:9rem; margin:0"><b>Test set</b><br><small>report the score</small></div>
  </div>
  <div class="arrow">→</div>
  <div class="node rose no-shrink" style="width:11rem; border-style:dashed"><ph-globe class="ic" /><b>Production data</b><br><small>score unknown</small></div>
</div>

Why do we trust the test score? What do we assume?

<v-click>

**New data comes from the same distribution as the training and test data.**

</v-click>

</div>

<!--
Intro ML: the test score estimates the score on new data only under this assumption. Week 4 pinned which data the model was trained on, by its hash, and Week 6's gate scored the test set. Today: what happens when production data stops looking like it, and how we notice.
-->

---

# Recap: what the contract checks

<carbon-rule-test class="icon-corner" />

<div class="middle">

What is the purpose of the data contract?

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-heartbeat class="ic" /><b>glucose = 0</b>no living patient<span v-click="1"><b style="color:#dc2626">422</b> rejected</span></div>
  <div class="card"><ph-heartbeat class="ic" /><b>glucose = 7.2</b>sent in mmol/L, not mg/dL<span v-click="1"><b style="color:#16a34a">200</b> scored</span></div>
  <div class="card"><ph-heartbeat class="ic" /><b>glucose = 190</b>possible, but rare<span v-click="1"><b style="color:#16a34a">200</b> scored</span></div>
</div>

<v-click at="2">

<div style="font-size:1.4rem; margin-top:1.2rem">

- **It rejects impossible values.**
- **It does not notice slow changes in valid data.**

</div>

</v-click>

</div>

<!--
Week 5: the contract checks each row against fixed rules (glucose above 0 and at most 400 mg/dL). 7.2 is impossible in mg/dL, but it is above 0, so a wrong unit passes. Week 5's "Keep drift checks out of the contract" sent the comparison with the past to this week.
-->

---

# Recap: the share of positives and the metrics

<carbon-percentage class="icon-corner" />

<div class="middle">

How does the share of positives affect the metrics?

- Hypothetical: the same model in two clinics, 100 patients each.
- It finds 80% of the sick patients and wrongly flags 10% of the healthy ones.

<div class="text-sm" style="max-width:36rem; margin:auto">
<table>
  <thead><tr><th></th><th style="text-align:right">Clinic A: 10% have diabetes</th><th style="text-align:right">Clinic B: 40% have diabetes</th></tr></thead>
  <tbody>
    <tr><td>Recall</td><td style="text-align:right">0.80</td><td style="text-align:right">0.80</td></tr>
    <tr :style="$clicks >= 2 ? 'background:#ffe4e6' : ''"><td>Precision</td><td style="text-align:right"><span v-click="1">0.47</span></td><td style="text-align:right"><span v-click="1">0.84</span></td></tr>
    <tr :style="$clicks >= 2 ? 'background:#ffe4e6' : ''"><td>F1</td><td style="text-align:right"><span v-click="1">0.59</span></td><td style="text-align:right"><span v-click="1">0.82</span></td></tr>
    <tr><td>ROC-AUC</td><td style="text-align:right"><span v-click="1">the same</span></td><td style="text-align:right"><span v-click="1">the same</span></td></tr>
  </tbody>
</table>
</div>

<v-click at="2">

**Precision and F1 change, although the model did not.**

</v-click>

</div>

<!--
Clinic A: 8 true and 9 false positives; Clinic B: 32 and 6. ROC-AUC compares the scores of sick and healthy patients, so the share does not move it. Week 6's F1 gate compared two models on one test set; today one model meets new patients.
-->

---

# What the dashboard does not show

<carbon-dashboard class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>up</b></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>errors</b><br><small>within budget</small></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>latency</b><br><small>within the SLO</small></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>predictions</b><br><small>score histogram</small></div>
</div>

<div v-click="1" class="flow" style="gap:0.5rem">
  <div class="node no-shrink" style="width:14rem; border-style:dashed; opacity:0.8"><ph-hourglass class="ic" /><b>wrong predictions</b><br><small>last updated: weeks ago</small></div>
</div>

<v-click at="2">

- Service errors and latency show at once.
- Wrong predictions show only when the true outcome arrives.
- Until then, the data can change while every panel stays green.

</v-click>

</div>

<!--
Week 11's dashboard watches the service and the spread of the scores. A wrong prediction is only known when the true outcome arrives, so that panel is always behind. The true outcome (the label) may take minutes (a click on a recommendation), weeks (a flu report) or years (a diagnosis); Section 2 comes back to it.
-->

---
layout: section
---

# 1 · Drifting apart

<img src="/drifting-apart.jpeg" alt="Meme: two cars drive side by side, then split at a fork; one car is labelled 'the world', the other 'our model'" style="height:220px; margin:0.5rem auto; display:block; border-radius:0.5rem" />

<!--
About 15 minutes: where we are, models that met a changed world, then one case. Option B (the Epic Sepsis Model during COVID-19) is hidden after the Google Flu Trends slides.
-->

---

# Where we are: monitoring the model

<div class="middle">

<Lifecycle stage="monitor" width="70%" />

Today: watch the model after it is deployed, when nothing is broken.

</div>

<!--
Week 11 also sat in "monitor", for the service. This week watches the inputs and outputs of the model on live traffic; what it finds feeds back into design and build (retraining, Week 8's flow).
-->

---
class: fn-inline
---

# When the world moves

<carbon-earth class="icon-corner" />

<div class="middle">

A model learns from the past and is used in the future.

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click="1" class="card"><ph-storefront class="ic" /><b>Retail, 2020</b>a sauce maker's stock forecasts broke on pandemic bulk orders<span v-click="5" style="display:block; color:#0369a1">outcome in days (sales)</span></div>
  <div v-click="2" class="card"><ph-television class="ic" /><b>Streaming, 2020</b>recommendations got worse after a wave of new subscribers<span v-click="5" style="display:block; color:#0369a1">outcome in minutes (clicks)</span></div>
  <div v-click="3" class="card"><ph-house-line class="ic" /><b>Real estate, 2021</b>Zillow closed its home-buying business: prices were far less predictable than expected<span v-click="5" style="display:block; color:#0369a1">outcome in months (a sale)</span></div>
</div>

<div class="text-sm opacity-70">

MIT Technology Review[^1][] · Zillow Group[^2][]

</div>

<v-click at="4">

Which of these would a service dashboard have shown? <span v-click="5">**None. Only the true outcomes showed it.**</span>

</v-click>

</div>

[^1]: Heaven, "Our weird behavior during the pandemic is messing with AI models", *MIT Technology Review*, 11 May 2020. https://www.technologyreview.com/2020/05/11/1001563/covid-pandemic-broken-ai-machine-learning-amazon-retail-fraud-humans-in-the-loop/
[^2]: Zillow Group, "Third Quarter 2021 Financial Results", 2 Nov 2021. https://www.sec.gov/Archives/edgar/data/1617640/000161764021000085/q32021991.htm

<!--
The streaming team could see the drop within days from clicks; Zillow only when it sold the homes it had bought. Zillow wrote down about $304 million of homes. Counter-example in the same article: a card-fraud model held up, because people kept their old spending habits.
-->

---
layout: two-cols
---

# Google Flu Trends

<carbon-search class="icon-corner" />

The US CDC counts doctor visits for flu-like illness. Its reports arrive about **two weeks** late.

- Google Flu Trends (GFT) estimated the same number from Google searches, with no delay.
- Its target was the CDC number: GFT "was built to predict CDC reports"[^1][].
- It was trained on past CDC reports.

::right::

<div style="margin-top:5rem">
<ImageSlot id="w12-gft-chart" text="Lazer et al. (2014), figure: Google Flu Trends estimates against CDC data, 2009–2013" height="260px" />
</div>

[^1]: Lazer, Kennedy, King and Vespignani, "The Parable of Google Flu: Traps in Big Data Analysis", *Science* 343(6176), 14 Mar 2014, pp. 1203–1205. https://www.science.org/doi/10.1126/science.1248506

<!--
CDC: the US Centers for Disease Control and Prevention. "Influenza-like illness" (ILI) is the CDC's measure: the share of doctor visits for flu symptoms. A peer-reviewed paper, four authors including Gary King.
-->

---

# Then the estimates went wrong

<carbon-warning-alt class="icon-corner" />

<div class="middle">

<div class="flex justify-center items-start gap-3 text-center">
  <div style="width:20rem"><div class="text-5xl font-bold" style="color:#dc2626">100 of 108</div><div>weeks with an estimate too high, from August 2011</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:18rem"><div class="text-5xl font-bold" style="color:#dc2626">× 2</div><div>the CDC's figure, in February 2013</div></div></div>
</div>

</div>

<!--
Both numbers are from Lazer et al.; the "more than double" was first reported by *Nature* in February 2013. The errors were not random: last week's error predicted this week's. In 2011–2012 GFT overshot the actual flu level by more than 50%.
-->

---
layout: center
---

# What went wrong?

<div class="cards" style="grid-template-columns:repeat(2,1fr); margin-top:1.5rem">
  <div v-click class="card"><ph-funnel class="ic" /><b>A fragile model</b>50 million search terms fitted to 1,152 data points: "part flu detector, part winter detector"</div>
  <div v-click class="card"><ph-virus class="ic" /><b>The flu changed</b>the 2009 flu pandemic came outside the winter season, and the first version missed it</div>
  <div v-click class="card"><ph-gear class="ic" /><b>The search engine changed</b>Google changed its search algorithm all the time: 86 changes in June and July 2012 alone</div>
  <div v-click class="card"><ph-users class="ic" style="color:#dc2626" /><b>How people searched changed</b>new suggested searches (June 2011) and possible diagnoses for "fever" and "cough" (February 2012)</div>
</div>

<v-click>

Every search was valid, but the world, the search engine and its users all changed. The model did not.

</v-click>

<!--
Lazer et al., pp. 1203–1204. Suggested searches pushed people towards flu treatments, and diagnoses towards "is it a cold or the flu?" searches, which tracked GFT's errors. The authors call this "blue team" dynamics: the provider changes the process that produces the data. They rule out media panic: it "cannot explain" two years of estimates that were too high.
-->

---

# Always look for the ground truth

<carbon-renew class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node amber no-shrink" style="width:9rem"><ph-magnifying-glass class="ic" /><b>Searches</b></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9rem"><ph-cube class="ic" /><b>GFT model</b></div>
  <div class="arrow">→</div>
  <div class="node no-shrink" style="width:9rem"><ph-chart-line class="ic" /><b>Estimate</b><br><small>this week</small></div>
  <div v-click="1" class="arrow-l">compare<span class="arrow">←</span></div>
  <div v-click="1" class="node green no-shrink" style="width:10rem"><ph-first-aid class="ic" /><b>CDC report</b><br><small>two weeks later</small></div>
</div>

<v-click at="2">

- The CDC report was the ground truth. It arrived every week, two weeks late.
- Compared and corrected with it, GFT "could have largely healed itself".

</v-click>

<v-click at="3">

> [!TIP]
> Compare the model's answers with the ground truth as soon as it arrives.

</v-click>

</div>

<!--
Lazer et al.: "Large errors in flu prediction were largely avoidable." GFT did not use the weekly CDC reports to correct itself. Mean absolute error out of sample: 0.486 for GFT, 0.311 for lagged CDC data alone, 0.232 for both together (figure caption). Even three-week-old CDC data predicted current flu better than GFT.
-->

---
hide: true
layout: two-cols
---

# Option B · 2020: a sepsis model meets COVID-19

<carbon-hospital class="icon-corner" />

The Epic Sepsis Model (Week 3) scores hospital patients and alerts nurses to possible sepsis.

- A study counted its alerts at **24 hospitals** in 4 US health systems, from November 2019 to April 2020[^1][].
- The University of Michigan paused the alerts in April 2020, 3–4 weeks after its first COVID-19 patient.

::right::

<div class="flow" style="flex-direction:column; margin-top:5rem">
  <div class="node amber" style="width:12rem"><ph-bed class="ic" /><b>Patient record</b></div>
  <div class="arrow">↓</div>
  <div class="node sky" style="width:12rem"><ph-cube class="ic" /><b>Epic Sepsis Model</b></div>
  <div class="arrow">↓</div>
  <div class="node rose" style="width:12rem"><ph-bell class="ic" /><b>Alert to a nurse</b></div>
</div>

[^1]: Wong et al., "Quantification of Sepsis Model Alerts in 24 US Hospitals Before and During the COVID-19 Pandemic", *JAMA Network Open* 4(11), 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8605481/

<!--
Option B for the cold open: use it instead of Google Flu Trends (switch `hide` on the four GFT slides and on these two). Also change the flu row on "When does the label arrive?", the GFT mention in the note of "This week's monitor", and the study notes' "Why this matters".
Michigan paused the alerts after nurses reported overalerting.
-->

---
hide: true
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:16rem"><div class="text-5xl font-bold">9% → 21%</div><div>of patients with an alert per day</div></div>
  <div v-click style="width:12rem"><div class="text-5xl font-bold">−35%</div><div>patients in hospital</div></div>
  <div v-click style="width:12rem"><div class="text-5xl font-bold" style="color:#dc2626">+43%</div><div>alerts per day</div></div>
</div>

<br>

Three weeks before and after each hospital's first COVID-19 case, Wong et al. (2021)[^1][]

[^1]: Wong et al., *JAMA Network Open* 4(11), 2021, Results.

<!--
Option B, second slide. 953 alerts a day from 10,159 patients, then 1,363 from 6,634. The study did not measure accuracy; the authors name dataset shift as one possible cause, next to cancelled elective surgeries and sicker patients.
The alert rate is a proxy metric (Section 5): it moved before anyone had labels.
-->

---
layout: section
---

# 2 · Types of drift

<!--
About 12 minutes: four types of drift, one slide each, then a summary and when the labels arrive. No tool in this section. The examples are typical situations, not reported incidents.
-->

---

# Data drift

<carbon-chart-histogram class="icon-corner" />

<div class="middle">

- **Data drift** (covariate shift): the distribution of the inputs, `P(X)`, changes. The link from inputs to outcome, `P(y|X)`, stays the same.
- **Visible without labels:** yes. Compare the inputs with the training data.

<div>
<svg viewBox="0 0 420 110" style="width:26rem; height:7rem; margin:0.5rem auto; display:block">
  <path d="M10,95 C60,95 80,20 130,20 C180,20 200,95 250,95" fill="none" stroke="#0284c7" stroke-width="3"/>
  <path d="M150,95 C200,95 220,20 270,20 C320,20 340,95 390,95" fill="none" stroke="#dc2626" stroke-width="3" stroke-dasharray="6 4"/>
  <line x1="0" y1="96" x2="420" y2="96" stroke="currentColor" stroke-opacity="0.4"/>
  <text x="130" y="12" text-anchor="middle" style="font-size:13px" fill="#0284c7">training data</text>
  <text x="270" y="12" text-anchor="middle" style="font-size:13px" fill="#dc2626">production</text>
  <text x="210" y="109" text-anchor="middle" style="font-size:11px" fill="currentColor" opacity="0.7">one input, for example the applicant's age</text>
</svg>
</div>

<div v-click class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-bank class="ic" /><b>Credit scoring</b>a bank advertises to students, so its applicants get younger</div>
  <div class="card"><ph-camera class="ic" /><b>Image recognition</b>a new phone camera makes every photo brighter</div>
</div>

</div>

<!--
Also called covariate shift: P(X) changes, P(y|X) does not. A model may still be right on the new inputs, or it may be weak in a region it rarely saw in training. In the lab, the April–June batch has a mean glucose of 134, against 112 in training.
-->

---

# Label shift

<carbon-percentage class="icon-corner" />

<div class="middle">

- **Label shift** (prior probability shift): the distribution of the outcome, `P(y)`, changes. What each outcome looks like, `P(X|y)`, stays the same.
- **Visible without labels:** only through a proxy, such as the share of positive predictions.

<div style="width:26rem; margin:0.5rem auto" class="text-sm">
  <div class="flex items-center gap-2"><span style="width:7rem">training data</span><div style="flex:1; height:1.2rem; background:#e5e7eb"><div style="width:10%; height:100%; background:#0284c7"></div></div><span style="width:3rem">10%</span></div>
  <div class="flex items-center gap-2" style="margin-top:0.4rem"><span style="width:7rem">production</span><div style="flex:1; height:1.2rem; background:#e5e7eb"><div style="width:40%; height:100%; background:#dc2626"></div></div><span style="width:3rem">40%</span></div>
  <div class="opacity-70" style="text-align:center; margin-top:0.3rem">share of positive cases (hypothetical)</div>
</div>

<div v-click class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-thermometer class="ic" /><b>Flu tests</b>in winter, a larger share of the people tested have the flu</div>
  <div class="card"><ph-credit-card class="ic" /><b>Card fraud</b>during a fraud wave, a larger share of payments is fraud</div>
</div>

</div>

<!--
Also called prior shift: P(y) changes, P(X|y) does not. This is the recap's two clinics: the same model, so recall stays, but precision and F1 move. Section 5 comes back to the proxy.
-->

---

# Concept drift

<carbon-ibm-watson-discovery class="icon-corner" />

<div class="middle">

- **Concept drift:** the link from inputs to outcome, `P(y|X)`, changes. The same input now has a different correct answer.
- **Visible without labels:** no. The inputs may not move at all.

<div class="flow" style="gap:0.6rem; margin-top:0.5rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-house-line class="ic" /><b>The same flat</b><br><small>3 rooms, city centre</small></div>
  <div style="display:flex; flex-direction:column; gap:0.4rem">
    <div class="flex items-center gap-2"><div class="arrow-l">low interest rates<span class="arrow">→</span></div><div class="node green" style="width:8rem; padding:0.3rem"><b>sells high</b></div></div>
    <div class="flex items-center gap-2"><div class="arrow-l fail">high interest rates<span class="arrow">→</span></div><div class="node rose" style="width:8rem; padding:0.3rem"><b>sells lower</b></div></div>
  </div>
</div>

<div v-click class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-envelope-simple class="ic" /><b>Spam filters</b>spammers copy the wording of normal mail to get through</div>
  <div class="card"><ph-storefront class="ic" /><b>Demand forecasting</b>after people start working from home, the same weekday brings different sales</div>
</div>

</div>

<!--
P(y|X) changes. The flat is an illustration, not data: the market turns and the same input is worth less. Spam is the classic case where the other side adapts to the model. A rule change that you are told about (a new pricing rule, a new medical guideline) is concept drift too, but you can plan a retrain for it.
-->

---

# Schema drift and skew

<carbon-data-structured class="icon-corner" />

<div class="middle">

- **Schema drift and skew:** production data is made differently from the training data[^1][]. A column, a type, a unit or the feature code changes.
- **Visible without labels:** yes, if a check covers it: a contract rule or the input distributions.

<div class="flow" style="margin-top:1rem">
  <div class="node amber no-shrink" style="width:11rem"><ph-flask class="ic" /><b>Lab device</b><br><small>after an update</small></div>
  <div class="arrow-l">glucose 7.2 mmol/L<span class="arrow">→</span></div>
  <div class="node green no-shrink" style="width:10rem"><ph-shield-check class="ic" /><b>Contract</b><br><small>above 0: passed</small></div>
  <div class="arrow">→</div>
  <div class="node rose no-shrink" style="width:10rem"><ph-cube class="ic" /><b>Model</b><br><small>reads 7.2 mg/dL</small></div>
</div>

<div v-click class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-currency-eur class="ic" /><b>Units</b>an app update sends prices in cents instead of euros</div>
  <div class="card"><ph-receipt class="ic" /><b>Training-serving skew</b>the service computes a feature differently from the training code</div>
</div>

[^1]: Zinkevich, "Rules of Machine Learning", Google for Developers, section "Training-Serving Skew". https://developers.google.com/machine-learning/guides/rules-of-ml

</div>

<!--
Not a change in the world but in our own pipeline or a supplier's. The recap showed that 7.2 passes the contract, which only checks "above 0"; a distribution check sees the glucose mean fall from over 100 to under 10 at once. Week 5's contract catches the rest: a renamed column, a wrong type.
-->

---

# Types of drift

<carbon-chart-multitype class="icon-corner" />

<div class="middle text-sm">

| **Type** | **What moves** | **Example** | **Visible without labels?** |
| --- | --- | --- | --- |
| data drift | the inputs, `P(X)` | applicants get younger | yes |
| label shift | the share of outcomes, `P(y)` | more flu in winter | only through a proxy |
| concept drift | the link, `P(y\|X)` | the same flat sells lower | **no** |
| schema drift, skew | the meaning of a column | glucose in mmol/L | yes, if a check covers it |

</div>

<!--
Most confusion about drift, also in vendor material, comes from mixing these four. Real cases are often a mix: COVID-19 changed who came to hospital (data drift), how many were sick (label shift) and what the symptoms meant (concept drift) at once.
-->

---

# When does the label arrive?

<carbon-time class="icon-corner" />

<div class="middle text-sm">

<div style="font-size:1.1rem; margin-bottom:0.8rem">

Label shift and concept drift show up only in the labels. How soon do they come?

</div>

<div style="display:grid; grid-template-columns:11rem repeat(6,1fr); gap:0.4rem; align-items:center">
  <div></div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">minutes</div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">hours</div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">days</div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">weeks</div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">months</div><div style="border-bottom:2px solid currentColor; opacity:0.7; padding-bottom:0.2rem; text-align:center">years →</div>
  <div style="display:contents">
    <div><b>Film recommendation</b></div>
    <div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">click</div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">watched to the end</div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">thumbs up</div><div></div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">cancels the subscription</div><div></div>
  </div>
  <div style="display:contents">
    <div><b>Flu estimate</b></div>
    <div></div><div></div><div></div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">CDC report</div><div></div><div></div>
  </div>
  <div style="display:contents">
    <div><b>Loan</b></div>
    <div></div><div></div><div></div><div></div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">first missed payment</div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">default</div>
  </div>
  <div style="display:contents">
    <div><b>Diabetes risk</b></div>
    <div></div><div></div><div></div><div></div><div></div><div style="color:#0c4a6e; background:#e0f2fe; border:1px solid #0284c7; border-radius:6px; padding:0.25rem 0.3rem; text-align:center; font-size:0.8rem; line-height:1.15">diagnosis</div>
  </div>
</div>

<div style="margin-top:1.5rem" />

> [!TIP]
> Labels often come in steps. Watch the fast, weak ones while you wait for the true outcome.

</div>

<!--
Concept drift and label shift need labels, so this decides how early you can see them. A click is a weak label: a user may click and stop after a minute. The early labels can be watched as proxies (Section 5). For our model the diagnosis comes years later; the labelled batches in the lab are historical data.
-->

---
layout: section
---

# 3 · Requirements for drift detection

<!--
About 15 minutes. A drift check compares two datasets: what the model was trained on, and what it sees now. This section is about collecting and choosing them; Section 4 is about the statistic. The lab's Exercises 1 and 2.
-->

---
layout: center
---

# What do we need to detect drift?

<carbon-help class="icon-corner" />

<v-click>

<div style="font-size:1.6rem; margin-top:1.5rem">

Something to compare with: a **reference**.

</div>

</v-click>

<!--
The follow-up question: which data do we know our model works on? The answer, the training data, where the test set showed it works, opens the next slide.
-->

---

# Reference and current window

<carbon-compare class="icon-corner" />

<div class="middle">

- **Reference window:** a fixed dataset, usually the training data. It shows what the model expects.
- **Current window:** recent production data, from the prediction log. It shows what the model gets.
- **A drift check** measures how far apart the two are, feature by feature.

<div style="width:40rem; margin:1.2rem auto 0.5rem">
  <div style="display:flex; gap:0.5rem; align-items:stretch">
    <div style="width:45%; background:#dcfce7; color:#14532d; border:2px solid #16a34a; border-radius:8px; padding:0.4rem 0.6rem; text-align:center; line-height:1.25"><ph-database /> <b>Reference</b><br><small>the training data, pinned to a version</small><br>mean glucose 112</div>
    <div style="flex:1"></div>
    <div style="width:32%; background:#fef3c7; color:#78350f; border:2px solid #d97706; border-radius:8px; padding:0.4rem 0.6rem; text-align:center; line-height:1.25"><ph-notepad /> <b>Current</b><br><small>the last month or N rows</small><br>mean glucose 134</div>
  </div>
  <div style="border-top:2px solid currentColor; opacity:0.6; margin-top:0.4rem"></div>
  <div class="text-xs opacity-70" style="display:flex; justify-content:space-between"><span>training</span><span>model in production</span><span>now →</span></div>
</div>

</div>

<!--
The glucose means are the lab's two batches (111.9 in training, 134.4 in April–June). This checks the recap's test-set assumption on live data. Keep the reference fixed: one that follows the live data never shows drift. Make the current window large enough: a small one shows drift that is only noise. After a retrain, the new training data becomes the reference.
-->


---

# What do we monitor now?

<carbon-dashboard class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem">
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>requests</b></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>errors</b></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>latency</b></div>
  <div class="node green no-shrink" style="width:8rem"><ph-check-circle class="ic" /><b>score histogram</b></div>
</div>

<div class="text-center opacity-70" style="margin-top:-0.5rem">service metrics</div>

<div style="font-size:1.2rem; margin-top:1.5rem">

- Service metrics show how the service runs.
- To see drift, we also need the inputs and the predictions themselves.

</div>

</div>

<!--
Last week's metrics watch the service and the shape of the output. No query recovers the distribution of one input from them. A histogram per feature would give each feature at fixed buckets, never the rows together, and you cannot re-bin data you did not keep.
-->


---

# One request, three records

<carbon-flow-data class="icon-corner" />

<div class="flow" style="margin-bottom:0">
  <div class="node amber" style="width:14rem"><ph-globe class="ic" /><b>POST /predict</b><br><small>one request</small></div>
</div>
<div class="split-stem"></div>
<div class="split-bar" style="width:33rem"></div>
<div class="flow" style="margin-top:0; align-items:stretch">
  <div class="node sky" style="width:15rem"><ph-chart-bar class="ic" /><b>Metric</b><br><small>a counter and a bucket</small><br>how many, how fast?<br><small>small, kept for a year</small></div>
  <div class="node violet" style="width:15rem"><ph-file-text class="ic" /><b>Access log line</b><br><small>id, path, status, ms</small><br>what happened to this request?<br><small>kept for weeks</small></div>
  <div v-click class="node rose" style="width:15rem"><ph-notepad class="ic" /><b>Prediction log</b><br><small>inputs, output, model version</small><br>what did we see, and what did we say?<br><small>large, often personal data</small></div>
</div>

<!--
Week 11 drew the first two. The prediction log carries the same request ID, so its row joins the access log line of the same request. When the true outcome arrives later, the same ID joins the label to the prediction.
-->


---

# The prediction log

<carbon-document class="icon-corner" />

<div class="middle">

One row per prediction:

```json
{"request_id": "a41f…", "time": "2026-11-23T09:14:02Z", "model_version": "3",
 "inputs": {"age": 45, "glucose": 158, "bmi": 33.6, …},
 "score": 0.66, "prediction": 1}
```

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div v-click class="card"><ph-list-checks class="ic" /><b>What to keep</b>the inputs as the model saw them, the output, the model version, an ID to join the label later</div>
  <div v-click class="card"><ph-ruler class="ic" /><b>How much</b>a size or time limit, so the log cannot fill the disk</div>
  <div v-click class="card"><ph-eye-slash class="ic" /><b>Who may read it</b>access and retention decided before it is switched on</div>
</div>

<v-click>

> [!WARNING]
> A prediction log of people is personal data. Decide who may read it and how long it is kept before you switch it on.

</v-click>

</div>

<!--
Log the inputs after validation and preprocessing, as the model saw them; otherwise you compare something else. The lab keeps it off by default, bounded and out of Git, at about 330 bytes a row. Retention is a governance decision: Week 13.
-->

---

# Compare like with like

<carbon-filter class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.5rem; margin:0.3rem 0">
  <div class="node amber no-shrink" style="width:9rem"><b>Requests</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><b>Validation</b><br><small>rejects bad rows</small></div>
  <div class="arrow">→</div>
  <div class="node amber no-shrink" style="width:10rem"><b>Current window</b></div>
</div>
<div v-click="1" class="flow" style="gap:0.5rem; margin:0.3rem 0">
  <div class="node green no-shrink" style="width:9rem"><b>Training data</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><b>the same validation</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:10rem"><b>Reference</b></div>
</div>

<div style="margin-top:1.5rem" />

<v-click at="2">

> [!TIP]
> Apply every filter between the world and the prediction log to the reference window too.

</v-click>

</div>

<!--
Measured in the lab on known-good traffic: the skin_thickness drift statistic (PSI) is 2.645 when only production is filtered, and 0.065 when both windows are. This is training-serving skew inside the monitor: the two windows were made differently. The training data still has the impossible zeros; production never does. The same trap elsewhere: rows dropped for missing values, requests blocked by rate limits, a field that is empty on an old app version.
-->

---

# Fixed or sliding window?

<carbon-calendar class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-calendar-blank class="ic" /><b>Fixed window</b>one batch at a time, such as last week<span style="display:block">easy to report, but a change waits for the batch to end</span></div>
  <div class="card"><ph-arrows-left-right class="ic" /><b>Sliding window</b>the last N rows or the last 7 days, checked often<span style="display:block">sees a change sooner, but checks overlap</span></div>
</div>

<v-click at="1">

<div style="margin-top:1.2rem">

Hypothetical: how big should the current window be?

</div>

<div class="text-sm" style="max-width:34rem; margin:auto">
<table>
  <thead><tr><th>Model</th><th style="text-align:right">Traffic</th><th style="text-align:right">Current window</th></tr></thead>
  <tbody>
    <tr><td>card fraud</td><td style="text-align:right">a million payments a day</td><td style="text-align:right"><span v-click="2">an hour is plenty</span></td></tr>
    <tr><td>a clinic's risk model</td><td style="text-align:right">30 patients a day</td><td style="text-align:right"><span v-click="2">a few hundred rows take weeks</span></td></tr>
  </tbody>
</table>
</div>

</v-click>

<v-click at="3">

A smaller window sees a change sooner, but with more false alarms.

</v-click>

</div>

<!--
Choose the window by row count, not only by time: a drift statistic needs enough rows to be stable (Section 4 measures it). A low-traffic model cannot see drift fast, which is one more reason to watch proxy metrics (Section 5).
-->


---
layout: section
---

# 4 · Drift detection tools

<!--
About 15 minutes. The lab's Exercise 3. No formulas: students need to know that drift tests exist, what a tool does with two datasets, and how a threshold gets a reason. The details of each test stay in the tool's documentation.
-->

---
class: fn-inline
---

# Tool options

<carbon-tool-box class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><carbon-report class="ic" /><b>Evidently</b>drift reports as JSON and HTML; Apache-2.0</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-chart-evaluation class="ic" /><b>NannyML</b>estimates performance without labels; Apache-2.0</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-debug class="ic" /><b>Alibi Detect</b>drift and outlier detectors; Business Source Licence</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-data-base class="ic" /><b>whylogs</b>logs statistical profiles of data; Apache-2.0</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-code class="ic" /><b>SciPy</b>the tests themselves, such as <code>ks_2samp</code>: you write the rest</div>
</div>

<div class="text-sm opacity-70">

Evidently[^1][] · NannyML[^2][] · Alibi Detect[^3][] · whylogs[^4][] · SciPy[^5][]

</div>

<v-click>

**We use Evidently:** open source, plain Python. Two data frames in, a drift report out.

</v-click>

[^1]: https://github.com/evidentlyai/evidently
[^2]: https://github.com/NannyML/nannyml
[^3]: https://github.com/SeldonIO/alibi-detect (licence: Business Source License 1.1)
[^4]: https://github.com/whylabs/whylogs
[^5]: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html

<!--
Checked 3 Oct 2026. Alibi Detect's BSL is not an open-source licence; each version turns into Apache-2.0 four years after release. Cloud platforms also sell model monitors; they make the same choices for you.
-->

---

# Statistical tests for drift

<carbon-chart-histogram class="icon-corner" />

<div class="middle">

A test compares one feature in the reference and current windows. Some common ones:

<div class="text-sm" style="max-width:36rem; margin:auto">

| **Test** | **Asks** |
| --- | --- |
| Kolmogorov–Smirnov (K-S) | Could both samples come from the same distribution? |
| Population Stability Index (PSI) | How much did the share of rows in each bin change? |
| Wasserstein distance | How far did the values move? |
| Chi-squared | Did the share of each category change? |

</div>

<div>
<svg viewBox="0 0 420 130" style="width:24rem; height:7.4rem; margin:0.6rem auto 0; display:block">
  <g fill="#0284c7" fill-opacity="0.35">
    <rect x="30" y="101" width="32" height="9"/><rect x="66" y="83" width="32" height="27"/><rect x="102" y="56" width="32" height="54"/><rect x="138" y="38" width="32" height="72"/><rect x="174" y="56" width="32" height="54"/><rect x="210" y="83" width="32" height="27"/><rect x="246" y="101" width="32" height="9"/>
  </g>
  <g fill="none" stroke="#dc2626" stroke-width="2" stroke-dasharray="5 3">
    <rect x="102" y="101" width="32" height="9"/><rect x="138" y="83" width="32" height="27"/><rect x="174" y="56" width="32" height="54"/><rect x="210" y="38" width="32" height="72"/><rect x="246" y="56" width="32" height="54"/><rect x="282" y="83" width="32" height="27"/><rect x="318" y="101" width="32" height="9"/>
  </g>
  <line x1="20" y1="110" x2="400" y2="110" stroke="currentColor" stroke-opacity="0.4"/>
  <line x1="158" y1="24" x2="222" y2="24" stroke="currentColor" stroke-width="2" marker-start="url(#tip)" marker-end="url(#tip)"/>
  <defs><marker id="tip" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
  <text x="190" y="14" text-anchor="middle" style="font-size:12px" fill="currentColor">size of the change</text>
  <text x="120" y="126" text-anchor="middle" style="font-size:11px" fill="#0284c7">reference window</text>
  <text x="300" y="126" text-anchor="middle" style="font-size:11px" fill="#dc2626">current window</text>
</svg>
</div>

</div>

<!--
Each test turns the gap between two histograms into one number. K-S gives a p-value: how sure we are that the two differ, which also depends on the number of rows. PSI and Wasserstein give the size of the change. Chi-squared is for categorical features. Evidently chooses a test for each column from its type and the number of rows, and you can set your own.
-->

---
class: fn-inline
---

# Evidently quick start

<carbon-terminal class="icon-corner" />

```python
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

# march, july: two pandas DataFrames with the columns temp_c and rain_mm
schema = DataDefinition(numerical_columns=["temp_c", "rain_mm"])
reference = Dataset.from_pandas(march, data_definition=schema)
current = Dataset.from_pandas(july, data_definition=schema)

result = Report([DataDriftPreset()]).run(current, reference)
result.save_html("drift.html")
```

<v-click>

```text
DriftedColumnsCount(drift_share=0.5) {'count': 1.0, 'share': 0.5}
ValueDrift(column=temp_c,method=K-S p_value,threshold=0.05) 3.614219303891289e-134
ValueDrift(column=rain_mm,method=K-S p_value,threshold=0.05) 0.8483422371364409
```

</v-click>

<div class="text-sm opacity-70">

Adapted from the Evidently quickstart[^1][]

</div>

[^1]: Evidently docs, "Quickstart: ML". https://docs.evidentlyai.com/quickstart_ml

<!--
Real output with Evidently 0.7.21: march has temperatures around 8 °C, july around 21 °C, the rain is the same. Printed from `result.dict()["metrics"]`. One result per column: the test, its threshold and the value. `run` takes the current window first, then the reference: the opposite of how we say it.
-->

---

# Threshold

<carbon-rule class="icon-corner" />

<div class="middle">

- Every test has a threshold parameter: a value above which the tool says "drifted".
- Without previous incidents, set it based on known good traffic.

<div class="flow" style="margin:1.2rem 0">
  <div class="node green no-shrink" style="width:11rem"><b>Known-good windows</b><br><small>past weeks with no problem</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:11rem"><b>Normal range</b><br><small>of the statistic, per feature</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:11rem"><b>Threshold</b><br><small>above the normal range</small></div>
</div>

<v-click>

- If you have a known change, such as a past incident, check that it lands above the threshold.
- Document the threshold with the measurements/incidents that set it.

</v-click>

</div>

<!--
A threshold copied from a blog post has no reason behind it. Rules of thumb such as "PSI above 0.25 is a major shift" depend on how the tool bins the values, so they do not move between tools.
-->

---

# Where would you put the threshold?

<carbon-growth class="icon-corner" />

Glucose PSI over 12 random windows: <span style="color:#16a34a">**known-good traffic**</span> and <span style="color:#e11d48">**drifted traffic**</span>

<div class="ranges">
  <div class="rrow"><b>200 rows</b><div class="track">
    <div class="seg good" style="left:11.8%;width:52.6%"></div>
    <div class="seg bad" style="left:51.7%;width:40.9%"></div>
  </div></div>
  <div v-click="1" class="rrow"><b>2,000 rows</b><div class="track">
    <div class="seg good" style="left:18.2%;width:10.3%"></div>
    <div class="seg bad" style="left:56.3%;width:11.7%"></div>
  </div></div>
</div>
<div class="axis ranges" style="margin-top:-0.6rem"><div class="axis"><span>0</span><span>0.1</span><span>0.2</span><span>0.3</span><span>0.4</span><span>0.5</span></div></div>

<v-clicks at="2">

- At 200 rows: nowhere. The ranges overlap.
- More rows make the ranges narrow. The window size sets what the monitor can see.

</v-clicks>

<!--
Measured in the lab. 200 rows: known-good 0.059–0.322, drifted 0.258–0.463. 2,000 rows: 0.091–0.143 against 0.282–0.340. When the window cannot grow, ask for the drift to last: Week 11's `for:` clause.
-->

---

# What can mislead a drift check

<carbon-warning-alt class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-trend-up class="ic" /><b>More traffic, more alarms</b>a p-value test finds even a tiny change when the window is large</div>
  <div class="card"><ph-gear class="ic" /><b>Defaults that change</b>a tool may choose another test when the dataset grows</div>
  <div class="card"><ph-ruler class="ic" /><b>Numbers from different tools</b>the same statistic, computed another way, gives another value</div>
  <div class="card"><ph-question class="ic" /><b>Too few rows</b>the result is noise: it means "could not check", not "no drift"</div>
</div>

</div>

<!--
All measured in the lab. Same glucose change: the K-S p-value falls from 5e-3 at 100 rows to 6e-18 at 800, while PSI stays near 0.2. Evidently's preset uses K-S up to 1,000 reference rows and Wasserstein above, so growing the reference changes the test. Our PSI for glucose is 0.585, Evidently's 0.645: different bins. Also: a dataset-level "drift: no" is a vote, and 3 of 8 drifted features lose it.
-->

---

# A drift check in production

<carbon-policy class="icon-corner" />

<div class="middle">

<div style="display:grid; grid-template-columns:12rem 1.5rem 12rem 1.5rem 12rem; align-items:center; justify-content:center; gap:0.5rem 0.3rem; font-size:0.8rem; text-align:center; line-height:1.25">
  <div></div><div></div>
  <div style="border:2px solid #7c3aed; background:#ede9fe; color:#3b0764; border-radius:8px; padding:0.4rem"><ph-file-text /> <b>Drift policy</b>, a reviewed file<br><small>reference version · rows to query, minimum rows · test and threshold per feature · action per result</small></div>
  <div></div><div></div>
  <div></div><div></div><div style="font-size:1.2rem">↓</div><div></div><div></div>
  <div style="display:grid; gap:0.6rem">
    <div style="border:2px solid #16a34a; background:#dcfce7; color:#14532d; border-radius:8px; padding:0.4rem"><ph-database /> <b>Training data</b><br><small>pinned version → reference</small></div>
    <div style="border:2px solid #d97706; background:#fef3c7; color:#78350f; border-radius:8px; padding:0.4rem"><ph-notepad /> <b>Prediction log</b><br><small>last N rows → current window</small></div>
  </div>
  <div style="font-size:1.2rem">→</div>
  <div style="border:2px solid #7c3aed; background:#ede9fe; color:#3b0764; border-radius:8px; padding:0.6rem"><ph-clock /> <b>Drift job</b><br><small>scheduled, runs Evidently</small></div>
  <div style="font-size:1.2rem">→</div>
  <div style="display:grid; gap:0.6rem">
    <div style="border:2px solid #0284c7; background:#e0f2fe; color:#0c4a6e; border-radius:8px; padding:0.4rem"><ph-file-html /> <b>Report</b><br><small>for people to read</small></div>
    <div style="border:2px solid #0284c7; background:#e0f2fe; color:#0c4a6e; border-radius:8px; padding:0.4rem"><ph-list-checks /> <b>Result per feature</b><br><small>drift → ticket · no drift · too few rows → could not check</small></div>
  </div>
</div>

<div style="margin-top:1.5rem" />

<v-click>

> [!TIP]
> Write the reference, the window, and the test and threshold for every feature in a reviewed file, with the measurement that set each one.

</v-click>

</div>

<!--
The policy sits next to the model's other config but not in the file that versions the model: a stricter drift threshold must not count as a new model. Drift alone opens a ticket and never pages anyone (Section 6). In the lab the policy is `drift.yaml`.
-->

---
layout: section
---

# 5 · Drift and degradation

<!--
About 8 minutes. Drift is about the data; degradation is about the model's answers. Only the second one is the reason to act, and it needs labels.
-->

---

# What is degradation?

<carbon-chart-line-data class="icon-corner" />

<div class="middle">

- **Degradation:** the model's performance on the true outcomes falls below the level it had at release.
- It needs the true outcomes, so it is always measured late.

<div>
<svg viewBox="0 0 420 130" style="width:26rem; height:8rem; margin:0.8rem auto 0; display:block">
  <line x1="40" y1="110" x2="400" y2="110" stroke="currentColor" stroke-opacity="0.4"/>
  <line x1="40" y1="10" x2="40" y2="110" stroke="currentColor" stroke-opacity="0.4"/>
  <line x1="40" y1="55" x2="400" y2="55" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="6 4"/>
  <text x="398" y="49" text-anchor="end" style="font-size:11px" fill="#dc2626">agreed minimum</text>
  <polyline points="50,30 90,33 130,29 170,34 210,38 250,47 290,58 330,66 370,72" fill="none" stroke="#0284c7" stroke-width="3"/>
  <circle cx="290" cy="58" r="5" fill="#dc2626"/>
  <text x="290" y="82" text-anchor="middle" style="font-size:11px" fill="#dc2626">degraded</text>
  <text x="34" y="34" text-anchor="end" style="font-size:11px" fill="currentColor" opacity="0.7">F1</text>
  <text x="220" y="125" text-anchor="middle" style="font-size:11px" fill="currentColor" opacity="0.7">weeks in production →</text>
</svg>
</div>

<div v-click class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-envelope class="ic" /><b>Spam filter</b>more spam reaches the inbox after spammers change their wording</div>
  <div class="card"><ph-shopping-cart class="ic" /><b>Demand forecast</b>the forecast error grows after a competitor opens nearby</div>
</div>

</div>

<!--
The level at release is the test-set metric from the gate. The agreed minimum is a decision, like an SLO: how much worse may the model get before we act? Degradation can come from drift, from a bug in our own pipeline, or from a change nobody can see in the inputs (concept drift).
-->

---

# Degradation detection

<carbon-chart-evaluation class="icon-corner" />

<div class="middle">

<div class="flow" style="gap:0.4rem; margin:0.5rem 0; align-items:center">
  <div class="node amber no-shrink" style="width:10rem"><ph-notepad class="ic" /><b>Prediction</b><br><small>+ model input<br>+ request id</small></div>
  <div style="width:12rem; text-align:center; font-size:0.8rem; color:#0284c7"><div style="border-top:3px dashed #0284c7; margin-bottom:0.3rem"></div><b>label delay</b><br>hours, days or months</div>
  <div class="node sky no-shrink" style="width:10rem"><ph-check-circle class="ic" /><b>True outcome</b><br><small>+ label<br>+ request id</small></div>
  <div class="arrow">→</div>
  <div class="node violet no-shrink" style="width:11rem"><ph-chart-line-down class="ic" /><b>Join and score</b><br><small>the metric, compared with the release level</small></div>
</div>
<div style="width:47rem; margin:0 auto 1.2rem; border-top:2px solid #94a3b8; text-align:right; font-size:0.75rem; opacity:0.75">time →</div>

<v-click>

- Same evaluation as before release, run again on production data.
- Until the labels arrive, fast signals such as the share of positive predictions only tell you to watch out.

</v-click>

</div>

<!--
The request id from the prediction log is what makes the join possible: log it with every prediction, and ask the team that records the outcome to keep it. Choose the metric carefully: F1 and precision also move when the share of positives changes, while ROC-AUC does not. When labels are expensive, label a sample on purpose: a periodic labelled study.
-->

---

# Drift, degradation, or both?

<carbon-flow class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:7rem 1fr 1fr; max-width:40rem; margin:auto; text-align:center; align-items:stretch">
  <div></div>
  <div><b>Degradation</b></div>
  <div><b>No degradation</b></div>
  <div style="align-self:center"><b>Drift</b></div>
  <div class="card"><ph-warning class="ic" style="color:#dc2626" /><b>Act now</b>the model no longer fits the data: roll back or retrain</div>
  <div class="card"><ph-coffee class="ic" /><b>Open a ticket</b>the common case: the inputs moved, the answers are still good</div>
  <div style="align-self:center"><b>No drift</b></div>
  <div class="card"><ph-eye-slash class="ic" style="color:#dc2626" /><b>Concept drift</b>an input monitor does not see it; only the labels do</div>
  <div class="card"><ph-check-circle class="ic" style="color:#16a34a" /><b>All good</b>keep checking</div>
</div>

</div>

<!--
Question to the room: which case can you find without labels? Only drift; whether it matters needs the true outcomes. A retrain on every drift signal spends a release, a gate run and a rollout on a model nobody needed, and the team stops trusting the monitor. That is why drift alone opens a ticket and never wakes anyone. Who acts on the ticket, and how fast, is Week 13.
-->

---
layout: section
---

# 6 · Wrap-up

<!--
About 6 minutes: takeaways, open questions, the lab, and the questions students can now answer.
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

- A healthy service can serve a model that is wrong.
- Drift detection needs the rows: keep a prediction log, and treat it as personal data.
- Compare with a pinned reference, filtered like the live data.
- Write the method, threshold and minimum window down, calibrated on known-good traffic.
- Only labels show that the model got worse, so a drift alert opens a ticket.

<!--
If time is short, ask which takeaway the room would drop for a model whose labels arrive within minutes, and why.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="middle">

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><carbon-alarm class="ic" /><b>What happens after the ticket?</b>Who decides, who may turn the model off, and how long we may keep the prediction log.<br><b>→ Week 13:</b> governance</div>
  <div class="card"><carbon-text-link-analysis class="ic" /><b>What drifts when the input is text?</b>Prompts and language models.<br><b>→ Week 14:</b> LLMOps</div>
</div>

</div>

<!--
Week 13 asks who the evidence of eleven weeks is for: dataset md5, gate verdict, validation report, SLO document, drift report. Alertmanager also arrives in Week 13: routing, grouping, silences, on-call.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="text-sm">

| # | Exercise | What you show |
| --- | --- | --- |
| 1 | The question the metric cannot answer | the prediction log on, and the rows of drifted traffic |
| 2 | Reference vs current | a pinned, filtered reference, and the Evidently report |
| 3 | The verdict is a policy | your calibration and your `drift.yaml` |
| 4 | Does the drift matter? | the model on labelled windows |

</div>

Exercises 3 and 4 have written answers. The drift alerts ship ready to run. The cluster stays down; the Compose stack stays up.

<!--
`evidently` is new and lives in a dependency group (+19 packages); the serving image does not install it. HW 3 is due this week.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

- Why can a model be wrong while every service metric is green?
- What are data drift, label shift and concept drift, and which need labels to detect?
- Why does drift monitoring need a prediction log, and what does that cost?
- How should a reference window be chosen, and why must it be pinned?
- How do you set a drift threshold, and what goes into a drift policy?
- What is the difference between drift and degradation, and which one needs labels?

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
