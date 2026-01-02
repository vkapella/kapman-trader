\pset pager off
\timing off

\echo '===================================================================='
\echo 'KAPMAN DAILY_SNAPSHOTS — PLANNING & ARCHITECTURE DUMP'
\echo 'Purpose: Wyckoff → Strategy → Strike/DTE → AI Agent Design'
\echo '===================================================================='


\echo ''
\echo '--------------------------------------------------------------------'
\echo '1) TABLE SCHEMA: daily_snapshots'
\echo '   - Authoritative agent input surface'
\echo '--------------------------------------------------------------------'

\d+ daily_snapshots;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '2) JSONB COLUMNS IN daily_snapshots'
\echo '   - Nested metric containers'
\echo '--------------------------------------------------------------------'

SELECT
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'daily_snapshots'
  AND data_type = 'jsonb'
ORDER BY column_name;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '3) JSON STRUCTURE: events_json'
\echo '   - Event payload shape (keys only)'
\echo '--------------------------------------------------------------------'

SELECT DISTINCT jsonb_object_keys(events_json)
FROM daily_snapshots
WHERE events_json IS NOT NULL;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '4) JSON STRUCTURE: technical_indicators_json'
\echo '   - TA category groupings'
\echo '--------------------------------------------------------------------'

SELECT DISTINCT jsonb_object_keys(technical_indicators_json)
FROM daily_snapshots
WHERE technical_indicators_json IS NOT NULL;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '5) JSON STRUCTURE: dealer_metrics_json'
\echo '   - Dealer positioning & gamma metrics'
\echo '--------------------------------------------------------------------'

SELECT DISTINCT jsonb_object_keys(dealer_metrics_json)
FROM daily_snapshots
WHERE dealer_metrics_json IS NOT NULL;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '6) JSON STRUCTURE: volatility_metrics_json'
\echo '   - IV, skew, term structure'
\echo '--------------------------------------------------------------------'

SELECT DISTINCT jsonb_object_keys(volatility_metrics_json)
FROM daily_snapshots
WHERE volatility_metrics_json IS NOT NULL;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '7) JSON STRUCTURE: price_metrics_json'
\echo '   - Realized volatility & activity'
\echo '--------------------------------------------------------------------'

SELECT DISTINCT jsonb_object_keys(price_metrics_json)
FROM daily_snapshots
WHERE price_metrics_json IS NOT NULL;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '8) BASELINE SNAPSHOT — NVDA (CONTEXT ONLY, NO SIGNAL ASSUMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.primary_event,
  ds.events_detected,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'NVDA'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '9) BASELINE SNAPSHOT — GOOG (CONTEXT ONLY, NO SIGNAL ASSUMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.primary_event,
  ds.events_detected,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'GOOG'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '10) BULLISH CANONICAL SNAPSHOT — BLTE (SOS CONFIRMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_score,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.wyckoff_regime_set_by_event,

  ds.primary_event,
  ds.events_detected,
  ds.events_json,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'BLTE'
  AND ds.primary_event = 'SOS'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '11) BULLISH CANONICAL SNAPSHOT — HERZ (SOS CONFIRMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_score,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.wyckoff_regime_set_by_event,

  ds.primary_event,
  ds.events_detected,
  ds.events_json,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'HERZ'
  AND ds.primary_event = 'SOS'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '12) BEARISH CANONICAL SNAPSHOT — BLIN (SOW CONFIRMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_score,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.wyckoff_regime_set_by_event,

  ds.primary_event,
  ds.events_detected,
  ds.events_json,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'BLIN'
  AND ds.primary_event = 'SOW'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '13) BEARISH CANONICAL SNAPSHOT — ILLR (SOW CONFIRMED)'
\echo '--------------------------------------------------------------------'

SELECT
  ds.time,
  t.symbol,

  ds.wyckoff_phase,
  ds.phase_score,
  ds.phase_confidence,
  ds.wyckoff_regime,
  ds.wyckoff_regime_confidence,
  ds.wyckoff_regime_set_by_event,

  ds.primary_event,
  ds.events_detected,
  ds.events_json,

  ds.technical_indicators_json,
  ds.dealer_metrics_json,
  ds.volatility_metrics_json,
  ds.price_metrics_json
FROM daily_snapshots ds
JOIN tickers t ON t.id = ds.ticker_id
WHERE UPPER(t.symbol) = 'ILLR'
  AND ds.primary_event = 'SOW'
ORDER BY ds.time DESC
LIMIT 1;


\echo ''
\echo '--------------------------------------------------------------------'
\echo '14) DATA COMPLETENESS SUMMARY'
\echo '   - Determines required vs optional agent inputs'
\echo '--------------------------------------------------------------------'

SELECT
  COUNT(*)                         AS total_rows,
  COUNT(events_json)               AS events_present,
  COUNT(technical_indicators_json) AS ta_present,
  COUNT(dealer_metrics_json)       AS dealer_present,
  COUNT(volatility_metrics_json)   AS vol_present,
  COUNT(price_metrics_json)        AS price_present
FROM daily_snapshots;


\echo ''
\echo '===================================================================='
\echo 'END OF KAPMAN DAILY_SNAPSHOTS PLANNING DUMP'
\echo '===================================================================='