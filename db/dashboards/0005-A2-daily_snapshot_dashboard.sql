/* =============================================================================
   A2 DAILY SNAPSHOTS INTEGRITY & COVERAGE DASHBOARD
   -----------------------------------------------------------------------------
   Purpose:
     - Validate daily_snapshots density and uniqueness
     - Detect duplicate or multi-snapshot days
     - Inspect completeness of snapshot sub-components:
         * Technical Indicators
         * Dealer Metrics
         * Volatility Metrics
         * Wyckoff Events & Regimes
     - Ensure A0 → B2 → B1 pipeline integrity

   Notes:
     - Read-only diagnostics
     - No temp tables
     - Safe for production
   ========================================================================== */

\echo '===================================================================='
\echo '1) GLOBAL DAILY SNAPSHOT COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(*)                         AS total_snapshots,
  COUNT(DISTINCT ticker_id)        AS tickers_covered,
  MIN(time)::date                  AS first_date,
  MAX(time)::date                  AS last_date
FROM daily_snapshots;

\echo '===================================================================='
\echo '2) SNAPSHOT DENSITY PER (TICKER, DAY)'
\echo '   - Detects multiple snapshots on same trading day'
\echo '===================================================================='

WITH per_day AS (
  SELECT
    ticker_id,
    time::date AS d,
    COUNT(*) AS snapshots_per_day
  FROM daily_snapshots
  GROUP BY ticker_id, time::date
)
SELECT
  snapshots_per_day,
  COUNT(*) AS occurrences
FROM per_day
GROUP BY snapshots_per_day
ORDER BY snapshots_per_day DESC;

\echo '===================================================================='
\echo '3) TICKERS WITH MULTIPLE SNAPSHOTS PER DAY (TOP 10)'
\echo '===================================================================='

WITH per_day AS (
  SELECT
    ticker_id,
    time::date AS d,
    COUNT(*) AS snapshots_per_day
  FROM daily_snapshots
  GROUP BY ticker_id, time::date
)
SELECT
  t.symbol,
  p.d,
  p.snapshots_per_day
FROM per_day p
JOIN tickers t ON t.id = p.ticker_id
WHERE p.snapshots_per_day > 1
ORDER BY p.snapshots_per_day DESC, p.d DESC
LIMIT 10;

\echo '===================================================================='
\echo '4) TOP 10 SNAPSHOT DAYS BY VOLUME'
\echo '   - Days with the highest snapshot count'
\echo '===================================================================='

SELECT
  time::date AS snapshot_date,
  COUNT(*)   AS snapshot_count
FROM daily_snapshots
GROUP BY time::date
ORDER BY snapshot_count DESC
LIMIT 10;

\echo '===================================================================='
\echo '5) TECHNICAL INDICATORS COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(*)                                       AS total_rows,
  COUNT(technical_indicators_json)               AS populated_rows,
  ROUND(
    COUNT(technical_indicators_json) * 100.0 / COUNT(*),
    2
  )                                              AS pct_populated
FROM daily_snapshots;

\echo '===================================================================='
\echo '6) DEALER METRICS COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(*)                            AS total_rows,
  COUNT(dealer_metrics_json)          AS populated_rows,
  ROUND(
    COUNT(dealer_metrics_json) * 100.0 / COUNT(*),
    2
  )                                   AS pct_populated
FROM daily_snapshots;

\echo '===================================================================='
\echo '7) VOLATILITY METRICS COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(*)                               AS total_rows,
  COUNT(volatility_metrics_json)         AS populated_rows,
  ROUND(
    COUNT(volatility_metrics_json) * 100.0 / COUNT(*),
    2
  )                                      AS pct_populated
FROM daily_snapshots;

\echo '===================================================================='
\echo '8) WYCKOFF EVENTS COVERAGE (B2)'
\echo '===================================================================='

SELECT
  COUNT(*)                          AS total_rows,
  COUNT(events_detected)            AS rows_with_events,
  ROUND(
    COUNT(events_detected) * 100.0 / COUNT(*),
    2
  )                                 AS pct_with_events
FROM daily_snapshots;

\echo '===================================================================='
\echo '9) WYCKOFF REGIME COVERAGE (B1)'
\echo '===================================================================='

SELECT
  COUNT(*)                          AS total_rows,
  COUNT(wyckoff_regime)             AS rows_with_regime,
  ROUND(
    COUNT(wyckoff_regime) * 100.0 / COUNT(*),
    2
  )                                 AS pct_with_regime
FROM daily_snapshots;

\echo '===================================================================='
\echo '10) EVENT → REGIME WIRING CHECK'
\echo '===================================================================='

SELECT
  wyckoff_regime,
  wyckoff_regime_set_by_event,
  COUNT(*) AS occurrences
FROM daily_snapshots
WHERE wyckoff_regime_set_by_event IS NOT NULL
GROUP BY wyckoff_regime, wyckoff_regime_set_by_event
ORDER BY occurrences DESC;

\echo '===================================================================='
\echo '11) PARTIAL SNAPSHOT DETECTION'
\echo '   - Rows missing one or more critical components'
\echo '===================================================================='

SELECT
  COUNT(*) AS partial_rows
FROM daily_snapshots
WHERE
  technical_indicators_json IS NULL
  OR dealer_metrics_json IS NULL
  OR volatility_metrics_json IS NULL;

\echo '===================================================================='
\echo '12) SINGLE-SYMBOL SNAPSHOT TIMELINE (MANUAL INSPECTION)'
\echo '   - Change NVDA as needed'
\echo '===================================================================='

SELECT
  ds.time,
  ds.technical_indicators_json IS NOT NULL AS has_ta,
  ds.dealer_metrics_json IS NOT NULL       AS has_dealer,
  ds.volatility_metrics_json IS NOT NULL   AS has_vol,
  ds.events_detected,
  ds.wyckoff_regime
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'NVDA'
ORDER BY ds.time;

\echo '===================================================================='
\echo 'END OF A2 DAILY SNAPSHOTS INTEGRITY DASHBOARD'
\echo '===================================================================='