\pset pager off
\echo =====================================================================
\echo KapMan A4 — Volatility Metrics Diagnostic Dashboard
\echo =====================================================================

/*
Assumptions:
- Volatility metrics are stored in daily_snapshots.volatility_metrics_json
- One row per ticker per day (or more, but we select latest per ticker)
*/

-------------------------------------------------------------
\echo 1. Latest Volatility Metrics Snapshot Per Ticker
-------------------------------------------------------------

WITH latest_vol AS (
    SELECT DISTINCT ON (ds.ticker_id)
        ds.ticker_id,
        ds.time AS snapshot_time,
        ds.model_version,
        ds.volatility_metrics_json
    FROM daily_snapshots ds
    WHERE ds.volatility_metrics_json IS NOT NULL
    ORDER BY ds.ticker_id, ds.time DESC
)
SELECT
    t.symbol,
    lv.snapshot_time,
    lv.model_version,
    lv.volatility_metrics_json ->> 'processing_status' AS processing_status,
    lv.volatility_metrics_json ->> 'confidence'         AS confidence,
    (lv.volatility_metrics_json -> 'metrics' ->> 'avg_iv')::numeric                 AS avg_iv,
    (lv.volatility_metrics_json -> 'metrics' ->> 'iv_rank')::numeric                AS iv_rank,
    (lv.volatility_metrics_json -> 'metrics' ->> 'iv_percentile')::numeric          AS iv_percentile,
    (lv.volatility_metrics_json -> 'metrics' ->> 'put_call_oi_ratio')::numeric       AS put_call_oi_ratio,
    (lv.volatility_metrics_json -> 'metrics' ->> 'iv_term_structure_slope')::numeric AS iv_term_structure_slope
FROM latest_vol lv
JOIN tickers t ON t.id = lv.ticker_id
ORDER BY t.symbol
LIMIT 100;

-------------------------------------------------------------
\echo 2. Volatility Metrics Status Distribution
-------------------------------------------------------------

WITH latest_vol AS (
    SELECT DISTINCT ON (ds.ticker_id)
        ds.ticker_id,
        ds.volatility_metrics_json
    FROM daily_snapshots ds
    WHERE ds.volatility_metrics_json IS NOT NULL
    ORDER BY ds.ticker_id, ds.time DESC
)
SELECT
    lv.volatility_metrics_json ->> 'processing_status' AS status,
    COUNT(*) AS rows
FROM latest_vol lv
GROUP BY 1
ORDER BY rows DESC;

-------------------------------------------------------------
\echo 3. Coverage — AAPL / NVDA / TSLA (Last 30 Days)
-------------------------------------------------------------

SELECT
    t.symbol,
    COUNT(*) FILTER (
        WHERE ds.volatility_metrics_json IS NOT NULL
          AND ds.volatility_metrics_json ->> 'processing_status' = 'SUCCESS'
    ) AS success_days,
    COUNT(*) AS total_days
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE t.symbol IN ('AAPL','NVDA','TSLA')
  AND ds.time::date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY t.symbol
ORDER BY t.symbol;

-------------------------------------------------------------
\echo 4. Daily Status Timeline — AAPL / NVDA / TSLA
-------------------------------------------------------------

SELECT
    t.symbol,
    ds.time::date AS date,
    ds.volatility_metrics_json ->> 'processing_status' AS status,
    ds.volatility_metrics_json ->> 'diagnostics'       AS diagnostics
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE t.symbol IN ('AAPL','NVDA','TSLA')
  AND ds.time::date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY t.symbol, date;

-------------------------------------------------------------
\echo 5. Representative Volatility Metrics JSON Blobs
-------------------------------------------------------------

\echo
\echo 5a. High-Confidence Example (SUCCESS)
\echo -------------------------------------------------------------

SELECT
    t.symbol,
    ds.time,
    ds.model_version,
    ds.volatility_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE ds.volatility_metrics_json IS NOT NULL
  AND ds.volatility_metrics_json ->> 'processing_status' = 'SUCCESS'
ORDER BY ds.time DESC
LIMIT 1;

\echo
\echo 5b. Partial or Failure Example (PARTIAL / ERROR)
\echo -------------------------------------------------------------

SELECT
    t.symbol,
    ds.time,
    ds.model_version,
    ds.volatility_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE ds.volatility_metrics_json IS NOT NULL
  AND ds.volatility_metrics_json ->> 'processing_status' <> 'SUCCESS'
ORDER BY ds.time DESC
LIMIT 1;

\echo =====================================================================
\echo End of KapMan A4 Volatility Metrics Dashboard
\echo =====================================================================