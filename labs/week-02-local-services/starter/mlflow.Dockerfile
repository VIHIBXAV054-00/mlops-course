# Pinned MLflow tracking server image.
# Installs MLflow plus the two backend dependencies:
#   - psycopg2-binary: PostgreSQL driver for the backend store
#   - boto3: AWS/S3 SDK for the artifact store (Silo is S3-compatible)
#
# Using a dedicated Dockerfile instead of `pip install` in the compose command
# is the week's lesson about reproducible runtimes: the image is pinned,
# immutable, and reproducible across machines and CI runs.

FROM python:3.12-slim

RUN pip install --no-cache-dir \
    mlflow==3.13.0 \
    psycopg2-binary==2.9.12 \
    boto3==1.43.29

EXPOSE 5000

ENTRYPOINT ["mlflow", "server"]
