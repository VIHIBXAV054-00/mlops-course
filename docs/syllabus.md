# Course Syllabus: Lifecycle of Artificial Intelligence Systems

## Course Objectives

The primary objective of this course is to equip students with an engineering mindset to understand and practically apply the complete model lifecycle management of Artificial Intelligence (AI) systems. The curriculum spans from initial requirements and data pipelines through development and validation, all the way to operations and continuous, feedback-driven improvement. 

Built heavily upon industrial MLOps practices, the course covers reproducibility, versioning and experiment tracking, automated quality assurance (testing and evaluation), CI/CD-based deployment, observability (monitoring and drift detection), incident management, and governance. Furthermore, the course provides an outlook on LLM-based systems (RAG pipelines, agentic architectures), with a specific focus on their operational challenges.

Upon successful completion, students will be capable of independently designing and maintaining production-ready, scalable, end-to-end AI pipelines that meet modern industrial and research standards. They will also be prepared to assume various roles within the AI system lifecycle (e.g., Data Scientist, Machine Learning Engineer, MLOps Engineer) and effectively collaborate and communicate with stakeholders across the entire process.

---

## Prerequisites & Audience

The course is designed for software engineering students. Expected background:

* **Programming:** Solid general programming skills and Git basics. Working Python familiarity (the course uses Python throughout but does not teach it).
* **Machine Learning:** A completed introductory ML course. We assume students have seen train/test splits, basic models, and evaluation metrics; Week 1 only briefly refreshes these. The ML used in labs is deliberately simple (Scikit-learn on tabular data) — the focus of this course is the engineering lifecycle, not modeling.
* **No prior experience assumed** with Docker, MLflow, DVC, Prefect, Kubernetes, or monitoring tooling — these are taught from scratch.

## Course Approach

* **One running example:** A single Scikit-learn pipeline predicting diabetes onset from real diagnostic data (Pima Indians Diabetes dataset, established in Week 1) is carried through the entire semester. Each week adds one lifecycle capability to the same project rather than introducing new toy problems.
* **Tutorial-first:** Labs follow the official getting-started tutorials of each tool (MLflow, DVC, Pandera, Prefect, KServe, Evidently, etc.) with minimal changes, so official documentation remains directly usable as a reference.

## Technical Requirements

Students need a laptop with Docker support and at least 16 GB RAM (later weeks run several services locally: Postgres, MLflow, MinIO, Prometheus, Grafana, and a local Kubernetes cluster). Setup is covered in the Week 1 lab. Windows, macOS, and Linux are all supported.

---

## Weekly Schedule

The following table details the theoretical lectures, practical laboratory exercises, and homework (HW) milestones throughout the 14-week semester.

