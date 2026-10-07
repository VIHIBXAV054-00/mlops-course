# Week 5 — Data Quality — Study Notes

These notes go with the Week 5 lecture and lab. In Week 4 we versioned the data, so we can tell which data trained a model. The version says nothing about whether that data was right. This week we decide what good data looks like, write it down as a contract, and stop the pipeline when a batch breaks it.

## Why this matters

**Unity's ad model (2022).** Unity makes a game engine and also runs an ad network: games show adverts for other games. A model called **Audience Pinpointer** picks the players most likely to install the advertised game. It learns from data that Unity's customers send in. On its earnings call of 10 May 2022, the CEO said Unity was "hit hard by two issues". A fault in the platform made the model less accurate. And part of the training data lost its value, "due in part to us ingesting bad data from a large customer".

Management estimated the cost at about **$110 million of 2022 revenue**, compared with what Unity expected to earn without the problem. About 60% of it was expected to fall in the next quarter, 30% in the one after and 10% in the last, with no impact on 2023. This is an estimate, not an audited loss. The fix was not a code change: "The first is data rebuilding. The second is model training." The CEO said Unity had "built more for growth and less for resiliency", and three months later: "We're measuring a lot of things we didn't use to measure."

Unity has not said what was wrong with the data, or which checks it had. The lesson we take from it is general: data that other companies send can break a model, and it has to be checked before it reaches training.

**Our own data.** The 768 patients we versioned in Week 4 contain **652 impossible zeros**: 5 in `glucose`, 35 in `blood_pressure`, 227 in `skin_thickness`, 374 in `insulin` and 11 in `bmi`. If you are alive, your glucose is not 0. These are measurements nobody took, stored as 0, and 376 of the 768 patients have at least one. The 111 zeros in `pregnancies` are real. Every model we trained in Weeks 1–4 learnt from the impossible ones.

### More cases from the lecture

- **Mars Climate Orbiter (1999).** Two teams shared a file of thruster data. A written specification said its unit was newton-seconds. The ground software wrote pound-force seconds, 4.45 times too small, and the navigation team read the file as newton-seconds. The orbiter passed about 57 km above Mars instead of the planned 226 km and was lost on 23 September 1999 (NASA Mishap Investigation Board, Phase I Report, 10 Nov 1999). The specification was a contract, but no program ever checked the file against it.
- **600 million IP addresses on one farm.** IP geolocation databases map an IP address to a place. For addresses known only to be "in the US", MaxMind used a default point, 38.0000, -97.0000, chosen in 2002. It is a farmhouse near Potwin, Kansas. More than 600 million IP addresses pointed at it. For years, police and angry strangers came to the door, and the family sued in 2016 (Kashmir Hill, Fusion, 10 Apr 2016; The Register, 10 Aug 2016). The default is a valid coordinate, so every range check passes. What works: store "unknown" as missing, and watch how often the most common value appears.
- **Google Play: features that never arrived.** Some features of an app-ranking model were always present in the training data and always missing at serving time. Nothing crashed. Google's data validation system found it by comparing the training data with the logged serving data. Removing the skew raised the app install rate by 2% (Breck et al., SysML 2019, Section 6.2).
- **Equifax (2022).** A code change made some model attributes use a fixed date instead of today's date. Between 17 March and 6 April 2022, fewer than 300,000 consumers had their credit score shift by 25 points or more (Equifax statement, 2 Aug 2022; New York Attorney General, 2025). The raw data was correct; a feature computed from it was wrong.

The teacher may use other cases instead:

- **Target Canada (2013–2015).** About 75,000 products were typed into a new SAP system by hand. The item data was right about 30% of the time, against 98–99% in the US (Castaldo, *Canadian Business*, 21 Jan 2016). In January 2015 Target Canada asked for creditor protection, with 133 stores and about 17,600 employees (Target 8-K, 15 Jan 2015).
- **Lab values with no unit.** The US N3C database pooled COVID-19 records from 55 hospitals and health systems. Of 1.6 billion measurement values, 42% arrived with no unit (Bradwell et al., *JAMIA* 29(7), 2022).
- **1,380 crimes at one address.** The Los Angeles police crime map put addresses it could not place on one default point near City Hall. That was about 4% of all mapped crimes (Geography Realm, reporting the *Los Angeles Times*).
- **Video recommendations at Google.** A backend stored features in a different format than expected, and the reading code dropped them without an error. With the validation system, diagnosing and fixing it took two days; similar problems had taken months (Breck et al., 2019).
- **Gene names that became dates.** Excel's default settings turn the gene name SEPT2 into the date "2-Sep". A study of 3,597 papers with gene lists found such errors in 19.6% of them (Ziemann et al., *Genome Biology* 17:177, 2016).

