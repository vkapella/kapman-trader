\echo '============================================================'
\echo 'B4 WYCKOFF DERIVED – VALIDATION DASHBOARD'
\echo '============================================================'
\echo ''

\echo '1) Global coverage for regime transitions'
\echo '------------------------------------------------------------'
SELECT
  COUNT(*)                  AS total_transitions,
  COUNT(DISTINCT ticker_id) AS tickers_with_transitions,
  MIN(date)                 AS first_transition_date,
  MAX(date)                 AS last_transition_date
FROM wyckoff_regime_transitions;

\echo ''

\echo '2) Transition matrix (prior_regime -> new_regime)'
\echo '------------------------------------------------------------'
SELECT
  prior_regime,
  new_regime,
  COUNT(*) AS transition_count
FROM wyckoff_regime_transitions
GROUP BY prior_regime, new_regime
ORDER BY transition_count DESC;

\echo ''

\echo '3) Transition occurrences restricted to active watchlist'
\echo '------------------------------------------------------------'
SELECT
  wrt.prior_regime,
  wrt.new_regime,
  COUNT(*) AS transition_count
FROM wyckoff_regime_transitions wrt
JOIN tickers t ON t.id = wrt.ticker_id
JOIN watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
WHERE w.active = TRUE
GROUP BY wrt.prior_regime, wrt.new_regime
ORDER BY transition_count DESC;

\echo ''

\echo '4) Per-ticker transition activity (top 25)'
\echo '------------------------------------------------------------'
SELECT
  t.symbol,
  COUNT(*)      AS transition_count,
  MIN(wrt.date) AS first_transition,
  MAX(wrt.date) AS last_transition
FROM wyckoff_regime_transitions wrt
JOIN tickers t ON t.id = wrt.ticker_id
GROUP BY t.symbol
ORDER BY transition_count DESC, t.symbol
LIMIT 25;

\echo ''

\echo '5) Duration stats (bars) by new_regime'
\echo '------------------------------------------------------------'
SELECT
  new_regime,
  COUNT(*)                         AS transitions,
  AVG(duration_bars)::NUMERIC(6,2) AS avg_duration_bars,
  MIN(duration_bars)               AS min_duration_bars,
  MAX(duration_bars)               AS max_duration_bars
FROM wyckoff_regime_transitions
WHERE duration_bars IS NOT NULL
GROUP BY new_regime
ORDER BY transitions DESC;

\echo ''

\echo '6) Evidence coverage for transitions'
\echo '------------------------------------------------------------'
SELECT
  COUNT(*) AS transitions,
  COUNT(e.ticker_id) AS transitions_with_evidence,
  ROUND(
    COUNT(e.ticker_id)::NUMERIC / NULLIF(COUNT(*), 0) * 100,
    2
  ) AS evidence_coverage_pct
FROM wyckoff_regime_transitions wrt
LEFT JOIN wyckoff_snapshot_evidence e
  ON e.ticker_id = wrt.ticker_id
 AND e.date = wrt.date;

\echo ''

\echo '7) Recent transitions (operator feed)'
\echo '------------------------------------------------------------'
SELECT
  t.symbol,
  wrt.date,
  wrt.prior_regime,
  wrt.new_regime,
  wrt.duration_bars
FROM wyckoff_regime_transitions wrt
JOIN tickers t ON t.id = wrt.ticker_id
ORDER BY wrt.date DESC, t.symbol
LIMIT 50;

\echo ''

\echo '8) Transition density by calendar year'
\echo '------------------------------------------------------------'
SELECT
  EXTRACT(YEAR FROM wrt.date) AS year,
  wrt.prior_regime,
  wrt.new_regime,
  COUNT(*) AS transitions
FROM wyckoff_regime_transitions wrt
GROUP BY year, wrt.prior_regime, wrt.new_regime
ORDER BY year, transitions DESC;

\echo ''

\echo '9) Sequences and context events'
\echo '------------------------------------------------------------'
SELECT
  (SELECT COUNT(*) FROM public.wyckoff_sequences)       AS sequences_total,
  (SELECT COUNT(*) FROM public.wyckoff_sequence_events) AS sequence_events_total,
  (SELECT COUNT(*) FROM wyckoff_snapshot_evidence) AS evidence_rows_total;

\echo ''

\echo '10) Per-symbol drilldown (optional)'
\echo '------------------------------------------------------------'

\if :{?symbol}

\echo '10a) Recent transitions for symbol :'symbol''
SELECT
  wrt.date,
  wrt.prior_regime,
  wrt.new_regime,
  wrt.duration_bars
FROM wyckoff_regime_transitions wrt
JOIN tickers t ON t.id = wrt.ticker_id
WHERE UPPER(t.symbol) = UPPER(:'symbol')
ORDER BY wrt.date DESC
LIMIT 50;

\echo ''

\echo '10b) Evidence presence for symbol :'symbol''
SELECT
  e.date,
  jsonb_typeof(e.evidence_json) AS evidence_json_type
FROM wyckoff_snapshot_evidence e
JOIN tickers t ON t.id = e.ticker_id
WHERE UPPER(t.symbol) = UPPER(:'symbol')
ORDER BY e.date DESC
LIMIT 50;

\else

\echo 'Symbol not provided; skipping per-symbol drilldown sections.'

\endif

\echo ''
\echo '============================================================'
\echo 'END OF B4 WYCKOFF DERIVED DASHBOARD'
\echo '============================================================'
