# kapman_catchup_2026-01-09.sh
# Purpose: bring a rebuilt DB that is current through 2026-01-06 up to 2026-01-09 (inclusive)
# Run from repo root with venv active.

set -euo pipefail

START_DATE="2026-01-07"
END_DATE="2026-01-09"

echo "=== A1: ensure tickers + watchlists exist (idempotent) ==="
python -m scripts.ingest_tickers
python -m scripts.ingest_watchlists --effective-date "${END_DATE}"

echo "=== A0: ingest OHLCV for missing trading days (${START_DATE}..${END_DATE}) ==="
python -m scripts.ingest_ohlcv incremental \
  --verbosity normal \
  --start "${START_DATE}" \
  --end "${END_DATE}"

echo "=== A1: ingest options chains per day (watchlists -> options_chains) ==="
# Use a deterministic snapshot_time aligned to the close:
# 4:00pm ET = 21:00:00Z during standard time (Jan).
for D in 2026-01-07 2026-01-08 2026-01-09; do
  SNAPSHOT_TIME="${D}T21:00:00Z"

  python -m scripts.ingest_options \
    --as-of "${D}" \
    --snapshot-time "${SNAPSHOT_TIME}" \
    --provider polygon \
    --concurrency 5 \
    --heartbeat 25 \
    --log-level INFO \
    --emit-summary
done

echo "=== A2: compute local TA + price metrics into daily_snapshots (range) ==="
python -m scripts.run_a2_local_ta \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --fill-missing \
  --heartbeat 50 \
  --max-workers 6

echo "=== A4: compute volatility metrics into daily_snapshots (range) ==="
python -m scripts.run_a4_volatility_metrics \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --fill-missing \
  --heartbeat 50

echo "=== A3: compute dealer metrics into daily_snapshots (per-day, aligned to options snapshot_time) ==="
for D in 2026-01-07 2026-01-08 2026-01-09; do
  SNAPSHOT_TIME="${D}T21:00:00Z"

  python -m scripts.run_a3_dealer_metrics \
    --snapshot-time "${SNAPSHOT_TIME}" \
    --log-level INFO
done

echo "=== B2: compute Wyckoff structural events into daily_snapshots (range) ==="
python -m scripts.run_b2_wyckoff_structural_events \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat

echo "=== B1: compute Wyckoff regime into daily_snapshots (watchlist) ==="
# Note: per your usage docs, this script has no start/end flags; run it after A2/B2 so it can fill missing regime rows.
python -m scripts.run_b1_wyckoff_regime \
  --watchlist \
  --verbose \
  --heartbeat \
  --max-workers 6

echo "=== B4: compute derived Wyckoff transitions/context into daily_snapshots (range) ==="
python -m scripts.run_b4_wyckoff_derived \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat \
  --include-evidence

echo "=== B4.1: compute canonical Wyckoff sequences (range) ==="
python -m scripts.run_b4_1_wyckoff_sequences \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat

echo "=== DASHBOARDS / VERIFICATION ==="
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0000-A0-ohlcv_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0001-A1-options_chains_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0007-B1-wyckoff_regime_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0008-B2-wyckoff_structural_events_dashboard.sql

echo "=== DONE: DB should now be current through ${END_DATE} ==="