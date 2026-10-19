# Week 6 — Model Quality Gates — Study Notes

These notes go with the Week 6 lecture and lab. In Week 5 we put a gate at the start of the pipeline: it decides whether a batch of data may come in. This week we put a second gate at the end: it decides whether a trained model may go out. Both gates check written rules and refuse when a rule fails. A dataset either meets its contract or it does not. A model is usually good on one number and worse on another. So the model gate needs more than one number, and a written decision about which one counts.

## Why this matters

**Gender Shades (2018).** Microsoft, IBM and Face++ sold gender classification as a cloud service: send a photo, get "male" or "female". Joy Buolamwini and Timnit Gebru built a balanced test set of 1,270 members of parliament from six countries and scored each product on it. IBM classified 87.9% of the 1,270 faces correctly, but got 34.7% of darker-skinned women wrong and 0.3% of lighter-skinned men: a gap of 34.4 percentage points. Across the three products, the worst rate for lighter-skinned men was 0.8%. All three products scored well overall. The data was fine and the metric was computed correctly, but one number for all faces hid the group the products were wrong about. The paper does not say whether the companies had a bar per group; nothing in it suggests they did. All three released new versions after the audit, and a second audit (Raji and Buolamwini, 2019) measured a 17.7% to 30.4% drop in their errors on darker-skinned women.

**The extra-care algorithm (2019).** US hospitals run care programmes for patients with complex health needs: dedicated nurses, extra doctor appointments. Places are expensive, so an algorithm picks who gets one; the top 3% of scores are enrolled automatically. The sickest patients gain most, but sickness is hard to measure. So the algorithm predicts **next year's health-care cost** instead, and the risk score follows the cost. Obermeyer and colleagues showed in *Science* that at the same risk score, Black patients were considerably sicker than White patients. At the enrolment line they had 4.8 chronic illnesses against 3.8. The cause: for the same illness, about $1,801 less a year was spent on Black patients, because of unequal access to care. Lower cost gave a lower score, so fewer Black patients were chosen. **17.7%** of the patients chosen were Black, against **46.5%** if they had been chosen by health. Checked against its label, the model looked fine: at the same score, both groups had about the same costs. Checked against health, it failed. The manufacturer replicated the result on its own data of 3,695,943 patients. Combining predicted health with cost cut the bias by 84% (Obermeyer et al., *Science* 366, 2019, pp. 1–7).

**Our own pipeline.** Week 5's imputer raised F1 by 0.019 and ROC-AUC by 0.016, while accuracy stayed at 0.7656. A report with accuracy alone would say that nothing changed.

Your lecture may use these cases instead:

- **Speech recognition (2020).** Koenecke and colleagues sent recorded interviews with Black and white speakers to the speech-to-text systems of Amazon, Apple, Google, IBM and Microsoft. The average word error rate was 0.35 for Black speakers and 0.19 for white speakers. With a word error rate above 0.5 counted as unusable, 23% of the Black speakers' snippets were unusable, against 1.6% of the white speakers'. The authors trace the gap to the acoustic models. They ask for more diverse training data, and for companies to "regularly assess and publicly report" their progress (*PNAS*, 2020).
- **Pneumonia risk (mid-1990s).** A research study trained models to predict which patients with pneumonia would die. The plan: high-risk patients go to hospital, low-risk patients are treated at home. A rule-based model learnt that asthma lowers the risk. Patients with asthma usually went straight to intensive care, and that care lowered their death rate; sent home, they have a much higher risk. The label recorded death after the care the patients got, not their risk without it. The team used logistic regression and corrected its asthma weight (Caruana et al., KDD 2015).

Lecture: "1 · What does one number hide?", "2019: who gets extra care?"

## Core concepts

### Metrics

Our model on the 192 test patients says yes when its probability is at least 0.5. Each metric answers a different question:

