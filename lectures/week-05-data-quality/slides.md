---
theme: default
title: Week 5 — Data Quality
info: |
  Lecture for the course "Lifecycle of Artificial Intelligence Systems".
  Covers data contracts, types of data errors, validation with Pandera, a data
  quality gate as a DVC stage, and training-serving skew.
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

# Week 5: Data Quality

<carbon-data-check class="icon-corner" />

**Lifecycle of Artificial Intelligence Systems**

- What a data contract is, and which errors it can catch
- Building a contract from rules with Pandera
- How to add a data quality gate to the pipeline
- The same checks before training and before prediction <!-- TODO: rethink wording -->

<!--
Focus: last week we could name the data. Today we decide whether it may come in.
-->

---

# Last week: we issued an ID to the data

<img src="/data-id-club.jpeg" alt="A dataframe at a nightclub door, showing its ID card" style="height:300px; margin:0.5rem auto; display:block; border-radius:0.5rem" />

Last week we gave our data a name it can never lose.

<!--
Week 4 in one line. The three quiz questions after this slide carry the recap.
-->

---
layout: center
---

# **Quiz**
# What name was written on the data's ID?

<div v-click>

- The content hash

</div>

<!--
Not the file name: the DVC md5 in the `.dvc` file (`a8fd7b4f…` for our data). Rename the file and the ID stays; change one cell and the ID changes.
-->

---
layout: center
---

# **Quiz**
# The pointer is in Git, the data is in a storage.
# What else do we store the same way?

<div v-click>

- Software packages: a hash in a lockfile, the binary in an index (PyPI, CRAN)
- Docker images: a tag in `compose.yaml`, the image in a registry

</div>

<!--
Pointer in version control, content in a store built for it. A tag can be moved to another image; a digest (`image@sha256:…`) cannot, which makes it the closer match to a DVC hash.
-->

---
layout: center
---

# **Quiz**
# Why is a data ID useful?

<div v-click>

- We log it to MLflow at training time
- A run can now say which data it used
- We can always trace a model back to its data

</div>

<!--
Week 4 put the ID on every run as the MLflow tag `dvc_md5`, so `search_runs` finds every model trained on one version. The tag says which data, not whether it was right.
-->

---

# You know its name. Do you know it?

<carbon-warning-alt class="icon-corner" />

768 patients, ID `a8fd7b4f…`

| Column | Count of `0`[^1][] | |
| --- | --- | --- |
| `pregnancies` | 111 | <span v-click="1"><carbon-checkmark class="ic" style="color:#16a34a" /> possible</span> |
| `glucose` | 5 | <span v-click="2"><carbon-close class="ic" style="color:#dc2626" /> impossible</span> |
| `blood_pressure` | 35 | <span v-click="3"><carbon-close class="ic" style="color:#dc2626" /> impossible</span> |
| `skin_thickness` | 227 | <span v-click="4"><carbon-close class="ic" style="color:#dc2626" /> impossible</span> |
| `insulin` | 374 | <span v-click="5"><carbon-close class="ic" style="color:#dc2626" /> impossible</span> |
| `bmi` | 11 | <span v-click="6"><carbon-close class="ic" style="color:#dc2626" /> impossible</span> |

[^1]: Counted in our `datasets/diabetes.csv`. The five impossible counts match Wei, Tang and McNicholas, arXiv:1703.02177 (2017), Table 4. https://arxiv.org/abs/1703.02177

<!--
If you are alive, your glucose is not 0. Nor is your blood pressure.
The zeros are measurements nobody took, stored as 0: 376 of the 768 patients have at least one. The dataset's R documentation calls them "physical impossibilities".
-->

---
layout: section
---

# 1 · What happens with unchecked data?

<!--
About 10 minutes, one case. Option B (Target Canada, retail) is hidden after the Unity slides.
-->

---
layout: two-cols
---

# 2022: Unity's ad model

Unity makes a game engine. It also runs an ad network: games show adverts for other games.

- **Audience Pinpointer** is a model that picks the players likely to install the advertised game.
- It learns from data that Unity's customers send in[^1][].

::right::

<div style="margin-top:6rem">
<img src="/unity-ads.avif" alt="Unity Ads" style="width:100%; max-height:260px; object-fit:contain; border-radius:0.5rem" />
</div>

[^1]: Unity Software, Q1 2022 earnings call, 10 May 2022 (transcript: The Motley Fool). https://www.fool.com/earnings/call-transcripts/2022/05/11/unity-software-inc-u-q1-2022-earnings-call-transcr/

<!--
The earnings call is the only public source. Unity's SEC filing of the same day mentions only "challenges with monetization products".
-->

---
layout: fact
---

<div class="flex justify-center items-start gap-3 text-center">
  <div v-click style="width:22rem"><div class="text-5xl font-bold" style="color:#dc2626">−&#36;110 million</div><div>revenue in 2022, by Unity's estimate</div></div>
  <div v-click class="flex gap-3"><div class="text-5xl">→</div><div style="width:16rem"><div class="text-5xl font-bold" style="color:#dc2626">60%</div><div>of it in the next quarter</div></div></div>
</div>

<br>

Unity, Q1 2022 earnings call[^1][]

[^1]: Unity Software, Q1 2022 earnings call, 10 May 2022.

<!--
Compared with what Unity expected to earn in 2022 without the problem. Unity announced it in May 2022 and lowered its forecast; it is management's estimate, not an audited loss.
The CFO expected about 60% of it in Q2, 30% in Q3 and 10% in Q4; the CEO said there was "no carryover impact to 2023".
-->

---
layout: center
---

# What went wrong?

The CEO: Unity was "hit hard by two issues"[^1][].

<div class="cards" style="grid-template-columns:repeat(2,1fr); font-size:1.2rem; margin-top:1.5rem">
  <div v-click class="card" style="font-size:1.1rem"><ph-gear class="ic" /><b style="font-size:1.3rem">A platform fault</b>Pinpointer became less accurate</div>
  <div v-click class="card" style="font-size:1.1rem"><ph-database class="ic" style="color:#dc2626" /><b style="font-size:1.3rem">Bad data from a large customer</b>part of the training data lost its value</div>
</div>

[^1]: Unity Software, Q1 2022 earnings call, 10 May 2022.

<!--
The CEO said the data loss was "due in part" to this customer; a senior vice president added that "several incidents" hit the data set.
Unity never said what was wrong with the data. If asked, say so; do not guess.
-->

---

# How the bad data got in

<carbon-data-error class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div style="display:flex; flex-direction:column; gap:0.6rem">
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem"><span style="white-space:nowrap"><ph-game-controller /> Customer A</span><DataBatch cells="gggg gggg" /></div>
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem; border-color:#dc2626"><span style="white-space:nowrap"><ph-game-controller /> Customer B</span><DataBatch cells="rrgr rrgr rrgr" /></div>
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem"><span style="white-space:nowrap"><ph-game-controller /> Customer C</span><DataBatch cells="gggg gggg" /></div>
  </div>
  <div class="arrow-l fail">no check<span class="arrow">→</span></div>
  <div class="node" style="width:10rem"><ph-database class="ic" /><b>Training data</b><br><DataBatch cells="ggrggrg grgggrg rggrgrg ggrgggr" :cols="7" /></div>
  <div class="arrow">→</div>
  <div class="node" style="width:8rem"><ph-cube class="ic" /><b>Pinpointer</b><br><small>trained on all of it</small></div>
</div>

<!--
An illustration, not Unity's real data: the customers, the batch sizes and the share of bad rows are made up.
Customer B stands for the "large customer"; Unity never named it.
-->

---

# The fix: rebuild the data, then retrain

<carbon-renew class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div class="node" style="width:10rem"><ph-database class="ic" /><b>Training data</b><br><DataBatch cells="ggrggrg grgggrg rggrgrg ggrgggr" :cols="7" /></div>
  <div class="arrow-l">remove the bad rows<span class="arrow">→</span></div>
  <div v-click="1" class="node" style="width:10rem"><ph-database class="ic" /><b>Rebuilt data</b><br><DataBatch cells="gg.gg.g g.ggg.g .gg.g.g gg.ggg." :cols="7" /></div>
  <div v-click="2" class="arrow-l">retrain<span class="arrow">→</span></div>
  <div v-click="2" class="node" style="width:8rem"><ph-cube class="ic" /><b>Pinpointer</b><br><small>trained again</small></div>
</div>

<v-click at="3">