### When is data validation too much?

A 2022 interview study of 18 ML engineers found teams with an alert on every column. One alert fired 1,000 times and was ignored 45% of the time, and hand-written bounds did not last once their authors left (Shankar et al., arXiv:2209.09125, Section 5.1.2). A rule that nobody acts on teaches the team to ignore all of them. Write few rules, each with an owner and an action. For a one-off analysis of a file you will never receive again, a look at the data in a notebook is enough.

Lecture: "Avoid generating noise"

## Core concepts

### Who knows the rules, and who checks them

Someone has to say what good data looks like, and someone has to look. The **domain expert** knows the rules: a doctor knows at once that a glucose of 0 is impossible and that 0 pregnancies is normal. Nobody can check every row of every batch by hand, so a program does it. The **data engineer** turns the rules into checks in the data pipeline. The pipeline runs them on every batch, and the MLOps or platform team keeps it running. The ML engineer or project lead makes sure each step is done. The data scientist gains most, because every training run starts from checked data. In a small team one person may hold several of these roles (Week 1, "Who is around the loop"), but the jobs stay different.

Name the people behind each data source when the project starts: who owns its rules, its checks, and the pipeline that runs them.

Lecture: "Who builds the program?"

### Data contracts

A **data contract** is the set of rules, written down and agreed between the team that produces the data and the teams that use it. The domain expert draws it up and the data engineer implements it. It has two parts:

- **for people:** what each column means, its type and unit, the allowed values, and whom to call when something is wrong;
- **for the pipeline:** code that checks every batch, stops a batch that fails, and raises an alert.

Only the code part can stop a bad batch. One open standard for writing a contract is the **Open Data Contract Standard (ODCS)**, a Linux Foundation AI & Data project, written in YAML.

Lecture: "A data contract", "Lost in unit conversion"

### Types of data errors

| Type | Examples | Needs |
| --- | --- | --- |
| **Schema** | wrong type, missing or extra column: `glucose = "unknown"` | one file |
| **Values** | out of range, wrong sign, unknown label, wrong unit: `age = 250` | one file |
| **Completeness** | empty cells, missing rows | one file |
| **Uniqueness** | the same row, or the same key, twice | one file |
| **Distribution** | this month does not look like last month | a reference dataset |

The first four are properties of one file, so a contract can check them with no history. Distribution needs a comparison: that is drift, in Week 12. A unit change is the hardest of the value errors: three `bmi` values multiplied by 10 (280.0, 297.0, 227.0) are still numbers, still positive and still present. Only an upper bound such as `bmi ≤ 100` catches them, and a BMI of 28.0 written as 2.8 passes even that.

Lecture: "Which data errors have you met?" · Lab: Exercise 2

### Sentinel values

A **sentinel value** is a special value that stands for "missing" or "unknown". Our data writes `0`; NOAA's daily weather records write `-9999`; one Google pipeline saw a spike of `-1` from a failing server's default value (Breck et al., 2019, p. 7). A mean, a chart or a model then uses the sentinel as a real measurement. Only someone who knows the column can say which zeros are real, so for every column, find out which sentinels it uses. Other common ones are `99`, `1900-01-01`, `"N/A"` and an empty string.

Lecture: "Missing values in disguise"

### Data validation tools

| Tool | Where the rules live | Where they run |
| --- | --- | --- |
| **Pandera** | a Python class | on a dataframe, in your process |
| **Great Expectations (GX Core)** | Expectation Suites in a project folder | through a Data Context and a Checkpoint; publishes Data Docs |
| **Soda Core** | YAML contracts | on SQL warehouses |
| **dbt data tests** | YAML and SQL | inside the warehouse |
| **Deequ** | Scala or Python | on Spark |
| **TFDV** | an inferred schema | part of TFX; also finds skew |
| **pydantic** | a Python class | one record at a time, such as a request (Week 9) |

