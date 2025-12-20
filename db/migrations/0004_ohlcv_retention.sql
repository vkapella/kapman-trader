-- A6 baseline invariant: enforce bounded OHLCV history via TimescaleDB policies.
-- Retention: keep exactly 730 days
-- Compression: compress chunks older than 120 days

-- Ensure retention policy exists
SELECT add_retention_policy(
    'ohlcv',
    INTERVAL '730 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);

-- Enable compression on the hypertable
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_id',
    timescaledb.compress_orderby = 'date DESC'
);

-- Add compression policy (compress chunks older than 120 days)
SELECT add_compression_policy(
    'ohlcv',
    INTERVAL '120 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);