Three months later, the CEO: "We're measuring a lot of things we didn't use to measure"[^1][].

</v-click>

[^1]: Unity Software, Q2 2022 earnings call, 9 Aug 2022. https://www.fool.com/earnings/call-transcripts/2022/08/10/unity-software-inc-u-q2-2022-earnings-call-transcr/

<!--
First you have to find the bad rows: every batch already in the training set is checked again. Unity's own words: "The first is data rebuilding. The second is model training" (Q1 call).
The CEO in May: "we built more for growth and less for resiliency". In August: "We have fixed the data challenges."
-->

---

# What would have stopped it?

<carbon-security class="icon-corner" />

<div v-click="1" class="flow" style="margin-top:2rem">
  <div style="display:flex; flex-direction:column; gap:0.6rem">
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem"><span style="white-space:nowrap"><ph-game-controller /> Customer A</span><DataBatch cells="gggg gggg" /></div>
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem; border-color:#dc2626"><span style="white-space:nowrap"><ph-game-controller /> Customer B</span><DataBatch cells="rrgr rrgr rrgr" /></div>
    <div class="node" style="width:14rem; display:flex; align-items:center; justify-content:space-between; gap:0.6rem"><span style="white-space:nowrap"><ph-game-controller /> Customer C</span><DataBatch cells="gggg gggg" /></div>
  </div>
  <div class="arrow">→</div>
  <div class="node" style="width:9rem; border-color:#16a34a"><ph-shield-check class="ic" style="color:#16a34a" /><b>Check every batch</b></div>
  <div class="arrow">→</div>
  <div class="node" style="width:11rem"><ph-database class="ic" /><b>Training data</b><br><DataBatch cells="gggggggg gggggggg" :cols="8" /></div>
  <div class="arrow">→</div>
  <div class="node" style="width:7rem"><ph-cube class="ic" /><b>Pinpointer</b></div>
</div>

<v-click at="2">

> [!TIP]
> Check every batch from every source **before** it reaches training. Stop a batch that fails, and tell its producer.

</v-click>

<!--
This is the practice, not what Unity said it built: Unity named "monitoring, alerting and recovery systems".
Last week the data got an ID card. This is the bouncer who looks at more than the card.
-->

---
hide: true
---

# Option B · 2013: Target opens in Canada

<carbon-shopping-cart class="icon-corner" />

Target opened its first Canadian stores in 2013. By January 2015 it had 133.

- Every product needed its data in a new SAP system: size, units, price, supplier.
- About **75,000 products** were typed in by hand[^1][].

[^1]: Joe Castaldo, "The Last Days of Target", *Canadian Business*, 21 Jan 2016 (archived). https://web.archive.org/web/20170202013238/http://www.canadianbusiness.com/the-last-days-of-target-canada/

<!--
Option B for the cold open: use it instead of Unity (switch `hide` on the six Unity slides and on these three Target slides). Unity also appears in the notes of "Two summaries: what broke, and whom to call" and "This week's pipeline", and in the study notes' "Why this matters"; change them too.
Most of the typing was done by junior staff, on a tight schedule.
-->

---
hide: true
---

# Option B · How good was the data?

<carbon-data-error class="icon-corner" />

<v-clicks>

- Inches instead of centimetres, width and height swapped, the wrong currency, empty fields[^1][]
- The system could not warn anyone about data-entry errors.
- About **30%** of the item data was right. In the US: **98–99%**.

</v-clicks>

[^1]: Joe Castaldo, *Canadian Business*, 21 Jan 2016.

<!--
Option B, second slide. The 30% is an internal team's estimate, quoted by Castaldo, not an audit.
-->

---
hide: true
---

# Option B · The fix came too late

<carbon-time class="icon-corner" />

- Autumn 2012: a "data week", in which staff checked every field with the suppliers[^1][].
- January 2015: Target Canada asked for creditor protection. 133 stores, about 17,600 employees[^2][].

> [!TIP]
> Check data where it is entered: required fields, units and plausible ranges, before anyone uses it.

[^1]: Joe Castaldo, *Canadian Business*, 21 Jan 2016.
[^2]: Target Corporation, Form 8-K, Exhibit 99(A), 15 Jan 2015. https://www.sec.gov/Archives/edgar/data/27419/000002741915000005/exhibit99atargetcorporatio.htm

<!--
Option B, third slide. One buyer could have 1,500 products with 50–80 fields each, all checked by hand.
Target expected about $5.4 billion of pre-tax losses on the Canadian business (8-K).
-->

---

# Where we are: the data pipeline

<Lifecycle stage="development" width="70%" />

Today: check the data before it becomes features.

<!--
Why the whole loop: in design we explore the data and agree what is allowed; in build the checks go into the data pipeline; in test they run on every batch, before features are made.
So a data check is not one stage. It is part of the pipeline, from the first look at the data.
-->

---
layout: section
---

# 2 · What should the data look like?

<!--
No tool in this section; Pandera comes in Section 3.
-->

---
layout: center
---

# Who knows what good data looks like?

<div v-click>

- The **domain expert**: in our data, a doctor or a nurse

</div>

<!--
Week 1, "Who is around the loop": the domain expert owns what the data means and which errors cost.
A doctor knows at once that a glucose of 0 is impossible and that 0 pregnancies is normal. The ML team has to ask.
-->

---
layout: center
---

# Five patients in our data have a glucose of 0.
# Whose job was it to notice?

<v-clicks>

- Nobody's.
- Nobody can check every row of every batch.
- **A program can.**

</v-clicks>

<!--
So for four weeks, nobody did: the zeros have been in the data since Week 1, and every model we trained in Weeks 1–4 learnt from them.
-->

---

# Who builds the program?

<carbon-user-multiple class="icon-corner" />

<div class="flow" style="margin-top:2rem">
  <div v-click="1" class="node" style="width:14rem"><ph-stethoscope class="ic" /><b>Domain expert</b><br>writes the rules<br><small>glucose &gt; 0 · pregnancies may be 0</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node" style="width:14rem"><ph-code class="ic" /><b>Data engineer</b><br>turns them into checks<br><small>code in the data pipeline</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node" style="width:14rem; border-color:#16a34a"><ph-shield-check class="ic" style="color:#16a34a" /><b>Pipeline</b><br>runs the checks<br><small>on every batch, before training</small></div>
</div>

<div v-click="4" class="flow">
  <div class="node" style="width:46rem; border-style:dashed"><ph-user-gear /> <b>ML engineer or project lead</b>: makes sure every step is done, and that the pipeline keeps running</div>
</div>

<v-click at="5">

> [!TIP]
> Name the people behind each data source when the project starts: who owns its rules, its checks, and the pipeline that runs them.

</v-click>

<!--
Week 1's roles: the MLOps or platform team keeps the pipeline running. In a small team one person holds several roles, but the jobs stay different.
A rule with no owner is the first one deleted after a false alarm. The data scientist gains most: every training run starts from checked data.
-->

---

# A data contract

<carbon-certificate class="icon-corner" />

The rules, written down and agreed between the team that **produces** the data and the teams that **use** it.

<div class="flow" style="margin-bottom:0">
  <div class="node amber" style="width:12rem"><ph-flask class="ic" /><b>Producer</b><br><small>the clinic that measures patients</small></div>
  <div class="arrow">→</div>
  <div class="node" style="width:14rem"><ph-file-text class="ic" /><b>Contract</b><br><small>drawn up by the domain expert, implemented by the data engineer</small></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:12rem"><ph-cube class="ic" /><b>Consumer</b><br><small>the training pipeline, built by the data scientist</small></div>
</div>

<div v-click>
  <div class="split-stem"></div>
  <div class="split-bar" style="width:16.75rem"></div>
  <div class="flow" style="margin-top:0">
    <div class="node violet" style="width:16rem"><ph-users class="ic" /><b>For people</b><br><small>what each column means · types · allowed values · units · who to call</small></div>
    <div class="node green" style="width:16rem"><ph-code class="ic" /><b>For the pipeline</b><br><small>checks on every batch · a failure stops the batch and raises an alert</small></div>
  </div>
</div>

<v-click>

An open standard for writing one: the Open Data Contract Standard (ODCS)[^1][].

</v-click>

[^1]: Bitol (Linux Foundation AI & Data), Open Data Contract Standard. https://github.com/bitol-io/open-data-contract-standard

<!--
ODCS (checked 2 Oct 2026): Apache-2.0, about 1,160 GitHub stars, and a vendor page listing about 25 tools and service providers, among them IBM and Databricks. AWS, Microsoft and Google are not listed as vendors.
Andrew Jones, 2021: "This schema is a contract between us and our downstream users."
-->

