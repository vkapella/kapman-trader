-- KapMan Trading System
-- Schema Baseline (Squashed)
-- Generated: 2026-01-07
-- Purpose: single, canonical rebuild migration for empty databases.
-- Notes:
--   * Includes all structural schema objects from legacy migrations 0001–0011.
--   * Excludes one-off/transitional data-migration logic (e.g., b4_1 copy-forward).
--   * Safe to run on an empty DB; largely idempotent via IF NOT EXISTS guards.

BEGIN;

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- -----------------------------------------------------------------------------
-- Types
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    CREATE TYPE option_type AS ENUM ('C', 'P');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_status AS ENUM ('active', 'closed', 'expired');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_direction AS ENUM ('LONG', 'SHORT', 'NEUTRAL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_action AS ENUM ('BUY', 'SELL', 'HOLD', 'HEDGE');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE option_strategy AS ENUM ('LONG_CALL', 'LONG_PUT', 'CSP', 'VERTICAL_SPREAD');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE outcome_status AS ENUM ('WIN', 'LOSS', 'NEUTRAL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

-- -----------------------------------------------------------------------------
-- Core reference tables
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tickers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ
);

-- -----------------------------------------------------------------------------
-- Base Market Data Layer (Timescale)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ohlcv (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
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

-- Convert to hypertable (idempotent)
SELECT create_hypertable('ohlcv', 'date', if_not_exists => TRUE);

-- Retention + compression policies for ohlcv
SELECT add_retention_policy(
    'ohlcv',
    INTERVAL '730 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);

ALTER TABLE public.ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_id',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy(
    'ohlcv',
    INTERVAL '120 days',
    if_not_exists => TRUE,
    schedule_interval => INTERVAL '1 day'
);

-- -----------------------------------------------------------------------------
-- Analytical Layer
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.daily_snapshots (
    time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,

    -- Wyckoff phase (A–E)
    wyckoff_phase VARCHAR(1) CHECK (wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')),
    phase_score NUMERIC(6, 3),
    phase_confidence NUMERIC(4, 3) CHECK (phase_confidence BETWEEN 0 AND 1),

    -- Wyckoff regime (ACCUM/MARKUP/DIST/MARKDOWN/UNKNOWN)
    wyckoff_regime VARCHAR(20)
        CHECK (wyckoff_regime IN ('ACCUMULATION', 'MARKUP', 'DISTRIBUTION', 'MARKDOWN', 'UNKNOWN')),
    wyckoff_regime_confidence NUMERIC(4, 3)
        CHECK (wyckoff_regime_confidence BETWEEN 0 AND 1),
    wyckoff_regime_set_by_event VARCHAR(20),

    -- Wyckoff events + scoring
    events_detected TEXT[],
    primary_event VARCHAR(20),
    events_json JSONB,
    bc_score INTEGER CHECK (bc_score BETWEEN 0 AND 28),
    spring_score INTEGER CHECK (spring_score BETWEEN 0 AND 12),
    composite_score NUMERIC(6, 2),

    -- Metric JSON blobs
    technical_indicators_json JSONB,
    dealer_metrics_json JSONB,
    volatility_metrics_json JSONB,
    price_metrics_json JSONB,

    model_version VARCHAR(50),
    created_at TIMESTAMPTZ,

    PRIMARY KEY (time, ticker_id)
);

-- Recommendations + outcomes
CREATE TABLE IF NOT EXISTS public.recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
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
        REFERENCES public.daily_snapshots(time, ticker_id)
);

CREATE TABLE IF NOT EXISTS public.recommendation_outcomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id UUID NOT NULL
        REFERENCES public.recommendations(id)
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

-- -----------------------------------------------------------------------------
-- Watchlists (authoritative analytical scope)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.watchlists (
    watchlist_id VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_date DATE NOT NULL,
    UNIQUE (watchlist_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_watchlists_watchlist_id_active
    ON public.watchlists (watchlist_id)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_watchlists_symbol
    ON public.watchlists (symbol);

-- -----------------------------------------------------------------------------
-- Options chains (Timescale hypertable)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.options_chains (
    time TIMESTAMPTZ NOT NULL,
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
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

-- Ensure option_type semantics for options_chains (kept as CHAR(1) for parity with legacy schema)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_options_chains_option_type'
          AND conrelid = 'public.options_chains'::regclass
    ) THEN
        ALTER TABLE public.options_chains
            ADD CONSTRAINT chk_options_chains_option_type
            CHECK (option_type IN ('C', 'P'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_options_chains_ticker_time_desc
    ON public.options_chains (ticker_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_options_chains_expiration_date
    ON public.options_chains (expiration_date);

CREATE INDEX IF NOT EXISTS idx_options_chains_time_desc
    ON public.options_chains (time DESC);

-- Create hypertable using the same chunk interval as OHLCV (fallback to 7 days)
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

ALTER TABLE public.options_chains SET (
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

-- -----------------------------------------------------------------------------
-- Wyckoff derived / research-validated tables (public)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wyckoff_regime_transitions (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,
    date DATE NOT NULL,
    prior_regime VARCHAR(20),
    new_regime VARCHAR(20),
    duration_bars INTEGER,
    PRIMARY KEY (ticker_id, date, new_regime)
);

CREATE TABLE IF NOT EXISTS public.wyckoff_sequences (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,
    sequence_id VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    completion_date DATE NOT NULL,
    events_in_sequence JSONB NOT NULL,
    PRIMARY KEY (ticker_id, sequence_id, completion_date)
);

CREATE TABLE IF NOT EXISTS public.wyckoff_sequence_events (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,
    sequence_id VARCHAR(50) NOT NULL,
    completion_date DATE NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    event_date DATE NOT NULL,
    event_role VARCHAR(12) NOT NULL,
    event_order INTEGER NOT NULL,
    PRIMARY KEY (ticker_id, sequence_id, completion_date, event_order),
    FOREIGN KEY (ticker_id, sequence_id, completion_date)
        REFERENCES public.wyckoff_sequences(ticker_id, sequence_id, completion_date)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.wyckoff_context_events (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,
    event_date DATE NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    prior_regime VARCHAR(20) NOT NULL,
    context_label VARCHAR(60) NOT NULL,
    PRIMARY KEY (ticker_id, event_date, event_type, prior_regime)
);

CREATE TABLE IF NOT EXISTS public.wyckoff_snapshot_evidence (
    ticker_id UUID NOT NULL
        REFERENCES public.tickers(id)
        ON DELETE CASCADE,
    date DATE NOT NULL,
    evidence_json JSONB NOT NULL,
    PRIMARY KEY (ticker_id, date)
);

COMMIT;
