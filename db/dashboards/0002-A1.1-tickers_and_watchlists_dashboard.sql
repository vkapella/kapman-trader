/* =============================================================================
   A1.1 TICKERS & WATCHLISTS VALIDATION DASHBOARD
   -----------------------------------------------------------------------------
   Purpose:
     - Validate ticker master integrity
     - Validate watchlist → ticker wiring
     - Detect symbol mismatches, duplicates, and inactive leakage
     - Confirm universe consistency for downstream pipelines (A0/B2/B1)

   Notes:
     - Read-only diagnostics
     - No temp tables required
     - Safe to run in production
   ========================================================================== */

\echo '===================================================================='
\echo '1) TICKERS TABLE OVERVIEW'
\echo '   - Total tickers and active/inactive split'
\echo '===================================================================='

SELECT
  COUNT(*)                                AS total_tickers,
  COUNT(*) FILTER (WHERE is_active)       AS active_tickers,
  COUNT(*) FILTER (WHERE NOT is_active)   AS inactive_tickers
FROM tickers;

\echo '===================================================================='
\echo '2) SYMBOL UNIQUENESS CHECK'
\echo '   - Should return ZERO rows'
\echo '===================================================================='

SELECT
  UPPER(symbol) AS symbol,
  COUNT(*)      AS occurrences
FROM tickers
GROUP BY UPPER(symbol)
HAVING COUNT(*) > 1
ORDER BY occurrences DESC;

\echo '===================================================================='
\echo '3) WATCHLIST OVERVIEW'
\echo '   - Total rows and active/inactive split'
\echo '===================================================================='

SELECT
  COUNT(*)                              AS total_watchlist_rows,
  COUNT(*) FILTER (WHERE active)        AS active_rows,
  COUNT(*) FILTER (WHERE NOT active)    AS inactive_rows
FROM watchlists;

\echo '===================================================================='
\echo '4) ACTIVE WATCHLIST SYMBOLS WITHOUT TICKERS'
\echo '   - CRITICAL: symbols that will be silently dropped'
\echo '===================================================================='

SELECT
  w.symbol
FROM watchlists w
LEFT JOIN tickers t
  ON UPPER(t.symbol) = UPPER(w.symbol)
WHERE w.active = TRUE
  AND t.id IS NULL
ORDER BY w.symbol;

\echo '===================================================================='
\echo '5) INACTIVE TICKERS STILL REFERENCED BY ACTIVE WATCHLIST'
\echo '   - Potential universe hygiene issue'
\echo '===================================================================='

SELECT
  t.symbol,
  t.is_active
FROM watchlists w
JOIN tickers t
  ON UPPER(t.symbol) = UPPER(w.symbol)
WHERE w.active = TRUE
  AND t.is_active = FALSE
ORDER BY t.symbol;

\echo '===================================================================='
\echo '6) WATCHLIST SYMBOL MULTIPLICITY'
\echo '   - Same symbol appearing multiple times'
\echo '===================================================================='

SELECT
  UPPER(symbol) AS symbol,
  COUNT(*)      AS occurrences
FROM watchlists
WHERE active = TRUE
GROUP BY UPPER(symbol)
HAVING COUNT(*) > 1
ORDER BY occurrences DESC;

\echo '===================================================================='
\echo '7) WATCHLIST → TICKER JOIN HEALTH (ACTIVE ONLY)'
\echo '   - Confirms one-to-one mapping'
\echo '===================================================================='

SELECT
  COUNT(DISTINCT w.symbol)        AS watchlist_symbols,
  COUNT(DISTINCT t.id)            AS matched_tickers,
  (COUNT(DISTINCT w.symbol) = COUNT(DISTINCT t.id))
                                  AS perfect_alignment
FROM watchlists w
LEFT JOIN tickers t
  ON UPPER(t.symbol) = UPPER(w.symbol)
WHERE w.active = TRUE;

\echo '===================================================================='
\echo '8) TICKERS NOT REFERENCED BY ANY ACTIVE WATCHLIST'
\echo '   - Informational: valid universe expansion candidates'
\echo '===================================================================='

SELECT
  t.symbol
FROM tickers t
LEFT JOIN watchlists w
  ON UPPER(w.symbol) = UPPER(t.symbol)
  AND w.active = TRUE
WHERE t.is_active = TRUE
  AND w.symbol IS NULL
ORDER BY t.symbol
LIMIT 50;

\echo '===================================================================='
\echo '9) WATCHLIST SIZE SUMMARY'
\echo '===================================================================='

SELECT
  COUNT(DISTINCT symbol) AS distinct_symbols,
  COUNT(*)               AS total_rows
FROM watchlists
WHERE active = TRUE;

\echo '===================================================================='
\echo 'END OF A1.1 TICKERS & WATCHLISTS DASHBOARD'
\echo '===================================================================='