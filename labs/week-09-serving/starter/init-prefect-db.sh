#!/bin/bash
# Creates Prefect's database alongside MLflow's.
# Runs only when the Postgres volume is empty; after reusing an old volume, run make down-v.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE ${PREFECT_DB:-prefectdb};
SQL
echo "created database ${PREFECT_DB:-prefectdb}"
