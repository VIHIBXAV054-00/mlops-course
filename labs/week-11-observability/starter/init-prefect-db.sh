#!/bin/bash
# Creates Prefect's database next to MLflow's.
# Postgres runs it only when the volume is first created. If the Prefect server
# cannot start on an older volume, run `make down-v` and `make up`.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE ${PREFECT_DB:-prefectdb};
SQL
echo "created database ${PREFECT_DB:-prefectdb}"
