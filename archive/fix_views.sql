-- Fix v_wyckoff_events view
DROP VIEW IF EXISTS v_wyckoff_events;
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    ds.symbol_id,
    t.symbol,
    ds.date,
    ds.events_json->>'event_type' as event_type,
    (ds.events_json->>'confidence')::numeric as confidence,
    ds.events_json->'metadata' as metadata
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.events_json IS NOT NULL;

-- Fix v_entry_signals view (depends on v_wyckoff_events)
DROP VIEW IF EXISTS v_entry_signals;
CREATE OR REPLACE VIEW v_entry_signals AS
SELECT * FROM v_wyckoff_events
WHERE event_type IN ('SPRING', 'SOS');

-- Fix v_exit_signals view (depends on v_wyckoff_events)
DROP VIEW IF EXISTS v_exit_signals;
CREATE OR REPLACE VIEW v_exit_signals AS
SELECT * FROM v_wyckoff_events
WHERE event_type = 'BC' AND confidence >= 24;

-- Verify the views were created
\dv