The course uses Pandera: one package, the contract is Python code you can test, and it runs inside a DVC stage. Great Expectations earns its set-up cost when many teams, including people who do not read code, must read the results. Many GX tutorials online use its old 0.x API. Soda Core moved from Apache 2.0 to the Elastic License 2.0 in January 2026; ELv2 is not an open-source licence.

Lecture: "Tool options", "Pandera or Great Expectations?"

### Pandera quick start

These tools turn the written contract into a program. With Pandera, you install the package, load the data, write a schema and validate the data against it:

```bash
uv add "pandera[pandas]"    # the base package does not install pandas
```

```python
import pandas as pd
import pandera.pandas as pa

readings = pd.read_csv("readings.csv")   # one row per station and day

schema = pa.DataFrameSchema({
    "station": pa.Column(str),
    "temp_c": pa.Column(float, pa.Check.in_range(-90, 60)),
})

schema.validate(readings)   # returns the frame, or raises an error
```

If one reading has `temp_c = -9999`, Pandera raises a `SchemaError` that names the column, the check and the value:

```text
SchemaError: Column 'temp_c' failed element-wise validator number 0:
in_range(-90, 60) failure cases: -9999.0
```

The documented import is `import pandera.pandas as pa`. Old blog posts write `import pandera as pa`; it still works, with a warning. The examples here use a table of weather readings, one row per station and day, so that the lab's own schema stays yours to write.

Lecture: "Pandera quick start" · Lab: Step 1

### The same schema as a class

A `DataFrameSchema` is an object built at run time. A `DataFrameModel` is a class with the same rules:

```python
from pandera.typing.pandas import Series

class ReadingsSchema(pa.DataFrameModel):
    station: Series[str]
    temp_c: Series[float] = pa.Field(ge=-90, le=60)

ReadingsSchema.validate(readings)
```

`validate` works the same way on the class: on the same file it raises the same `SchemaError`, naming the check `greater_than_or_equal_to(-90)`. The lab uses the class:

- it has a name you can import and use in a type hint;
- a changed rule shows as a changed line in a code review, so you can track every change to the contract.

Give the class a name that differs from the data's name: `ReadingsSchema` checks the frame `readings`. `ReadingsSchema.to_schema()` gives you the object. The object style fits a schema that code builds from a config file.

Lecture: "The same schema as a class" · Lab: Exercise 1

### `Field`: rules for one column

| **Rule** | **Pandera code** |
| --- | --- |
| within bounds | `ge=`, `gt=`, `le=`, `lt=` |
| one of a set | `isin=[0, 1]` |
| a text pattern | `str_matches=r"…"` |
| may be missing | `nullable=True` (the default is `False`) |
| no repeats | `unique=True` |
| your own rule | a method with `@pa.check` |

```python
class ReadingsSchema(pa.DataFrameModel):
    station: Series[str] = pa.Field(str_matches=r"^[A-Z0-9]{11}$")
    temp_c: Series[float] = pa.Field(ge=-90, le=60, nullable=True)
    rain_mm: Series[float] = pa.Field(ge=0, nullable=True)
```

A station ID is 11 capital letters or digits; a temperature is a float between -90 and 60 and may be missing; rain is a float, never negative, and may be missing. NOAA's `-9999` fails `ge=-90` for a temperature and `ge=0` for rain.

Lecture: "`Field`: rules for one column" · Lab: Exercises 1 and 3

### `Config`: rules for the whole table

