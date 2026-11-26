# The serving image.
#
# BAKE, DO NOT FETCH — and the choice is the lesson, not a default.
#
# The model is copied in at BUILD time, so the running container has ZERO
# runtime dependencies: no MLflow, no Silo, no DVC remote, no network at all.
# Consequences, all deliberate:
#
#   * two identical images always serve the same model. An image that fetched
#     at startup would serve whatever the registry said that morning, and the
#     traceability chain this course spent six weeks building would end at the
#     container wall.
#   * deploy = a new image; rollback = an older image. Both are just tags.
#   * the whole Kubernetes half of this lab runs with the Compose stack DOWN,
#     which matters when a laptop is already running a cluster.
#
# Week 10 takes the other branch: KServe's `storageUri` fetches at startup, one
# image serving many models. That is not a contradiction — it is the same
# trade-off decided differently once a control plane exists to record which
# model a revision is serving.
FROM python:3.12-slim

# Provenance, supplied by `make image` and recorded twice: as OCI labels on the
# image, and as a file the app reads for /health. The labels are for whoever
# runs `docker inspect`; the file is for whoever curls the pod.
ARG MODEL_VERSION="unknown"
ARG RUN_ID="unknown"
ARG GATE_VERDICT="unknown"
ARG MODEL_SOURCE="unknown"

LABEL org.opencontainers.image.title="diabetes-prediction" \
      ai.course.model-version="${MODEL_VERSION}" \
      ai.course.run-id="${RUN_ID}" \
      ai.course.gate-verdict="${GATE_VERDICT}" \
      ai.course.model-source="${MODEL_SOURCE}"

WORKDIR /app

# uv, for the same lockfile the labs use. `--locked` refuses a stale lock here
# exactly as it does in CI: an image built from a re-resolved lock is an image
# whose environment nobody reviewed.
COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /usr/local/bin/uv

# README.md is copied because pyproject.toml declares it as the package
# readme, and hatchling refuses to build without it:
#   OSError: Readme file does not exist: README.md
# A build context is exactly what you put in it, and nothing else.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

# The model, and the note saying which model it is.
COPY models/model.pkl ./models/model.pkl
RUN printf '{"model_version": "%s", "run_id": "%s", "gate_verdict": "%s", "source": "%s"}\n' \
      "${MODEL_VERSION}" "${RUN_ID}" "${GATE_VERDICT}" "${MODEL_SOURCE}" \
      > ./models/baked.json

# params.yaml and the canonical dataset are read by config/schemas at import.
COPY params.yaml ./params.yaml
COPY data/diabetes.csv ./data/diabetes.csv

ENV MODEL_PATH=/app/models/model.pkl \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# One worker. Not a tuning decision — a teaching one: Exercise 3 measures
# per-request latency, and workers change throughput without changing latency,
# which would muddle the number the exercise is about.
CMD ["uv", "run", "--no-dev", "uvicorn", "week_10_kserve_rollout.api:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
