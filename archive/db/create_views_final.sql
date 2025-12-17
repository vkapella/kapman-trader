-- Drop views if they exist (ignore errors if they don't)
DROP VIEW IF EXISTS v_exit_signals;
DROP VIEW IF EXISTS v_entry_signals;
DROP VIEW IF EXISTS v_wyckoff_events;

-- Create v_wyckoff_events with proper schema references
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    ds.symbol_id,
    t.symbol,
    ds.time as date,
    ds.events_json->>'event_type' as event_type,
    (ds.events_json->>'confidence')::numeric as confidence,
    ds.events_json->'metadata' as metadata
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.events_json IS NOT NULL;

-- Create dependent views
CREATE OR REPLACE VIEW v_entry_signals AS
SELECT * FROM v_wyckoff_events
WHERE event_type IN ('SPRING', 'SOS');

CREATE OR REPLACE VIEW v_exit_signals AS
SELECT * FROM v_wyckoff_events
WHERE event_type = 'BC' AND confidence >= 24;

-- Verify the views were created
\dv
