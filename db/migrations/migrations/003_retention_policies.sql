-- 003_retention_policies.sql
-- Set up retention and compression policies for time-series data

-- Enable compression on hypertables
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset_id'
);

ALTER TABLE order_book_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset_id'
);

ALTER TABLE trade_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'asset_id'
);

-- Set data retention policies
-- Keep market data for 5 years
SELECT add_retention_policy('market_data', INTERVAL '5 years');

-- Keep order book snapshots for 1 year
SELECT add_retention_policy('order_book_snapshots', INTERVAL '1 year');

-- Keep trade history for 2 years
SELECT add_retention_policy('trade_history', INTERVAL '2 years');

-- Set compression policies (compress data older than 7 days)
SELECT add_compression_policy('market_data', INTERVAL '7 days');
SELECT add_compression_policy('order_book_snapshots', INTERVAL '7 days');
SELECT add_compression_policy('trade_history', INTERVAL '7 days');

-- Create continuous aggregates for common queries
-- Daily OHLCV
CREATE MATERIALIZED VIEW market_data_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    asset_id,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(volume * vwap) / NULLIF(sum(volume), 0) AS vwap,
    sum(trade_count) AS trade_count
FROM market_data
GROUP BY bucket, asset_id;

-- Add refresh policy for the continuous aggregate
SELECT add_continuous_aggregate_policy('market_data_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Create an index on the continuous aggregate
CREATE INDEX idx_market_data_daily_asset_id ON market_data_daily(asset_id, bucket DESC);
