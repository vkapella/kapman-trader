CREATE TABLE tickers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ
);

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
    created_at TIMESTAMPTZ,
    PRIMARY KEY (ticker_id, date)
);

SELECT create_hypertable('ohlcv', 'date', if_not_exists => TRUE);


CREATE TABLE daily_snapshots (
    time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    wyckoff_phase VARCHAR(1) CHECK (wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')),
    phase_score NUMERIC(6, 3),
    phase_confidence NUMERIC(4, 3) CHECK (phase_confidence BETWEEN 0 AND 1),
    events_detected TEXT[],
    primary_event VARCHAR(20),
    events_json JSONB,
    bc_score INTEGER CHECK (bc_score BETWEEN 0 AND 28),
    spring_score INTEGER CHECK (spring_score BETWEEN 0 AND 12),
    composite_score NUMERIC(6, 2),
    technical_indicators_json JSONB,
    dealer_metrics_json JSONB,
    volatility_metrics_json JSONB,
    price_metrics_json JSONB,
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ,
    PRIMARY KEY (time, ticker_id)
);

CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
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
    status recommendation_status NOT NULL DEFAULT 'active',
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ,
    FOREIGN KEY (snapshot_time, ticker_id)
        REFERENCES daily_snapshots(time, ticker_id)
);

CREATE TABLE recommendation_outcomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id UUID NOT NULL
        REFERENCES recommendations(id)
        ON DELETE CASCADE,
    evaluation_date DATE NOT NULL,
    evaluation_window_days INTEGER,
    entry_price_actual NUMERIC(12, 4),
    exit_price_actual NUMERIC(12, 4),
    high_price_during_window NUMERIC(12, 4),
    low_price_during_window NUMERIC(12, 4),
    days_held INTEGER,
    direction_correct BOOLEAN,
    predicted_confidence NUMERIC(4, 3),
    directional_brier NUMERIC(6, 4),
    actual_return_pct NUMERIC(8, 4),
    hit_profit_target BOOLEAN,
    hit_stop_loss BOOLEAN,
    outcome_status outcome_status,
    notes TEXT,
    evaluated_at TIMESTAMPTZ
);
