-- Enable compression on hypertables
ALTER TABLE ohlcv_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id'
);

ALTER TABLE options_chains SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id, expiration_date, strike_price, option_type'
);

ALTER TABLE daily_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id'
);

-- Add compression policies (compress after 1 year)
SELECT add_compression_policy('ohlcv_daily', INTERVAL '1 year');
SELECT add_compression_policy('daily_snapshots', INTERVAL '1 year');

-- Add retention policies
SELECT add_retention_policy('ohlcv_daily', INTERVAL '3 years');
SELECT add_retention_policy('options_chains', INTERVAL '90 days');
SELECT add_retention_policy('daily_snapshots', INTERVAL '2 years');
