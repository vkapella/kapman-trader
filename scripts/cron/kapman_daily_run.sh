#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# KapMan Daily Pipeline Cron
# - Ingest yesterday (ET) OHLCV + options
# - Compute TA, vol, dealer, Wyckoff
# - Run dashboards
# - Email verification report
# -----------------------------

# ====== CONFIG (edit these) ======
REPO_ROOT="/absolute/path/to/kapman-trader"
VENV_ACTIVATE="${REPO_ROOT}/.venv/bin/activate"   # adjust if different

# Email
MAIL_TO="you@yourdomain.com"

# DB dashboard password used by docker exec psql (avoid hardcoding in real use)
PGPASSWORD_VALUE="kapman_password_here"

# Options provider
OPTIONS_PROVIDER="polygon"   # or polygon

# Cron-safe PATH (so python/docker are found)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"

# If you rely on env vars for DATABASE_URL, POLYGON_API_KEY, UNICORN_API_TOKEN, etc,
# source them here (recommended).
# Example:
# source "${REPO_ROOT}/.env.prod"

# ====== END CONFIG ======

cd "${REPO_ROOT}"

# Activate venv
if [[ -f "${VENV_ACTIVATE}" ]]; then
  # shellcheck disable=SC1090
  source "${VENV_ACTIVATE}"
fi

# ----- single-instance lock -----
LOCKFILE="/tmp/kapman_daily_pipeline.lock"
exec 9>"${LOCKFILE}"
if ! flock -n 9; then
  echo "Another KapMan daily run is already in progress. Exiting."
  exit 0
fi

