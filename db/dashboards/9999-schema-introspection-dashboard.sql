cat <<'EOF' > db/dashboards/9999-schema-introspection-dashboard.sql
-- ============================================================
-- KapMan Schema Introspection Dashboard
-- Purpose: Understand end-to-end data flow for Wyckoff (B1–B4.1)
-- ============================================================

-- ----------------------------
-- Core Tables
-- ----------------------------

\echo '--- tickers ---'
\d+ tickers

\echo '--- ohlcv ---'
\d+ ohlcv

\echo '--- daily_snapshots ---'
\d+ daily_snapshots

\echo '--- wyckoff_context_events ---'
\d+ wyckoff_context_events

\echo '--- wyckoff_regime_transitions ---'
\d+ wyckoff_regime_transitions

\echo '--- wyckoff_sequences ---'
\d+ wyckoff_sequences

-- ----------------------------
-- Row Counts (sanity check)
-- ----------------------------

\echo '--- row counts ---'
SELECT 'tickers' AS table, COUNT(*) FROM tickers
UNION ALL
SELECT 'ohlcv', COUNT(*) FROM ohlcv
UNION ALL
SELECT 'daily_snapshots', COUNT(*) FROM daily_snapshots
UNION ALL
SELECT 'wyckoff_context_events', COUNT(*) FROM wyckoff_context_events
UNION ALL
SELECT 'wyckoff_regime_transitions', COUNT(*) FROM wyckoff_regime_transitions
UNION ALL
SELECT 'wyckoff_sequences', COUNT(*) FROM wyckoff_sequences;

-- ----------------------------
-- AAPL Data Flow Walkthrough
-- ----------------------------

\echo '--- AAPL: OHLCV range ---'
SELECT
  MIN(date) AS start_date,
  MAX(date) AS end_date,
  COUNT(*) AS bars
FROM ohlcv o
JOIN tickers t ON t.id = o.ticker_id
WHERE t.symbol = 'AAPL';

\echo '--- AAPL: daily snapshots ---'
SELECT
  COUNT(*) AS snapshot_rows,
  COUNT(*) FILTER (WHERE wyckoff_regime IS NOT NULL) AS with_regime
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE t.symbol = 'AAPL';

\echo '--- AAPL: structural events ---'
SELECT
  event_type,
  COUNT(*) AS cnt,
  MIN(event_date) AS first_event,
  MAX(event_date) AS last_event
FROM wyckoff_context_events e
JOIN tickers t ON t.id = e.ticker_id
WHERE t.symbol = 'AAPL'
GROUP BY event_type
ORDER BY event_type;

\echo '--- AAPL: regime transitions ---'
SELECT *
FROM wyckoff_regime_transitions r
JOIN tickers t ON t.id = r.ticker_id
WHERE t.symbol = 'AAPL'
ORDER BY date;

\echo '--- AAPL: sequences ---'
SELECT *
FROM wyckoff_sequences s
JOIN tickers t ON t.id = s.ticker_id
WHERE t.symbol = 'AAPL'
ORDER BY completion_date;

-- ============================================================
-- End Dashboard
-- ============================================================
EOF