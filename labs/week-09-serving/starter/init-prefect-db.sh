#!/bin/bash
# Creates Prefect's database alongside MLflow's.
#
# Runs ONLY on first initialisation of the postgres volume (that is how
# docker-entrypoint-initdb.d works). If you reuse a volume from an earlier
# week, this never runs and the Prefect server cannot start -- see the
# troubleshooting table in the README.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE ${PREFECT_DB:-prefectdb};
SQL
echo "created database ${PREFECT_DB:-prefectdb}"