# ----- compute dates in America/New_York (DST-safe) -----
# Produces:
#   YDAY_ET (YYYY-MM-DD) = "yesterday" in ET
#   SNAPSHOT_TIME_UTC    = yesterday 16:00 ET converted to UTC (ISO8601 Z)
read -r YDAY_ET SNAPSHOT_TIME_UTC < <(python - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

et = ZoneInfo("America/New_York")
utc = ZoneInfo("UTC")

now_et = datetime.now(et)
yday_et_date = (now_et.date() - timedelta(days=1))

# 4:00pm ET "close" snapshot time
close_et = datetime(yday_et_date.year, yday_et_date.month, yday_et_date.day, 16, 0, 0, tzinfo=et)
close_utc = close_et.astimezone(utc)

print(yday_et_date.isoformat(), close_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"))
PY
)

RUN_TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
REPORT_DIR="${REPO_ROOT}/data/cron_reports"
mkdir -p "${REPORT_DIR}"
REPORT_FILE="${REPORT_DIR}/kapman_daily_${YDAY_ET}_${RUN_TS_UTC}.log"

# Redirect all output to report (and console if run manually)
exec > >(tee -a "${REPORT_FILE}") 2>&1

echo "============================================================"
echo "KapMan Daily Pipeline Run"
echo "Run time (UTC):     ${RUN_TS_UTC}"
echo "Target date (ET):   ${YDAY_ET}"
echo "Dealer snapshot UTC:${SNAPSHOT_TIME_UTC}"
echo "Repo root:          ${REPO_ROOT}"
echo "============================================================"

# ----- optional: ensure docker DB is reachable -----
if ! docker ps >/dev/null 2>&1; then
  echo "ERROR: docker not available. Exiting."
  exit 1
fi

# ----- A1: ensure watchlists are present (idempotent) -----
echo "=== A1: ingest_watchlists (idempotent) ==="
python -m scripts.ingest_watchlists --effective-date "${YDAY_ET}"

# ----- A0: OHLCV ingestion (yesterday only) -----
# Use incremental --date for a single day (cleanest for cron)
echo "=== A0: ingest_ohlcv incremental for ${YDAY_ET} ==="
python -m scripts.ingest_ohlcv incremental \
  --verbosity normal \
  --date "${YDAY_ET}"

# ----- A1: options chains ingestion for yesterday (watchlist) -----
echo "=== A1: ingest_options for ${YDAY_ET} ==="
python -m scripts.ingest_options \
  --as-of "${YDAY_ET}" \
  --snapshot-time "${SNAPSHOT_TIME_UTC}" \
  --provider "${OPTIONS_PROVIDER}" \
  --concurrency 5 \
  --heartbeat 25 \
  --log-level INFO \
  --emit-summary

# ----- A2: local TA into daily_snapshots (yesterday only) -----
echo "=== A2: run_a2_local_ta for ${YDAY_ET} ==="
python -m scripts.run_a2_local_ta \
  --date "${YDAY_ET}" \
  --fill-missing \
  --heartbeat 50 \
  --max-workers 6

# ----- A4: volatility metrics into daily_snapshots (yesterday only) -----
echo "=== A4: run_a4_volatility_metrics for ${YDAY_ET} ==="
python -m scripts.run_a4_volatility_metrics \
  --date "${YDAY_ET}" \
  --fill-missing \
  --heartbeat 50

# ----- A3: dealer metrics (WRITE TO CANONICAL EOD SNAPSHOT ROW) -----
EOD_SNAPSHOT_TIME_UTC="${YDAY_ET}T23:59:59.999999+00:00"

echo "=== A3: run_a3_dealer_metrics snapshot-time ${EOD_SNAPSHOT_TIME_UTC} (canonical EOD) ==="
python -m scripts.run_a3_dealer_metrics \
  --snapshot-time "${EOD_SNAPSHOT_TIME_UTC}" \
  --log-level INFO

# ----- B2: wyckoff structural events (yesterday only) -----
echo "=== B2: run_b2_wyckoff_structural_events for ${YDAY_ET} ==="
python -m scripts.run_b2_wyckoff_structural_events \
  --watchlist \
  --start-date "${YDAY_ET}" \
  --end-date "${YDAY_ET}" \
  --verbose \
  --heartbeat

# ----- B1: wyckoff regime (script has no start/end flags per your docs) -----
# Assumption: the implementation fills missing regime rows (or recomputes for recent rows).
echo "=== B1: run_b1_wyckoff_regime (watchlist) ==="
python -m scripts.run_b1_wyckoff_regime \
  --watchlist \
  --verbose \
  --heartbeat \
  --max-workers 6

# ----- B4: derived wyckoff (yesterday only) -----
echo "=== B4: run_b4_wyckoff_derived for ${YDAY_ET} ==="
python -m scripts.run_b4_wyckoff_derived \
  --watchlist \
  --start-date "${YDAY_ET}" \
  --end-date "${YDAY_ET}" \
  --verbose \
  --heartbeat \
  --include-evidence

# ----- B4.1: sequences (yesterday only) -----
echo "=== B4.1: run_b4_1_wyckoff_sequences for ${YDAY_ET} ==="
python -m scripts.run_b4_1_wyckoff_sequences \
  --watchlist \
  --start-date "${YDAY_ET}" \
  --end-date "${YDAY_ET}" \
  --verbose \
  --heartbeat

# ----- dashboards / verification -----
echo "=== DASHBOARDS / VERIFICATION ==="
export PGPASSWORD="${PGPASSWORD_VALUE}"

docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" kapman-db psql -U kapman -d kapman < db/dashboards/0000-A0-ohlcv_dashboard.sql
docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" kapman-db psql -U kapman -d kapman < db/dashboards/0001-A1-options_chains_dashboard.sql
docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" kapman-db psql -U kapman -d kapman < db/dashboards/0005-A2-daily_snapshot_dashboard.sql
docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" kapman-db psql -U kapman -d kapman < db/dashboards/0007-B1-wyckoff_regime_dashboard.sql
docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" kapman-db psql -U kapman -d kapman < db/dashboards/0008-B2-wyckoff_structural_events_dashboard.sql

echo "=== SUCCESS: daily pipeline completed for ${YDAY_ET} ==="

# ----- email report (requires local MTA or mailx/msmtp configured) -----
SUBJECT="[KapMan] Daily pipeline SUCCESS for ${YDAY_ET} (run ${RUN_TS_UTC})"
if command -v mail >/dev/null 2>&1; then
  mail -s "${SUBJECT}" "${MAIL_TO}" < "${REPORT_FILE}" || true
elif command -v mailx >/dev/null 2>&1; then
  mailx -s "${SUBJECT}" "${MAIL_TO}" < "${REPORT_FILE}" || true
else
  echo "WARN: mail/mailx not found; report not emailed. Report saved at: ${REPORT_FILE}"
fi