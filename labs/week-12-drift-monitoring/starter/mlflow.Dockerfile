# Pinned MLflow tracking server image.
# Installs MLflow plus the two backend dependencies:
#   - psycopg2-binary: PostgreSQL driver for the backend store
#   - boto3: AWS/S3 SDK for the artifact store (Silo is S3-compatible)

FROM python:3.12-slim

RUN pip install --no-cache-dir \
    mlflow==3.13.0 \
    psycopg2-binary==2.9.12 \
    boto3==1.43.29

EXPOSE 5000

ENTRYPOINT ["mlflow", "server"]