```python
class ReadingsSchema(pa.DataFrameModel):
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

With `coerce = True`, a value that cannot be converted is reported with its column and row. Use `strict = True` for data from outside your team: an extra column means the producer changed the file without telling you.

`@pa.dataframe_check` marks a method as a check on the whole frame. Pandera calls it with the frame, and every row where it returns `False` fails. A row with a minimum of 7.0 and a maximum of 3.0 fails as `<Check min_not_above_max>`. The lab uses the same kind of check for "no duplicated rows".

Lecture: "`Config`: rules for the whole table" · Lab: Exercise 1

### Stop at the first error, or collect them all

`ReadingsSchema.validate(readings)` stops at the first problem and raises `SchemaError`. `ReadingsSchema.validate(readings, lazy=True)` checks every rule, then raises **`SchemaErrors`**, with an s. It is not a subclass of `SchemaError`, so a handler for the singular never runs. The exception carries a table, `failure_cases`, with one row per failure and the columns `schema_context`, `column`, `check`, `check_number`, `failure_case` and `index`; `exc.data` holds the frame that failed. A lazy report shows every problem at once, so you fix a file in one pass.

Lecture: "Stop at the first error, or collect them all" · Lab: Exercise 2

### Reading a validation report

The lab's broken batch has 60 rows and 4 faults, and `lazy=True` reports **7** failures. Row numbers in the report are 0-based pandas positions: row 3 is line 5 of the CSV file. One fault can break several checks: row 3's `glucose = "unknown"` causes four (the conversion fails, the type check fails, and both range checks fail on text). So fix type errors first. Two check names look alike: `column_in_schema` means a column is present that the contract does not name; `column_in_dataframe` means a column the contract names is missing.

The same failures can be counted two ways. **By check** tells you which rule broke, which is how you fix the data. **By column** tells you where it broke, which is whom to call: several failures in one column usually mean one change on the producer's side. Send the report to the producer, not only to your own log.

Lecture: "Reading a real report" · Lab: Exercise 2

### Two contracts at two boundaries

Data passes two gates on the way to the model: first it is accepted as a raw measurement, then it is admitted as model input. The clinic sends zeros in every real batch. If the first gate rejected them, every batch would fail and the gate would be switched off within a week. So the lab has two contracts:

| | `RawMeasurements` | `ModelInput` |
| --- | --- | --- |
| Guards | what arrives from the clinic | what the model may see |
| The 5 sentinel columns | `ge=0`: zero allowed | `gt=0, nullable=True`: zero illegal, missing allowed |
| Column order | free | fixed: `ordered = True` |

Between them, `to_nullable` replaces 0 with `<NA>`, pandas' missing value, in the five columns where 0 is impossible (not in `pregnancies`). It only converts; it fills nothing in. In `ModelInput`, `gt=0` means a value must be greater than 0, and `nullable=True` means the value may be missing. So `<NA>` passes, and a surviving `0.0` fails `greater_than(0)`. The column needs a nullable type, `Float64` with a capital F: plain `float64` turns `<NA>` into `NaN`. Measured on our 768 patients: **652 failures before `to_nullable`, 0 after.**

Lecture: "Two contracts, at two boundaries", "Zero becomes missing" · Lab: Exercises 1 and 3

### Filling the gaps inside the model

Deciding what to do with a missing value is a modelling decision. The order of the steps matters: first the train/test split, then a scikit-learn `Pipeline` of `SimpleImputer`, `StandardScaler` and `LogisticRegression`. If the imputer ran before the split, the test patients would help choose the medians, and the test score would look better than it is. This is **data leakage**. So `fit` learns the medians from the training split only (glucose 117, blood pressure 72, skin thickness 29, insulin 122, BMI 32.4). They are saved in `model.pkl` with the model, and `predict` fills a missing value the same way at serving time. The strategy is set in `params.yaml` (`train.impute_strategy: median`).

| Metric | Week 4: zeros used as values | Week 5: median imputer |
| --- | --- | --- |
| accuracy | 0.7656 | 0.7656 |
| precision | 0.7200 | 0.6964 |
| recall | 0.5373 | 0.5821 |
| F1 | 0.6154 | 0.6341 |
| ROC AUC | 0.8183 | 0.8345 |

These are the results you will reproduce in the lab. Accuracy did not move, while the model ranks patients better and finds more of the diabetic ones. Judge a data fix on more than one metric; Week 6 makes this a rule.

Lecture: "Fill the gaps inside the model" · Lab: Exercise 5

### The data quality gate

A contract protects nothing if it only runs when someone remembers it.

| Where | Runs every time? | Stops the pipeline? | Leaves a record? |
| --- | --- | --- | --- |
| in a notebook, by hand | no | no | no |
| an `assert` in `prepare` | yes | yes | no |
| `@pa.check_types` on a function | when the function is called | yes | no |
| its own pipeline stage | yes | yes | yes: a report file |

In `dvc.yaml` the gate is one dependency edge:

```yaml
stages:
  validate:
    cmd: uv run python src/main.py validate
    outs:
      - reports/validation.json:
          cache: false              # the verdict is committed to Git
  prepare:
    deps:
      - reports/validation.json     # prepare waits for a passing validate
