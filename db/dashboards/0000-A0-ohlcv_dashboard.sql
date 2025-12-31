/* =============================================================================
   A0 OHLCV DATA QUALITY & COVERAGE DASHBOARD
   -----------------------------------------------------------------------------
   Purpose:
     - Validate OHLCV coverage and continuity
     - Detect gaps, anomalies, and suspicious bars
     - Confirm suitability for B2 structural event detection
     - Provide baseline health metrics for the data layer

   Notes:
     - Read-only diagnostics
     - No temp tables required
     - Safe to run in production
   ========================================================================== */

\echo '===================================================================='
\echo '1) GLOBAL OHLCV COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(*)                  AS total_bars,
  COUNT(DISTINCT ticker_id) AS tickers_covered,
  MIN(date)                 AS first_date,
  MAX(date)                 AS last_date
FROM ohlcv;

\echo '===================================================================='
\echo '2) BAR COUNTS PER TICKER (LOW-END DISTRIBUTION)'
\echo '   - Identifies thin-history symbols'
\echo '===================================================================='

WITH per_ticker AS (
  SELECT
    ticker_id,
    COUNT(*) AS bar_count
  FROM ohlcv
  GROUP BY ticker_id
)
SELECT
  MIN(bar_count)                       AS min_bars,
  MAX(bar_count)                       AS max_bars,
  ROUND(AVG(bar_count))                AS avg_bars,
  COUNT(*) FILTER (WHERE bar_count < 50)   AS tickers_lt_50,
  COUNT(*) FILTER (WHERE bar_count < 100)  AS tickers_lt_100,
  COUNT(*) FILTER (WHERE bar_count < 250)  AS tickers_lt_250
FROM per_ticker;

\echo '===================================================================='
\echo '3) THIN HISTORY TICKERS (TOP 25)'
\echo '===================================================================='

WITH per_ticker AS (
  SELECT
    ticker_id,
    COUNT(*) AS bar_count
  FROM ohlcv
  GROUP BY ticker_id
)
SELECT
  t.symbol,
  p.bar_count
FROM per_ticker p
JOIN tickers t ON t.id = p.ticker_id
ORDER BY p.bar_count ASC
LIMIT 25;

\echo '===================================================================='
\echo '4) DATE CONTINUITY CHECK (LARGE GAPS)'
\echo '   - Gaps > 7 calendar days'
\echo '===================================================================='

WITH ordered AS (
  SELECT
    ticker_id,
    date,
    LAG(date) OVER (
      PARTITION BY ticker_id ORDER BY date
    ) AS prior_date
  FROM ohlcv
)
SELECT
  t.symbol,
  COUNT(*) AS gap_count
FROM ordered o
JOIN tickers t ON t.id = o.ticker_id
WHERE prior_date IS NOT NULL
  AND date > prior_date + INTERVAL '7 days'
GROUP BY t.symbol
ORDER BY gap_count DESC
LIMIT 25;

\echo '===================================================================='
\echo '5) OHLC SANITY CHECKS'
\echo '   - Invalid price relationships (should be ZERO)'
\echo '===================================================================='

SELECT
  COUNT(*) AS invalid_bars
FROM ohlcv
WHERE
  low  > high
  OR open < low
  OR open > high
  OR close < low
  OR close > high;

\echo '===================================================================='
\echo '6) ZERO / NULL VOLUME CHECK'
\echo '===================================================================='

SELECT
  COUNT(*) AS zero_or_null_volume_bars
FROM ohlcv
WHERE volume IS NULL OR volume <= 0;

\echo '===================================================================='
\echo '7) EXTREME DAILY RANGE OUTLIERS'
\echo '   - (high - low) / close > 25%'
\echo '===================================================================='

SELECT
  t.symbol,
  o.date,
  o.open,
  o.high,
  o.low,
  o.close,
  ROUND((o.high - o.low) / NULLIF(o.close, 0), 3) AS range_ratio
FROM ohlcv o
JOIN tickers t ON t.id = o.ticker_id
WHERE (o.high - o.low) / NULLIF(o.close, 0) > 0.25
ORDER BY range_ratio DESC
LIMIT 25;

\echo '===================================================================='
\echo '8) EXTREME VOLUME SPIKES'
\echo '===================================================================='

SELECT
  t.symbol,
  o.date,
  o.volume
FROM ohlcv o
JOIN tickers t ON t.id = o.ticker_id
ORDER BY o.volume DESC
LIMIT 25;

\echo '===================================================================='
\echo '9) WATCHLIST OHLCV COVERAGE'
\echo '===================================================================='

SELECT
  COUNT(DISTINCT o.ticker_id) AS watchlist_tickers_with_data,
  MIN(o.date)                 AS earliest_date,
  MAX(o.date)                 AS latest_date
FROM ohlcv o
JOIN tickers t ON t.id = o.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE;

\echo '===================================================================='
\echo '10) SINGLE-SYMBOL OHLCV TIMELINE (MANUAL INSPECTION)'
\echo '===================================================================='

SELECT
  o.date,
  o.open,
  o.high,
  o.low,
  o.close,
  o.volume
FROM ohlcv o
JOIN tickers t ON t.id = o.ticker_id
WHERE UPPER(t.symbol) = 'NVDA'
ORDER BY o.date;

\echo '===================================================================='
\echo '11) B2 READINESS CHECK'
\echo '    - Bars with high == low (invalid for close-position logic)'
\echo '===================================================================='

SELECT
  COUNT(*) AS flat_range_bars
FROM ohlcv
WHERE high = low;

\echo '===================================================================='
\echo 'END OF A0 OHLCV DATA QUALITY DASHBOARD'
\echo '===================================================================='