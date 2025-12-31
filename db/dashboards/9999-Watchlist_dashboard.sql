/* =============================================================================
   A2.2 WATCHLIST REGIME TRANSITION DETAILS DASHBOARD
   -----------------------------------------------------------------------------
   Purpose:
     - For each active watchlist symbol:
         • current Wyckoff regime
         • date regime began
         • event that triggered the regime
         • date of that triggering event
         • days in current regime
     - Provides operationally meaningful regime context

   Notes:
     - Read-only
     - Safe for production
     - Assumes B1 regime persistence is authoritative
   ========================================================================== */

\echo '===================================================================='
\echo 'WATCHLIST REGIME TRANSITION DETAILS'
\echo '===================================================================='

/* ---------------------------------------------------------------------
   1) CURRENT REGIME PER WATCHLIST SYMBOL
--------------------------------------------------------------------- */
\echo ''
\echo '1) CURRENT REGIME STATE'
\echo '--------------------------------------------------------------------'

WITH latest AS (
  SELECT DISTINCT ON (ds.ticker_id)
    ds.ticker_id,
    ds.time::date AS as_of_date,
    ds.wyckoff_regime,
    ds.wyckoff_regime_confidence
  FROM daily_snapshots ds
  WHERE ds.wyckoff_regime IS NOT NULL
  ORDER BY ds.ticker_id, ds.time DESC
)
SELECT
  t.symbol,
  l.wyckoff_regime,
  l.wyckoff_regime_confidence,
  l.as_of_date
FROM latest l
JOIN tickers t    ON t.id = l.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE
ORDER BY t.symbol;

\echo ''
\echo '===================================================================='
\echo '2) REGIME TRANSITION EVENT (AUTHORITATIVE)'
\echo '--------------------------------------------------------------------'

/*
  The transition event is defined as:
    - the most recent row where:
        • wyckoff_regime_set_by_event IS NOT NULL
        • that regime matches the CURRENT regime
*/

WITH current_regime AS (
  SELECT DISTINCT ON (ds.ticker_id)
    ds.ticker_id,
    ds.wyckoff_regime
  FROM daily_snapshots ds
  WHERE ds.wyckoff_regime IS NOT NULL
  ORDER BY ds.ticker_id, ds.time DESC
),
transition_event AS (
  SELECT DISTINCT ON (ds.ticker_id)
    ds.ticker_id,
    ds.time::date AS event_date,
    ds.wyckoff_regime,
    ds.wyckoff_regime_set_by_event AS event_code
  FROM daily_snapshots ds
  JOIN current_regime cr
    ON cr.ticker_id = ds.ticker_id
   AND cr.wyckoff_regime = ds.wyckoff_regime
  WHERE ds.wyckoff_regime_set_by_event IS NOT NULL
  ORDER BY ds.ticker_id, ds.time DESC
)
SELECT
  t.symbol,
  te.wyckoff_regime,
  te.event_code        AS transition_event,
  te.event_date        AS transition_date,
  (CURRENT_DATE - te.event_date) AS days_in_regime
FROM transition_event te
JOIN tickers t    ON t.id = te.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE
ORDER BY days_in_regime DESC, t.symbol;

\echo ''
\echo '===================================================================='
\echo '3) WATCHLIST REGIME SUMMARY'
\echo '--------------------------------------------------------------------'

SELECT
  ds.wyckoff_regime,
  COUNT(DISTINCT ds.ticker_id) AS tickers
FROM daily_snapshots ds
JOIN tickers t    ON t.id = ds.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE
GROUP BY ds.wyckoff_regime
ORDER BY tickers DESC;

\echo ''
\echo '===================================================================='
\echo '4) WATCHLIST SYMBOLS MISSING TRANSITION EVENTS'
\echo '   - Indicates regime persistence without explicit event'
\echo '--------------------------------------------------------------------'

SELECT
  w.symbol
FROM watchlists w
JOIN tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
LEFT JOIN daily_snapshots ds
  ON ds.ticker_id = t.id
 AND ds.wyckoff_regime_set_by_event IS NOT NULL
WHERE w.active = TRUE
GROUP BY w.symbol
HAVING COUNT(ds.time) = 0
ORDER BY w.symbol;

\echo ''
\echo '===================================================================='
\echo 'END OF WATCHLIST REGIME TRANSITION DASHBOARD'
\echo '===================================================================='