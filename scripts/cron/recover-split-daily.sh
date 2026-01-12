#!/usr/bin/env bash
# recover-split-daily.sh
# Fix split daily_snapshots rows by writing dealer metrics onto the canonical EOD snapshot rows
# and deleting the duplicate 21:00 rows for the same ticker/day.

set -euo pipefail

START_DATE="2026-01-07"
END_DATE="2026-01-09"

DB_CONTAINER="kapman-db"
DB_NAME="kapman"
DB_USER="kapman"
PGPASSWORD_VALUE="kapman_password_here"

# Your canonical A2 “EOD marker” time-of-day (UTC) from the NVDA timeline:
CANONICAL_EOD_TOD="23:59:59.999999"
DUP_TOD="21:00:00"

psql_exec () {
  docker exec -i -e PGPASSWORD="${PGPASSWORD_VALUE}" "${DB_CONTAINER}" \
    psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1
}

echo "============================================================"
echo "Fix split daily_snapshots for ${START_DATE}..${END_DATE}"
echo "============================================================"

echo "=== Detect canonical time-of-day per ET trading day (FYI) ==="
psql_exec <<SQL
WITH base AS (
  SELECT
    ("time" at time zone 'America/New_York')::date AS trading_day_et,
    ("time" at time zone 'UTC')::time AS tod_utc,
    count(*) AS n
  FROM public.daily_snapshots
  WHERE ("time" at time zone 'America/New_York')::date
        BETWEEN DATE '${START_DATE}' AND DATE '${END_DATE}'
  GROUP BY 1,2
),
ranked AS (
  SELECT *,
         row_number() OVER (PARTITION BY trading_day_et ORDER BY n DESC) AS rnk
  FROM base
)
SELECT trading_day_et, tod_utc AS most_common_tod_utc, n
FROM ranked
WHERE rnk = 1
ORDER BY trading_day_et;
SQL

echo
echo "=== Re-run A3 on canonical EOD snapshot rows (${CANONICAL_EOD_TOD}+00:00) ==="
for D in 2026-01-07 2026-01-08 2026-01-09; do
  SNAPSHOT_TIME="${D}T${CANONICAL_EOD_TOD}+00:00"
  echo "--- A3 for ${D} @ ${SNAPSHOT_TIME}"
  python -m scripts.run_a3_dealer_metrics \
    --snapshot-time "${SNAPSHOT_TIME}" \
    --log-level INFO
done

echo
echo "=== Delete duplicate ${DUP_TOD} rows when canonical EOD row exists (same ticker + same ET date) ==="
psql_exec <<SQL
WITH dups AS (
  SELECT ds."time", ds.ticker_id
  FROM public.daily_snapshots ds
  WHERE ("time" at time zone 'America/New_York')::date
        BETWEEN DATE '${START_DATE}' AND DATE '${END_DATE}'
    AND ("time" at time zone 'UTC')::time = time '${DUP_TOD}'
    AND EXISTS (
      SELECT 1
      FROM public.daily_snapshots ds2
      WHERE ds2.ticker_id = ds.ticker_id
        AND (ds2."time" at time zone 'America/New_York')::date
            = (ds."time" at time zone 'America/New_York')::date
        AND (ds2."time" at time zone 'UTC')::time = time '${CANONICAL_EOD_TOD}'
    )
)
DELETE FROM public.daily_snapshots ds
USING dups
WHERE ds."time" = dups."time"
  AND ds.ticker_id = dups.ticker_id;

-- show how many were deleted
SELECT 'deleted_dup_rows' AS metric, count(*) AS n
FROM dups;
SQL

echo
echo "=== Verify snapshot density for the range (should move toward 1 per ticker/day) ==="
psql_exec <<SQL
WITH per_day AS (
  SELECT
    (ds."time" at time zone 'America/New_York')::date AS d_et,
    ds.ticker_id,
    count(*) AS snapshots_per_day
  FROM public.daily_snapshots ds
  WHERE (ds."time" at time zone 'America/New_York')::date
        BETWEEN DATE '${START_DATE}' AND DATE '${END_DATE}'
  GROUP BY 1,2
)
SELECT snapshots_per_day, count(*) AS occurrences
FROM per_day
GROUP BY 1
ORDER BY 1;
SQL

echo
echo "=== Verify dealer metrics now exist on canonical EOD rows for these days ==="
psql_exec <<SQL
SELECT
  (ds."time" at time zone 'America/New_York')::date AS trading_day_et,
  count(*) AS rows_with_dealer_metrics_on_eod
FROM public.daily_snapshots ds
WHERE ds.dealer_metrics_json IS NOT NULL
  AND (ds."time" at time zone 'America/New_York')::date
      BETWEEN DATE '${START_DATE}' AND DATE '${END_DATE}'
  AND (ds."time" at time zone 'UTC')::time = time '${CANONICAL_EOD_TOD}'
GROUP BY 1
ORDER BY 1;
SQL

echo "=== DONE ==="