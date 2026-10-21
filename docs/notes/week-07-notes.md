# Week 7 — CI/CT Principles — Study Notes

These notes go with the Week 7 lecture and lab. Weeks 5 and 6 built two gates: one refuses bad data at the entrance, one refuses a bad model at the exit. Both run only when someone remembers to run them. This week a machine runs them on every change. Doing so shows a second way for a change to reach production: a retrained model.

## Why this matters

**CrowdStrike (2024).** CrowdStrike sells security software for Windows computers, and ships two kinds of update. New sensor code goes through tests and a staged release: CrowdStrike's own staff first, then early adopters, then everyone. New detection rules for a rapid response ("Rapid Response Content", with no code change) go through one check, the Content Validator, and then to all computers at once.

On 19 July 2024, new rules went out at 04:09 UTC and were withdrawn at 05:27. Microsoft estimated that **8.5 million Windows devices** were affected, "less than one percent of all Windows machines", many of them at "enterprises that run many critical services". Delta Air Lines cancelled about **7,000 flights** over five days (Form 8-K, 8 Aug 2024), and the insurer Parametrix estimated that US Fortune 500 companies, without Microsoft, lost **$5.4 billion**. It was not a cyberattack, and the sensor code did not change.

CrowdStrike's root cause analysis (6 Aug 2024) explains how the rules got through. Their definition had **21** input fields, while the sensor code supplied only **20**. The Content Validator checked each new rule file against the definition, so the file passed; nobody compared the definition with the code. The earlier rules, and every test, put "match anything" in field 21, so the sensor never read it. On 19 July a rule used field 21 for the first time. The sensor read a value that was not there, and Windows crashed.

CrowdStrike had a strict release process for code, and this update was not code. There were two ways to reach a customer's computer, and only one of them had all the tests. New data is similar: it changes what your model does, but nobody can review it by reading a diff. The checks that happen in code review are not on that path.

**Knight Capital (2012).** On 1 August 2012, a technician copied new trading code by hand to eight servers and missed one. The eighth server still ran old code, which the new code switched on by mistake. In 45 minutes Knight made 4 million trades in 154 stocks and lost more than $460 million. The SEC found no second review of the deployment and no written procedure that required one. Before the market opened, 97 automated emails reading "Power Peg disabled" reached Knight's staff, and nobody acted on them (US SEC, Release No. 70694, 16 Oct 2013). The lesson: automate every step that changes production, and check its result.

**A loop with no limit (2011).** On Amazon, two sellers offered Peter Lawrence's *The Making of a Fly*, a biology book. Programs set their prices every day: one at 0.9983 times the other's price, the other at 1.270589 times. Both prices grew by about 27% a day. On 18 April 2011 the book was listed at **$23,698,655.93**, plus $3.99 shipping. The next day someone noticed, and the price fell to $106.23 (Michael Eisen, *it is NOT junk*, 22 April 2011). Both programs did what they were told. Nothing checked the result: one line, a maximum price, would have stopped it. That is the job of the gate you wrote last week, and this week it runs by itself.

## Core concepts

### Every path into production

A change can reach production on more than one path. A **code change** goes through review, where someone reads a diff, and through tests. **New data** changes the model too. In our project a new batch is a commit, because the data's pointer is in Git (Week 4), but its diff is one new md5, which no reviewer can judge. In many teams, new data lands in a warehouse and a clock starts the retraining, with no commit at all (see "Continuous training" below). On a data path the checks must be automatic: the data contract and  gate. Today they run only when someone types `dvc repro`.


### What is continuous integration?

**Continuous integration (CI)** means that the team merges small changes often, and a machine checks every change automatically, on a machine that is not yours. Each part matters:

| Without | What breaks |
| --- | --- |
| every change | several changes fail at once, and nobody knows which one broke it |
| automatically | someone forgets to run it |
| not yours | it passes because of something only your laptop has |

Your laptop has things the repository does not. A `.env` file is never committed. A package was installed by hand and is missing from `uv.lock`. A data file was pulled months ago. A service such as MLflow or Silo is still running. A fresh runner has none of them. So make the build create everything it needs from the repository: the data, a default `.env`, the packages in the lock file. In the lab, `make ci` copies `.env.example` when there is no `.env`, and rebuilds the data from committed batches.

A team with no CI tool, but with a rule "run `make check` before every push", has the practice and no enforcement. It works until someone is in a hurry.

