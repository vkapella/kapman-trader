#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# KapMan SAFE CATCH-UP SCRIPT
# Window: 2026-01-13 .. 2026-01-16 (inclusive)
# Order:
#   A0  OHLCV
#   A1  Options Chains
#   A2  Local TA
#   A4  Volatility Metrics
#   A3  Dealer Metrics
#   B2  Wyckoff Structural Events
#   B1  Wyckoff Regime
#   B4  Wyckoff Derived
#
# GUARANTEES:
# - OHLCV anchors all dates
# - No phantom daily_snapshots rows
# - Explicit dealer snapshot-time
# - NY trading date remains canonical
# ============================================================

START_DATE="2026-01-13"
END_DATE="2026-01-16"

# Fixed, explicit, end-of-day UTC snapshot time
DEALER_SNAPSHOT_TIME="2026-01-16T23:00:00"

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
echo "STEP 1: OHLCV BACKFILL (A0) — AUTHORITATIVE BASE"
echo "============================================================"
python -m scripts.ingest_ohlcv backfill \
  --start "${START_DATE}" \
  --end   "${END_DATE}" \
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
echo "STEP 5: DEALER METRICS (A3) — EXPLICIT SNAPSHOT TIME"
echo "============================================================"
python -m scripts.run_a3_dealer_metrics \
  --snapshot-time "${DEALER_SNAPSHOT_TIME}" \
  --log-level INFO

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 6: WYCKOFF STRUCTURAL EVENTS (B2r2)"
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
  --start-date "${START_DATE}" \
  --end-date   "${END_DATE}" \
  --heartbeat

# ------------------------------------------------------------
echo
echo "============================================================"
echo "STEP 8: WYCKOFF DERIVED (B4)"
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
echo "==> SAFE CATCH-UP COMPLETE FOR ${START_DATE} → ${END_DATE}"