| Week | Lecture Topic | Laboratory Exercise | Assignments |
| :--- | :--- | :--- | :--- |
| **Week 1** | **Introduction to MLOps:** Goals, role in ML practice, ML lifecycle vs. DevOps. Concepts of reproducibility, scalability, and automation. Roles and tool overview (Git, Docker, MLflow, CI/CD). | **Dev Environment:** Cross-platform setup (Python, Git, Docker). Repo structure, entry points, `.env` configs, and running/versioning a baseline ML pipeline. | - |
| **Week 2** | **Reproducible Runtimes:** Developer runs vs. reproducible environments. The role and storage of artifacts and metadata. | **Local Services:** Docker Compose setup separating artifacts (MinIO), metadata (MLflow), and databases (Postgres). "One-command" startup. | **Project topic due (W2)** |
| **Week 3** | **Experiment Tracking:** MLflow from an engineering perspective. Logging parameters, metrics, plots. Model registry: versions, aliases, promotion, and traceability. | **MLflow Integration:** Running the baseline model, logging metrics/plots, registering models, and promoting to staging. | - |
| **Week 4** | **Data Versioning:** Data lifecycle (DVC + MinIO). Dataset snapshots, pipeline stages, and data lineage basics. | **DVC Introduction:** Adding data to DVC with MinIO as the S3-compatible remote storage, `dvc.yaml` pipeline setup, and linking runs to MLflow. | - |
| **Week 5** | **Data Quality:** Data contracts and quality gates. Types of data errors, training-serving skew, and automated validation. Tooling landscape (Pandera, Great Expectations). | **Data Validation:** Introduction to Pandera schemas. Inserting validation into the data prep pipeline. | **HW1 out** |
| **Week 6** | **Model Quality Gates:** Automated evaluation and decision points. Metric regression, acceptance criteria, slice-based evaluation, and basic Responsible AI/fairness checks. | **Evaluation Pipeline:** Recording baseline metrics, implementing regression tests, slice metric calculation, and "go/no-go" rules. | — |
| **Week 7** | **CI/CT Principles:** Continuous Training vs. classic CI. Versioning strategies (branching, release tags) and automated testing (unit, data, eval tests). | **CI Workflow:** Creating a GitHub Actions workflow covering linting, testing, model training, and evaluation. | **HW2 out** |
| **Week 8** | **Orchestration:** Operational ML workflows. Scheduling, retries, parameterization, and pipeline-level observability. | **Prefect Flow:** End-to-end training chain (prepare, validate, train, evaluate, register) with parameters and retry policies. | **HW1 due** |
| **Week 9** | **Model Serving & Deployment:** Batch vs. online inference, latency/throughput, containerization patterns, and an introduction to Kubernetes concepts. | **Containerized Serving:** Serving the registered model as a REST API (FastAPI / `mlflow models serve`) in Docker. Local Kubernetes cluster setup from provided templates. | **HW3 out** |
| **Week 10** | **Rollout Strategies:** Declarative deployment with KServe. Canary/blue-green deployments, gradual rollouts, rollbacks, smoke testing, and basic load testing. | **KServe InferenceService:** First KServe model deployment, managing multiple model revisions, traffic splitting (e.g., 90/10), and endpoint testing. | **HW2 due** |
| **Week 11** | **Observability:** Metrics, SLI, SLO, and alerting. Differences between logs/metrics/traces. Avoiding alert fatigue. | **Prometheus & Grafana:** Metric collection, dashboard creation (latency, RPS, error rate), and basic alerting rules. | **HW4 out** |
| **Week 12** | **Drift & Degradation:** Data drift vs. concept drift. Monitoring strategies, proxy metrics, and reaction protocols (retraining triggers, rollbacks). | **Drift Reporting:** Evidently (or custom stats), documenting drift signals, adding drift alerts, and optional retraining triggers. | **HW3 due** |
| **Week 13** | **Governance & Responsible AI:** Auditability, evidence requirements, Model Cards, incident management, postmortems, and kill-switches. | **Model Cards & Incidents:** Filling out a Model Card template. Simulating an incident (drifting metric) and the resulting decision process. | **HW5 out** · **HW4 due** |
| **Week 14** | **Course Summary & LLMOps:** The whole lifecycle in one picture; refusals vs. records; cloud alternatives (e.g., Azure ML) and what they cannot decide for you; an outlook on operating LLM-based systems — which of the thirteen mechanisms survive when the model is somebody else's. | **Spare Session:** Buffer for delayed labs or exam preparation. **No new lab.** | **HW5 due** · **ZH (written test)** |

---

## Assessment

This is a **mid-semester-grade** subject: everything is assessed during the teaching period, and nothing happens in the examination period.

### Requirements during the teaching period

All three must be met — they are thresholds, not weights, and failing any one of them fails the semester:

1. **Labs — 70% completed.** Of the 13 laboratory exercises, at least **10** must be completed successfully. If exercises are cancelled because of a mid-week public holiday or teaching break, the threshold moves with the count: **12 labs → 9**, **11 labs → 8**.
2. **Homework — at least 4 of the 5** small assignments at a satisfactory level, each individually scoring **at least 50%** of its available points.
3. **Written test (ZH) — at least 50%** of the available points.

### Grade

With all three met, the mid-semester grade is:

> **Grade = 0.6 × (HF1 + HF2 + HF3 + HF4 + HF5) / 5 + 0.4 × ZH**

The homework mean includes **all five** assignments, including any that were not submitted — only four have to *pass*, but a missing fifth still enters the average as a zero.

### Retakes

| Component | Repeatable? |
| :--- | :--- |
| A missed or failed **laboratory exercise** | **No** — labs cannot be made up. |
| **Homework** | **One** of the five, during the retake week. |
| **ZH** | Once, during the retake week. There is no second retake. |