| Metric | Question | Our model |
| --- | --- | --- |
| accuracy | How often is it right? | 147 / 192 = 0.7656 |
| precision | Of the patients it flags, how many have diabetes? | 39 / 56 = 0.6964 |
| recall | Of the patients with diabetes, how many does it find? | 39 / 67 = 0.5821 |
| F1 | the harmonic mean of precision and recall | 0.6341 |
| ROC-AUC | Does a patient with diabetes get a higher score than one without? | 0.8345 |

F1 = 2 · precision · recall / (precision + recall), so it is high only when both are high. Accuracy, precision, recall and F1 depend on the threshold. ROC-AUC does not. Each threshold gives one point on the **ROC curve**: false positive rate on the x-axis, true positive rate on the y-axis. ROC-AUC is the area under that curve. 0.5 is a random order, 1.0 a perfect ranking. Because it ignores the threshold, it is blind to the decision. With `train.C: 0.001`, the model says "no diabetes" to all 192 patients: accuracy 0.6510, F1 0.0000, and ROC-AUC 0.8407. Judged by ROC-AUC alone, this model looks better than ours, yet it finds no patient with diabetes.

Lecture: "Quiz · Which number answers which question?", "A model that never says yes" · Lab: Exercise 3

### Acceptance criteria

**Acceptance criteria** are the written rules a model must meet before it is released. The domain expert weighs the errors: a doctor can say that a missed diabetes case costs more than a false alarm. The data scientist turns that into metrics, baselines and groups. The ML engineer writes the gate that applies them to every model. The project lead signs the criteria and approves every later change.

Write the criteria when you plan the project, before you see a score. A floor set after the run lands just below the model's score, and the gate cannot refuse that model. Give the criteria a version (`criteria_version`) and raise it with every change.

| Type | Asks | Example |
| --- | --- | --- |
| floors | Is each metric above a minimum? | `accuracy ≥ 0.70` |
| regression | Is it worse than the champion? | F1 drop ≤ `max_drop` |
| slices | Is it good enough for each group? | each group's F1 ≥ 0.50 |
| fairness | Are the errors shared in a way we can defend? | selection-rate and TPR gaps on one chosen axis |

All four live in one versioned block of `params.yaml`, next to the code.

```yaml
acceptance:
  criteria_version: "1.0.0"
  minimum:              # floors
    accuracy: 0.70
    f1: 0.55
  regression:           # no worse than the champion
    primary_metric: f1
    max_drop: 0.01
  slice_rules:          # each group
    min_f1: 0.50
  fairness:             # gaps between groups
    max_tpr_gap: 0.20
```

Lecture: "Who decides what is good enough?", "Four kinds of acceptance criteria" · Lab: Exercise 3

### Baselines

A **baseline** is a score the model must beat. Three baselines are common:

- **The majority class:** is the model doing anything at all? 125 of our 192 test patients have no diabetes, so a model that always says "no" scores 125 / 192 = 0.6510. A floor below that lets a model that does nothing pass.
- **The champion:** is the new model worse than the one we run? The **champion** is the model now in production; in our registry, the alias `@champion` points to it.
- **The current process:** is a model better than what we do today, for example today's screening rule?

The champion's score can come from two places:

| Option | The `gate` stage gives the same result every time? | Always the current champion? |
| --- | --- | --- |
| a file in Git (`metrics/baseline.json`) | yes | no: a person must update it for every new champion |
| the registry in MLflow (`@champion`) | no: it depends on a database in another container | yes |

The lab uses the file, updated on purpose with `make baseline-sync`, which loads the champion and scores it on today's test split. A stored score is true only for the test set it was measured on. When the test data changes, score the champion again on the new test set; otherwise the comparison measures the data, not the model.

Lecture: "Baseline options", "Where does the champion's score come from?" · Lab: Exercises 3 and 6

### Regression tolerance

