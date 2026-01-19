-- ============================================================
-- KapMan Daily Inspection Dashboard (psql-safe)
-- ============================================================

\echo ''
\echo '============================================================'
\echo 'PANEL 1: TABLE INVENTORY & FOOTPRINT'
\echo '============================================================'

SELECT
  c.relname AS table_name,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
  c.reltuples::bigint AS est_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
    'ohlcv',
    'daily_snapshots',
    'options_chains',
    'recommendations',
    'recommendation_outcomes',
    'wyckoff_context_events',
    'wyckoff_regime_transitions',
    'wyckoff_sequences',
    'wyckoff_sequence_events',
    'wyckoff_snapshot_evidence',
    'tickers',
    'watchlists'
  )
ORDER BY pg_total_relation_size(c.oid) DESC;

\echo ''
\echo '============================================================'
\echo 'PANEL 2: DAILY SNAPSHOTS — TIME COVERAGE'
\echo '============================================================'

SELECT
  MIN(time)::date AS first_day,
  MAX(time)::date AS last_day,
  COUNT(*)        AS total_rows
FROM daily_snapshots;

\echo ''
\echo '============================================================'
\echo 'PANEL 2A: OHLCV — DATE COVERAGE (BASE LAYER)'
\echo '============================================================'

SELECT
  COUNT(*)  AS total_rows,
  MIN(date) AS first_day,
  MAX(date) AS last_day
FROM ohlcv;

\echo ''
\echo '============================================================'
\echo 'PANEL 3: DAILY SNAPSHOTS — WYCKOFF PHASE DISTRIBUTION (LATEST DAY)'
\echo '============================================================'

WITH latest_day AS (
  SELECT MAX(time)::date AS d FROM daily_snapshots
)
SELECT
  wyckoff_phase,
  COUNT(*) AS rows
FROM daily_snapshots
WHERE time::date = (SELECT d FROM latest_day)
GROUP BY wyckoff_phase
ORDER BY rows DESC;

\echo ''
\echo '============================================================'
\echo 'PANEL 4: DAILY SNAPSHOTS — NULL DENSITY CHECK'
\echo '============================================================'

SELECT
  COUNT(*) FILTER (WHERE wyckoff_phase IS NULL)           AS null_phase_rows,
  COUNT(*) FILTER (WHERE composite_score IS NULL)         AS null_composite_rows,
  COUNT(*) FILTER (WHERE dealer_metrics_json IS NULL)     AS null_dealer_rows,
  COUNT(*) FILTER (WHERE volatility_metrics_json IS NULL) AS null_vol_rows,
  COUNT(*) FILTER (WHERE price_metrics_json IS NULL)      AS null_price_rows,
  COUNT(*)                                                AS total_rows
FROM daily_snapshots;

\echo ''
\echo '============================================================'
\echo 'PANEL 5: WYCKOFF CONTEXT EVENTS — BY TYPE'
\echo '============================================================'

SELECT
  event_type,
  COUNT(*)        AS total_events,
  MIN(event_date) AS first_seen,
  MAX(event_date) AS last_seen
FROM wyckoff_context_events
GROUP BY event_type
ORDER BY total_events DESC;

\echo ''
\echo '============================================================'
\echo 'PANEL 6: WYCKOFF REGIME TRANSITIONS — ROW COUNT'
\echo '============================================================'

SELECT COUNT(*) AS total_rows
FROM wyckoff_regime_transitions;

\echo ''
\echo '============================================================'
\echo 'PANEL 7: WYCKOFF SEQUENCES — ROW COUNT'
\echo '============================================================'

SELECT COUNT(*) AS total_rows
FROM wyckoff_sequences;

\echo ''
\echo '============================================================'
\echo 'PANEL 8: OPTIONS CHAINS — COVERAGE'
\echo '============================================================'

SELECT
  COUNT(*)             AS total_rows,
  MIN(expiration_date) AS nearest_expiry,
  MAX(expiration_date) AS furthest_expiry
FROM options_chains;

\echo ''
\echo '============================================================'
\echo 'PANEL 9: RECOMMENDATIONS — VOLUME & TIME RANGE'
\echo '============================================================'

SELECT
  COUNT(*)                 AS total_recommendations,
  MIN(recommendation_date) AS first_seen,
  MAX(recommendation_date) AS last_seen
FROM recommendations;

\echo ''
\echo '============================================================'
\echo 'PANEL 10: RECOMMENDATION OUTCOMES — COVERAGE'
\echo '============================================================'

SELECT
  COUNT(*)                          AS total_outcomes,
  COUNT(DISTINCT recommendation_id) AS recommendations_scored,
  MIN(evaluation_date)              AS first_eval,
  MAX(evaluation_date)              AS last_eval
FROM recommendation_outcomes;

\echo ''
\echo '============================================================'
\echo 'PANEL 11: WATCHLISTS — COUNT ONLY'
\echo '============================================================'

SELECT COUNT(*) AS total_watchlists
FROM watchlists;

\echo ''
\echo '============================================================'
\echo 'END OF DAILY INSPECTION DASHBOARD'
\echo '============================================================'