### Delivery

* **Odd weeks (in person):** a practice-oriented lecture, followed by a related laboratory exercise in which students apply the new material by solving tasks independently under the lab leader's supervision.
* **Even weeks (online / at home, asynchronous):** students study a short theoretical summary ([`docs/notes/`](notes/)) and then complete the laboratory tasks on their own; the lab leaders evaluate the submissions.
* **Homework** is developed independently, project-style, with optional consultation.

### Project work

All five homework assignments build incrementally on a single student project. The project topic (dataset + prediction task) is chosen and approved in Week 2; the canonical course dataset may be used as a fallback. See [`datasets/README.md`](../datasets/README.md) for the topic catalogue.

### Written test (ZH)

Held in Week 14 and covering lecture material from all fourteen weeks. The revision guide — what is examinable per week, the recurring question shapes, and worked answers — is [`docs/exam-revision.md`](exam-revision.md). <!-- TODO: Week 14 is an asynchronous week — schedule the in-person slot, or move the ZH to the last in-person session (Wed 2 December, Week 13). Confirm room and format. -->

### Grade boundaries

| Score | Grade |
| :--- | :--- |
| 85–100% | 5 (jeles) |
| 70–84% | 4 (jó) |
| 55–69% | 3 (közepes) |
| 40–54% | 2 (elégséges) |
| below 40% | 1 (elégtelen) |

These convert the weighted score into a grade **only once all three requirements above are met** — the 40% pass boundary does not override the 50% component thresholds on homework and the ZH.

### AI tool policy

Use of AI assistants is permitted and encouraged — this is an industry reality the course embraces. The condition is accountability: **students must understand and be able to explain every artifact they submit**, and may be asked to do so in person. "The assistant wrote it" is not an answer to a question about why a threshold, a configuration value or a design decision is what it is.

---

## Assignment Deadlines Summary

**Each assignment is released on the odd (in-person) week whose lab it depends on, and is due three to four weeks later** (the last two windows are shorter, because the semester ends). The windows overlap on purpose: the work is project-style and runs alongside the rest of the semester rather than in a one-week sprint. Each assignment is released only after every lab it depends on has been taught.

*Submissions are due by 23:59 (Budapest) on the Sunday closing the deadline week, via the student's own project repository.*

| | Released | Due | Window | What it covers |
| :--- | :--- | :--- | :--- | :--- |
| **Project topic** | Week 1 | **Week 2** (Sun 20 Sep) | 2 weeks | Dataset + prediction task, approved by the instructor. — [brief](../homework/project-topic/README.md) |
| **HW 1** | Week 5 (5 Oct) | **Week 8** (Sun 1 Nov) | 4 weeks | Basic MLOps project with data versioning, experiment tracking, and model management. — [brief](../homework/hw-01-data-versioning-and-tracking/README.md) |
| **HW 2** | Week 7 (19 Oct) | **Week 10** (Sun 15 Nov) | 4 weeks | Automated data validation, evaluation, and documented quality thresholds ("go/no-go"). — [brief](../homework/hw-02-validation-and-evaluation-gates/README.md) |
| **HW 3** | Week 9 (2 Nov) | **Week 12** (Sun 29 Nov) | 4 weeks | End-to-end Prefect flow with parameterization and retry handling. — [brief](../homework/hw-03-orchestration/README.md) |
| **HW 4** | Week 11 (16 Nov) | **Week 13** (Sun 6 Dec) | 3 weeks | Model serving via KServe with version handling, documented rollouts, and smoke tests. — [brief](../homework/hw-04-serving-and-rollout/README.md) |
| **HW 5** | Week 13 (30 Nov) | **Week 14** (Sun 13 Dec) | 2 weeks | Observability setup (Grafana + alerts) and drift analysis with intervention strategies. — [brief](../homework/hw-05-observability-and-drift/README.md) |

*Dates assume Week 1 begins Monday 7 September 2026; adjust with the academic calendar. HW 5 has the shortest window because the semester ends — its scope is correspondingly smaller, and it is due in the same week as the written test (ZH). One homework may be repeated in the retake week (see Assessment).*
