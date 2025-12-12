-- v3.1 Base OHLCV schema required by scripts/init/load_ohlcv_base.py
-- Recreates ohlcv table keyed by (ticker_id, date) for Massive ingestion

DROP TABLE IF EXISTS ohlcv;

CREATE TABLE ohlcv (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,

    date DATE NOT NULL,

    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker_id, date)
);