---

# Lost in unit conversion

<carbon-rocket class="icon-corner" />

1999, Mars Climate Orbiter. Two teams shared a file of thruster data. A written specification set its unit: **newton-seconds**[^1][].

<div class="flow">
  <div class="node" style="width:13rem"><ph-desktop class="ic" /><b>Ground software</b><br>writes the file<br><small>in pound-force seconds</small></div>
  <div class="arrow-l fail">× 4.45 too small<span class="arrow">→</span></div>
  <div class="node" style="width:13rem"><ph-compass class="ic" /><b>Navigation team</b><br>reads the file<br><small>as newton-seconds</small></div>
  <div v-click class="arrow">→</div>
  <div v-click class="node" style="width:13rem"><ph-planet class="ic" style="color:#dc2626" /><b>23 Sept 1999</b><br>orbiter lost at Mars</div>
</div>

<v-click>

Each team worked with its own assumption. Nothing checked the file against the written one.

</v-click>

[^1]: NASA, Mars Climate Orbiter Mishap Investigation Board, Phase I Report, 10 Nov 1999. https://llis.nasa.gov/llis_lib/pdf/1009464main1_0641-mr.pdf

<!--
The specification was the contract: written, agreed, and never checked by a program. Both teams were American: JPL navigated, Lockheed Martin wrote the ground software. Two teams in one country were enough for a unit mismatch.
For four months the files had format errors, and odd values from April 1999 were "only informally reported".
The orbiter passed about 57 km above Mars instead of the planned 226 km.
-->

---
hide: true
---

# Option B · Lab values with no unit

<carbon-hospital class="icon-corner" />

2021: the US N3C database pooled COVID-19 patient records from **55** hospitals and health systems[^1][].

<div class="flow">
  <div class="node" style="width:14rem"><ph-files class="ic" /><b>1.6 billion</b><br>measurement values</div>
  <div class="arrow">→</div>
  <div v-click class="node" style="width:14rem"><ph-question class="ic" style="color:#dc2626" /><b>42%</b><br>arrived with no unit</div>
</div>

Body weight came in kg, g, oz and lb. One site's "pounds" looked like ounces.

[^1]: Bradwell et al., "Harmonizing units and values of quantitative data elements in a very large nationally pooled electronic health record (EHR) dataset", *JAMIA* 29(7), 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9196692/

<!--
Option B for this slot: use it instead of Mars Climate Orbiter (switch `hide` on both slides).
Our glucose is in mg/dL; much of Europe reports mmol/L. A contract that names the unit can check that the values fit it.
-->

---
layout: center
---

# Which data errors have you met?

<div class="cards" style="grid-template-columns:repeat(5,1fr)">
  <div v-click class="card"><ph-table class="ic" /><b>Schema</b>wrong type, missing or extra column<br><code>glucose = "unknown"</code></div>
  <div v-click class="card"><ph-ruler class="ic" /><b>Values</b>out of range, wrong sign, unknown label, wrong unit<br><code>age = 250</code></div>
  <div v-click class="card"><ph-selection class="ic" /><b>Completeness</b>empty cells, missing rows<br><code>blood_pressure = ␣</code></div>
  <div v-click class="card"><ph-copy class="ic" /><b>Uniqueness</b>the same row, or the same key, twice</div>
  <div v-click class="card" style="opacity:0.35"><ph-chart-bar class="ic" /><b>Distribution</b>this month does not look like last month<br><br><b>→ Week 12</b></div>
</div>

<!--
The first four can be checked on one file, with no history. Distribution needs a reference batch to compare with: that is drift, in Week 12.
-->

---

# Quiz · Which type of error?

<carbon-help class="icon-corner" />

The lab's broken batch has four faults. Sort them.

<div class="text-sm">

| Fault | Type |
| --- | --- |
| an extra column, `notes` | <span v-click="1">schema</span> |
| `glucose = "unknown"` | <span v-click="2">schema</span> |
| `age = 250` | <span v-click="3">values</span> |
| one `bmi` value multiplied by 10 | <span v-click="4">values: a unit change</span> |

</div>

<!--
Covers the same ground as "Which data errors have you met?": with little time, use only one of the two.
`glucose = "unknown"` counts as a schema error because the text cannot be converted to a number at all.
-->

---

# Missing values in disguise

<carbon-view-off class="icon-corner" />

Some systems write a **number** where a value is missing.

<div class="cards" style="grid-template-columns:repeat(3,1fr)">
  <div class="card"><ph-heartbeat class="ic" /><b>Our data</b><code>glucose = 0</code><br>5 patients</div>
  <div class="card"><ph-cloud-rain class="ic" /><b>Weather records</b><code>-9999</code><br>NOAA's daily data</div>
  <div class="card"><ph-google-logo class="ic" /><b>A Google pipeline</b><code>-1</code><br>a failing server's default</div>
</div>

> [!NOTE]
> **Sentinel value:** a special value that stands for "missing" or "unknown".

NOAA GHCN-Daily[^1][] · Breck et al.[^2][]

[^1]: NOAA NCEI, GHCN-Daily readme, Section III ("missing = -9999"). https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt
[^2]: Breck et al., "Data Validation for Machine Learning", SysML 2019, p. 7: a spike in "-1" revealed a server returning a default value. https://mlsys.org/Conferences/2019/doc/2019/167.pdf

<!--
Other common sentinels: 99, 1900-01-01, "N/A", an empty string.
Only the domain expert can say which zeros are real: 0 pregnancies is a value, 0 glucose is a sentinel. For every column, find out which sentinels it uses.
-->

---

# 600 million IP addresses on one farm

<carbon-location class="icon-corner" />

IP geolocation: a database maps an IP address to a place. Police, fraud teams and websites use it.

<div class="flow">
  <div class="node" style="width:13rem"><ph-globe class="ic" /><b>An IP address</b><br><small>known only to be "in the US"</small></div>
  <div class="arrow-l">default<span class="arrow">→</span></div>
  <div class="node mono" style="width:11rem"><ph-map-pin class="ic" />38.0000, -97.0000</div>
  <div class="arrow">→</div>
  <div class="node" style="width:13rem"><ph-house class="ic" style="color:#dc2626" /><b>A farmhouse</b><br><small>near Potwin, Kansas</small></div>
</div>

- More than **600 million** IP addresses pointed at one house. MaxMind chose the default in 2002[^1][].
- For years, police and angry strangers came to the door. The family sued in 2016[^2][].

[^1]: Kashmir Hill, "How an internet mapping glitch turned a random Kansas farm into a digital hell", Fusion, 10 Apr 2016. https://www.jezebel.com/how-an-internet-mapping-glitch-turned-a-random-kansas-f-1793856052
[^2]: The Register, 10 Aug 2016. https://www.theregister.com/2016/08/10/maxmind_lawsuit/

<!--
No range check: 38.0000, -97.0000 is a valid coordinate. What works: store "unknown" as missing, and watch how often the most common value appears.
MaxMind later moved its default points into bodies of water, which are still valid coordinates.
-->

---
hide: true
---

# Option B · 1,380 crimes at one address

<carbon-location class="icon-corner" />

The Los Angeles police crime map could not place some addresses. It put them on a default point near City Hall[^1][].

<div class="flow">
  <div class="node" style="width:13rem"><ph-map-trifold class="ic" /><b>An address</b><br><small>the map cannot place</small></div>
  <div class="arrow-l">default<span class="arrow">→</span></div>
  <div class="node" style="width:13rem"><ph-map-pin class="ic" style="color:#dc2626" /><b>One point</b><br><small>1,380 crimes in six months</small></div>
</div>

- That was about **4%** of all mapped crimes. The police learnt it from a newspaper reporter.

[^1]: Caitlin Dempsey, "Crime Mapping and the Los Angeles Police", Geography Realm (updated 2024), reporting the *Los Angeles Times*. https://www.geographyrealm.com/crime-mapping-and-the-los-angeles-police/

<!--
Option B for this slot: use it instead of the MaxMind farm (switch `hide` on both slides).
A default location passes every range check. The contractor's fix moved the default to 0,0 ("Null Island"), which is still a valid coordinate.
-->

---
layout: section
---

# 3 · Tools to implement the contract

<!--
These tools turn the written contract into a program that checks every batch. The code examples use weather readings, not our patients: the lab writes the diabetes schema, so the lecture does not give it away.
-->

