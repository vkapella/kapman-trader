\echo '============================================================'
\echo 'B2 WYCKOFF STRUCTURAL EVENTS – VALIDATION DASHBOARD'
\echo '============================================================'
\echo ''

/* ------------------------------------------------------------ */
\echo '1) Global snapshot coverage for B2 structural events'
\echo '   (How much data exists, date range, ticker coverage)'
\echo '------------------------------------------------------------'
SELECT
  COUNT(*)                       AS total_snapshots,
  COUNT(DISTINCT ticker_id)      AS tickers_covered,
  MIN(time)::date                AS first_date,
  MAX(time)::date                AS last_date
FROM daily_snapshots
WHERE events_detected IS NOT NULL;

\echo ''

/* ------------------------------------------------------------ */
\echo '2) Total occurrences by Wyckoff event code (all history)'
\echo '   (Validates relative frequency vs research benchmark)'
\echo '------------------------------------------------------------'
SELECT
  e.event_code,
  COUNT(*) AS occurrences
FROM daily_snapshots ds
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
GROUP BY e.event_code
ORDER BY occurrences DESC;

\echo ''

/* ------------------------------------------------------------ */
\echo '3) Distinct tickers that have ever emitted each event'
\echo '   (Coverage diagnostic: how many symbols participate)'
\echo '------------------------------------------------------------'
SELECT
  e.event_code,
  COUNT(DISTINCT ds.ticker_id) AS tickers_with_event
FROM daily_snapshots ds
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
GROUP BY e.event_code
ORDER BY tickers_with_event DESC;

\echo ''

/* ------------------------------------------------------------ */
\echo '4) Event occurrences restricted to active watchlist'
\echo '   (Operational relevance for current universe)'
\echo '------------------------------------------------------------'
SELECT
  e.event_code,
  COUNT(*) AS occurrences
FROM daily_snapshots ds
JOIN tickers t
  ON t.id = ds.ticker_id
JOIN watchlists w
  ON UPPER(w.symbol) = UPPER(t.symbol)
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
WHERE w.active = TRUE
GROUP BY e.event_code
ORDER BY occurrences DESC;

\echo ''

/* ------------------------------------------------------------ */
\echo '5) Latest structural event per ticker'
\echo '   (Ensures single-instance-per-event semantics hold)'
\echo '------------------------------------------------------------'
WITH exploded AS (
  SELECT
    ds.ticker_id,
    ds.time,
    e.event_code
  FROM daily_snapshots ds
  CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
),
latest AS (
  SELECT DISTINCT ON (ticker_id, event_code)
    ticker_id,
    event_code,
    time
  FROM exploded
  ORDER BY ticker_id, event_code, time DESC
)
SELECT
  event_code,
  COUNT(*) AS tickers_with_latest_event
FROM latest
GROUP BY event_code
ORDER BY tickers_with_latest_event DESC;

\echo ''

/* ------------------------------------------------------------ */
\echo '6) Event co-occurrence sanity check (should be rare)'
\echo '   (Counts bars with more than one structural event)'
\echo '------------------------------------------------------------'
SELECT
  COUNT(*) AS bars_with_multiple_events
FROM daily_snapshots
WHERE events_detected IS NOT NULL
  AND array_length(events_detected, 1) > 1;

\echo ''

/* ------------------------------------------------------------ */
\echo '7) Event timeline sample for manual inspection'
\echo '   (Replace :symbol with a real ticker symbol)'
\echo '------------------------------------------------------------'
-- Example usage:
-- \set symbol 'NVDA'
SELECT
  ds.time::date AS date,
  e.event_code
FROM daily_snapshots ds
JOIN tickers t
  ON t.id = ds.ticker_id
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
WHERE UPPER(t.symbol) = UPPER(:symbol)
ORDER BY ds.time;

\echo ''

/* ------------------------------------------------------------ */
\echo '8) Event density by calendar year'
\echo '   (Checks temporal clustering and drift)'
\echo '------------------------------------------------------------'
SELECT
  EXTRACT(YEAR FROM ds.time) AS year,
  e.event_code,
  COUNT(*) AS occurrences
FROM daily_snapshots ds
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
GROUP BY year, e.event_code
ORDER BY year, occurrences DESC;

\echo ''

/* ------------------------------------------------------------ */
\echo '9) Structural event to regime alignment check'
\echo '   (Ensures B2 events line up with B1 regime outcomes)'
\echo '------------------------------------------------------------'
SELECT
  e.event_code,
  ds.wyckoff_regime,
  COUNT(*) AS occurrences
FROM daily_snapshots ds
CROSS JOIN LATERAL unnest(ds.events_detected) AS e(event_code)
WHERE ds.wyckoff_regime IS NOT NULL
GROUP BY e.event_code, ds.wyckoff_regime
ORDER BY e.event_code, occurrences DESC;

\echo ''
\echo '============================================================'
\echo 'END OF B2 WYCKOFF STRUCTURAL EVENTS DASHBOARD'
\echo '============================================================'