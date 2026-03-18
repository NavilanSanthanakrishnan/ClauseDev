#!/usr/bin/env bash
set -euo pipefail

DATABASES=("clauseai-db" "clauseai-db-user")

for database in "${DATABASES[@]}"; do
  if psql postgres -Atqc "select 1 from pg_database where datname = '${database}'" | grep -q 1; then
    echo "Database ${database} already exists"
  else
    createdb "${database}"
    echo "Created database ${database}"
  fi
done
