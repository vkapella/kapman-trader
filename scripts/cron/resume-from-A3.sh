set -euo pipefail

START_DATE="2026-01-07"
END_DATE="2026-01-09"

echo "=== RESUME: A3 dealer metrics (per-day) ==="
for D in 2026-01-07 2026-01-08 2026-01-09; do
  SNAPSHOT_TIME="${D}T21:00:00+00:00"
  python -m scripts.run_a3_dealer_metrics \
    --snapshot-time "${SNAPSHOT_TIME}" \
    --log-level INFO
done

echo "=== RESUME: B2 wyckoff structural events (range) ==="
python -m scripts.run_b2_wyckoff_structural_events \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat

echo "=== RESUME: B1 wyckoff regime (watchlist) ==="
python -m scripts.run_b1_wyckoff_regime \
  --watchlist \
  --verbose \
  --heartbeat \
  --max-workers 6

echo "=== RESUME: B4 wyckoff derived (range) ==="
python -m scripts.run_b4_wyckoff_derived \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat \
  --include-evidence

echo "=== RESUME: B4.1 wyckoff sequences (range) ==="
python -m scripts.run_b4_1_wyckoff_sequences \
  --watchlist \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --verbose \
  --heartbeat

echo "=== RESUME: DASHBOARDS / VERIFICATION ==="
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0007-B1-wyckoff_regime_dashboard.sql
docker exec -i -e PGPASSWORD=kapman_password_here kapman-db psql -U kapman -d kapman < db/dashboards/0008-B2-wyckoff_structural_events_dashboard.sql