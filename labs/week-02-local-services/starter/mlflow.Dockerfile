# Pinned MLflow tracking server image: MLflow, a PostgreSQL driver for the
# backend store, and boto3 for the S3-compatible artifact store.

FROM python:3.12-slim

RUN pip install --no-cache-dir \
    mlflow==3.13.0 \
    psycopg2-binary==2.9.12 \
    boto3==1.43.29

EXPOSE 5000

ENTRYPOINT ["mlflow", "server"]
