#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# KapMan SAFE CATCH-UP SCRIPT
#
# Usage:
#   ./run_kapman_catchup.sh START_DATE END_DATE
#
# Example:
#   ./run_kapman_catchup.sh 2026-01-27 2026-01-28
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

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 START_DATE END_DATE"
  echo "Example: $0 2026-01-27 2026-01-28"
  exit 1
fi

START_DATE="$1"
END_DATE="$2"

echo "==> KapMan SAFE CATCH-UP: ${START_DATE} → ${END_DATE}"

echo "==> Activating environment"
source venv/bin/activate
set -a
source .env
set +a

echo "==> Ensuring Docker environment is running"
docker compose up -d

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 1: OHLCV BASE INGEST (A0)"
echo "============================================================"
python -m scripts.ingest_ohlcv base \
  --days 3 \
  --as-of "${END_DATE}" \
  --verbosity normal

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 2: OPTIONS CHAINS INGEST (A1)"
echo "============================================================"
python -m scripts.ingest_options \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --emit-summary

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 3: LOCAL TA + PRICE METRICS (A2)"
echo "============================================================"
python -m scripts.run_a2_local_ta \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --quiet

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 4: VOLATILITY METRICS (A4)"
echo "============================================================"
python -m scripts.run_a4_volatility_metrics \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --quiet

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 5: DEALER METRICS (A3)"
echo "============================================================"
python -m scripts.run_a3_dealer_metrics \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --fill-missing \
  --quiet

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 6: WYCKOFF STRUCTURAL EVENTS (B2)"
echo "============================================================"
python -m scripts.run_b2_wyckoff_structural_events \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --heartbeat

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 7: WYCKOFF REGIME (B1)"
echo "============================================================"
python -m scripts.run_b1_wyckoff_regime \
  --heartbeat

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 8: WYCKOFF SEQUENCES (B4.1)"
echo "============================================================"
python -m scripts.run_b4_1_wyckoff_sequences \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --heartbeat

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 9: WYCKOFF DERIVED (B4)"
echo "============================================================"
python -m scripts.run_b4_wyckoff_derived \
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --heartbeat \
  --include-evidence

# ------------------------------------------------------------
echo
echo "============================================================"
echo "POSTCHECK: DEALER SNAPSHOT DATE SAFETY"
echo "============================================================"
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
echo "==> SAFE CATCH-UP COMPLETE: ${START_DATE} → ${END_DATE}"