A **regression check** compares the new model's primary metric with the champion's. `max_drop` is the largest drop it accepts. Set it at least as big as the noise between two runs of the same pipeline, so measure that noise before you choose the number. Our pipeline is deterministic (seed 42, fixed split), so the lab's 0.01 is a choice, not a measurement. On a GPU, with another BLAS library or with a different split, scores move. Measure that spread and set `max_drop` just above it.

Lecture: "Is it worse than the champion?", "Measure the noise before you set a tolerance" · Lab: Exercise 3

### The primary metric

Metrics can disagree about the same change. With `train.C: 0.01`:

| Metric | `C: 1.0` | `C: 0.01` |
| --- | --- | --- |
| accuracy | 0.7656 | 0.7656 |
| F1 | 0.6341 | 0.6087 (−0.0254) |
| ROC-AUC | 0.8345 | 0.8445 (+0.0100) |

On F1 it is a regression; on ROC-AUC it is an improvement. `primary_metric` names the one metric that decides. Choose it before the run, with the people who know how the model is used. The other metrics are still reported (`also_report`).

Lecture: "`train.C: 1.0 → 0.01`" · Lab: Exercise 4

### Slices and support

A **slice** is a group of test patients, scored on its own. Choosing the groups is a clinical question, so the lab keeps them in `params.yaml` (block `evaluation`): age band, BMI band and whether insulin was measured. A band includes its lower edge: 30–39 means [30, 40). The code is a `groupby` with a metric per group; fairlearn's `MetricFrame` does it in one call for any list of scikit-learn metrics (`by_group` holds one row per group).

| Age band | n | with diabetes | F1 | ROC-AUC |
| --- | --- | --- | --- | --- |
| all patients | 192 | 67 | 0.6341 | 0.8345 |
| 21–29 | 94 | 21 | 0.6316 | 0.8656 |
| 30–39 | 48 | 22 | 0.5946 | 0.7832 |
| 40–49 | 31 | 17 | 0.7500 | 0.8571 |
| 50+ | 19 | 7 | 0.5000 | 0.6071 |

The 50+ group has the lowest ROC-AUC, and its false-positive rate is 0.4167, against 0.0685 for the under-30s. It has 19 patients.

A score on a small group can jump from 0.00 to 1.00 with one patient. **Support** is how much evidence a group gives, and the lab has two rules for it: `min_support` (at least 20 rows) and `min_positives` (at least 10 patients with diabetes). Rows alone are not enough: the under/normal BMI band has 30 rows and one patient with diabetes. Lower `min_support` to 15 alone, and the 50+ group is still not scored, because its 7 positives are too few. Two more rules set the bar per group: `min_f1: 0.50` and `max_f1_gap: 0.10` (all patients' F1 minus a group's F1).

Lecture: "Which groups of patients should we check?", "Slice metrics in code", "Which group would you worry about?", "How many patients make a slice?" · Lab: Exercises 1 and 2

### Skipped checks

A group below a support rule is neither passed nor failed: its check is **skipped**. A skip reported as a pass makes the report say "everything checked" when the group we worried about was never scored. A skip reported as a fail refuses every model that has a small group. So the gate puts the count of skips in its first line and gives each skip its reason:

```text
GO — 13 passed, 0 failed, 4 SKIPPED (criteria v1.0.0)
    slice.age_band.50+               support 19 < min_support 20
    slice.bmi_band.under_normal      positives 1 < min_positives 10
    slice.bmi_band.overweight        positives 9 < min_positives 10
    slice.bmi_band.missing           support 2 < min_support 20
```

The 50+ group, the one with the lowest ROC-AUC, is one of the four. Read the skips before you trust a GO.

Lecture: "How many patients make a slice?", "Always check what was skipped" · Lab: Exercise 3

### Slice the raw values

The BMI groups are under 25, 25 to 29, 30 and over (obese), and missing. Two test patients have `bmi = 0`: their BMI was never measured. Sliced on the raw data, they form the `missing` group. Sliced after Week 5's `SimpleImputer`, they get the training median, 32.4, and join `obese`: that group grows from 112 to 114 patients and its F1 moves from 0.6792 to 0.6729, while `missing` disappears. A group must say who the patient is, and the imputer only guesses a value. So cut the slices from the raw test data, before the imputer.