---
hide: true
---

# Where should the contract run?

<carbon-location-current class="icon-corner" />

| Where | Runs every time? | Stops the pipeline? | Leaves a record? |
| --- | --- | --- | --- |
| in a notebook, by hand | <span v-click="1">no</span> | <span v-click="1">no</span> | <span v-click="1">no</span> |
| an `assert` in `prepare` | <span v-click="2">yes</span> | <span v-click="2">yes</span> | <span v-click="2">no</span> |
| a check inside the function that uses the data | <span v-click="3">when the function is called</span> | <span v-click="3">yes</span> | <span v-click="3">no</span> |
| **its own pipeline stage** | <span v-click="4">yes</span> | <span v-click="4">yes</span> | <span v-click="4">**yes: a report file**</span> |

<!--
Hidden by the instructor (2026-10-02): in Section 5 it came too late. If used, it belongs here, before the tools.
An `assert` stops the run but says nothing about which rows failed, and nobody sees it in `dvc dag`. Only the stage leaves a file that can be committed, sent to the producer and logged with the run.
-->

---
class: fn-inline
---

# Tool options

<carbon-tool-box class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(4,1fr)">
  <div :class="$clicks >= 1 ? 'card picked' : 'card'"><div class="logo" style="background-image:url(/pandera.webp)"></div><b>Pandera</b>a Python class, checked on a dataframe</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/gx-logo.jpeg)"></div><b>Great Expectations</b>Expectation Suites, Checkpoints, Data Docs</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/soda-core.png)"></div><b>Soda Core</b>YAML contracts, run on SQL warehouses</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/dbt.png)"></div><b>dbt data tests</b>YAML and SQL, inside the warehouse</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-test-tool class="ic" /><b>Deequ</b>"unit tests for data" on Spark</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><carbon-flow-data class="ic" /><b>TFDV</b>infers a schema, finds skew; part of TFX</div>
  <div :class="$clicks >= 1 ? 'card faded' : 'card'"><div class="logo" style="background-image:url(/pydantic.svg)"></div><b>pydantic</b>one record at a time: a request</div>
</div>

<div class="text-sm opacity-70">

Pandera[^1][] · GX[^2][] · Soda[^3][] · dbt[^4][] · Deequ[^5][] · TFDV[^6][] · pydantic[^7][]

</div>

<v-click>

**We use Pandera:** one package, the contract is Python code, and it runs inside a DVC stage.

</v-click>

[^1]: https://pandera.readthedocs.io/en/stable/
[^2]: https://docs.greatexpectations.io/docs/core/introduction/gx_overview/
[^3]: https://github.com/sodadata/soda-core
[^4]: https://docs.getdbt.com/docs/build/data-tests
[^5]: https://github.com/awslabs/deequ
[^6]: https://www.tensorflow.org/tfx/data_validation/get_started
[^7]: https://github.com/pydantic/pydantic

<!--
They differ in where the rules live (Python, YAML, SQL) and where they run (your process, a warehouse, Spark). pydantic comes back in Week 9, for the prediction API.
Soda Core moved from Apache 2.0 to the Elastic License 2.0 in January 2026; ELv2 is not an open-source licence.
-->

---

# Pandera or Great Expectations?

<carbon-compare class="icon-corner" />

<div class="text-sm">

| | **Pandera**[^1][] | **Great Expectations** (GX Core)[^2][] |
| --- | --- | --- |
| The contract is | a Python class you import | an Expectation Suite, stored in a project |
| It runs | in your process, on a dataframe | through a Data Context and a Checkpoint |
| Good at | dataframes: pandas, Polars, PySpark… | SQL databases, files and dataframes |
| Results | an exception with a table of failures | results, and **Data Docs**: a web report for people who do not read code |
| Set-up | one package | a project folder, configuration and stores |
| Choose it when | the engineers who own the code own the contract | many teams, also non-programmers, read the results |

</div>

[^1]: Pandera docs. https://pandera.readthedocs.io/en/stable/
[^2]: GX Core docs, "GX Core overview". https://docs.greatexpectations.io/docs/core/introduction/gx_overview/

<!--
No deep dive: the table is for students to read later. The point is that Pandera fits the dataframes we work with, at our scale; GX earns its set-up cost on a data platform with many producers and an audit trail.
If students search for GX: many tutorials online use the old 0.x API. In May 2026, Fivetran announced that it will become the steward of GX Core.
-->

---

# Pandera quick start

<carbon-terminal class="icon-corner" />

```bash
uv add "pandera[pandas]"    # the [pandas] extra installs the pandas support
```

```python {1-2|4|6-9|11|all}
import pandas as pd
import pandera.pandas as pa

readings = pd.read_csv("readings.csv")   # one row per station and day

schema = pa.DataFrameSchema({
    "station": pa.Column(str),
    "temp_c": pa.Column(float, pa.Check.in_range(-90, 60)),
})

schema.validate(readings)   # returns the frame, or raises an error
```

<v-click at="5">

```text
SchemaError: Column 'temp_c' failed element-wise validator number 0:
in_range(-90, 60) failure cases: -9999.0
```

</v-click>

<div class="text-sm opacity-70">

Adapted from the Pandera Quick Start[^1][]

</div>

[^1]: Pandera docs, home page and Quick Start. https://pandera.readthedocs.io/en/stable/

<!--
The error is real output from the lab's Pandera version, for a file with one `temp_c = -9999` (NOAA's missing value from "Missing values in disguise").
Old blog posts write `import pandera as pa`: it still works, with a warning. The base `pandera` package does not install pandas; the `[pandas]` extra does.
-->

---

# The same schema as a class

<carbon-code class="icon-corner" />

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
<div>

An object: `DataFrameSchema`

```python
schema = pa.DataFrameSchema({
    "station": pa.Column(str),
    "temp_c": pa.Column(float,
        pa.Check.in_range(-90, 60)),
})

schema.validate(readings)
```

</div>
<div>

A class: `DataFrameModel`

```python
from pandera.typing.pandas import Series

class ReadingsSchema(pa.DataFrameModel):
    station: Series[str]
    temp_c: Series[float] = pa.Field(ge=-90, le=60)

ReadingsSchema.validate(readings)
```

</div>
</div>

<v-click>

The lab uses the class:

- it has a name you can import and use in a type hint
- a changed rule is a changed line in a code review, so you can track every change to the contract

</v-click>

<!--
`validate` works the same way on both: on the same file the class raises the same `SchemaError`, naming `greater_than_or_equal_to(-90)` instead of `in_range(-90, 60)`. `ReadingsSchema.to_schema()` turns the class into the object, which fits a schema that code builds at run time from a config file.
-->

---

# `Field`: rules for one column

<carbon-rule class="icon-corner" />

```python
class ReadingsSchema(pa.DataFrameModel):
    station: Series[str] = pa.Field(str_matches=r"^[A-Z0-9]{11}$")
    temp_c: Series[float] = pa.Field(ge=-90, le=60, nullable=True)
    rain_mm: Series[float] = pa.Field(ge=0, nullable=True)
```

<div class="text-sm">

| **Rule** | **Pandera code** |
| --- | --- |
| within bounds | `ge=`, `gt=`, `le=`, `lt=` |
| one of a set | `isin=[0, 1]` |
| a text pattern | `str_matches=r"…"` |
| may be missing | `nullable=True` (default `False`) |
| no repeats | `unique=True` |
| your own rule | a method with `@pa.check` |

</div>

<!--
Read the class line by line: a station ID is 11 capital letters or digits; a temperature is a float between -90 and 60, and may be missing; rain is a float, never negative, and may be missing.
NOAA's -9999 from "Missing values in disguise" fails `ge=-90` here, and `ge=0` for rain (checked with the lab's Pandera version).
-->

---

# `Config`: rules for the whole table

<carbon-table-split class="icon-corner" />

```python {all|5|6|7|8|10-12}
class ReadingsSchema(pa.DataFrameModel):
    date: Series[pa.DateTime]
    ...
    class Config:
        coerce = True                 # convert types first: "12.5" becomes 12.5
        strict = True                 # a column the schema does not name is an error
        ordered = True                # the columns must come in this order
        unique = ["station", "date"]  # no two rows with the same station and date

    @pa.dataframe_check               # a rule that needs several columns
    def min_not_above_max(cls, df) -> Series[bool]:
        return df["temp_min_c"] <= df["temp_max_c"]
```

