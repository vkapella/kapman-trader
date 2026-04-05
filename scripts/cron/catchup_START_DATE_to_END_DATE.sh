#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# KapMan SAFE CATCH-UP SCRIPT
#
# Usage:
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh START_DATE END_DATE
#
# Example:
#   scripts/cron/catchup_START_DATE_to_END_DATE.sh 2026-01-27 2026-01-28
#
# Order:
#   A0  OHLCV
#   A1  Options Chains
#   A2  Local TA
#   A4  Volatility Metrics
#   A3  Dealer Metrics
#   B2  Wyckoff Structural Events
#   B1  Wyckoff Regime
#   B4.1 Canonical Sequences
#   B4  Wyckoff Derived
#
# GUARANTEES:
# - OHLCV anchors all dates
# - No phantom daily_snapshots rows
# - NY trading date remains canonical
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
RUN_TS_UTC="$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
SCRIPT_START_TS="$(date +%s)"
REPORT_DIR="${REPO_ROOT}/data/cron_reports"
STEP_TIMINGS_FILE="$(mktemp -t kapman_catchup_timings.XXXXXX)"

cleanup() {
  rm -f "${STEP_TIMINGS_FILE}"
}

trap cleanup EXIT

format_duration() {
  local total_seconds="$1"
  printf "%02d:%02d:%02d" \
    "$((total_seconds / 3600))" \
    "$(((total_seconds % 3600) / 60))" \
    "$((total_seconds % 60))"
}

record_timing() {
  local elapsed_sec="$1"
  local label="$2"
  printf "%s\t%s\n" "${elapsed_sec}" "${label}" >> "${STEP_TIMINGS_FILE}"
}

run_step() {
  local step_id="$1"
  local step_label="$2"
  shift 2

  echo
  echo "============================================================"
  echo "${step_label} (${step_id})"
  echo "============================================================"

  local started_at ended_at elapsed_sec
  started_at="$(date +%s)"
  "$@"
  ended_at="$(date +%s)"
  elapsed_sec="$((ended_at - started_at))"

  record_timing "${elapsed_sec}" "${step_id} ${step_label}"
  echo "STEP TIMING step=${step_id} elapsed_sec=${elapsed_sec} elapsed_hms=$(format_duration "${elapsed_sec}")"
}

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 START_DATE END_DATE"
  echo "Example: $0 2026-01-27 2026-01-28"
  exit 1
fi

START_DATE="$1"
END_DATE="$2"
REPORT_FILE="${REPORT_DIR}/kapman_catchup_${START_DATE}_${END_DATE}_${RUN_TS_UTC}.log"

mkdir -p "${REPORT_DIR}"
exec > >(tee -a "${REPORT_FILE}") 2>&1

echo "==> KapMan SAFE CATCH-UP: ${START_DATE} → ${END_DATE}"
echo "==> Report file: ${REPORT_FILE}"

echo "==> Activating environment"
cd "${REPO_ROOT}"
source "${REPO_ROOT}/venv/bin/activate"
set -a
source "${REPO_ROOT}/.env"
set +a

echo "==> Ensuring Docker environment is running"
docker compose up -d

run_step "A0" "STEP 1: OHLCV BASE INGEST" \
  python -m scripts.ingest_ohlcv backfill \
    --start "${START_DATE}" \
    --end "${END_DATE}" \
    --verbosity normal

run_step "A1" "STEP 2: OPTIONS CHAINS INGEST" \
  python -m scripts.ingest_options \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --emit-summary

run_step "A2" "STEP 3: LOCAL TA + PRICE METRICS" \
  python -m scripts.run_a2_local_ta \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --quiet

run_step "A4" "STEP 4: VOLATILITY METRICS" \
  python -m scripts.run_a4_volatility_metrics \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --quiet

run_step "A3" "STEP 5: DEALER METRICS" \
  python -m scripts.run_a3_dealer_metrics \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --fill-missing \
    --quiet

run_step "B2" "STEP 6: WYCKOFF STRUCTURAL EVENTS" \
  python -m scripts.run_b2_wyckoff_structural_events \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat

run_step "B1" "STEP 7: WYCKOFF REGIME" \
  python -m scripts.run_b1_wyckoff_regime \
    --heartbeat

run_step "B4.1" "STEP 8: WYCKOFF SEQUENCES" \
  python -m scripts.run_b4_1_wyckoff_sequences \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat

run_step "B4" "STEP 9: WYCKOFF DERIVED" \
  python -m scripts.run_b4_wyckoff_derived \
    --start-date "${START_DATE}" \
    --end-date "${END_DATE}" \
    --heartbeat \
    --include-evidence

run_step "CHECK" "POSTCHECK: DEALER SNAPSHOT DATE SAFETY" \
  docker exec -i -e PGPASSWORD="${PGPASSWORD:-kapman_password_here}" kapman-db \
    psql -U kapman -d kapman -v ON_ERROR_STOP=1 -X -q <<SQL
SELECT
  (time AT TIME ZONE 'UTC')::date              AS utc_date,
  (time AT TIME ZONE 'America/New_York')::date AS ny_date,
  COUNT(*) AS rows
FROM daily_snapshots
WHERE dealer_metrics_json IS NOT NULL
  AND (time AT TIME ZONE 'America/New_York')::date
      BETWEEN '${START_DATE}' AND '${END_DATE}'
GROUP BY 1,2
ORDER BY 1;
SQL

echo
echo "============================================================"
echo "RUNTIME SUMMARY (LONGEST FIRST)"
echo "============================================================"
while IFS=$'\t' read -r elapsed_sec label; do
  printf "%6ss  %s (%s)\n" "${elapsed_sec}" "${label}" "$(format_duration "${elapsed_sec}")"
done < <(sort -rn "${STEP_TIMINGS_FILE}")

TOTAL_RUNTIME_SEC="$(( $(date +%s) - SCRIPT_START_TS ))"
echo "TOTAL_RUNTIME_SEC=${TOTAL_RUNTIME_SEC} TOTAL_RUNTIME_HMS=$(format_duration "${TOTAL_RUNTIME_SEC}")"
echo "==> SAFE CATCH-UP COMPLETE: ${START_DATE} → ${END_DATE}"