Give missing values their own group, and cut the groups from the raw data.

Lecture: "Which BMI group is a patient with no BMI in?" · Lab: Exercise 1

### Group fairness

Slices (above) ask whether each group is above a fixed bar. **Group fairness** compares the groups with each other: do they get the same rates? The groups come from a **sensitive feature**, such as age, sex or ethnicity; in our data, age and whether insulin was measured. fairlearn names two harms to look for. An **allocation harm** withholds an opportunity or a resource. A **quality-of-service harm** means the model works worse for some people.

Fairness checks use three rates per group, all from the confusion matrix:

| Rate | Computed as | Means | Our model |
| --- | --- | --- | --- |
| selection rate | (TP + FP) / all | how often we act | 56 / 192 = 0.2917 |
| TPR (= recall) | TP / (TP + FN) | whom we catch | 0.5821 |
| FPR | FP / (FP + TN) | whom we alarm | 17 / 125 = 0.1360 |

Three fairness metrics ask for one of these rates to be equal in every group. Each is measured as a difference: the highest group's rate minus the lowest group's. The names follow fairlearn's user guide:

| Metric | Equal in every group | The question it asks |
| --- | --- | --- |
| demographic parity | selection rate | Is every group flagged as often? |
| equal opportunity | TPR | Of the patients with diabetes, is every group found as often? |
| equalized odds | TPR and FPR (the larger gap) | Are both errors the same in every group? |

Choose the metric by the harm a wrong decision causes. Use equal opportunity when a missed case costs most (our case), and demographic parity when the decision gives out a resource.

In fairlearn each metric is one function: `demographic_parity_difference`, `equal_opportunity_difference` and `equalized_odds_difference`. fairlearn compares every group, however small, and reports a TPR of 0.0 for a group with no patients with diabetes. So the lab reports such a rate as undefined, and leaves out of the gaps any group under 5 rows or without both classes.

Lecture: "Group fairness: compare the groups", "Three rates for each group", "Three fairness metrics", "Which groups get a fairness gate?" · Lab: Exercise 5

### Choosing a fairness criterion

The criteria can disagree on the same model. Split our test patients by whether an insulin value was ever recorded:

| Group | n | selection rate | TPR |
| --- | --- | --- | --- |
| insulin measured | 104 | 0.2885 | 0.5238 |
| insulin not measured | 88 | 0.2955 | 0.6800 |

The selection-rate gap is 0.0070, so demographic parity holds. The TPR gap is 0.1562, so equal opportunity does not. The base rates differ too: 40% of the patients with an insulin value have diabetes, against 28% of those without one.

The **base rate** is the share of a group that really has diabetes. When base rates differ, a model cannot meet every criterion. A perfect model flags 40% of the first group and 28% of the second, so the selection rates differ. To make them equal, it must miss patients in one group or flag healthy ones in the other, so the error rates differ. Equal selection rates and equal error rates hold together only when the base rates are equal or the model is no better than chance. Barocas, Hardt and Narayanan prove this in *Fairness and Machine Learning*, Chapter 3, where the two are called independence and separation. Calibration and equal error rates cannot both hold either (Chouldechova, 2017; Kleinberg, Mullainathan and Raghavan, 2016). So choose one criterion, and write the reason down in the acceptance criteria.

Which gaps should stop a release? All three gaps of our model:

| Groups | Selection rate | TPR | TPR or FPR |
| --- | --- | --- | --- |
| age band | 0.3030 · report | 0.2059 · gate ≤ 0.25 | 0.3482 · report |
| insulin measured or not | 0.0070 · gate ≤ 0.10 | 0.1562 · gate ≤ 0.20 | 0.1562 · report |