Is it worth it? Hilton et al. (2016) studied 34,544 open-source projects on GitHub and surveyed 442 developers. Projects with CI released 0.54 times a month, those without 0.24; the same projects released 0.34 times a month before they added CI. With CI, the median pull request was accepted 1.6 hours sooner. The costs: an average build took just under 500 seconds, and the configuration needs changes. Of the developers without CI, 47% said the team did not know CI well enough, and 44% said the project had no automated tests. CI runs only the tests you have.


### Tool options

GitHub Actions, GitLab CI/CD, Jenkins, CircleCI and Azure Pipelines all keep the pipeline in a file in the repository. So a change to the pipeline is reviewed like a change to the code. The course uses GitHub Actions, because your repository is on GitHub.

### The ML test pyramid

An ML system can break in four places: our code, the data, the model, and the parts working together. Ordinary software tests only the first and the last. Breck et al. (Google, 2017) describe tests for each part. The course uses four layers:

| Layer | Question | Example |
| --- | --- | --- |
| **unit** | Is our code correct? | `to_celsius(32)` returns 0 |
| **data** | Is the data what we agreed? | every row of the batch passes the ingestion contract |
| **eval** | Is the model good enough? | the new model's F1 is not lower than the champion's |
| **integration** | Do several parts work over a real connection? | a training run appears in MLflow with its data tag |

The shape comes from Mike Cohn's test pyramid (see Ham Vocke, "The Practical Test Pyramid", 2018). Lower layers are fast and many; higher layers are slow and few. CI runs the bottom three. Some tests fit two layers, for example a test of the gate's own code: it needs no model, but it protects the release decision.

### Why integration tests stay out of CI

The word "integration" has two meanings. **Continuous integration** merges every change into the main branch often; an **integration test** runs several parts together, over a real connection. Our CI integrates every change, but leaves the integration tests out.

Our CI leaves out tests that need Postgres, Silo or MLflow because starting and waiting for those services on every push is slow and can fail for reasons unrelated to the code. These connections change less often than the code, data and model checks that CI already runs. Teams that need integration tests usually run them in a slower job after a merge or overnight, often with service containers. In this course, later pipelines must also run on a bare runner with no services.


### Pytest markers

