#!/usr/bin/env bash
set -euo pipefail

# Required env vars
: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${DB_CONTAINER:=kapman-db}"

echo "Using DB container: ${DB_CONTAINER}"
echo "Using DATABASE_URL: ${DATABASE_URL}"

run_smoke() {
  local sql_file="$1"
  echo ""
  echo "Running $(basename "$sql_file") ..."
  docker exec -i "${DB_CONTAINER}" \
    psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
    < "${sql_file}"
  echo "✓ $(basename "$sql_file") passed"
}

run_smoke scripts/db/smoke_sprint_2_0_1_base_ohlcv.sql
run_smoke scripts/db/smoke_sprint_2_0_2_base_ohlcv.sql

echo ""
echo "All smoke tests passed."