<!--
`@pa.dataframe_check` marks the method as a check: Pandera calls it with the whole frame, and every row where it returns False fails. Measured with the lab's version: a row with min 7.0 and max 3.0 fails as `<Check min_not_above_max>`; two rows for station A on the same day fail `unique`.
Use `strict = True` for data from outside your team: an extra column means the producer changed the file. `strict` and `ordered` come back with training-serving skew.
-->

---

# Stop at the first error, or collect them all

<carbon-list-checked class="icon-corner" />

```python
ReadingsSchema.validate(readings)             # stops at the first problem
ReadingsSchema.validate(readings, lazy=True)  # checks every rule, then reports all failures
```

<v-click>

The lazy report is a table, `failure_cases`, with one row per failure[^1][]:

<div class="text-sm">

| `schema_context` | `column` | `check` | `failure_case` | `index` |
| --- | --- | --- | --- | --- |
| Column | `temp_c` | `greater_than_or_equal_to(-90)` | -9999.0 | 1 |

</div>

</v-click>

[^1]: Pandera docs, "Lazy Validation". https://pandera.readthedocs.io/en/stable/lazy_validation.html

<!--
A lazy report shows every problem at once, so a file is fixed in one pass, not one error per run.
For the lab: the first form raises `SchemaError`, the lazy one `SchemaErrors` (with an s), and a handler for the singular does not catch the plural. The hidden "Traps you will meet in the lab" slide lists it.
-->

---

# Reading a real report

<carbon-report class="icon-corner" />

```text {all|3,4,7,8}
    row  column             check                            failure_case
      —  RawMeasurements    column_in_schema                 notes
      3  glucose            coerce_dtype('float64')          unknown
      3  glucose            dtype('float64')                 unknown
     23  bmi                less_than_or_equal_to(100.0)     280.0
      7  age                less_than_or_equal_to(120)       250
      —  glucose            greater_than_or_equal_to(0)      TypeError…
      —  glucose            less_than_or_equal_to(400.0)     TypeError…
```

<v-click>

Fix type errors first: the checks after a failed conversion fail too.

</v-click>

<!--
Measured with the lab's solution (`make validate-broken`): 4 faults give 7 failures, and row 3's "unknown" alone gives four. Rows are 0-based pandas positions: row 3 is line 5 of the CSV file. Exercise 2 maps all 7 lines to the 4 faults.
-->

---
hide: true
---

# Two summaries: what broke, and whom to call

<carbon-user-multiple class="icon-corner" />

```text
by check : column_in_schema: 1, coerce_dtype('float64'): 1, dtype('float64'): 1, …
by column: glucose: 4, RawMeasurements: 1, bmi: 1, age: 1
```

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><ph-wrench class="ic" /><b>By check</b>which rule broke: how to fix the data</div>
  <div v-click class="card"><ph-phone class="ic" /><b>By column</b>where it broke: whom to call</div>
</div>

<!--
Hidden by the instructor (2026-10-02): the title does not work yet.
Several failures in one column usually mean one change on the producer's side. Unity's "bad data from a large customer" was a finding by source.
-->

---

# `@pa.check_types`: a contract on a function

<carbon-function class="icon-corner" />

```python
from pandera.typing.pandas import DataFrame

@pa.check_types
def daily_totals(df: DataFrame[ReadingsSchema]) -> DataFrame[DailyTotalsSchema]:
    ...
```

Pandera checks the input when the function is called, and the output when it returns.

<!--
Optional: hide it if time is short. Students will meet this form in other teams' code.
A decorator stops the stage it runs in, but leaves no report and no edge in `dvc dag`; a separate stage gives both ("The gate is one dependency edge").
-->

---
layout: section
---

# 4 · Two gates on the way to the model

<!--
Back to our diabetes data. A batch passes two gates: first it is accepted as a raw measurement, then it is admitted as model input. The lab builds both (Exercises 1, 3 and 5).
-->

---
layout: center
---

# The clinic sends a glucose of 0 in some batches.
# Should the ingestion contract reject it?

<v-clicks>

- Not at the door: every real batch has zeros.
- **Before the model.**

</v-clicks>

<!--
A gate that rejects every real file gets switched off within a week. The ingestion contract describes what the source really sends; the strict rules wait for the boundary where we can act on them.
-->

---

# Two contracts, at two boundaries

<carbon-flow class="icon-corner" />

<div class="flow" style="gap:0.4rem; margin-top:5rem; font-size:0.95rem">
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
`ModelInput` also fixes the column order (`ordered = True`); `RawMeasurements` leaves it free. "Why column order matters" shows the reason.
Both are Pandera classes in the lab's `schemas.py`.
-->

---

# Zero becomes missing

<carbon-data-check class="icon-corner" />

<div class="flow" style="margin-top:1.5rem">
  <div class="node rose" style="width:12rem"><b>Raw batch</b><br><span class="mono">glucose = 0</span><br><small>impossible</small></div>
  <div class="arrow-l">to_nullable<span class="arrow">→</span></div>
  <div v-click="1" class="node violet" style="width:12rem"><b>After <span class="mono">to_nullable</span></b><br><span class="mono">glucose = &lt;NA&gt;</span><br><small>missing: not measured</small></div>
  <div v-click="2" class="arrow-l">ModelInput<span class="arrow">→</span></div>
  <div v-click="2" class="node green" style="width:10rem"><b>passes</b><br><small>missing is allowed</small></div>
</div>

<v-click at="1">

`to_nullable` replaces 0 with `<NA>`, pandas' missing value, in the five columns where 0 is impossible. It fills nothing in.

</v-click>

<div v-click="3" class="text-sm">

| `ModelInput` rule | Means |
| --- | --- |
| `gt=0` | a value must be greater than 0, so a 0 fails |
| `nullable=True` | the value may be missing, so `<NA>` passes |

</div>

<v-click at="4">

On our 768 patients: **652** failures before `to_nullable`, **0** after.

</v-click>

<!--
`pregnancies` is not converted: its zeros are real. The values are still unknown; now the data says so.
The column needs a nullable type, `Float64` with a capital F: plain `float64` turns `<NA>` into `NaN`.
-->

---

# Fill the gaps inside the model

<carbon-model class="icon-corner" />

Four steps. In which order?

<div class="cards" style="grid-template-columns:repeat(4,1fr)">
  <div class="card"><b>StandardScaler</b>puts every feature on the same scale</div>
  <div class="card"><b>train / test split</b>keeps some patients for the test</div>
  <div class="card"><b>LogisticRegression</b>the classifier</div>
  <div class="card"><b>SimpleImputer</b>fills missing values with the median</div>
</div>

<div v-click="1" class="flow" style="margin-top:1.2rem">
  <div class="node amber no-shrink" style="width:10.5rem"><b>train / test split</b></div>
  <div class="arrow">→</div>
  <div class="node sky" style="display:flex; align-items:center; gap:0.5rem"><b>Pipeline</b>
    <div class="node violet no-shrink">SimpleImputer</div><span class="arrow">→</span>
    <div class="node no-shrink">StandardScaler</div><span class="arrow">→</span>
    <div class="node no-shrink">LogisticRegression</div>
  </div>
</div>

<v-clicks at="2">

- Split first: the medians and the scale are learnt from the training split only, so nothing from the test set leaks into training.
- The medians are saved with the model, and `predict` fills a missing value the same way at serving time.

</v-clicks>

<!--
If the imputer ran before the split, the test patients would help choose the medians, and the test score would look better than it is: data leakage. The medians on our training split: glucose 117, blood pressure 72, skin thickness 29, insulin 122, BMI 32.4.
The lab sets the strategy in `params.yaml` (`train.impute_strategy: median`).
-->

---
layout: section
---

# 5 · The data quality gate

<!--
The lab's Exercise 4 builds this stage. Until now the contract runs only when someone calls it.
-->

---

# The gate is one dependency edge

<carbon-flow-connection class="icon-corner" />

```yaml {all|2-7|11}
stages:
  validate:
    cmd: uv run python src/main.py validate
    deps: [data/measurements.csv, src/week_05_data_validation/schemas.py]
    outs:
      - reports/validation.json:
          cache: false              # the verdict is committed to Git
  prepare:
    deps:
      - data/measurements.csv
      - reports/validation.json     # prepare waits for a passing validate
```

<div class="flow">
  <div class="node green" style="width:9rem"><b>validate</b></div>
  <div class="arrow-l on">validation.json<span class="arrow">→</span></div>
  <div class="node" style="width:8rem"><b>prepare</b></div>
  <div class="arrow">→</div>
  <div class="node" style="width:8rem"><b>train</b></div>
  <div class="arrow">→</div>
  <div class="node" style="width:8rem"><b>evaluate</b></div>