Diabetes really is more common with age (22% under 30, 55% at 40–49), so unequal selection rates are expected. But a patient with diabetes should be found as often at any age. The age limit is looser because the age groups are small: one patient found or missed moves a group's TPR by about 0.05. Whether the insulin test was ordered is about access to care, not about the body, so both its gaps are gated. Gate a gap only where equal rates are what you expect; report the others, and write down why. Exercise 5 asks you to defend a choice like this.

Lecture: "Is the model fair to both groups?", "Can a model satisfy all three at once?" · Lab: Exercise 5

### When the label is wrong

Every check in this lecture compares the predictions with the label. If the label measures the wrong thing, every check can pass. In the extra-care case the label was future cost: a **proxy label**, a stand-in for health need, which is what the programme is for. Checked against cost, both groups had the same costs at the same score. Checked against health, what the programme is for, it failed: Black patients were sicker at the same score. So also check each group against the goal, not only against the label. Only someone who asks what the label means finds this: the domain expert from Week 1.

Lecture: "Which check would have caught it?" · Lab: Exercise 5

### The gate as a stage

The gate turns four inputs into a verdict: `metrics.json`, `slices.json`, `baseline.json` and the `acceptance` rules. `evaluate_gate` is a pure function of four plain dicts: no files, no model, no network. So the tests can check every rule with nothing running. The verdict is GO if no check failed and NO-GO otherwise; the first line also prints the skip count.

In `dvc.yaml`, `gate` is the stage after `evaluate`. On a NO-GO it writes `reports/gate.json` and exits with code 1, so `dvc repro` fails. `make register` and `make promote` read the recorded verdict and refuse without a GO; in Week 9, `make image` refuses too. Make every command that publishes a model read the gate report.

In our case, the report has two copies. One in Git, next to the code, `params.yaml` and `dvc.lock`. The stage writes it as a DVC output with `cache: false`, so DVC does not move it into its cache and Git tracks the file itself. `make register` and CI read this copy without MLflow. One in the MLflow run, next to the model, for tracing the model later. It holds `criteria_version`, the pass/fail/skip counts and every number behind each check. It has no timestamp, so the same run gives the same file and a Git diff shows only real changes. The `gate` stage tags the training run in MLflow (`gate`, `gate_criteria_version`, `gate_checks_failed`, `gate_checks_skipped`), on a NO-GO too, and logs `gate.json` and `slices.json` with it. `make trace` prints the chain from the alias to the gate verdict.

Lecture: "From evidence to a verdict", "The gate in the pipeline", "Inspect the report", "Why was this model allowed out?" · Lab: Exercises 3 and 4

### Measurement and policy

`params.yaml` keeps what we measure (`evaluation`: the groups) apart from whether it passes (`acceptance`: the thresholds). `evaluate` lists `evaluation` as its parameters and `gate` lists `acceptance`. So raising the F1 floor from 0.55 to 0.60 re-runs only `gate`: a new threshold needs no new model. A new age band re-runs `evaluate` and `gate`; a new `train.C` re-runs `train`, `evaluate` and `gate`.

Lecture: "Four kinds of acceptance criteria" · Lab: Exercise 4

### The ratchet

The champion's score is the bar for the next model. In the lab, a random forest scores F1 0.6452 against the champion's 0.6341 and gets a GO (+0.0111). Promote it to `@champion` and run `make baseline-sync`, and the bar is now 0.6452. The old logistic regression, unchanged, now gets a NO-GO: its drop of 0.0111 is larger than `max_drop` 0.01, about one patient's worth of F1 on 192 patients. The bar follows the champion: up with a better model, and down by up to `max_drop` each time a slightly worse one is promoted.

Lecture: "The bar moves up" · Lab: Exercise 6

## Red flags and good practices

### Make sure every rule can fire

