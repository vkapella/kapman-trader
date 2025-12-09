-- 0002_create_continuous_aggregates.up.sql
-- Create continuous aggregates for time-series data

-- Create daily market data aggregate
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_daily
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
GROUP BY bucket, asset_id
WITH NO DATA;

-- Add refresh policy for daily aggregate
SELECT add_continuous_aggregate_policy('market_data_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
) WHERE NOT EXISTS (
    SELECT 1 
    FROM timescaledb_information.continuous_aggregates 
    WHERE view_name = 'market_data_daily'
);

-- Create hourly market data aggregate
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    asset_id,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(volume * vwap) / NULLIF(sum(volume), 0) AS vwap,
    sum(trade_count) AS trade_count
FROM market_data
GROUP BY bucket, asset_id
WITH NO DATA;

-- Add refresh policy for hourly aggregate
SELECT add_continuous_aggregate_policy('market_data_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '15 minutes'
) WHERE NOT EXISTS (
    SELECT 1 
    FROM timescaledb_information.continuous_aggregates 
    WHERE view_name = 'market_data_hourly'
);
