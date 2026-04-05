\echo '============================================================'
\echo 'B4.1 WYCKOFF SEQUENCES DASHBOARD'
\echo '============================================================'
\echo ''
\echo 'Notes:'
\echo '  - Source tables: wyckoff_sequences, wyckoff_sequence_events'
\echo '  - Exact run-time skipped/processed counters are not persisted by B4.1'
\echo '  - Main panels focus on canonical B4.1 rows where events_in_sequence includes terminal_event'
\echo '  - Legacy rows from older sequence logic are surfaced separately for drift visibility'
\echo ''

\echo '1) Global sequence coverage'
\echo '------------------------------------------------------------'
WITH canonical_sequences AS (
  SELECT *
  FROM public.wyckoff_sequences
  WHERE events_in_sequence ? 'terminal_event'
)
SELECT
  COUNT(*) AS canonical_sequences,
  COUNT(DISTINCT ticker_id) AS tickers_with_sequences,
  COUNT(*) FILTER (
    WHERE COALESCE((events_in_sequence ->> 'invalidated')::boolean, FALSE)
  ) AS invalidated_sequences,
  COUNT(*) FILTER (
    WHERE NOT COALESCE((events_in_sequence ->> 'invalidated')::boolean, FALSE)
  ) AS non_invalidated_sequences,
  MIN(start_date) AS first_sequence_start,
  MAX(completion_date) AS last_sequence_completion
FROM canonical_sequences;

\echo ''

\echo '2) Canonical vs legacy sequence rows'
\echo '------------------------------------------------------------'
SELECT
  COUNT(*) AS total_sequence_rows,
  COUNT(*) FILTER (WHERE events_in_sequence ? 'terminal_event') AS canonical_b4_1_rows,
  COUNT(*) FILTER (WHERE NOT (events_in_sequence ? 'terminal_event')) AS legacy_noncanonical_rows
FROM public.wyckoff_sequences;

\echo ''

\echo '3) Sequence type distribution (canonical B4.1 only)'
\echo '------------------------------------------------------------'
WITH canonical_sequences AS (
  SELECT *
  FROM public.wyckoff_sequences
  WHERE events_in_sequence ? 'terminal_event'
)
SELECT
  ws.sequence_id,
  COUNT(*) AS sequences,
  COUNT(DISTINCT ws.ticker_id) AS tickers,
  COUNT(*) FILTER (
    WHERE COALESCE((ws.events_in_sequence ->> 'invalidated')::boolean, FALSE)
  ) AS invalidated_sequences,
  ROUND(
    AVG(NULLIF(ws.events_in_sequence ->> 'confidence', '')::numeric),
    4
  ) AS avg_confidence,
  ROUND(AVG((ws.completion_date - ws.start_date + 1)::numeric), 2) AS avg_span_days,
  MIN(ws.start_date) AS first_start_date,
  MAX(ws.completion_date) AS last_completion_date
FROM canonical_sequences ws
GROUP BY ws.sequence_id
ORDER BY sequences DESC, ws.sequence_id;

\echo ''

\echo '4) Sequence event composition (canonical B4.1 only)'
\echo '------------------------------------------------------------'
WITH canonical_sequences AS (
  SELECT ticker_id, sequence_id, completion_date
  FROM public.wyckoff_sequences
  WHERE events_in_sequence ? 'terminal_event'
)
SELECT
  wse.sequence_id,
  wse.event_role,
  wse.event_type,
  COUNT(*) AS total_events,
  COUNT(DISTINCT wse.ticker_id) AS distinct_tickers
FROM public.wyckoff_sequence_events wse
JOIN canonical_sequences cs
  ON cs.ticker_id = wse.ticker_id
 AND cs.sequence_id = wse.sequence_id
 AND cs.completion_date = wse.completion_date
GROUP BY wse.sequence_id, wse.event_role, wse.event_type
ORDER BY wse.sequence_id, wse.event_role, total_events DESC, wse.event_type;

\echo ''

\echo '5) Watchlist sequence coverage (canonical B4.1 only)'
\echo '------------------------------------------------------------'
WITH active_watchlist AS (
  SELECT DISTINCT t.id AS ticker_id, UPPER(t.symbol) AS symbol
  FROM public.watchlists w
  JOIN public.tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
  WHERE w.active = TRUE
),
watchlist_with_sequences AS (
  SELECT DISTINCT ws.ticker_id
  FROM public.wyckoff_sequences ws
  JOIN active_watchlist aw ON aw.ticker_id = ws.ticker_id
  WHERE ws.events_in_sequence ? 'terminal_event'
)
SELECT
  (SELECT COUNT(*) FROM active_watchlist) AS active_watchlist_symbols,
  (SELECT COUNT(*) FROM watchlist_with_sequences) AS watchlist_symbols_with_sequences,
  (SELECT COUNT(*) FROM active_watchlist) - (SELECT COUNT(*) FROM watchlist_with_sequences) AS watchlist_symbols_without_sequences,
  ROUND(
    100.0 * (SELECT COUNT(*) FROM watchlist_with_sequences)::numeric
    / NULLIF((SELECT COUNT(*) FROM active_watchlist), 0),
    2
  ) AS watchlist_sequence_coverage_pct;

\echo ''

\echo '6) Watchlist symbols with no persisted canonical B4.1 sequences'
\echo '------------------------------------------------------------'
SELECT
  aw.symbol
FROM (
  SELECT DISTINCT t.id AS ticker_id, UPPER(t.symbol) AS symbol
  FROM public.watchlists w
  JOIN public.tickers t ON UPPER(t.symbol) = UPPER(w.symbol)
  WHERE w.active = TRUE
) aw
LEFT JOIN public.wyckoff_sequences ws
  ON ws.ticker_id = aw.ticker_id
 AND ws.events_in_sequence ? 'terminal_event'
