\pset pager off
\timing on

-- ============================================================
-- Dealer Metrics Dashboard (A3.1 – Corrected)
-- Reads persisted dealer_metrics_json only
-- ============================================================

\echo
\echo ============================================================
\echo Dealer Metrics Dashboard
\echo ============================================================
\echo

-- ------------------------------------------------------------
-- 0) Snapshot selection
-- ------------------------------------------------------------

DROP TABLE IF EXISTS _snapshot_menu;

CREATE TEMP TABLE _snapshot_menu AS
SELECT
    ROW_NUMBER() OVER (ORDER BY time DESC) AS n,
    time AS snapshot_time,
    COUNT(*) AS rows_total
FROM daily_snapshots
WHERE dealer_metrics_json IS NOT NULL
GROUP BY time
ORDER BY time DESC;

\echo Recent snapshot_time values:
SELECT * FROM _snapshot_menu ORDER BY n;

\set SNAPSHOT_N 1

DROP TABLE IF EXISTS _chosen_snapshot;
CREATE TEMP TABLE _chosen_snapshot AS
SELECT snapshot_time
FROM _snapshot_menu
WHERE n = :SNAPSHOT_N;

\echo
\echo Using snapshot_time:
SELECT snapshot_time FROM _chosen_snapshot;
\echo

-- ------------------------------------------------------------
-- 1) Coverage
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS rows_at_snapshot_time,
    COUNT(DISTINCT ticker_id) AS distinct_tickers
FROM daily_snapshots
WHERE time = (SELECT snapshot_time FROM _chosen_snapshot);

-- ------------------------------------------------------------
-- 2) Status distribution
-- ------------------------------------------------------------

SELECT
    dealer_metrics_json->>'status' AS status,
    COUNT(*) AS ticker_count
FROM daily_snapshots
WHERE time = (SELECT snapshot_time FROM _chosen_snapshot)
GROUP BY 1
ORDER BY ticker_count DESC;

-- ------------------------------------------------------------
-- 3) Dealer Wall Summary (Primary Walls)
-- ------------------------------------------------------------

\echo
\echo ============================================================
\echo Dealer Wall Analysis (Primary)
\echo ============================================================

WITH base AS (
    SELECT
        t.symbol,
        ds.dealer_metrics_json AS j
    FROM daily_snapshots ds
    JOIN tickers t ON t.id = ds.ticker_id
    WHERE ds.time = (SELECT snapshot_time FROM _chosen_snapshot)
      AND ds.dealer_metrics_json IS NOT NULL
)

SELECT
    symbol,

    -- Canonical spot
    (j->>'spot_price')::numeric AS spot_price,

    -- Primary call wall (persisted)
    (j->'primary_call_wall'->>'strike')::numeric AS call_wall_strike,
    (j->'primary_call_wall'->>'gex')::numeric    AS call_wall_gex,
    (j->'primary_call_wall'->>'distance_from_spot')::numeric
        AS call_wall_distance,

    -- Primary put wall (persisted)
    (j->'primary_put_wall'->>'strike')::numeric AS put_wall_strike,
    (j->'primary_put_wall'->>'gex')::numeric    AS put_wall_gex,
    (j->'primary_put_wall'->>'distance_from_spot')::numeric
        AS put_wall_distance,

    -- Counts
    jsonb_array_length(j->'call_walls') AS call_wall_count,
    jsonb_array_length(j->'put_walls')  AS put_wall_count

FROM base
ORDER BY symbol
LIMIT 25;

-- ------------------------------------------------------------
-- 4) Expanded Wall Detail (Top-N)
-- ------------------------------------------------------------

\echo
\echo ------------------------------------------------------------
\echo Expanded Wall Detail (Top N)
\echo ------------------------------------------------------------

WITH base AS (
    SELECT
        t.symbol,
        ds.dealer_metrics_json AS j
    FROM daily_snapshots ds
    JOIN tickers t ON t.id = ds.ticker_id
    WHERE ds.time = (SELECT snapshot_time FROM _chosen_snapshot)
      AND ds.dealer_metrics_json IS NOT NULL
),

expanded AS (
    SELECT
        symbol,
        'CALL' AS wall_type,
        jsonb_array_elements(j->'call_walls') AS wall
    FROM base

    UNION ALL

    SELECT
        symbol,
        'PUT' AS wall_type,
        jsonb_array_elements(j->'put_walls') AS wall
    FROM base
)

SELECT
    symbol,
    wall_type,
    (wall->>'strike')::numeric              AS strike,
    (wall->>'gex')::numeric                 AS gex,
    (wall->>'weighted_gex')::numeric        AS weighted_gex,
    (wall->>'open_interest')::int           AS open_interest,
    (wall->>'contracts')::int               AS contracts,
    (wall->>'distance_from_spot')::numeric  AS distance_from_spot,
    ROUND((wall->>'moneyness')::numeric, 4) AS moneyness
FROM expanded
ORDER BY symbol, wall_type, weighted_gex DESC
LIMIT 50;

-- ------------------------------------------------------------
-- 5) Sample Dealer Metrics Payload (Debug / Inspection)
-- ------------------------------------------------------------

\echo
\echo ============================================================
\echo Sample Dealer Metrics JSON (Representative Symbols)
\echo ============================================================

SELECT
    t.symbol,
    jsonb_pretty(ds.dealer_metrics_json) AS dealer_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE ds.time = (SELECT snapshot_time FROM _chosen_snapshot)
  AND t.symbol IN ('AAPL', 'NVDA', 'TSLA')
ORDER BY t.symbol;

\echo
\echo ============================================================
\echo End Dealer Metrics Dashboard
\echo ============================================================