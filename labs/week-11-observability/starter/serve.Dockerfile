# The serving image. The model is copied in at build time, so the container
# needs no MLflow, Silo or network to start.
FROM python:3.12-slim

# Provenance from `make image`: OCI labels for `docker inspect`, a file for /health.
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

COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /usr/local/bin/uv

# hatchling needs README.md, because pyproject.toml names it as the readme.
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

# Not read at runtime. It ships so that the image can print its SLO:
#   docker run --rm diabetes-api:local uv run --no-dev python -m week_11_observability.slo
COPY slo.yaml ./slo.yaml

ENV MODEL_PATH=/app/models/model.pkl \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# One worker: each worker process keeps its own metric counters, so a scrape
# would see only part of the traffic.
CMD ["uv", "run", "--no-dev", "uvicorn", "week_11_observability.api:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
