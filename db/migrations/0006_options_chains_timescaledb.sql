-- STORY A6.1 — Options Snapshot Storage on TimescaleDB
-- Destructive, schema-level rebuild of public.options_chains into a TimescaleDB hypertable
-- governed by native retention and compression policies.

DROP TABLE IF EXISTS options_chains CASCADE;

CREATE TABLE options_chains (
    time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    expiration_date DATE NOT NULL,
    strike_price NUMERIC(12, 4) NOT NULL,
    option_type CHAR(1) NOT NULL,
    bid NUMERIC,
    ask NUMERIC,
    last NUMERIC,
    volume INTEGER,
    open_interest INTEGER,
    implied_volatility NUMERIC,
    delta NUMERIC,
    gamma NUMERIC,
    theta NUMERIC,
    vega NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_options_chains_snapshot_identity
        UNIQUE (time, ticker_id, expiration_date, strike_price, option_type)
);

CREATE INDEX idx_options_chains_ticker_time_desc
    ON options_chains (ticker_id, time DESC);

CREATE INDEX idx_options_chains_expiration_date
    ON options_chains (expiration_date);

CREATE INDEX idx_options_chains_time_desc
    ON options_chains (time DESC);

DO $$
DECLARE
    ohlcv_chunk_interval INTERVAL;
BEGIN
    SELECT time_interval
      INTO ohlcv_chunk_interval
      FROM timescaledb_information.dimensions
     WHERE hypertable_schema = 'public'
       AND hypertable_name = 'ohlcv'
       AND dimension_type = 'Time'
     ORDER BY dimension_number
     LIMIT 1;

    IF ohlcv_chunk_interval IS NULL THEN
        ohlcv_chunk_interval := INTERVAL '7 days';
    END IF;

    PERFORM create_hypertable(
        'options_chains',
        'time',
        chunk_time_interval => ohlcv_chunk_interval,
        if_not_exists => TRUE
    );
END $$;

SELECT add_retention_policy(
    'options_chains',
    INTERVAL '730 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);

ALTER TABLE options_chains SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_id',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy(
    'options_chains',
    INTERVAL '120 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);
