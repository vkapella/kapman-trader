/* =============================================================================
   B1 WYCKOFF REGIME VALIDATION DASHBOARD
   -----------------------------------------------------------------------------
   Purpose:
     - Validate B1 daily regime persistence correctness
     - Verify B2 → B1 wiring (event → regime)
     - Inspect coverage, churn, and watchlist health
     - Spot-check individual symbols

   Notes:
     - Read-only diagnostics
     - No temp tables required
     - Safe to run in production
   ========================================================================== */

\echo '===================================================================='
\echo '1) GLOBAL SNAPSHOT COVERAGE'
\echo '   - Total rows, ticker coverage, and date range'
\echo '===================================================================='

SELECT
  COUNT(*)                       AS total_snapshots,
  COUNT(DISTINCT ticker_id)      AS tickers_covered,
  MIN(time)::date                AS first_date,
  MAX(time)::date                AS last_date
FROM daily_snapshots
WHERE wyckoff_regime IS NOT NULL;

\echo '===================================================================='
\echo '2) CURRENT REGIME DISTRIBUTION (LATEST PER TICKER)'
\echo '   - One row per ticker (most recent regime)'
\echo '===================================================================='

WITH latest AS (
  SELECT DISTINCT ON (ds.ticker_id)
    ds.ticker_id,
    t.symbol,
    ds.wyckoff_regime,
    ds.wyckoff_regime_confidence,
    ds.wyckoff_regime_set_by_event,
    ds.time::date AS as_of_date
  FROM daily_snapshots ds
  JOIN tickers t ON t.id = ds.ticker_id
  WHERE ds.wyckoff_regime IS NOT NULL
  ORDER BY ds.ticker_id, ds.time DESC
)
SELECT
  wyckoff_regime,
  COUNT(*) AS ticker_count,
  ROUND(AVG(wyckoff_regime_confidence), 3) AS avg_confidence
FROM latest
GROUP BY wyckoff_regime
ORDER BY ticker_count DESC;

\echo '===================================================================='
\echo '3) REGIME PERSISTENCE (TIME-WEIGHTED DAYS)'
\echo '   - How much time the market spends in each regime'
\echo '===================================================================='

SELECT
  wyckoff_regime,
  COUNT(*) AS total_days,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_days
FROM daily_snapshots
WHERE wyckoff_regime IS NOT NULL
GROUP BY wyckoff_regime
ORDER BY total_days DESC;

\echo '===================================================================='
\echo '4) EVENT → REGIME ATTRIBUTION'
\echo '   - Verifies B2 structural events are driving B1 regimes'
\echo '===================================================================='

SELECT
  wyckoff_regime,
  wyckoff_regime_set_by_event AS event_code,
  COUNT(*) AS occurrences
FROM daily_snapshots
WHERE wyckoff_regime_set_by_event IS NOT NULL
GROUP BY wyckoff_regime, wyckoff_regime_set_by_event
ORDER BY occurrences DESC;

\echo '===================================================================='
\echo '5) STRUCTURAL EVENT FIRING COUNTS (B2 HEALTH CHECK)'
\echo '   - Confirms B2 is emitting expected event distribution'
\echo '===================================================================='

SELECT
  e.event_code,
  COUNT(*) AS total_events
FROM daily_snapshots ds
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
GROUP BY e.event_code
ORDER BY total_events DESC;

\echo '===================================================================='
\echo '6) REGIME TRANSITIONS (CHURN / STABILITY)'
\echo '   - Counts regime changes across all tickers'
\echo '===================================================================='

WITH ordered AS (
  SELECT
    ds.ticker_id,
    t.symbol,
    ds.time::date AS d,
    ds.wyckoff_regime,
    LAG(ds.wyckoff_regime) OVER (
      PARTITION BY ds.ticker_id ORDER BY ds.time
    ) AS prior_regime
  FROM daily_snapshots ds
  JOIN tickers t ON t.id = ds.ticker_id
  WHERE ds.wyckoff_regime IS NOT NULL
)
SELECT
  prior_regime || ' → ' || wyckoff_regime AS transition,
  COUNT(*) AS occurrences
FROM ordered
WHERE prior_regime IS NOT NULL
  AND prior_regime <> wyckoff_regime
GROUP BY transition
ORDER BY occurrences DESC;

\echo '===================================================================='
\echo '7) WATCHLIST REGIME SNAPSHOT'
\echo '   - Current regimes for active watchlist symbols'
\echo '===================================================================='

SELECT
  ds.wyckoff_regime,
  COUNT(DISTINCT ds.ticker_id) AS tickers
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE
GROUP BY ds.wyckoff_regime
ORDER BY tickers DESC;

\echo '===================================================================='
\echo '8) SINGLE-SYMBOL REGIME TIMELINE'
\echo '   - Manual inspection (change NVDA as needed)'
\echo '===================================================================='

SELECT
  ds.time::date,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.wyckoff_regime_set_by_event,
  ds.events_detected
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'NVDA'
ORDER BY ds.time;

\echo '===================================================================='
\echo '9) CONFIDENCE AUDIT'
\echo '   - Expected flat 1.0 for event-driven regimes'
\echo '===================================================================='

SELECT
  wyckoff_regime,
  MIN(wyckoff_regime_confidence) AS min_conf,
  MAX(wyckoff_regime_confidence) AS max_conf,
  COUNT(*) AS rows
FROM daily_snapshots
WHERE wyckoff_regime_confidence IS NOT NULL
GROUP BY wyckoff_regime
ORDER BY wyckoff_regime;

\echo '===================================================================='
\echo '10) PARTIAL-WRITE / CORRUPTION GUARD'
\echo '    - Should return ZERO rows'
\echo '===================================================================='

WITH per_ticker AS (
  SELECT
    ticker_id,
    COUNT(*) AS rows,
    COUNT(wyckoff_regime) AS regimes_set
  FROM daily_snapshots
  WHERE wyckoff_regime IS NOT NULL
  GROUP BY ticker_id
)
SELECT *
FROM per_ticker
WHERE regimes_set <> rows
ORDER BY (rows - regimes_set) DESC;

\echo '===================================================================='
\echo 'END OF B1 WYCKOFF REGIME VALIDATION DASHBOARD'
\echo '===================================================================='