While this lab was built, `max_f1_gap` was 0.15. With `min_f1: 0.50` and all patients at F1 0.6341, a group's gap to all patients is at most 0.1341, so a gap of 0.15 is always already a failed `min_f1`. The rule could never fail. A test that expected a gap failure found it; the lab now uses 0.10. A floor below the majority-class rate (0.6510) is the same mistake. For each rule, make a model that should fail it, and check that the gate says NO-GO.

Lecture: "Make sure every rule can fire" · Lab: Exercise 3

### Measure the noise before you set a tolerance

A guessed `max_drop` of 0.01 lets a real drop of 0.009 pass every time. Weeks of "only 0.009 worse" add up to a model much worse than the champion it replaced. Train the same model several times, with different seeds or on different machines, and set `max_drop` just above the spread you measure.

Lecture: "Measure the noise before you set a tolerance" · Lab: Exercise 3

### Change a threshold in a reviewed commit

The model misses the F1 floor by 0.003 the day before a release, and someone edits `params.yaml` from 0.55 to 0.54. Then every later GO means less, and nobody can see why. Change a threshold in a reviewed commit that gives the reason, has an approver and raises `criteria_version` (1.0.0 → 1.1.0). `criteria_version` is tagged on every MLflow run, so an old verdict still names the rules it was issued under. A threshold may go down for a good reason, for example a harder test set; the commit message then says so.

Lecture: "Change a threshold in a reviewed commit" · Lab: Exercise 4

## Commands

| Command | What it does |
| --- | --- |
| `make slices` | writes `metrics/slices.json`: every group with its `n`, positives and metrics |
| `make gate` | applies the `acceptance` rules and prints the verdict |
| `make fairness` | prints the three rates per group and the three gaps per axis |
| `make repro` | runs the pipeline; it stops at a NO-GO |
| `dvc params diff` | shows which parameters changed since the last commit |
| `make gate-fail` | sets `train.C: 0.005`, shows that `dvc repro`, `register` and `promote` stop, then restores it |
| `make register` / `make promote` | register the model / move `@staging`; both refuse without a GO |
| `make promote-champion` | moves `@staging` and `@champion` |
| `make baseline-sync` | scores the champion on today's test split and writes `metrics/baseline.json` |
| `make ratchet` | trains a better model, promotes it, syncs the baseline and shows the old model refused |
| `make trace` | prints the chain from the alias to the gate verdict |

## Key terms

- **Acceptance criteria**: the written, versioned rules a model must meet before it is released, agreed before the run.
- **Go / no-go**: the release decision the criteria produce, recorded as a file.
- **Floor**: a minimum a metric must reach, whatever the baseline.
- **Baseline**: a score the model must beat: the majority class, the champion or the current process.
- **Champion**: the model now in production; the alias `@champion` points to it.
- **Regression**: a drop against the champion larger than `max_drop`.
- **Primary metric**: the one metric that decides the regression check.
- **Ratchet**: each promotion moves the bar for the next model to the new champion's score.
- **Slice**: a group of test rows, scored on its own.
- **Support**: how much evidence a slice gives: its rows and its positive cases, two separate rules.
- **Skipped check**: a check that could not be run; neither a pass nor a fail, and reported as such.
- **Selection rate**: the share of a group the model says yes to.
- **TPR / recall**: the share of a group's positive cases the model finds; **FPR**: the share of its negative cases the model flags.
- **ROC curve**: one point (false positive rate, true positive rate) for every threshold; ROC-AUC is the area under it.
- **Sensitive feature**: a feature that defines the groups a fairness check compares, such as age or sex.
- **Allocation harm / quality-of-service harm**: a model withholds an opportunity or a resource / works worse for some people.
- **Base rate**: the share of a group that is positive.
- **Demographic parity difference**: the selection-rate gap between groups.
- **Equal opportunity difference**: the TPR gap; **equalized odds difference**: the larger of the TPR and FPR gaps.
- **Proxy label**: a label that stands in for what you care about, such as cost for health need. A gate cannot see that it is wrong.
- **`criteria_version`**: the version of the acceptance criteria a verdict was issued under.
- **Word error rate**: the share of words a speech recognition system gets wrong.
- **Pneumonia** (*tüdőgyulladás*): an infection of the lungs.