</div>

`validate` exits with code 1 when the contract fails, so `dvc repro` runs **nothing after it**.

<!--
No orchestrator and no `if`: the gate is an edge in the graph, visible in `dvc dag`. The lab's stage lists more dependencies; the slide shows two.
-->

---

# Did it really stop?

<carbon-stop-sign class="icon-corner" />

One impossible `age = 250` planted in the tracked data, then `dvc repro`:

```text
Running stage 'validate':
  measurements.csv failed the RawMeasurements contract with 1 failure case(s).
ERROR: failed to reproduce 'validate': ... exited with 1
```

<v-clicks>

- `prepare`, `train` and `evaluate` do not run.
- `data/processed/train.csv` is unchanged: md5 `d9eba76c…` before and after.
- `reports/validation.json` records `"passed": false`, the row and the rule.

</v-clicks>

<!--
Measured in a copy of the lab solution. The order matters: write the report first, then stop. A gate that stops without a report leaves nobody able to fix the data. The lab has a test for this.
-->

---
layout: center
---

# **Quiz**
# A gate can stop the pipeline, or only warn.
# When is a warning the right choice?

<div v-click>

> [!TIP]
> Decide for each rule: warn, quarantine the batch (keep it aside until someone checks it), or stop. For a model that suggests a treatment, stop.

</div>

<!--
A warning is the right choice when someone reads every warning and acts on it, and a bad batch costs little. A `validate` that writes the report and exits with 0 on failure is a warning, not a gate: the model trains on the bad data. In the lab's Exercise 4, students run the same bad batch before and after they add the gate.
-->

---

# Record the verdict with the run

<carbon-tag class="icon-corner" />

<div class="flow">
  <div class="node sky" style="width:6rem"><span class="mono">@staging</span></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:5.5rem">version</div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:4.5rem">run</div>
  <div class="arrow">→</div>
  <div class="node amber" style="width:8rem"><span class="mono">dvc_md5</span><br><small>which data</small></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink text-sm text-left" style="width:19rem;border-width:3px"><span class="mono">data_validation: pass</span> <small>passed the contract</small><br><span class="mono">schema_version: 1.0.0</span> <small>which contract</small><br><span class="mono">n_failure_cases: 0</span> <small>how many failures</small></div>
</div>

Each training run carries these tags, and the validation report as an artifact.

<v-click>

A bound changes in March. Which rules did February's model pass?

</v-click>

<v-click>

`schema_version` says it: raise it whenever a rule changes.

</v-click>

<!--
`data_validation` is the training contract's verdict on the training split; a fourth tag, `ingestion_validation`, holds the gate's. `n_failure_cases` is 0 on any run that exists, because `train` stops before it logs; a non-zero value means someone trained anyway. `make trace` prints the whole chain.
-->

---

# The third row of Article 10

<carbon-policy class="icon-corner" />

Last week's table ended with **"not yet: data validation is Week 5"**. The EU AI Act, for high-risk AI systems[^1][]:

<div class="flow" style="margin:0.3rem 0">
  <div v-click class="node no-shrink text-left" style="width:22rem"><ph-scales class="ic" style="display:inline;font-size:1.3rem" /> 10(3): data "free of errors and complete", "to the best extent possible"</div>
  <div v-click class="arrow">→</div>
  <div v-click class="node green no-shrink text-left" style="width:22rem"><ph-list-checks class="ic" style="display:inline;font-size:1.3rem" /> two contracts, run by the <span class="mono">validate</span> stage</div>
</div>
<div class="flow" style="margin:0.3rem 0">
  <div v-click class="node no-shrink text-left" style="width:22rem"><ph-scales class="ic" style="display:inline;font-size:1.3rem" /> 10(2)(h): find "data gaps or shortcomings"</div>
  <div v-click class="arrow">→</div>
  <div v-click class="node green no-shrink text-left" style="width:22rem"><ph-file-text class="ic" style="display:inline;font-size:1.3rem" /> the validation report: which row, which rule</div>
</div>

[^1]: Regulation (EU) 2024/1689, Art. 10. https://artificialintelligenceact.eu/article/10/

<!--
Optional: hide it to shorten the section. With it, the Week 4 table has all three rows covered.
-->

---

# Avoid generating noise

<carbon-notification-off class="icon-corner" />

A 2022 study interviewed 18 ML engineers about running models in production[^1][]:

<v-clicks>

- Teams put an alert on every column, so the chance that at least one fired was high.
- One alert fired **1,000 times**. It was ignored **45%** of the time.
- The bounds were written by hand. They did not last once the people who knew them left.

</v-clicks>

<v-click>

> [!TIP]
> Write few rules, each with an owner and an action.

</v-click>

[^1]: Shankar, Garcia, Hellerstein and Parameswaran, "Operationalizing Machine Learning: An Interview Study", arXiv:2209.09125 (2022), Section 5.1.2. https://arxiv.org/abs/2209.09125

<!--
The counter-case of the week: validation has a cost. One engineer: "You typically ignore most alerts." A rule nobody acts on teaches the team to ignore all of them.
-->

---
hide: true
---

# Option B · A table six months out of date

<carbon-time class="icon-corner" />

Google Play: a table of features used by a model stopped updating. It was stale for **six months**[^1][].

- Refreshing the table raised the app install rate by **2%**.
- A stale table can have the right types and valid ranges.

<v-click>

> [!TIP]
> Record when the data was produced, and fail the run when it is too old.

</v-click>

[^1]: Google, "Rules of Machine Learning", Rule #10: Watch for silent failures (page updated 25 Aug 2025). https://developers.google.com/machine-learning/guides/rules-of-ml

<!--
Option B for the counter-case: use it instead of the interview study (switch `hide` on both slides). It is also Google Play with a 2% install-rate gain, like "Google Play: features that never arrived": they are two different problems.
The checks ran and passed; a schema check cannot see the data's age.
-->

---

# No contract is bulletproof

<carbon-warning-alt class="icon-corner" />

What passes every check?

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1rem">
  <div v-click class="card"><ph-tag class="ic" /><b>Wrong labels</b>on average, at least 3.3% of test labels in 10 popular benchmarks are wrong</div>
  <div v-click class="card"><ph-pencil-simple class="ic" /><b>Plausible wrong values</b>a BMI of 28.0 typed as 26.0</div>
  <div v-click class="card"><ph-arrows-left-right class="ic" /><b>Swapped columns</b>two features with similar ranges</div>
</div>

<v-click>

A passing run checks the **agreed shape**. Wrong labels and plausible wrong values still pass.

</v-click>

Northcutt et al.[^1][]

[^1]: Northcutt, Athalye and Mueller, "Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks", NeurIPS 2021 Datasets and Benchmarks. https://arxiv.org/abs/2103.14749

<!--
In ImageNet's validation set, at least 6% of the labels are wrong (same paper). People who know the data must check samples; Week 13's Model Cards record what the data cannot show.
-->

---
layout: section
---

# 6 · Training-serving skew

<!--
A new term for most students; the definition comes after the Google Play case. The lab's Exercise 6, the only exercise that needs the Docker stack.
-->

---

# Google Play: features that never arrived

<carbon-application-mobile class="icon-corner" />

App store recommendations: a model ranks apps for each user.

- Some features were **always present** in the training data and **always missing** at serving time[^1][].
- Nothing crashed. The model predicted with less information than it had learnt from.

How would you notice?

<v-click>

Google's data validation system compared the training data with the logged serving data. Removing the skew raised the app install rate by **2%**.

</v-click>

[^1]: Breck, Polyzotis, Roy, Whang and Zinkevich, "Data Validation for Machine Learning", SysML 2019, Section 6.2. https://mlsys.org/Conferences/2019/doc/2019/167.pdf

<!--
Offline metrics were fine, because the training data was fine; only the serving path was wrong. The paper's authors are from Google; the system checked data for more than 700 pipelines.
-->

---
hide: true
---

# Option B · Video recommendations: features lost on the way

<carbon-video class="icon-corner" />

Video recommendations at Google:

- A backend stored some features in a different format.
- The code that read the data dropped them, without an error[^1][].
- The validation system found it. The fix took **two days**; similar problems had taken months.

[^1]: Breck et al., "Data Validation for Machine Learning", SysML 2019, Section 6.2.