GROUP BY aw.symbol
HAVING COUNT(ws.ticker_id) = 0
ORDER BY aw.symbol;

\echo ''

\echo '7) Candidate terminal events without persisted canonical sequence (watchlist)'
\echo '------------------------------------------------------------'
WITH candidate_terminals AS (
  SELECT DISTINCT
    ds.ticker_id,
    t.symbol,
    ds.time::date AS terminal_date,
    UPPER(ev.event_code) AS terminal_event,
    ds.wyckoff_regime
  FROM public.daily_snapshots ds
  JOIN public.tickers t ON t.id = ds.ticker_id
  JOIN public.watchlists w ON UPPER(w.symbol) = UPPER(t.symbol)
  CROSS JOIN LATERAL unnest(ds.events_detected) AS ev(event_code)
  WHERE w.active = TRUE
    AND UPPER(ev.event_code) IN ('SOS', 'SOW')
),
persisted_terminals AS (
  SELECT
    ws.ticker_id,
    ws.completion_date,
    UPPER(ws.events_in_sequence ->> 'terminal_event') AS terminal_event,
    ws.sequence_id,
    COALESCE((ws.events_in_sequence ->> 'invalidated')::boolean, FALSE) AS invalidated
  FROM public.wyckoff_sequences ws
  WHERE ws.events_in_sequence ? 'terminal_event'
)
SELECT
  ct.symbol,
  ct.terminal_date,
  ct.terminal_event,
  ct.wyckoff_regime AS regime_on_terminal_date
FROM candidate_terminals ct
LEFT JOIN persisted_terminals pt
  ON pt.ticker_id = ct.ticker_id
 AND pt.completion_date = ct.terminal_date
 AND pt.terminal_event = ct.terminal_event
WHERE pt.ticker_id IS NULL
ORDER BY ct.terminal_date DESC, ct.symbol
LIMIT 100;

\echo ''

\echo '8) Invalidated sequence reasons (canonical B4.1 only)'
\echo '------------------------------------------------------------'
SELECT
  COALESCE(ws.events_in_sequence ->> 'invalidated_reason', 'UNKNOWN') AS invalidated_reason,
  COUNT(*) AS sequences
FROM public.wyckoff_sequences ws
WHERE ws.events_in_sequence ? 'terminal_event'
  AND COALESCE((ws.events_in_sequence ->> 'invalidated')::boolean, FALSE)
GROUP BY COALESCE(ws.events_in_sequence ->> 'invalidated_reason', 'UNKNOWN')
ORDER BY sequences DESC, invalidated_reason;

\echo ''

\echo '9) Recent canonical B4.1 sequence completions (operator feed)'
\echo '------------------------------------------------------------'
SELECT
  t.symbol,
  ws.sequence_id,
  ws.start_date,
  ws.completion_date,
  (ws.completion_date - ws.start_date + 1) AS span_days,
  ws.events_in_sequence ->> 'terminal_event' AS terminal_event,
  ws.events_in_sequence ->> 'prior_regime' AS prior_regime,
  NULLIF(ws.events_in_sequence ->> 'confidence', '')::numeric(6,4) AS confidence,
  COALESCE((ws.events_in_sequence ->> 'invalidated')::boolean, FALSE) AS invalidated,
  ws.events_in_sequence ->> 'invalidated_reason' AS invalidated_reason
FROM public.wyckoff_sequences ws
JOIN public.tickers t ON t.id = ws.ticker_id
WHERE ws.events_in_sequence ? 'terminal_event'
ORDER BY ws.completion_date DESC, t.symbol
LIMIT 50;

\echo ''

\echo '10) Optional per-symbol drilldown'
\echo '------------------------------------------------------------'

\if :{?symbol}

\echo '10a) Canonical sequence history for symbol :'symbol''
SELECT
  ws.sequence_id,
  ws.start_date,
  ws.completion_date,
  (ws.completion_date - ws.start_date + 1) AS span_days,
  ws.events_in_sequence ->> 'terminal_event' AS terminal_event,
  ws.events_in_sequence ->> 'prior_regime' AS prior_regime,
  NULLIF(ws.events_in_sequence ->> 'confidence', '')::numeric(6,4) AS confidence,
  COALESCE((ws.events_in_sequence ->> 'invalidated')::boolean, FALSE) AS invalidated,
  ws.events_in_sequence ->> 'invalidated_reason' AS invalidated_reason
FROM public.wyckoff_sequences ws
JOIN public.tickers t ON t.id = ws.ticker_id
WHERE UPPER(t.symbol) = UPPER(:'symbol')
  AND ws.events_in_sequence ? 'terminal_event'
ORDER BY ws.completion_date DESC, ws.sequence_id;

\echo ''

\echo '10b) Canonical sequence event chains for symbol :'symbol''
SELECT
  ws.completion_date,
  ws.sequence_id,
  wse.event_order,
  wse.event_role,
  wse.event_type,
  wse.event_date
FROM public.wyckoff_sequence_events wse
JOIN public.wyckoff_sequences ws
  ON ws.ticker_id = wse.ticker_id
 AND ws.sequence_id = wse.sequence_id
 AND ws.completion_date = wse.completion_date
JOIN public.tickers t ON t.id = wse.ticker_id
WHERE UPPER(t.symbol) = UPPER(:'symbol')
  AND ws.events_in_sequence ? 'terminal_event'
ORDER BY ws.completion_date DESC, ws.sequence_id, wse.event_order;

\else

\echo 'Symbol not provided; skipping per-symbol drilldown sections.'

\endif

\echo ''
\echo '============================================================'
\echo 'END OF B4.1 WYCKOFF SEQUENCES DASHBOARD'
\echo '============================================================'
