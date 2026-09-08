# Lifecycle of Artificial Intelligence Systems

A 14-week, hands-on MLOps course for software-engineering students. One running
example — a diabetes-prediction pipeline — is carried from a laptop script to a
monitored production service, adding one lifecycle capability each week
(reproducible runtimes, experiment tracking, data versioning, validation,
evaluation gates, CI/CT, orchestration, serving, rollout, observability, drift,
and governance).

> **New here? Start with [`docs/syllabus.md`](docs/syllabus.md), then do the
> one-time setup in [Getting the materials](#getting-the-materials-once-in-week-1).**

Rendered slides for the published weeks: **<https://vihibxav054-00.github.io/mlops-course>**

## Materials are released week by week

This repository grows as the term goes. Each week's lecture deck, lab starter
and study notes appear on the **morning of that week's lecture**; homework
briefs appear in the week the syllabus says they are handed out; reference
solutions appear about a week after the lab was taught.

So a folder you expected being absent is normal — it has not been published
yet, not lost. [`RELEASED.md`](RELEASED.md) lists what is out and the date each
remaining week arrives. To pick up what is new, pull (below).

## Getting the materials (once, in Week 1)

**Fork this repository, then keep it up to date.** The fork is yours to commit
lab work into; the `upstream` remote is where new weeks come from.

```bash
# 1. Fork on GitHub (the "Fork" button), or with the GitHub CLI:
gh repo fork VIHIBXAV054-00/mlops-course --clone --remote
cd mlops-course

# 2. If you forked in the browser instead, clone your fork and add upstream:
#    git clone https://github.com/<your-username>/mlops-course.git
#    cd mlops-course
#    git remote add upstream https://github.com/VIHIBXAV054-00/mlops-course.git

# 3. Check it worked — you want BOTH origin (yours) and upstream (the course):
git remote -v
```

Then **every week, before the lab**:

```bash
git pull upstream main      # fetch the new week
```

If that pull reports a conflict, it is nearly always in a lab file you edited.
Your work is in your fork's history and is not lost — the recovery is:

```bash
git stash                   # park your changes
git pull upstream main      # take the new week cleanly
git stash pop               # replay your changes on top
```

Do **not** push to `upstream`; you have no write access to it, by design.

## Repository map

| Path | What's in it |
| :--- | :--- |
| [`docs/syllabus.md`](docs/syllabus.md) | The 14-week plan and assessment. |
| [`docs/resources.md`](docs/resources.md) | Recommended books, free courses, papers — mapped per week. |
| `docs/exam-revision.md` | Revision guide for the Week 14 written exam — published in Week 13. |
| `docs/notes/` | Short study notes for each week. |
| `lectures/week-XX-topic/` | Lecture slides (Slidev). Rendered slides are published to the course Pages site. |
| `labs/week-XX-topic/starter/` | The lab you work in — exercises marked `TODO(student)`. |
| `datasets/` | The course dataset, per-dataset documentation, and the project-dataset catalogue. |
| `homework/` | Homework briefs, including the Week 2 "Define Project Topic" milestone. |
| `solutions/week-XX-topic/` | Reference solution for a lab, published about a week after that lab. |
| [`RELEASED.md`](RELEASED.md) | What is published so far, and when the rest arrives. |

(Answer keys, rubrics and teaching notes live in a separate private repository
and are never published here.)

## Prerequisites (one-time setup)

You need a laptop with **16 GB RAM** and:

- **Git** — https://git-scm.com/
- **uv** (Python project/dependency manager) — https://docs.astral.sh/uv/getting-started/installation/
- **Docker Desktop / Docker Engine + Compose** — https://docs.docker.com/get-docker/ (needed from Week 2 onward)
- **kind** — https://kind.sigs.k8s.io/docs/user/quick-start/#installation (needed from Week 9 onward)
- **kubectl** — https://kubernetes.io/docs/tasks/tools/ (needed from Week 9 onward)

`kind` runs a Kubernetes cluster inside Docker; both are single binaries and neither needs a
cloud account. From Week 9, **do not run the Compose stack and the cluster at the same time** on
16 GB — you will not need to, because the Week 9 serving container is self-contained.

From **Week 10** the cluster also runs a serving control plane (cert-manager, Istio, Knative and
KServe): about 2.5 GB of images and ~2.3 GiB of RAM before your model is even deployed, installed by
a `make` target in the lab. Still no new host tool, and still nothing to sign up for — but keep the
Compose stack down that week.

**Week 11 is the reverse**: delete the cluster (`kind delete cluster --name mlops`) and bring the
Compose stack back, now with Prometheus and Grafana alongside the existing four services. Nothing
that week needs Kubernetes. Still **no new host tool** — `promtool` ships inside the Prometheus
image and is run through `docker compose`.

**Week 12 adds nothing to install and nothing to run.** The cluster stays down, the Compose stack
stays up, and there is **no new service and no new port** — because the drift monitor is a *job*
rather than a server. It does add one substantial Python dependency (`evidently`), and it is declared
in a dependency **group** so the serving container never installs it.

**Week 13 adds one container and no Python dependency at all.** Alertmanager on **5570**, pinned in
`compose.yaml`, with `amtool` inside it — so there is no new host tool either. Governance turns out to
be `hashlib`, `json`, string formatting and YAML: `uv.lock` moves by the project name and nothing else.
The cluster stays down.

**Week 14 has no lab.** The syllabus reserves the slot as a spare session; the lecture is a summary and
an LLMOps outlook, and the revision guide for the written exam is
`docs/exam-revision.md`, published in Week 13. Nothing new to install, ever again.

Python itself is installed for you by `uv`. Windows, macOS, and Linux are all supported.

## Running a lab

Each lab is a self-contained `uv` project. From a lab's `starter/` directory:

```bash
uv sync --all-groups       # create the environment from the lockfile
uv run python src/main.py  # run the pipeline
uv run pytest -v           # run the tests
```

Labs from Week 2 onward also start local services with one command:

```bash
docker compose up -d --wait
```

Per-lab `README.md` files give the exact steps, expected output, and the
official tutorial each lab is based on.

## Homework & your project

The five homework assignments are **not** done in this repository. In Week 2 you
create your own **private** project repo from the project template — click *Use
this template* on **<https://github.com/VIHIBXAV054-00/mlops-project-template>** — and grow it across HW1-HW5. Keeping it
separate is what lets this repository keep updating underneath you without ever
touching your graded work.

In Week 2 you also choose a dataset and prediction task (see
[`homework/project-topic/`](homework/project-topic/)) that you carry through all
five homework assignments. Need ideas? See the
[dataset catalogue](datasets/README.md). If you have no preference, the course
Pima diabetes dataset is the fallback.

## Licensing

- **Code** (labs, scripts, config): MIT — see [`LICENSE`](LICENSE).
- **Content** (slides, notes, docs): CC BY 4.0 — see [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md).
- **Datasets**: per upstream license, documented in [`datasets/`](datasets/).
