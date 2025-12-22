\pset pager off
\timing on

-- ============================================================
-- Dealer Metrics Dashboard (A3)
-- Non-interactive, safe for psql -f
--
-- Optional psql variable:
--   SNAPSHOT_N = rank of snapshot_time to analyze (1 = most recent)
-- If SNAPSHOT_N is not provided, defaults to 1.
-- ============================================================

\echo
\echo ============================================================
\echo Dealer Metrics Dashboard
\echo ============================================================
\echo

-- ------------------------------
-- 0) Resolve snapshot selection
-- ------------------------------

DROP TABLE IF EXISTS _snapshot_menu;

CREATE TEMP TABLE _snapshot_menu AS
SELECT
    ROW_NUMBER() OVER (ORDER BY ds.time DESC) AS n,
    ds.time AS snapshot_time,
    COUNT(*) AS rows_total,
    COUNT(*) FILTER (WHERE ds.dealer_metrics_json IS NOT NULL) AS rows_with_dealer_json
FROM daily_snapshots ds
WHERE ds.dealer_metrics_json IS NOT NULL
GROUP BY ds.time
ORDER BY ds.time DESC;

\echo Recent snapshot_time values with dealer_metrics_json:
SELECT * FROM _snapshot_menu ORDER BY n;

-- Default SNAPSHOT_N to 1 if not supplied
\set SNAPSHOT_N 1
\if :{?SNAPSHOT_N}
\else
\set SNAPSHOT_N 1
\endif

-- Resolve chosen snapshot_time
WITH chosen AS (
    SELECT snapshot_time
    FROM _snapshot_menu
    WHERE n = :SNAPSHOT_N
)
SELECT snapshot_time FROM chosen;

-- Materialize chosen snapshot_time once
DROP TABLE IF EXISTS _chosen_snapshot;
CREATE TEMP TABLE _chosen_snapshot AS
SELECT snapshot_time
FROM _snapshot_menu
WHERE n = :SNAPSHOT_N;

\echo
\echo Using snapshot_time:
SELECT snapshot_time FROM _chosen_snapshot;
\echo

-- -----------------------------------------
-- 1) Coverage: rows written at snapshot_time
-- -----------------------------------------

SELECT
    COUNT(*) AS rows_at_snapshot_time,
    COUNT(DISTINCT ds.ticker_id) AS distinct_tickers
FROM daily_snapshots ds
JOIN _chosen_snapshot cs ON cs.snapshot_time = ds.time;

-- -----------------------------------------
-- 2) Status taxonomy distribution
-- -----------------------------------------

SELECT
    ds.dealer_metrics_json->'metadata'->>'status' AS status,
    COUNT(*) AS ticker_count
FROM daily_snapshots ds
JOIN _chosen_snapshot cs ON cs.snapshot_time = ds.time
GROUP BY 1
ORDER BY ticker_count DESC, status;

-- -----------------------------------------
-- 3) Summary counts
-- -----------------------------------------

SELECT
    COUNT(*)                                                   AS rows_total,
    COUNT(*) FILTER (WHERE ds.dealer_metrics_json IS NOT NULL) AS rows_with_metrics,
    COUNT(*) FILTER (
        WHERE ds.dealer_metrics_json->'metadata'->>'status' = 'FULL'
    ) AS full_count,
    COUNT(*) FILTER (
        WHERE ds.dealer_metrics_json->'metadata'->>'status' = 'LIMITED'
    ) AS limited_count,
    COUNT(*) FILTER (
        WHERE ds.dealer_metrics_json->'metadata'->>'status' = 'INVALID'
    ) AS invalid_count
FROM daily_snapshots ds
JOIN _chosen_snapshot cs ON cs.snapshot_time = ds.time;

-- ---------------------------------------------------
-- 4) Hard guardrail: INVALID with eligible options
-- ---------------------------------------------------

SELECT
    t.symbol,
    ds.dealer_metrics_json->'metadata'->>'status'        AS status,
    (ds.dealer_metrics_json->>'total_options')::int      AS total_options,
    (ds.dealer_metrics_json->>'eligible_options')::int   AS eligible_options,
    ds.dealer_metrics_json->'metadata'->>'spot_source'   AS spot_source,
    ds.dealer_metrics_json->'metadata'->>'effective_trading_date' AS effective_trading_date,
    ds.dealer_metrics_json->'diagnostics'                AS diagnostics
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
JOIN _chosen_snapshot cs ON cs.snapshot_time = ds.time
WHERE COALESCE((ds.dealer_metrics_json->>'eligible_options')::int, 0) > 0
  AND ds.dealer_metrics_json->'metadata'->>'status' = 'INVALID'
ORDER BY t.symbol;

-- ---------------------------------------------------
-- 5) Completeness check for FULL / LIMITED
-- ---------------------------------------------------

WITH base AS (
    SELECT
        t.symbol,
        ds.dealer_metrics_json AS j,
        ds.dealer_metrics_json->'metadata'->>'status' AS status
    FROM daily_snapshots ds
    JOIN tickers t ON t.id = ds.ticker_id
    JOIN _chosen_snapshot cs ON cs.snapshot_time = ds.time
    WHERE ds.dealer_metrics_json IS NOT NULL
)
SELECT
    symbol,
    status,
    (j ? 'gex_total')   AS has_gex_total,
    (j ? 'gex_net')     AS has_gex_net,
    (j ? 'gamma_flip')  AS has_gamma_flip,
    (j ? 'walls')       AS has_walls,
    (j ? 'filters')     AS has_filters,
    (j ? 'metadata')    AS has_metadata
FROM base
WHERE status IN ('FULL','LIMITED')
  AND NOT (
      (j ? 'gex_total')
  AND (j ? 'gex_net')
  AND (j ? 'filters')
  AND (j ? 'metadata')
  )
ORDER BY symbol;

\echo
\echo ============================================================
\echo End Dealer Metrics Dashboard
\echo ============================================================