## How this connects to the lab

The lab adds evaluation per group and a release gate to the Week 5 pipeline. You:

1. slice the test set and write `metrics/slices.json`;
2. read the slice table and answer two written questions;
3. write the `acceptance` block and the gate, and see `make gate` print GO with every check;
4. make the gate a DVC stage, break the model with `train.C: 0.005`, and see `dvc repro` stop, `register` and `promote` refuse, and `models/model.pkl` stay on disk;
5. compute the three fairness gaps per axis and choose which axis to gate;
6. run the ratchet: a better champion, and the old model refused.

Written answers go in `answers.md`, committed with your code. Nothing about the model changes this week: `metrics/metrics.json` is the same as in Week 5. Check this rather than assume it.

## Recommended reading

- **Buolamwini and Gebru, "Gender Shades"**, PMLR 81 (2018) (https://proceedings.mlr.press/v81/buolamwini18a.html). *Focus on:* Table 4 and Section 4.5.
- **Obermeyer et al., "Dissecting racial bias in an algorithm used to manage the health of populations"**, *Science* 366 (2019) (https://www.science.org/doi/10.1126/science.aax2342). *Focus on:* how the label was chosen, and the fix.
- **Barocas, Hardt and Narayanan, *Fairness and Machine Learning*, Chapter 3** (https://fairmlbook.org/classification.html). *Focus on:* the section "Relationships between criteria".
- **Breck et al., "The ML Test Score"** (Google, 2017) (https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/). *Focus on:* the Model and Monitoring sections.
- **Zinkevich, "Rules of Machine Learning"** (https://developers.google.com/machine-learning/guides/rules-of-ml). *Focus on:* Rules #12–19, on choosing a metric and slicing.
- **scikit-learn, model evaluation** (https://scikit-learn.org/stable/modules/model_evaluation.html). *Focus on:* the classification metrics used here.
- **fairlearn, common fairness metrics** (https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html). *Focus on:* the definitions of the three gaps.
- **fairlearn, performing a fairness assessment** (https://fairlearn.org/main/user_guide/assessment/perform_fairness_assessment.html). *Focus on:* `MetricFrame`, `overall` and `by_group`.
- Optional: **Koenecke et al., "Racial disparities in automated speech recognition"**, *PNAS* (2020) (https://pmc.ncbi.nlm.nih.gov/articles/PMC7149386/), and **Caruana et al., "Intelligible Models for HealthCare"**, KDD 2015 (https://doi.org/10.1145/2783258.2788613), the two other cases.
- Optional: **Chouldechova (2017)** (https://arxiv.org/abs/1703.00056) and **Kleinberg, Mullainathan and Raghavan (2016)** (https://arxiv.org/abs/1609.05807). *Focus on:* the statements of the results; the proofs are optional.
- Huyen, *Designing Machine Learning Systems*, Ch. 6. *Focus on:* offline evaluation, baselines and slice-based evaluation.

## Check yourself

1. A colleague proposes gating on ROC-AUC alone, because it needs no threshold. Using a number from this week, show them a model that passes and should not.
2. Your worst group has 19 patients. Give the argument for gating on it and the argument for skipping it. What would you need to settle the question, and what would you do about the group in the meantime?
3. Explain why Week 5's gate could work as a dependency edge in `dvc.yaml` and Week 6's cannot. What replaces the edge, and what breaks if somebody adds a second way to publish a model?
4. Your model has a selection-rate gap of 0.30 on one axis and 0.007 on another. Explain why the second one might be the more serious finding, and name one thing you would need to know about each axis before deciding.
5. A team sets its F1 floor after it sees the model's F1. What can the gate no longer do, and how does `criteria_version` help?
6. Why does the gate read the champion's score from a file in Git instead of asking the registry?
