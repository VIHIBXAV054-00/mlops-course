# The serving image: the code, the locked packages and the model, built by `make image`.
# The model is copied in when the image is built, so the container needs no registry.
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /usr/local/bin/uv

# README.md too: pyproject.toml names it, and the package does not build without it.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# --locked fails the build if uv.lock does not match pyproject.toml.
RUN uv sync --locked --no-dev

# Which model this is. `make image` passes the values; `docker inspect` shows the labels.
# They come after `uv sync`, so a new model version does not reinstall the packages.
ARG MODEL_VERSION="unknown"
ARG RUN_ID="unknown"
ARG GATE_VERDICT="unknown"
ARG MODEL_SOURCE="unknown"

LABEL org.opencontainers.image.title="diabetes-prediction" \
      ai.course.model-version="${MODEL_VERSION}" \
      ai.course.run-id="${RUN_ID}" \
      ai.course.gate-verdict="${GATE_VERDICT}" \
      ai.course.model-source="${MODEL_SOURCE}"

# The model, and the file `/health` reads to say which model it is.
COPY models/model.pkl ./models/model.pkl
RUN printf '{"model_version": "%s", "run_id": "%s", "gate_verdict": "%s", "source": "%s"}\n' \
      "${MODEL_VERSION}" "${RUN_ID}" "${GATE_VERDICT}" "${MODEL_SOURCE}" \
      > ./models/baked.json

# The app reads these two files when it starts.
COPY params.yaml ./params.yaml
COPY data/diabetes.csv ./data/diabetes.csv

ENV MODEL_PATH=/app/models/model.pkl \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "week_09_serving.api:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
