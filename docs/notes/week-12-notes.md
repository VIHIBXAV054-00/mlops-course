# Week 12 — Drift & Degradation — Study Notes

These notes accompany the Week 12 lecture and lab. Week 11 watched the **service**: is it up, is it
fast, does it return errors. This week the service is healthy, and the model can still be wrong.

## Why this matters

**Lazer, Kennedy, King & Vespignani, "The Parable of Google Flu: Traps in Big Data Analysis"**,
*Science* 343(6176), 14 March 2014.

Google Flu Trends (GFT) estimated flu activity from search queries. Its target was the number the US
CDC publishes from doctor visits: GFT "was built to predict CDC reports", and it was trained on past
CDC reports.

From August 2011 the estimates were too high in **100 of 108 weeks**. In February 2013 GFT predicted
**more than double** the share of doctor visits for flu-like illness that the CDC reported.

The service itself never failed. It was available, fast, and answered every query. What changed were
the inputs:

- Google changed its search engine many times, for business reasons.
- Search suggestions changed what people typed.
- The world changed: the 2009 pandemic did not follow the winter pattern GFT had learned.

The CDC report was the **ground truth**. It arrived every week, about two weeks late. The authors write
that GFT, compared and corrected with it, "could have largely healed itself". The lesson: always
compare the model's answers with the ground truth as soon as it arrives.

## Core concepts

### Drift is not an error

A data contract (Week 5) catches the **impossible**: a glucose of 0, a missing column, a wrong type.
Drift is the **merely different**: every value is valid, but the data no longer looks like the
training data. Nothing breaks and no exception is raised. In the lab, the drifted batch passes every
contract check while its mean glucose moves from 112 to 134.

### Types of drift

| **Type** | **What changes** | **Visible without labels?** |
| --- | --- | --- |
| Data drift (covariate shift) | the inputs, `P(X)`; the link `P(y\|X)` stays | yes: compare the inputs |
| Label shift (prior probability shift) | the share of each outcome, `P(y)`; `P(X\|y)` stays | only through proxies, such as the share of positive predictions |
| Concept drift | the link from inputs to outcome, `P(y\|X)` | no: only the labels show it |
| Schema drift and training-serving skew | the format or the meaning of the data, or how it is prepared | yes: a data contract and the same code path catch it |

Concept drift is the one that breaks a model most directly, and it is the one an input monitor cannot
see.

### When does the label arrive?

Label shift and concept drift show up only in the labels, so the label delay decides how fast you can
see them. Labels often come in steps: a streaming service sees a click at once, a finished film within
hours and a rating days later. Watch the fast, weak signals while you wait for the true outcome. For a
diabetes model, the true outcome can be a diagnosis years later.

### Reference and current window

To measure drift you need something to compare with.

- **Reference window:** a fixed dataset, usually the training data. It shows what the model expects.
  Pin it to a dataset version, so it cannot follow the live data.
- **Current window:** recent production data, from the prediction log. It shows what the model gets.

A drift check measures how far apart the two are, feature by feature. A reference that is "the last 30
days" moves with the live data and never reports drift.

### The prediction log

Service metrics (request rate, errors, latency, saturation) show how the service runs. They are
aggregates: you cannot ask them whether the glucose distribution moved. To see drift you need the
inputs and the predictions themselves, so the service writes one record per request: a request id, a
timestamp, the inputs as the model saw them, and the prediction.

The log holds personal data. Keep it off by default, bound its size, keep it out of Git, and decide
how long you may keep it (Week 13).

### Compare like with like

The current window contains only the requests that passed validation. If the reference still contains
rows that validation would reject, the two windows differ before the world changes anything. In the
lab, an unfiltered reference makes `skin_thickness`, a feature that did not move, the largest signal
in the report. Apply every filter between the world and the prediction log to the reference too.

### Fixed or sliding window?

- **Fixed window:** one batch at a time, such as last week. Easy to report, but a change waits for the
  batch to end.
- **Sliding window:** the last N rows or the last 7 days, checked often. Sees a change sooner, but
  the checks overlap.

Choose the size by row count, not only by time. A card-fraud model with a million payments a day has
enough rows in an hour; a clinic with 30 patients a day needs weeks for a few hundred rows. A smaller
window sees a change sooner, but with more false alarms.

### Statistical tests for drift

A test compares one feature in the reference and current windows and turns the difference into one
number.

| **Test** | **Asks** |
| --- | --- |
| Kolmogorov–Smirnov (K-S) | could both samples come from the same distribution? (a p-value) |
| Population Stability Index (PSI) | how much did the share of rows in each bin change? |
| Wasserstein distance | how far did the values move? |
| Chi-squared | did the share of each category change? (categorical features) |

A p-value says how sure we are that there is a difference, and it also depends on the number of rows.
PSI and Wasserstein measure the size of the change.

### Drift detection tools

Evidently, NannyML, Alibi Detect and whylogs implement these tests; SciPy has the tests alone. The
course uses **Evidently**: open source, plain Python, two data frames in, a drift report out.

```python
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

schema = DataDefinition(numerical_columns=["temp_c", "rain_mm"])
reference = Dataset.from_pandas(march, data_definition=schema)
current = Dataset.from_pandas(july, data_definition=schema)

result = Report([DataDriftPreset()]).run(current, reference)   # current first
result.save_html("drift.html")
```

The report has one result per column: the test, its threshold and the value.

### Setting a threshold

Every tool has a default threshold. It is a starting point, not a reason. To set your own:

