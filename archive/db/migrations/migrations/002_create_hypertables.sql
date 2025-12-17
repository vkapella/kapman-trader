-- 002_create_hypertables.sql
-- Convert time-series tables to hypertables

-- Create market data hypertable
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    vwap NUMERIC(20, 8),
    trade_count INTEGER,
    PRIMARY KEY (time, asset_id)
);

-- Convert to hypertable
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- Create order book snapshots hypertable
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    bid_price_1 NUMERIC(20, 8),
    bid_size_1 NUMERIC(20, 8),
    ask_price_1 NUMERIC(20, 8),
    ask_size_1 NUMERIC(20, 8),
    bid_price_2 NUMERIC(20, 8),
    bid_size_2 NUMERIC(20, 8),
    ask_price_2 NUMERIC(20, 8),
    ask_size_2 NUMERIC(20, 8),
    bid_price_3 NUMERIC(20, 8),
    bid_size_3 NUMERIC(20, 8),
    ask_price_3 NUMERIC(20, 8),
    ask_size_3 NUMERIC(20, 8),
    bid_price_4 NUMERIC(20, 8),
    bid_size_4 NUMERIC(20, 8),
    ask_price_4 NUMERIC(20, 8),
    ask_size_4 NUMERIC(20, 8),
    bid_price_5 NUMERIC(20, 8),
    bid_size_5 NUMERIC(20, 8),
    ask_price_5 NUMERIC(20, 8),
    ask_size_5 NUMERIC(20, 8),
    PRIMARY KEY (time, asset_id)
);

-- Convert to hypertable
SELECT create_hypertable('order_book_snapshots', 'time', if_not_exists => TRUE);

-- Create trade history hypertable
CREATE TABLE IF NOT EXISTS trade_history (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    side order_side,
    is_buyer_maker BOOLEAN,
    trade_id BIGINT,
    PRIMARY KEY (time, asset_id, trade_id)
);

-- Convert to hypertable
SELECT create_hypertable('trade_history', 'time', if_not_exists => TRUE);

-- Create indexes for better query performance
CREATE INDEX idx_market_data_asset_id ON market_data(asset_id, time DESC);
CREATE INDEX idx_order_book_snapshots_asset_id ON order_book_snapshots(asset_id, time DESC);
CREATE INDEX idx_trade_history_asset_id ON trade_history(asset_id, time DESC);