A marker puts a label on a test, and `pytest -m` runs only the tests with that label. Register each marker in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: our code is correct",
    "data: the data is what we agreed",
]
```

Put `@pytest.mark.unit` above a test, or write `pytestmark = pytest.mark.unit` at the top of a file to mark every test in it. Then `pytest -m unit -q` runs one layer and prints how many tests it left out, for example `1 passed, 2 deselected`. A marker that is not registered, such as the typo `@pytest.mark.untt`, gives only a warning; the `strict_markers` option turns it into an error.

We use markers of two types; both are ordinary pytest markers, and a test can carry one of each. The **layer** (`unit`, `data`, `eval`, `integration`) says what the test checks, and CI runs one job per layer. The **guard** (`live` for the Docker stack, `dvc` for a DVC repository) says what the test needs to run, and CI leaves it out with `-m "not live and not dvc"`. In the lab, `test_dvc_repo.py` holds data tests that need a DVC repository: `pytestmark = [pytest.mark.data, pytest.mark.dvc]`. Keep the two apart, so that "leave out what needs a service" does not also leave out a whole kind of check.

If CI runs one job per layer, a test with no layer runs in no job. It never fails CI, whatever it checks. To find such tests, run `pytest -m "not unit and not data and not eval and not integration"`. It must select 0 tests.

Lecture: "Pytest markers", "Marker types" · Lab: Exercise 3

### GitHub Actions example

A workflow is a YAML file in `.github/workflows/`. GitHub's quick start builds one in a few lines, and it answers four questions:

| Key | Means |
| --- | --- |
| `on` | when the workflow runs, for example `[push, pull_request]` |
| `jobs` | what runs; jobs run in parallel unless one `needs` another |
| `runs-on` | where: a fresh virtual machine, deleted after the job |
| `steps` | which commands, in order |

Nothing survives between jobs. Each job checks out the code and installs the dependencies again, unless a step uploads something.

GitHub reads workflows only from `.github/workflows/` at the **repository root**. A workflow in a subfolder, such as `ml/.github/workflows/ci.yml`, never runs, and GitHub shows no error. The lab keeps its workflows next to the code they test, and `make install-ci` copies them to the root as `week07-ci.yml` and `week07-ct.yml`.

Lecture: "GitHub Actions example" · Lab: Exercise 4

### `uses:` and `run:`

A `run:` step is a shell command from your repository, such as `run: make lint`. A `uses:` step runs someone else's program in your job, such as `uses: actions/checkout@v7`. It can read your code, change files in your checkout, and use the job's `GITHUB_TOKEN`, even if you never pass it. It is closer to `curl … | sh` with a version number than to `import`. The `permissions:` key limits what the token may do; GitHub advises giving actions "only the minimum access they require".

Lecture: "`uses:` and `run:`"

### Pinning actions

The text after `@` says which code of the action you run:

| Pin | Example | Means |
| --- | --- | --- |
| a branch | `actions/checkout@main` | new code on every commit to `main` |
| a major tag | `actions/checkout@v7` | new code within v7: fixes arrive by themselves |
| a release tag | `astral-sh/setup-uv@v9.0.0` | one release, unless its owner moves the tag |
| a commit SHA | `actions/checkout@<40 hex characters>` | never changes |

GitHub says a full-length commit SHA is "the only way to use an action as an immutable release". A major tag is a compromise: you get security fixes without an edit, but the code you run tomorrow is not the code you reviewed today. A SHA pin needs a tool such as Dependabot or Renovate to update it, or it goes stale. The lab pins major tags, and setup-uv to its release tag `v9.0.0`, because there is no `v9` tag.

On 6 August 2026, all six action pins in the course repository's workflows were 1–3 major tags behind (measured with the lab's `make ci-explain`). They were updated to the newest releases. On that day the newest setup-uv release was `v9.0.0`, but its newest major tag was `v7`. So `uses: astral-sh/setup-uv@v9` stopped every job before its first step with `unable to find version v9`. The fix was `@v9.0.0`, the exact release tag. The GitHub API answers "what is the newest release?", not "which tag exists?". Pin what CI runs, and check that the pin exists.

Lecture: "Pin examples", "Our pins on 6 August 2026" · Lab: Exercise 1

### The job graph and the matrix

The lab's `ci.yml` has five jobs. `lint` and three test jobs (`unit`, `data`, `eval`) run side by side. `lint` is a job of its own because it fails in seconds: nobody should wait for the tests to hear about an unused import. The `pipeline` job trains a model, so it waits for the lint and test jobs (`needs:`). Training on a branch whose tests fail only wastes runner time. In the lab's first green run on GitHub, the jobs took 12, 22, 25, 36 and 53 seconds.

The three test jobs come from one definition, a **matrix**: one copy of the job per value. In the lab's `ci.yml`, `layer: [unit, data, eval]` gives the jobs `test (unit)`, `test (data)` and `test (eval)`, and each step reads its copy's value as `${{ matrix.layer }}`. A red `test (data)` names the layer at a glance; one job for all tests says only "tests failed". The same key runs a job on several Python versions or operating systems, the usual example in the docs. By default, when one copy fails, GitHub cancels the others; `fail-fast: false` lets them finish, so you learn whether the other layers are broken too. The cost: each copy installs the dependencies again.

Lecture: "The job graph", "One job per test layer" · Lab: Exercise 4

### One pipeline definition

Your laptop, `ci.yml` and `ct.yml` all call the same Makefile targets, and no workflow lists the commands itself. If a workflow lists them, it is a second copy of the build, and every change to the pipeline must be made twice. Say you add the gate to the Makefile and forget `ci.yml`: CI never runs the gate, and stays green. In the lab a test reads every `run:` line of both workflows and fails if one calls `src/main.py` directly. A rule with a test lasts longer than a rule in a README. The tool does not matter: a shell script or a task runner works too, as long as there is one definition.

Lecture: "One pipeline definition" · Lab: Exercise 2

### Service containers

A job can start a database next to it, for its tests to use: a **service container** (`jobs.<job_id>.services`). The pro: integration tests can run in CI. The con: every run starts the service and waits for it, and a slow start looks like a failing test. Our CI does not use them.

Lecture: "Service containers"

### What our CI does not need

The lab's CI needs no Docker, no MLflow, no Silo, no secrets and no `dvc pull`. Earlier decisions made that possible:

| Week | Decision | What CI gains |
| --- | --- | --- |
| 4 | the dataset rebuilds from batches committed to Git | no object store, no credentials |
| 4 | `train` checks whether MLflow answers | training skips the run log instead of failing |
| 5 | the contracts read committed files | validation runs offline |
| 6 | the gate is a pure function: numbers in, verdict out | the gate needs no server |

Had any of these gone the other way, CI would need a Postgres, a Silo and an MLflow container, plus credentials. In the lab, `make ci` runs from a clean checkout with the stack down in about 19 seconds. The price: CI can train, evaluate and gate, but it cannot register or promote a model, because that needs the tracking server. Design the pipeline so that it runs on a bare machine, from the first week of the project. This is common practice, called **hermetic** builds and tests. Everything a build needs comes from the repository, not from a service that happens to be running (Bazel docs, "Hermeticity"; Google Testing Blog, "Hermetic Servers", 2012).

Lecture: "What our CI does not need" · Lab: Exercises 2 and 4

### A red build you can read

A failed run should say why it failed, without making you open the logs. GitHub Actions gives three ways:

- an **annotation** (`echo "::error title=...::message"`): one line at the top of the run, for someone scanning the pull request;
- a **job summary** (append Markdown to `$GITHUB_STEP_SUMMARY`): a table on the run page, for someone deciding whether to care;
- an **artifact** (`actions/upload-artifact`): the files, for someone debugging.

By default, a failed step skips every step after it. A condition changes that: `if: failure()` runs a step only when a step before it failed, and `if: always()` runs it even after a failure. A step that writes evidence must still run on a failed build, or the run that most needs evidence leaves none. This is the same rule as Week 5's gate: write the report first, then stop.

Lab: Exercises 4 and 6

### Continuous training

**Continuous training (CT)** is retraining started by a person, a clock or new data, with no code change. In GitHub Actions, `workflow_dispatch` lets a person start it from the Actions tab. An input, such as a note on why, can be printed into the run's log. `schedule` with a cron line, such as `"30 2 * * *"` (every day, 02:30 UTC), starts it on a clock. A CT workflow must not run on `push`, or it is a slower copy of CI. `ct.yml` calls the same Makefile as `ci.yml`.

On a retraining at 02:30 at night, nobody waits for the result, there is no diff to review, and nobody approved the new data. Only the checks inside the pipeline look at the new model: the data contract and the gate.

A clock is not fully reliable. GitHub says a scheduled run can be delayed under high load, for example at the start of every hour, and "some queued jobs may be dropped". GitHub advises scheduling at a different time of the hour, such as 02:30 rather than 02:00. In a public repository, scheduled workflows are switched off after 60 days with no repository activity. The docs page does not say that you are warned, so check the Actions tab: you will not notice a run that never happened. Knowing that a scheduled run happened, and retrying it, is Week 8.

Lecture: "Continuous training", "The model was retrained at 02:30 last night. Who checked it?", "Can a clock be trusted?" · Lab: Exercise 5

### What can a green build hide?

A green build can hide four things:

- a missing check: green means only that the checks you wrote passed;
- a threshold set too low: the model met the bar you chose;
- a skipped test: pytest counts it, and the job stays green;
- a workflow that never ran: one outside the root `.github/workflows/`, or a schedule that GitHub switched off.

CrowdStrike's Content Validator ran, and passed the file that crashed the computers. "Why did CI not catch it?" has an answer: CI checked what it was told to. After every incident, find the check that was missing, and add it to CI.

Lecture: "What can a green build hide?"

### What identifies a model?

Ordinary software has one identifier, the commit. A trained model needs four:

| Identifier | Says | Added in |
| --- | --- | --- |
| Git commit | which code | Week 3 |
| data md5 | which data | Week 4 |
| params | which settings | Week 3 |
| registry version | which file | Week 3 |

Week 6 added the gate verdict and `criteria_version` to the same trace, and the lab's `make trace` prints them for the model behind an alias. A model is code and data, so when the data lives outside the repository, the same commit retrained a week later gives a different model.

Lecture: "What identifies a model?"

### Branching options

A branching model says how changes reach `main`. Three are common:

| Model | How it works | Fits |
| --- | --- | --- |
| trunk-based development | everyone merges small changes into `main` at least once a day | small changes and a fast CI |
| GitHub flow | a branch and a pull request for each change, then a merge, then the branch is deleted | one version in production |
| Git flow | long-lived `main` and `develop` branches, with feature, release and hotfix branches | several released versions in use at once |

DORA's research links three or fewer active branches, and merging into `main` at least once a day, with better delivery. Vincent Driessen, who published Git flow in 2010, added a note in 2020: a team that delivers continuously should use a simpler workflow, such as GitHub flow. Our model service has one version in production, so short branches and pull requests fit it. A retrain needs no branch: a scheduled workflow runs on the newest commit of the default branch.

Lecture: "Branching options"

### Which model made this prediction?

Branches and release tags work as in any project: a short branch, a pull request that runs CI, a merge to `main`, and a release tag such as `v1.4.0`. A release tag names the code. Now a nightly retrain runs on `v1.4.0` and produces registry versions 7, 8 and 9 on Monday, Tuesday and Wednesday; each night the alias `@champion` moves to the version that passed the gate. A user reports a bad prediction from Tuesday. The tag cannot say which model made it. Version 8 did: the one `@champion` pointed to on Tuesday (its `promoted_at` tag). That version's run holds its commit, data md5 and params. In Week 9, the service returns the model version with every prediction, which closes this gap.

Lecture: "Which model made this prediction?"

## Red flags and good practices

### Pin the linter and its rules

On the code Week 7 starts from (the Week 6 solution), ruff 0.16.1 with its default rule set reports **22** findings from 10 rules. With the rules of older ruff releases written out, `select = ["E4", "E7", "E9", "F"]`, it reports **2**, both unused imports. Newer ruff releases select more rules by default, so an unpinned linter can fail a build on a day you changed nothing. The lab pins `ruff==0.16.1` in a `lint` dependency group and sets `select` in `pyproject.toml`. Pin the version of every tool CI runs, and list the linter's rules.

Lecture: "Pin the linter and its rules" · Lab: Exercise 2

### Key the cache on the lock file

CI saves the installed packages between runs, to install faster. Then `uv.lock` changes. If the cache is keyed on the branch name, the key stays the same and the old cache is reused. CI tests last month's packages, and you debug a failure that exists on no real machine. If it is keyed on a hash of `uv.lock`, the key changes and CI installs the packages in the lock file. setup-uv's `enable-cache: true` keys its cache on a hash of `uv.lock` and `pyproject.toml`, and it saves only the downloads; `uv sync --locked` still decides what is installed. Key every cache on a hash of the files that define its contents. When CI fails and your laptop does not, clear the cache before you debug.

Lecture: "Key the cache on the lock file"

### Make switching a check off visible

The gate says NO-GO every week, and the team is tired of red builds. Someone adds one line, `continue-on-error: true`, to the pipeline job. The run is green even when the job fails: the gate still runs, and nobody reads it. The same move exists in many forms: `|| true`, a skipped test, a threshold lowered to the last score. Weaken a check only in a reviewed pull request, with a reason, an owner and a date to look at it again.

Lecture: "Make switching a check off visible"

## Commands

| Command | What it does |
| --- | --- |
| `pytest -m unit` | runs only the tests marked `unit` |
| `pytest -m "not unit and not data and not eval and not integration"` | finds tests with no layer; must select 0 |
| `make test-unit` / `make test-data` / `make test-eval` | runs one layer of the pyramid |
| `make ci` | the one pipeline definition: lint, tests, pipeline and gate, with the stack down |
| `make ci-local` | everything `ci.yml` does, on your machine, in the runner's order |
| `make ct-local` | what `ct.yml` does: retrain and gate, with no code change |
| `make ci-explain` | lists the workflows' action pins and how old they are |
| `make install-ci` / `make uninstall-ci` | copies the lab's workflows to the repository root / removes them |
| `make ci-fail` | plants `train.C: 0.005`, runs `make ci`, and restores `params.yaml` |
| `make trace` | prints the code, data, params and verdict for the model behind an alias |

## Key terms

- **CI (continuous integration)**: the team merges small changes often, and a machine checks every change automatically.
- **CT (continuous training)**: retraining started by a person, a clock or new data, with no code change.
- **Workflow / job / step**: the YAML file / a unit of work on one runner / one command or action.
- **Runner**: the fresh machine a job runs on, deleted after the job.
- **`run:` / `uses:`**: a shell command from your repository / someone else's program, run in your job with its token.
- **Matrix**: one job definition that runs as several copies, one per value.
- **`needs:`**: a job waits for the jobs it names.
- **`fail-fast: false`**: when one matrix copy fails, the others still finish.
- **Annotation / job summary / artifact**: the three ways a run tells you what happened.
- **`if: always()`**: run this step even when an earlier one failed.
- **Test layer**: `unit`, `data`, `eval`, `integration`: what a test checks.
- **Integration test**: a test of several parts together, over a real connection; a different "integration" from the one in CI.
- **Guard marker**: `live`, `dvc`: what a test needs to run.
- **Pinning**: a branch (moves on every commit), a major tag (moves within the major), a release tag (one release, unless its owner moves the tag), a commit SHA (never changes).
- **Service container**: a database or queue started next to a job; this project needs none.
- **Hermetic build**: a build that needs nothing outside the repository, so it runs the same on any machine.
- **Cron**: a line of five fields that says when a scheduled job runs.
- **Branching model**: how changes reach `main`; trunk-based development, GitHub flow and Git flow are the common ones.

## How this connects to the lab

Exercise 1 has you open `autograde.yml`, the workflow that has graded every push since Week 1, and list its pins with `make ci-explain`. Exercise 2 writes `make ci`, the one pipeline definition both workflows call. Exercise 3 gives every test module a layer marker, so the make target of each layer selects its tests; Exercise 4 runs each layer as its own job. Exercise 4 writes `ci.yml` with the job graph, the artifact, the job summary and the annotation, then installs it at the repository root and pushes. Exercise 5 writes `ct.yml` and asks what must differ from `ci.yml`. Exercise 6, which is optional, pushes the Week 6 regression (`train.C: 0.005`) and has you inspect the failed build.

In Exercise 6, read the whole failed run before you answer: which jobs passed, which one failed and at which step, and what the run left behind for you to read.

`tests/test_workflows.py` is your specification. It parses the YAML and checks the structure, so a missing `needs:` or an unpinned action fails in milliseconds, before a push and a queue. It also checks every `make` target a workflow calls against the Makefile. While the lab was built, a workflow called `make gate-summary` before the Makefile defined it, and only a real runner noticed. Remove its skip markers one at a time, and let the failures tell you what is missing.

## Recommended reading

- **GitHub Actions quick start and workflow syntax**: the main references, and short.
  https://docs.github.com/en/actions/get-started/quickstart ·
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- **Workflow commands**: annotations and `$GITHUB_STEP_SUMMARY`.
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- **Events that trigger workflows, `schedule`**: delays, dropped runs and the 60-day rule.
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- **Astral, "Using uv in GitHub Actions"**: the caching guidance the lab follows.
  https://docs.astral.sh/uv/guides/integration/github/
- **Breck et al., "The ML Test Score"** (Google, 2017): where the test layers come from; read the Infrastructure and Monitoring sections this week.
  https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/
- **Sculley et al., "Hidden Technical Debt in Machine Learning Systems"** (NeurIPS 2015): why CI for ML is not ordinary CI; the CACE principle and pipeline jungles.
  https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf
- **CrowdStrike's Preliminary Post Incident Review and External Technical Root Cause Analysis**: a rare, detailed first-party account of a failure on a second release path. Worth reading in full.
- **Hilton et al., "Usage, Costs, and Benefits of Continuous Integration in Open-Source Projects"** (ASE 2016): what CI changed in 34,544 projects, and why some teams do not use it.
  https://doi.org/10.1145/2970276.2970358
- **Vincent Driessen, "A successful Git branching model"** (2010): Git flow, and his 2020 note on when not to use it.
  https://nvie.com/posts/a-successful-git-branching-model/
- **Ruff's linter documentation**: how `select` works, and why the default rule set depends on the version. https://docs.astral.sh/ruff/linter/

## Check yourself

1. Your CI is green on every push. Name three things that green does **not** tell you, and for each one say what would.
2. Explain why the lab's `pipeline` job needs no service containers. Name at least two decisions from Weeks 4–6 that made that possible, and say what CI would need if they had gone the other way.
3. A colleague copies your pipeline commands into `ct.yml` instead of calling `make`. The build is green and the diff looks harmless. Describe the failure this causes, when it shows up, and which test in the lab would have caught it.
4. In August 2026, `astral-sh/setup-uv`'s newest release was `v9.0.0`, and `uses: astral-sh/setup-uv@v9` failed. Explain why, give the correct pin, and say what this tells you about an API that answers "what is the newest version?".
5. Your CI is called continuous integration, but it leaves the integration tests out. Give two reasons, and say how a team that needs those tests would still run them.
6. Your team runs one model service, and a scheduled workflow retrains it every night. Which branching model fits, and why does the retrain need no branch? A user complains about yesterday's prediction from release `v1.4.0`: what does the tag tell you, and how do you find the model that made it?