```

`validate` writes the report first and then exits with code 1 when the contract fails, so `dvc repro` runs nothing after it. Measured with one impossible `age = 250`: `prepare`, `train` and `evaluate` did not run, `data/processed/train.csv` kept the same md5 before and after, and `reports/validation.json` recorded `"passed": false` with the row and the rule. A `validate` that exits with 0 on failure is not a gate, only a warning. Decide for each rule: warn, quarantine the batch (keep it aside until someone checks it), or stop. For a model that suggests a treatment, stop.

Lecture: "The gate is one dependency edge", "Did it really stop?" · Lab: Exercise 4

### Recording the verdict with the run

Each training run gets four MLflow tags, and the gate's report as an artifact:

- `data_validation`: the training contract's verdict (`ModelInput` on the training split);
- `ingestion_validation`: the gate's verdict (`RawMeasurements`);
- `schema_version`: which version of the contract;
- `n_failure_cases`: 0 on any run that exists, because `train` stops before it logs. A non-zero value means someone trained anyway.

The chain from Weeks 3 and 4 now ends with the verdict: alias → model version → run → `dvc_md5` (which data) → `data_validation` (whether it passed its contracts). Rules change, so "it passed" means little without the contract's version: raise `schema_version` whenever a rule changes. `make trace` prints the whole chain.

For high-risk AI systems, the EU AI Act asks for data that is "free of errors and complete", "to the best extent possible" (Art. 10(3)), and for finding "data gaps or shortcomings" (Art. 10(2)(h)). The two contracts and the validation report are this week's answer, and complete the Week 4 table.

Lecture: "Record the verdict with the run", "The third row of Article 10" · Lab: Exercise 6

### Training-serving skew

**Training-serving skew** means the model gets different input when it serves than when it was trained. Its most common cause is "different code paths" for training and serving data (Breck et al., 2019, Section 4). Google's Rule #32: "Re-use code between your training pipeline and your serving pipeline whenever possible."

We measured it with one example patient, for a model trained on data filled with medians in `prepare` instead of in the model. With glucose filled with the median, the probability of diabetes is 0.4236. With glucose sent as 0, as the source system does, it is **0.0068**. With insulin sent empty, scikit-learn crashes with `ValueError: Input X contains NaN`. The crash is the lucky case. So put every transformation the model needs inside the model's `Pipeline`.

The second defence is the same contract at both boundaries. The lab's `PredictionInput` inherits from `ModelInput`, without the label. Without it, a request with glucose and insulin sent as 0 gets 0.0092, and one with insulin and BMI swapped gets 1.0000. With it, both are rejected, by `greater_than(0)` and `less_than_or_equal_to(100.0)`.

Column order matters too. Give the model the same patient with the columns reversed. scikit-learn refuses a DataFrame ("The feature names should match…"), but answers 1.0000 for a NumPy array. An array has no column names, so the values are read by position: our patient (6 pregnancies, glucose 148, …, age 50) arrives as 50, 0.627, 33.6, …, 6, and the model reads 50 as the number of pregnancies and 0.627 as the glucose. In the right order, the same patient gets 0.7173. That is why `ModelInput` sets `ordered = True`. A JSON request has no column order, and the lab's code puts the columns in order, so `PredictionInput` does not check it.

Lecture: "Training-serving skew", "Imputing outside the model", "One contract at both boundaries", "Why column order matters" · Lab: Exercise 6

### No contract is bulletproof

A contract checks that the data has the **agreed shape**, not that it is **true**. Wrong labels pass every rule. On average, at least 3.3% of the test labels in 10 popular benchmarks are wrong, and at least 6% in ImageNet's validation set (Northcutt et al., NeurIPS 2021). A BMI of 28.0 typed as 26.0, or two swapped features with similar ranges, also pass. No tool in this course solves this. People who know the data must check samples, and Week 13's Model Cards record what the data cannot show.

Lecture: "No contract is bulletproof"

## Red flags and good practices

### Write down why each rule exists

`age ≤ 120`: a guess, or a clinical rule? `bmi ≤ 100`: who decided, and why 100? An engineer can guess a bound; a clinician knows it. A bound nobody can explain is removed at the first false alarm. Next to each rule, write its source and its owner, in the schema's docstring or in the contract file.

Lecture: "Write down why each rule exists"

### Check computed features too

At Equifax the credit data was correct; the attributes computed from it used a fixed date instead of today's. Every value was a valid number. Check computed features as well as raw data: for example, an age counted from today must grow every day.

Lecture: "Check computed features too"

### Fix the producer, not your copy

Say you fix bad rows by hand in your CSV file. The fix is not in the pipeline, so nobody can repeat it, and the next batch brings the same error. The producer never learns that its export is wrong, and the data's Week 4 hash changes for a reason nobody recorded. Send the validation report to the producer. Put any repair in code, as a pipeline step, so it runs on every batch.

Lecture: "Fix the producer, not your copy"

### Keep drift checks out of the contract

A contract asks "what must every row be?": one file, no history, rules that change only when we change them. A drift check asks "does this month look like last month?": it needs a reference dataset and changes with the world. Pandera can test statistics, but in a gate such a test fails whenever the world changes. On large data it also raises needless alerts: on 100 million values with 0.01% changed, a chi-square test fired one in 7 of 10 trials (Breck et al., 2019, p. 7). Put row rules in the contract, and compare distributions in a separate monitor (Week 12).

Lecture: "Keep drift checks out of the contract"

## Commands

| Command | What it does |
| --- | --- |
| `uv add "pandera[pandas]"` | installs Pandera with its pandas support |
| `Model.validate(df)` | checks a frame; raises `SchemaError` at the first problem |
| `Model.validate(df, lazy=True)` | checks every rule; raises `SchemaErrors` with `failure_cases` |
| `Model.to_schema()` | gives the `DataFrameSchema` object for a `DataFrameModel` |
| `make validate` / `make validate-broken` | runs `RawMeasurements` on the real data / on the broken batch |
| `make validate-model-input` | runs `ModelInput` before and after `to_nullable` |
| `make repro` / `make dag` | runs the pipeline / shows the `validate → prepare` edge |
| `make gate-fail` | plants a bad value and shows that the pipeline stops |
| `make metrics` | prints the evaluation metrics |
| `make link` | runs a fresh training run, tagged with the validation verdict |
| `make predict` / `make predict-bad` | sends a legal request / three bad requests through `PredictionInput` |
| `make trace` | prints the chain from the alias to the validation verdict |

## Key terms

- **Data contract**: the rules for a dataset, agreed between the team that produces the data and the teams that use it. Part prose, part code that runs.
- **Domain expert**: the person who knows what the data means and which errors cost; here, a doctor or a nurse.
- **Sentinel value**: a special value that stands for "missing" or "unknown", such as `0` in our data or `-9999` in NOAA's.
- **Schema / values / completeness / uniqueness / distribution errors**: the five types of data error; the first four can be checked on one file.
- **`DataFrameModel`**: Pandera's class-style schema; **`DataFrameSchema`**: the object style.
- **`Field`**: the rules for one column (`ge`, `gt`, `le`, `lt`, `isin`, `str_matches`, `nullable`, `unique`).
- **`coerce` / `strict` / `ordered`**: convert types first / an unnamed column is an error / the column order is part of the contract.
- **Lazy validation**: `lazy=True`; check every rule, then raise `SchemaErrors` (plural).
- **`failure_cases`**: the report table with one row per failure.
- **Ingestion contract / training contract**: describes what the source really sends / what the model may see.
- **Nullable type**: a type that can hold a missing value, such as pandas' `Float64`.
- **Imputer**: a step that fills missing values, here with the training median.
- **Data leakage**: information from the test set reaches training, so the test score looks better than it is.
- **Quality gate**: a pipeline stage that stops the pipeline when the data fails, and leaves a report.
- **Quarantine**: keeping a failed batch aside until someone checks it.
- **Training-serving skew**: the model gets different input when it serves than when it was trained.
- **Drift**: the data changes over time compared with a reference dataset (Week 12).
- **Thruster** (*kormányhajtómű*): a small rocket engine that adjusts a spacecraft's path.
- **Geolocation** (*helymeghatározás*): finding the place on Earth that belongs to an IP address or a device.

## How this connects to the lab

The lab adds one stage to the Week 4 pipeline. You:

1. write the ingestion contract, `RawMeasurements`, and see our 768 patients pass with the zeros allowed;
2. run it on `data/quality/broken_batch.csv` (60 rows, 4 faults) and trace each of the 7 failures to its fault;
3. write the training contract, `ModelInput`, and `to_nullable`: 652 failures before, 0 after;
4. break the data on purpose and see it reach the model; then add the `validate` stage to `dvc.yaml`, and show that `dvc repro` stops and the processed data stays unchanged;
5. put the imputer inside the model's `Pipeline` and compare the metrics;
6. optionally, send bad requests to the model, then put `PredictionInput` in front of it, and see the verdict on the training run;
7. commit your work.

Exercises 1–5 need no Docker; start the stack only for Exercise 6, and stop the Week 4 stack first, because both use the same ports. Traps you will meet:

- `pandera` without `[pandas]` has no pandas support.
- `except SchemaError` after `lazy=True` never runs.
- `float64` turns `<NA>` into `NaN`; use `Float64`.
- `to_schema()` returns one shared object, so copy it before you change it.
- `Field(required=False)` does not exist in the lab's Pandera version; write an optional column as `Optional[Series[int]]`.

## Recommended reading

- **Breck, Polyzotis, Roy, Whang and Zinkevich, "Data Validation for Machine Learning"**, SysML 2019 (https://mlsys.org/Conferences/2019/doc/2019/167.pdf). *Focus on:* Section 4 on training-serving skew, and the Google cases in Section 6.
- **Google, "Rules of Machine Learning"** (https://developers.google.com/machine-learning/guides/rules-of-ml). *Focus on:* Rules #10 and #29–32.
- **Pandera documentation: DataFrame Models, Checks, Lazy Validation** (https://pandera.readthedocs.io/en/stable/). *Focus on:* the `Config` options, and the difference between column and dataframe checks.
- **Designing Machine Learning Systems (Huyen), Ch. 4.** *Focus on:* how missing values and sampling decisions reach the model.
- **Gebru et al., "Datasheets for Datasets"** (https://arxiv.org/abs/1803.09010). *Focus on:* the prose part of a contract, written as a document. It comes back in Week 13.
- Optional: **Shankar et al., "Operationalizing Machine Learning: An Interview Study"**, arXiv:2209.09125 (2022). *Focus on:* Section 5.1.2, on alerts that nobody reads.
- Optional: **GX Core overview** (https://docs.greatexpectations.io/docs/core/introduction/gx_overview/). *Focus on:* what the Data Context, Checkpoints and Data Docs give an organisation.

(More reading: `docs/resources.md`.)

## Check yourself

1. Five patients in our data have a glucose of 0. Whose job is it to know that this is impossible, and whose job is it to notice it in every batch?
2. A data contract has a part for people and a part for the pipeline. What goes in each, and which part can stop a bad batch?
3. Sort these into the five types of data error: an extra column, `age = 250`, an empty cell, a row that appears twice, and a month in which most patients are older.
4. Why did no range check catch the MaxMind farm? Which check would?
5. The lab's broken batch has 4 faults, but the report lists 7 failures. How can one fault cause several failures, and which ones should you fix first?
6. Your ingestion contract uses `ge=0` on `glucose`, and the training contract rejects the same zeros. Defend this to a colleague who says the ingestion contract is wrong. What happens with the contract they propose?
7. A teammate moves `SimpleImputer` out of the `Pipeline` and into `prepare`, "so the processed files are already clean". The tests pass and the metrics do not change. What has broken, and when will someone notice?
8. `validate` exits with code 1 and `dvc repro` stops. Why is "`train.csv` has the same md5 as before" a stronger claim than the exit code?
9. A model was trained in February. In March, one bound in the contract changes. Which run tag tells you which rules the February model's data passed?
10. Your contract has passed on every batch for six months. What may you now believe about your data, and give three ways it could still be wrong.