<!--
Option B for this slot: use it instead of Google Play (switch `hide` on both slides).
The lesson is the same: compare what the model receives at serving time with what it learnt from, and log the serving features.
-->

---
class: fn-inline
---

# Training-serving skew

<carbon-arrows-horizontal class="icon-corner" />

**Training-serving skew:** the model gets different input when it serves than when it was trained.

<div class="flow" style="margin:0.25rem 0">
  <div class="node amber no-shrink" style="width:10.5rem"><ph-files /> training data</div>
  <div class="arrow-l">code path A<span class="arrow">→</span></div>
  <div class="node green" style="width:10rem"><b>features</b> <small>every field filled</small><DataBatch cells="gggg gggg" /></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:7rem"><span class="mono">fit</span></div>
</div>
<div v-click="1" class="flow" style="margin:0.25rem 0">
  <div class="node amber no-shrink" style="width:10.5rem"><ph-globe /> a request</div>
  <div class="arrow-l fail">code path B<span class="arrow">→</span></div>
  <div class="node rose" style="width:10rem"><b>features</b> <small>some fields empty</small><DataBatch cells="g.g." /></div>
  <div class="arrow">→</div>
  <div class="node sky" style="width:7rem"><span class="mono">predict</span></div>
</div>

<v-click at="2">

The most common cause: "different code paths" for training and serving data[^1][].

</v-click>

<v-click at="3">

> [!TIP]
> Google's rule: "Re-use code between your training pipeline and your serving pipeline whenever possible"[^2][].

</v-click>

[^1]: Breck et al., SysML 2019, Section 4.
[^2]: Google, Rules of ML, #32. https://developers.google.com/machine-learning/guides/rules-of-ml

<!--
Two code paths drift apart; one shared path cannot. Uber's Michelangelo platform (2017) applies "the same expressions" at training and at prediction time for the same reason.
-->

---

# Imputing outside the model

<carbon-chart-evaluation class="icon-corner" />

One example patient from the lab. The model was trained on data filled with medians in `prepare`.

| The request | Probability of diabetes |
| --- | --- |
| glucose unknown, filled with the training median (117) | 0.4236 |
| glucose sent as **0**, as the source system does | <span v-click="1">**0.0068**</span> |
| insulin sent as an empty value | <span v-click="2">crash: `ValueError: Input X contains NaN`</span> |

<v-click at="3">

> [!TIP]
> Put every transformation the model needs inside the model's `Pipeline`.

</v-click>

<!--
Training saw no zeros and no gaps; serving sends both. The crash is the lucky case: the zero gets a confident, wrong answer.
Measured with the lab's training split, StandardScaler and LogisticRegression.
-->

---

# One contract at both boundaries

<carbon-security class="icon-corner" />

<div class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:8rem"><ph-globe class="ic" /><b>Request</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:12rem"><ph-shield-check class="ic" /><b>PredictionInput</b><br><small>inherits <span class="mono">ModelInput</span>, without the label</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:8rem"><ph-cube class="ic" /><b>predict</b><br><small>the same model</small></div>
</div>

<div class="text-sm">

| The request | Without a contract | With `PredictionInput` |
| --- | --- | --- |
| a legal patient | 0.7173 | 0.7173 |
| glucose and insulin sent as 0 | <span v-click="1">0.0092</span> | <span v-click="2">rejected: `greater_than(0)`</span> |
| insulin and bmi swapped | <span v-click="1">1.0000</span> | <span v-click="2">rejected: `less_than_or_equal_to(100.0)`</span> |
| no `insulin` field in the request | <span v-click="1">an error from scikit-learn</span> | <span v-click="2">rejected: `column_in_dataframe`</span> |

</div>

<!--
Measured with the lab's solution model (median imputer inside the Pipeline). Without the contract, two bad requests get confident numbers.
Two schemas written by hand drift apart; a class that inherits the training contract cannot.
-->

---

# Why column order matters

<carbon-list-numbered class="icon-corner" />

The model expects the columns in one order. The same patient, sent with the columns reversed:

<div class="text-sm">

| | pregnancies | glucose | blood pressure | skin | insulin | BMI | pedigree | age |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **the model expects** | 6 | 148 | 72 | 35 | 155 | 33.6 | 0.627 | 50 |
| <span v-click="1">**reversed, as an array**</span> | <span v-click="1">50</span> | <span v-click="1">0.627</span> | <span v-click="1">33.6</span> | <span v-click="1">155</span> | <span v-click="1">35</span> | <span v-click="1">72</span> | <span v-click="1">148</span> | <span v-click="1">6</span> |

</div>

<v-clicks at="2">

- An array has no column names. The model reads 50 as the number of pregnancies and 0.627 as the glucose: probability of diabetes **1.0000**.
- A DataFrame keeps the names. scikit-learn compares them and refuses: "The feature names should match…".
- `ModelInput` sets `ordered = True`, so a file with its columns in another order fails before it reaches the model.

</v-clicks>

<!--
Optional: hide it if time is short. In the right order, the same patient gets 0.7173. The DataFrame check is a safety net that disappears the moment someone calls `.to_numpy()`.
A JSON request has no column order: the lab's code puts the columns in order, so `PredictionInput` does not check it.
-->

---
layout: section
---

# 7 · Red flags and good practices

<!--
Each of these happens at work with any tool, not only Pandera. The lab-specific traps are on a hidden slide; show them at the start of the lab session.
-->

---
hide: true
---

# Traps you will meet in the lab

<carbon-debug class="icon-corner" />

<div class="text-sm">

| Trap | What you see | What is wrong |
| --- | --- | --- |
| `pandera` without `[pandas]` | an import error about pandas | install `pandera[pandas]` |
| `except SchemaError` after `lazy=True` | the handler never runs | catch `SchemaErrors` |
| `float64` for a sentinel column | `<NA>` becomes `NaN` | use `Float64` |
| `Model.to_schema().strict = False` | another test sees fewer failures | `to_schema()` returns one shared object; copy it first |
| an optional column | `pa.Field(required=False)` fails in the lab's Pandera | write `Optional[Series[int]]` |

</div>

<!--
Hidden: lab-specific. Show it at the start of the lab session instead.
Newer Pandera releases add `Field(required=...)`; the lab's locked version does not have it.
-->

---

# Write down why each rule exists

<carbon-user-certification class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(3,1fr); margin-top:1.5rem">
  <div class="card"><code>age ≤ 120</code><br>a guess, or a clinical rule?</div>
  <div class="card"><code>bmi ≤ 100</code><br>who decided, and why 100?</div>
  <div class="card"><code>pregnancies = 0</code><br>real, while <code>glucose = 0</code> is not</div>
</div>

Which of the lab's rules would you ask a doctor about?

<v-click>

> [!TIP]
> Next to each rule, write its source and its owner: in the schema's docstring, or in the contract file.

</v-click>

<!--
An engineer can guess a bound; a clinician knows it. A bound nobody can explain is removed at the first false alarm, and with it the protection.
-->

---

# Check computed features too

<carbon-calculator class="icon-corner" />

2022: a code change at Equifax made some model attributes use a **fixed date** instead of today's date[^1][].

<div class="flow">
  <div class="node green" style="width:12rem"><ph-database class="ic" /><b>Credit data</b><br><small>correct</small></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:14rem"><ph-calculator class="ic" style="color:#dc2626" /><b>Computed attributes</b><br><small>based on a date: wrong</small></div>
  <div class="arrow">→</div>
  <div class="node" style="width:14rem"><ph-gauge class="ic" /><b>Credit scores</b><br><small>17 March – 6 April 2022</small></div>
</div>

- Fewer than **300,000** consumers had their score shift by **25 points or more**[^2][].
- Every value was a valid number.

> [!TIP]
> Check computed features as well as raw data. For example, an age counted from today must grow every day.

[^1]: New York Attorney General, Assurance of Discontinuance with Equifax Information Services (2025). https://ag.ny.gov/sites/default/files/settlements-agreements/equifax_information_services_assurance_of_discontinuance_2025.pdf
[^2]: Equifax, "Equifax Statement on Recent Coding Issue", 2 Aug 2022. https://www.equifax.com/newsroom/all-news/-/story/equifax-statement-on-recent-coding-issue/

<!--
Main case for this slot. The hidden gene-name slide is the alternative.
The raw data passed any contract; the error was in a feature computed from it. The fix was complete on 8 April 2022; the settlement with New York was $725,000.
-->

---
hide: true
---

