-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Create enum types
CREATE TYPE option_type AS ENUM ('C', 'P');
CREATE TYPE recommendation_status AS ENUM ('active', 'closed', 'expired');
CREATE TYPE recommendation_direction AS ENUM ('LONG', 'SHORT', 'NEUTRAL');
CREATE TYPE recommendation_action AS ENUM ('BUY', 'SELL', 'HOLD', 'HEDGE');
CREATE TYPE option_strategy AS ENUM (
    'LONG_CALL', 'LONG_PUT', 'CSP', 'VERTICAL_SPREAD'
);
CREATE TYPE outcome_status AS ENUM ('WIN', 'LOSS', 'NEUTRAL');

-- Portfolios
CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tickers
CREATE TABLE tickers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Portfolio Tickers (Junction Table)
CREATE TABLE portfolio_tickers (
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker_id UUID REFERENCES tickers(id) ON DELETE CASCADE,
    priority VARCHAR(10) CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, ticker_id)
);

-- OHLCV Data (TimescaleDB Hypertable)
CREATE TABLE ohlcv_daily (
    time TIMESTAMPTZ NOT NULL,
    symbol_id UUID REFERENCES tickers(id),
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    vwap NUMERIC(12, 4),
    source VARCHAR(50) DEFAULT 'polygon_s3',
    PRIMARY KEY (time, symbol_id)
);

-- Convert to hypertable
SELECT create_hypertable('ohlcv_daily', 'time', if_not_exists => TRUE);

-- Options Chains (TimescaleDB Hypertable)
CREATE TABLE options_chains (
    time TIMESTAMPTZ NOT NULL,
    symbol_id UUID REFERENCES tickers(id),
    expiration_date DATE NOT NULL,
    strike_price NUMERIC(12, 4) NOT NULL,
    option_type option_type NOT NULL,
    bid NUMERIC(12, 4),
    ask NUMERIC(12, 4),
    last NUMERIC(12, 4),
    volume INTEGER,
    open_interest INTEGER,
    implied_volatility NUMERIC(10, 6),
    delta NUMERIC(10, 6),
    gamma NUMERIC(10, 6),
    theta NUMERIC(10, 6),
    vega NUMERIC(10, 6),
    PRIMARY KEY (time, symbol_id, expiration_date, strike_price, option_type)
);

-- Convert to hypertable
SELECT create_hypertable('options_chains', 'time', if_not_exists => TRUE);

-- Daily Snapshots (Wyckoff Analysis)
CREATE TABLE daily_snapshots (
    time TIMESTAMPTZ NOT NULL,
    symbol_id UUID REFERENCES tickers(id),
    wyckoff_phase VARCHAR(1) CHECK (wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')),
    phase_confidence NUMERIC(4, 3) CHECK (phase_confidence BETWEEN 0 AND 1),
    phase_sub_stage VARCHAR(10),
    events_detected TEXT[],
    primary_event VARCHAR(20),
    primary_event_confidence NUMERIC(4, 3),
    bc_score INTEGER CHECK (bc_score BETWEEN 0 AND 28),
    spring_score INTEGER CHECK (spring_score BETWEEN 0 AND 12),
    composite_score NUMERIC(4, 2),
    volatility_regime VARCHAR(20),
    checklist_json JSONB,
    technical_indicators JSONB,
    dealer_metrics JSONB,
    price_metrics JSONB,
    model_version VARCHAR(50),
    data_quality VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (time, symbol_id)
);

-- Convert to hypertable
SELECT create_hypertable('daily_snapshots', 'time', if_not_exists => TRUE);

-- Recommendations
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ NOT NULL,
    symbol_id UUID REFERENCES tickers(id),
    recommendation_date DATE NOT NULL,
    direction recommendation_direction NOT NULL,
    action recommendation_action NOT NULL,
    confidence NUMERIC(4, 3) CHECK (confidence BETWEEN 0 AND 1),
    justification TEXT,
    entry_price_target NUMERIC(12, 4),
    stop_loss NUMERIC(12, 4),
    profit_target NUMERIC(12, 4),
    risk_reward_ratio NUMERIC(6, 2),
    option_strike NUMERIC(12, 4),
    option_expiration DATE,
    option_type option_type,
    option_strategy option_strategy,
    status recommendation_status DEFAULT 'active',
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (snapshot_time, symbol_id) 
        REFERENCES daily_snapshots(time, symbol_id)
);

-- Recommendation Outcomes
CREATE TABLE recommendation_outcomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id UUID REFERENCES recommendations(id) ON DELETE CASCADE,
    evaluation_date DATE NOT NULL,
    evaluation_window_days INTEGER,
    entry_price_actual NUMERIC(12, 4),
    exit_price_actual NUMERIC(12, 4),
    high_price_during_window NUMERIC(12, 4),
    low_price_during_window NUMERIC(12, 4),
    days_to_target INTEGER,
    days_to_stop INTEGER,
    days_held INTEGER,
    max_favorable_excursion NUMERIC(8, 4),
    max_adverse_excursion NUMERIC(8, 4),
    direction_correct BOOLEAN,
    predicted_confidence NUMERIC(4, 3),
    directional_brier NUMERIC(6, 4),
    actual_return_pct NUMERIC(8, 4),
    hit_profit_target BOOLEAN,
    hit_stop_loss BOOLEAN,
    success_score_v1 NUMERIC(4, 3),
    outcome_status outcome_status,
    notes TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_ohlcv_daily_symbol ON ohlcv_daily(symbol_id, time DESC);
CREATE INDEX idx_options_chains_symbol ON options_chains(symbol_id, time DESC);
CREATE INDEX idx_daily_snapshots_symbol ON daily_snapshots(symbol_id, time DESC);
CREATE INDEX idx_recommendations_symbol ON recommendations(symbol_id, recommendation_date DESC);
CREATE INDEX idx_recommendations_status ON recommendations(status, recommendation_date DESC);
CREATE INDEX idx_outcomes_recommendation ON recommendation_outcomes(recommendation_id);
CREATE INDEX idx_outcomes_date ON recommendation_outcomes(evaluation_date DESC);

-- Create a function to update the updated_at column
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_portfolios_modtime
    BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_tickers_modtime
    BEFORE UPDATE ON tickers
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();
