\set ON_ERROR_STOP on
\timing on

\echo '============================================================'
\echo ' KAPMAN DAILY_SNAPSHOTS — BLOB & PIPELINE COVERAGE DASHBOARD'
\echo '============================================================'
\echo ''
\echo 'Purpose:'
\echo ' • Determine date ranges for each JSON/blob column'
\echo ' • Identify which pipeline stages are active, stale, or missing'
\echo ' • NO schema changes'
\echo ' • NO functions'
\echo ' • NO temp tables'
\echo ' • Explicit and auditable'
\echo ''

------------------------------------------------------------
-- GLOBAL DAILY_SNAPSHOTS RANGE (BASELINE)
------------------------------------------------------------
\echo ''
\echo '------------------------------------------------------------'
\echo ' GLOBAL DAILY_SNAPSHOTS RANGE'
\echo '------------------------------------------------------------'

SELECT
  MIN(time)                                  AS min_snapshot_time,
  MAX(time)                                  AS max_snapshot_time,
  CURRENT_DATE - MAX(time::date)             AS staleness_days,
  COUNT(*)                                   AS total_rows
FROM daily_snapshots;

------------------------------------------------------------
-- JSON / BLOB COVERAGE BY PIPELINE STAGE
------------------------------------------------------------
\echo ''
\echo '------------------------------------------------------------'
\echo ' DAILY_SNAPSHOTS — BLOB DATE RANGES'
\echo '------------------------------------------------------------'

SELECT
  blob_name,
  MIN(time)                                  AS first_present,
  MAX(time)                                  AS last_present,
  CURRENT_DATE - MAX(time::date)             AS staleness_days,
  COUNT(*)                                   AS rows_with_blob
FROM (
  SELECT time, 'events_json'                AS blob_name
    FROM daily_snapshots
   WHERE events_json IS NOT NULL

  UNION ALL
  SELECT time, 'technical_indicators_json'
    FROM daily_snapshots
   WHERE technical_indicators_json IS NOT NULL

  UNION ALL
  SELECT time, 'dealer_metrics_json'
    FROM daily_snapshots
   WHERE dealer_metrics_json IS NOT NULL

  UNION ALL
  SELECT time, 'volatility_metrics_json'
    FROM daily_snapshots
   WHERE volatility_metrics_json IS NOT NULL

  UNION ALL
  SELECT time, 'price_metrics_json'
    FROM daily_snapshots
   WHERE price_metrics_json IS NOT NULL
) blobs
GROUP BY blob_name
ORDER BY blob_name;

------------------------------------------------------------
-- BLOB COMPLETENESS (% OF SNAPSHOTS POPULATED)
------------------------------------------------------------
\echo ''
\echo '------------------------------------------------------------'
\echo ' DAILY_SNAPSHOTS — BLOB COMPLETENESS'
\echo '------------------------------------------------------------'

WITH total AS (
  SELECT COUNT(*) AS total_rows FROM daily_snapshots
)
SELECT
  blob_name,
  COUNT(*)                                   AS rows_with_blob,
  total.total_rows,
  ROUND(100.0 * COUNT(*) / total.total_rows, 2) AS pct_coverage
FROM (
  SELECT 'events_json' AS blob_name
    FROM daily_snapshots
   WHERE events_json IS NOT NULL

  UNION ALL
  SELECT 'technical_indicators_json'
    FROM daily_snapshots
   WHERE technical_indicators_json IS NOT NULL

  UNION ALL
  SELECT 'dealer_metrics_json'
    FROM daily_snapshots
   WHERE dealer_metrics_json IS NOT NULL

  UNION ALL
  SELECT 'volatility_metrics_json'
    FROM daily_snapshots
   WHERE volatility_metrics_json IS NOT NULL

  UNION ALL
  SELECT 'price_metrics_json'
    FROM daily_snapshots
   WHERE price_metrics_json IS NOT NULL
) blobs
CROSS JOIN total
GROUP BY blob_name, total.total_rows
ORDER BY pct_coverage DESC;

------------------------------------------------------------
-- PIPELINE REGRESSION / LAG CHECK
-- (Which blobs are behind the latest snapshot time)
------------------------------------------------------------
\echo ''
\echo '------------------------------------------------------------'
\echo ' DAILY_SNAPSHOTS — PIPELINE LAG VS GLOBAL MAX'
\echo '------------------------------------------------------------'

WITH blob_last_seen AS (
  SELECT 'events_json' AS blob_name, MAX(time) AS last_seen
    FROM daily_snapshots
   WHERE events_json IS NOT NULL

  UNION ALL
  SELECT 'technical_indicators_json', MAX(time)
    FROM daily_snapshots
   WHERE technical_indicators_json IS NOT NULL

  UNION ALL
  SELECT 'dealer_metrics_json', MAX(time)
    FROM daily_snapshots
   WHERE dealer_metrics_json IS NOT NULL

  UNION ALL
  SELECT 'volatility_metrics_json', MAX(time)
    FROM daily_snapshots
   WHERE volatility_metrics_json IS NOT NULL

  UNION ALL
  SELECT 'price_metrics_json', MAX(time)
    FROM daily_snapshots
   WHERE price_metrics_json IS NOT NULL
),
global_max AS (
  SELECT MAX(time) AS max_time FROM daily_snapshots
)
SELECT
  b.blob_name,
  b.last_seen,
  g.max_time                              AS global_max_time,
  (g.max_time::date - b.last_seen::date) AS lag_days
FROM blob_last_seen b
CROSS JOIN global_max g
ORDER BY lag_days DESC;

------------------------------------------------------------
-- OPTIONAL: MODEL VERSION COVERAGE
------------------------------------------------------------
\echo ''
\echo '------------------------------------------------------------'
\echo ' DAILY_SNAPSHOTS — MODEL VERSION RANGE'
\echo '------------------------------------------------------------'

SELECT
  model_version,
  MIN(time) AS first_seen,
  MAX(time) AS last_seen,
  COUNT(*)  AS rows
FROM daily_snapshots
GROUP BY model_version
ORDER BY last_seen DESC;

\echo ''
\echo '============================================================'
\echo ' DASHBOARD COMPLETE'
\echo '============================================================'
\echo ''