1. Run the check on windows you know are fine, such as past weeks with no problem.
2. Note the normal range of the statistic for each feature.
3. Put the threshold above that range.
4. If you have a known change, such as a past incident, check that it lands above the threshold.
5. Write down the threshold with the measurement that set it.

The window size limits what you can see. In the lab, at 200 rows the glucose PSI of known-good and
drifted traffic overlap, so no threshold separates them; at 2,000 rows the ranges are far apart.

### What can mislead a drift check

- **More traffic, more alarms:** a p-value test finds even a tiny change when the window is large.
- **Defaults that change:** a tool may choose another test when the dataset grows. Evidently's preset
  switches from K-S to Wasserstein when the reference has more than 1,000 rows.
- **Numbers from different tools:** the same statistic, computed another way, gives another value.
  PSI depends on how the values are binned.
- **Too few rows:** the result is noise. It means "could not check", not "no drift".

### A drift check in production

A drift check is a **scheduled job**, not a server. It reads the pinned training data as the reference
and the last N rows of the prediction log as the current window, runs the tests, and writes a report
for people and a result for each feature.

A **drift policy** in a reviewed file sets the reference version, the window size and minimum rows,
the test and threshold for each feature, and the action for each result: drift opens a ticket, too few
rows means "could not check", and drift alone never wakes anyone at night.

### Degradation

**Degradation:** the model's performance on the true outcomes falls below the level it had at release.
It needs the true outcomes, so it is always measured late. Degradation can come from drift, from a bug
in your own pipeline, or from concept drift.

### Detecting degradation

Join the prediction log with the true outcomes by request id, compute the metric on each labelled
window, and compare it with the level at release. It is the same evaluation as before release, run
again on production data, and it is only as fresh as the labels.

Choose the metric with care. F1 and precision also move when the share of positives changes, so they
can report a change in the population as a change in the model. In the lab, F1 gets both cohorts
backwards, while ROC-AUC gets both right.

### Drift, degradation, or both?

| | **Degradation** | **No degradation** |
| --- | --- | --- |
| **Drift** | act now: roll back or retrain | open a ticket: the common case |
| **No drift** | concept drift: only the labels show it | all good: keep checking |

Without labels you can find only drift. Whether it matters needs the true outcomes. Retraining on every
drift signal spends a release on a model nobody needed, and the team stops trusting the monitor.

## Key terms

- **Data drift (covariate shift)**: `P(X)` changes. Visible from the inputs alone.
- **Label shift (prior probability shift)**: `P(y)` changes. Visible only through proxies without labels.
- **Concept drift**: `P(y|X)` changes. Not visible without labels.
- **Training-serving skew**: the serving path prepares the data differently from the training path.
- **Ground truth**: the true outcome, which often arrives late.
- **Reference window**: the pinned dataset every current window is compared with.
- **Current window**: recent rows of the prediction log.
- **Prediction log**: one record per scored request; also personal data.
- **PSI**: Population Stability Index, the change in the share of rows per bin.
- **K-S test**: a two-sample test; its p-value depends on the number of rows.
- **Calibration**: running the check on traffic you know is fine, to find the normal range.
- **Drift policy**: a reviewed file with the reference, the window, the tests, the thresholds and the actions.
- **Degradation**: performance on the true outcomes falls below the level at release.
- **Proxy metric**: a fast signal that needs no labels, such as the share of positive predictions.

## How this connects to the lab

The code ships finished, and you change settings and read the results. Exercise 1 turns on the
prediction log and checks what the request log and the prediction log keep for a valid and a
rejected request. Exercise 2 runs the same drift check with three bad references and the pinned one.
Exercise 3 looks at a p-value and a small window, then calibrates the threshold and `min_samples` in
`drift.yaml`. Exercise 4 scores the model on two labelled windows and chooses the degradation metric. The drift alerts and the
reaction policy ship ready to run, and Week 13 builds on them.

`metrics/metrics.json` stays byte-identical to Weeks 5–11 and the gate is still **GO — 13 passed, 0
failed, 4 skipped**: this week changes no modelling.

## Recommended reading

- **Lazer et al., "The Parable of Google Flu: Traps in Big Data Analysis"**, *Science*, 2014.
  https://www.science.org/doi/10.1126/science.1248506
- **Evidently: quickstart and metrics reference.**
  https://docs.evidentlyai.com/quickstart_ml · https://docs.evidentlyai.com/metrics/all_metrics
- **Zinkevich, "Rules of Machine Learning"**, on training-serving skew.
  https://developers.google.com/machine-learning/guides/rules-of-ml
- **SciPy: `ks_2samp`**, the K-S test and its assumptions.
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
- Huyen, *Designing Machine Learning Systems*, **Ch. 8**: the types of drift and why natural labels
  are rarer than people assume.

## Check yourself

1. A model has every service metric green, and its predictions are wrong. Name two types of drift that
   could cause this, and say which one an input monitor can see.
2. A teammate sets the reference window to "the last 30 days of the prediction log", so it stays fresh.
   What will the drift check report during a slow change, and what should the reference be?
3. Your drift rule uses a K-S p-value at 0.05. A marketing campaign doubles the traffic, with the same
   kind of users. What happens to the p-value, to the PSI of the same feature, and to the alert?
4. How would you set the threshold for one feature, and what do you do if known-good and drifted
   windows give overlapping values?
5. Your drift report shows that glucose moved, and the labels show no fall in ROC-AUC. Which case of
   drift and degradation is this, and what do you do?
6. Your model's labels arrive two years late. Which kind of change can you still detect in time, and
   which can you not?