# Option B · Gene names that became dates

<carbon-calculator class="icon-corner" />

Scientists share lists of genes as supplementary Excel files with their papers.

<div class="flow">
  <div class="node" style="width:12rem"><ph-dna class="ic" /><b>Gene name</b><br><span class="mono">SEPT2</span></div>
  <div class="arrow-l">Excel's default<span class="arrow">→</span></div>
  <div class="node rose" style="width:12rem"><ph-calendar class="ic" style="color:#dc2626" /><b>A date</b><br><span class="mono">2-Sep</span></div>
</div>

- A study screened 3,597 papers with gene lists from 18 journals, 2005–2015[^1][].
- **19.6%** of them had gene names converted to dates or numbers.

> [!TIP]
> Check values after every automatic conversion, not only the raw file. Declare the type of each column, so a tool cannot guess it.

[^1]: Ziemann, Eren and El-Osta, "Gene name errors are widespread in the scientific literature", *Genome Biology* 17, 177 (2016). https://pmc.ncbi.nlm.nih.gov/articles/PMC4994289/

<!--
Option B for this slot: use it instead of Equifax (switch `hide` on both slides).
A conversion step, not the source, made the data wrong; every converted value was a valid date. A gene column must contain gene names.
-->

---

# Fix the producer, not your copy

<carbon-edit-off class="icon-corner" />

You find the bad rows and fix them by hand in your CSV file.

<div class="flow" style="margin-top:5rem">
  <div class="node amber" style="width:12rem"><ph-flask class="ic" /><b>Producer</b><br><small>still sends the error</small></div>
  <div class="arrow">→</div>
  <div class="node rose" style="width:12rem"><ph-pencil-simple class="ic" style="color:#dc2626" /><b>Your copy</b><br><small>edited by hand</small></div>
  <div class="arrow">→</div>
  <div v-click class="node" style="width:12rem"><ph-cube class="ic" /><b>Next batch</b><br><small>the same error again</small></div>
</div>

<!--
What to do instead: send the validation report to the producer, and put any repair in code, as a pipeline step, so it runs on every batch.
The hand fix is not in the pipeline, so nobody can repeat it, and the producer never learns that the export is wrong. It also breaks the Week 4 record: the data's hash changes, and nobody knows why.
-->

---

# Keep drift checks out of the contract

<carbon-chart-bar class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div class="card"><ph-list-checks class="ic" /><b>A contract</b>"What must every row be?"<br>one file, no history<br>the rules change only when we change them<br><br><b>→ this week</b></div>
  <div class="card" style="opacity:0.6"><ph-chart-line class="ic" /><b>A drift check</b>"Does this month look like last month?"<br>needs a reference dataset<br>changes with the world<br><br><b>→ Week 12</b></div>
</div>

> [!TIP]
> Put row rules in the contract. Compare distributions in a separate monitor.

<!--
Pandera can also test statistics, but in a gate such a test fails whenever the world changes. The gate stops the pipeline; a drift monitor alerts a person.
If asked: on 100 million values, a chi-square test with 0.01% of values changed fired a needless alert in 7 of 10 trials (Breck et al., SysML 2019, p. 7).
-->

---
layout: section
---

# 8 · Wrap-up

<!--
About 10 minutes: the whole pipeline, takeaways, open questions, the lab, next week, discussion, and the questions students can now answer.
-->

---

# This week's pipeline

<carbon-flow class="icon-corner" />

<div class="flow text-sm" style="gap:0.4rem; margin-top:3.5rem">
  <div class="node amber no-shrink" style="width:6.5rem"><ph-file-csv class="ic" /><b>Batch</b></div>
  <div class="arrow">→</div>
  <div v-click="1" class="node green no-shrink" style="width:9.5rem"><ph-shield-check class="ic" /><b>validate</b><br><small>RawMeasurements<br>report, or stop</small></div>
  <div v-click="2" class="arrow">→</div>
  <div v-click="2" class="node no-shrink" style="width:7.5rem"><ph-arrows-split class="ic" /><b>prepare</b><br><small>train / test split</small></div>
  <div v-click="3" class="arrow">→</div>
  <div v-click="3" class="node green no-shrink" style="width:8.5rem"><ph-shield-check class="ic" /><b>ModelInput</b><br><small>0 → missing, then checked</small></div>
  <div v-click="4" class="arrow">→</div>
  <div v-click="4" class="node sky no-shrink" style="width:9.5rem"><ph-cube class="ic" /><b>model</b><br><small>imputer inside<br>tags: verdict, version</small></div>
</div>

<div v-click="5" class="flow text-sm" style="gap:0.4rem">
  <div class="node amber no-shrink" style="width:6.5rem"><ph-globe class="ic" /><b>Request</b></div>
  <div class="arrow">→</div>
  <div class="node green no-shrink" style="width:9.5rem"><ph-shield-check class="ic" /><b>PredictionInput</b><br><small>the same contract</small></div>
  <div class="arrow">→</div>
  <div class="node sky no-shrink" style="width:9.5rem"><ph-cube class="ic" /><b>predict</b><br><small>the same model</small></div>
</div>

<!--
In the lab, `to_nullable` and `ModelInput` run at the start of the `train` stage, after `prepare` has split the data; `prepare` itself refuses to run without a passing report.
Back to Unity: the first two boxes are the check at the door from "What would have stopped it?".
-->

---

# Key takeaways

<carbon-list-checked class="icon-corner" />

<v-clicks>

- Check the data before it trains a model.
- Write the contract down, and implement it in code.
- Store unknown values as missing, and fill them inside the model.
- A gate stops the pipeline and leaves a report.
- The model's contract guards both training and serving.

</v-clicks>

<!--
If time is short, ask which takeaway the room would drop for data that comes from one in-house table, and why.
-->

---

# What this week does not solve

<carbon-face-dissatisfied class="icon-corner" />

<div class="cards" style="grid-template-columns:repeat(2,1fr)">
  <div v-click class="card"><carbon-scales class="ic" /><b>Is the model good enough to ship?</b>The data passed; the model can still be worse.<br><b>→ Week 6:</b> model quality gates</div>
  <div v-click class="card"><carbon-automatic class="ic" /><b>Who runs the checks?</b>Today, we run <code>dvc repro</code> by hand.<br><b>→ Week 7:</b> CI on every change</div>
  <div v-click class="card"><carbon-chart-line class="ic" /><b>Has the data changed?</b>A contract cannot compare months.<br><b>→ Week 12:</b> drift monitoring</div>
  <div v-click class="card"><carbon-document class="ic" /><b>Is the data true?</b>Wrong labels pass every rule.<br><b>→ Week 13:</b> Model Cards record what the data cannot show</div>
</div>

<!--
Week 6 brings acceptance criteria written before the run, a comparison with the production model, slices and a go/no-go decision. In the lab's Exercise 5, accuracy stays at 0.7656 while F1 and ROC AUC rise: one number is not enough, which is Week 6's starting point.
"Is the data true?" has no tool in this course: people who know the data must check samples. "Datasheets for Datasets" (Gebru et al.) is the written record for a dataset, as a Model Card is for a model.
-->

---

# This week's lab

<carbon-chemistry class="icon-corner" />

<div class="text-sm">

| # | Exercise | What you show |
| --- | --- | --- |
| 1 | Write the ingestion contract | `RawMeasurements` passes on our 768 patients |
| 2 | Read a validation report | each of the 7 failures traced to one of the 4 faults |
| 3 | Write the training contract | 652 failures before `to_nullable`, 0 after |
| 4 | The gate as a pipeline stage | `dvc repro` stops, and the processed data stays unchanged |
| 5 | Fix the model, not the data | the imputer inside the `Pipeline`, and the new metrics |
| 6 | Training-serving skew (optional) | one contract rejects three bad requests |

</div>

Exercises 1–5 need no Docker. Homework 1 is out this week.

<!--
Stop the Week 4 stack before the lab: both use the same ports. The stack is needed only in Exercise 6.
-->

---

# After this lecture, you can answer

<carbon-education class="icon-corner" />

- What is a data contract, and who should write its rules?
- Which data errors can a contract catch on one file, and which need a comparison?
- Why does our project need two contracts, and where does a zero become illegal?
- How does a validation stage stop a DVC pipeline, and what must it leave behind?
- What is training-serving skew, and why does the imputer belong inside the model?
- What can a passing validation run not tell you?

<!--
The notes' "Check yourself" has more questions on the same topics; the lab checks each one in practice.
-->
