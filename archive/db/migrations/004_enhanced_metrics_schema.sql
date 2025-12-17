-- ============================================================================
-- MIGRATION 004: Enhanced Metrics Schema (CORRECTED)
-- Kapman Trading System
-- Date: December 9, 2025
-- 
-- This migration uses the symbol_id UUID foreign key pattern from Sprint 1.
-- All views and tables join through tickers table to get symbol names.
-- ============================================================================

-- ============================================================================
-- SECTION 1: TICKER UNIVERSE CLASSIFICATION
-- ============================================================================

-- Add universe tier to track where ticker came from
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS 
    universe_tier VARCHAR(20) DEFAULT 'custom';

-- Add check constraint safely
DO $$
BEGIN
    ALTER TABLE tickers ADD CONSTRAINT chk_universe_tier 
        CHECK (universe_tier IN ('sp500', 'russell3000', 'polygon_full', 'custom', 'etf', 'index'));
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint chk_universe_tier already exists';
END $$;

-- Track data freshness per ticker
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS last_ohlcv_date DATE;
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS last_analysis_date DATE;
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS options_enabled BOOLEAN DEFAULT false;

-- Index for efficient universe queries
CREATE INDEX IF NOT EXISTS idx_tickers_universe ON tickers(universe_tier, is_active);

COMMENT ON COLUMN tickers.universe_tier IS 'Source universe: sp500, russell3000, polygon_full, custom, etf, index';
COMMENT ON COLUMN tickers.last_ohlcv_date IS 'Most recent OHLCV data date loaded';
COMMENT ON COLUMN tickers.last_analysis_date IS 'Most recent Wyckoff analysis date';
COMMENT ON COLUMN tickers.options_enabled IS 'Whether to fetch options data for this ticker';

-- ============================================================================
-- SECTION 2: ENHANCED DAILY_SNAPSHOTS TABLE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 2A: Technical Indicators (Extracted Key Columns)
-- ----------------------------------------------------------------------------

-- Momentum Indicators
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS rsi_14 NUMERIC(6,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS macd_line NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS macd_signal NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS macd_histogram NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS stoch_k NUMERIC(6,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS stoch_d NUMERIC(6,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS mfi_14 NUMERIC(6,2);

-- Trend Indicators
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS sma_20 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS sma_50 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS sma_200 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS ema_12 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS ema_26 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS adx_14 NUMERIC(6,2);

-- Volatility Indicators
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS atr_14 NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS bbands_upper NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS bbands_middle NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS bbands_lower NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS bbands_width NUMERIC(8,4);

-- Volume Indicators
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS obv BIGINT;
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS vwap NUMERIC(12,4);

-- Comments for technical indicators
COMMENT ON COLUMN daily_snapshots.rsi_14 IS '14-period RSI (0-100)';
COMMENT ON COLUMN daily_snapshots.macd_histogram IS 'MACD histogram (MACD line - signal)';
COMMENT ON COLUMN daily_snapshots.adx_14 IS '14-period ADX trend strength (0-100)';
COMMENT ON COLUMN daily_snapshots.bbands_width IS 'Bollinger Band width as percentage';

-- ----------------------------------------------------------------------------
-- 2B: Dealer Metrics (Extracted from dealer_metrics_json)
-- ----------------------------------------------------------------------------

ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS gex_total NUMERIC(18,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS gex_net NUMERIC(18,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS gamma_flip_level NUMERIC(12,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS call_wall_primary NUMERIC(12,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS call_wall_primary_oi INTEGER;
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS put_wall_primary NUMERIC(12,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS put_wall_primary_oi INTEGER;
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS dgpi NUMERIC(5,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS dealer_position VARCHAR(15);

-- Constraint for dealer position values (added safely)
DO $$
BEGIN
    ALTER TABLE daily_snapshots ADD CONSTRAINT chk_dealer_position 
        CHECK (dealer_position IS NULL OR dealer_position IN ('long_gamma', 'short_gamma', 'neutral'));
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint chk_dealer_position already exists';
END $$;

-- Constraint for DGPI range (added safely)
DO $$
BEGIN
    ALTER TABLE daily_snapshots ADD CONSTRAINT chk_dgpi_range 
        CHECK (dgpi IS NULL OR (dgpi >= -100 AND dgpi <= 100));
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint chk_dgpi_range already exists';
END $$;

-- Comments for dealer metrics
COMMENT ON COLUMN daily_snapshots.gex_total IS 'Total Gamma Exposure across all strikes';
COMMENT ON COLUMN daily_snapshots.gex_net IS 'Net directional Gamma Exposure';
COMMENT ON COLUMN daily_snapshots.gamma_flip_level IS 'Price level where dealers flip long/short gamma';
COMMENT ON COLUMN daily_snapshots.call_wall_primary IS 'Highest OI call strike (resistance)';
COMMENT ON COLUMN daily_snapshots.put_wall_primary IS 'Highest OI put strike (support)';
COMMENT ON COLUMN daily_snapshots.dgpi IS 'Dealer Gamma Pressure Index (-100 to +100)';
COMMENT ON COLUMN daily_snapshots.dealer_position IS 'Current dealer gamma positioning';

-- ----------------------------------------------------------------------------
-- 2C: Volatility Metrics (New columns)
-- ----------------------------------------------------------------------------

ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS iv_skew_25d NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS iv_term_structure NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS put_call_ratio_oi NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS put_call_ratio_volume NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS average_iv NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS iv_rank NUMERIC(5,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS iv_percentile NUMERIC(5,2);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS volatility_metrics_json JSONB;

-- Comments for volatility metrics
COMMENT ON COLUMN daily_snapshots.iv_skew_25d IS '25-delta put-call IV spread (positive = put premium)';
COMMENT ON COLUMN daily_snapshots.iv_term_structure IS 'Long vs short-dated IV difference (negative = backwardation)';
COMMENT ON COLUMN daily_snapshots.put_call_ratio_oi IS 'Put/Call ratio based on open interest';
COMMENT ON COLUMN daily_snapshots.put_call_ratio_volume IS 'Put/Call ratio based on volume';
COMMENT ON COLUMN daily_snapshots.average_iv IS 'OI-weighted average implied volatility';
COMMENT ON COLUMN daily_snapshots.iv_rank IS 'Current IV rank vs 52-week range (0-100)';
COMMENT ON COLUMN daily_snapshots.iv_percentile IS 'Current IV percentile vs 52-week (0-100)';

-- ----------------------------------------------------------------------------
-- 2D: Price Metrics (Extracted from price_metrics_json)
-- ----------------------------------------------------------------------------

ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS rvol NUMERIC(8,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS vsi NUMERIC(8,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS hv_20 NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS hv_60 NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS iv_hv_diff NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS price_vs_sma20 NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS price_vs_sma50 NUMERIC(6,4);
ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS price_vs_sma200 NUMERIC(6,4);

-- Comments for price metrics
COMMENT ON COLUMN daily_snapshots.rvol IS 'Relative Volume (1.0 = average, >1.5 = elevated)';
COMMENT ON COLUMN daily_snapshots.vsi IS 'Volume Surge Index (z-score, >2 = significant)';
COMMENT ON COLUMN daily_snapshots.hv_20 IS '20-day Historical Volatility (annualized)';
COMMENT ON COLUMN daily_snapshots.hv_60 IS '60-day Historical Volatility (annualized)';
COMMENT ON COLUMN daily_snapshots.iv_hv_diff IS 'IV minus HV spread (positive = IV rich)';
COMMENT ON COLUMN daily_snapshots.price_vs_sma20 IS 'Price distance from SMA20 as percentage';
COMMENT ON COLUMN daily_snapshots.price_vs_sma50 IS 'Price distance from SMA50 as percentage';
COMMENT ON COLUMN daily_snapshots.price_vs_sma200 IS 'Price distance from SMA200 as percentage';

-- ----------------------------------------------------------------------------
-- 2E: Indexes for Efficient Querying
-- ----------------------------------------------------------------------------

-- Technical indicator screening indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_rsi ON daily_snapshots(rsi_14, time DESC) 
    WHERE rsi_14 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_snapshots_adx ON daily_snapshots(adx_14, time DESC) 
    WHERE adx_14 IS NOT NULL;

-- Dealer metrics indexes (for alerting)
CREATE INDEX IF NOT EXISTS idx_snapshots_dgpi ON daily_snapshots(dgpi, time DESC) 
    WHERE dgpi IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_snapshots_gamma_flip ON daily_snapshots(gamma_flip_level, time DESC) 
    WHERE gamma_flip_level IS NOT NULL;

-- Volatility screening indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_iv ON daily_snapshots(average_iv, time DESC) 
    WHERE average_iv IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_snapshots_pcr ON daily_snapshots(put_call_ratio_oi, time DESC) 
    WHERE put_call_ratio_oi IS NOT NULL;

-- Price metrics indexes (Wyckoff confirmation)
CREATE INDEX IF NOT EXISTS idx_snapshots_rvol ON daily_snapshots(rvol, time DESC) 
    WHERE rvol IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_snapshots_vsi ON daily_snapshots(vsi, time DESC) 
    WHERE vsi IS NOT NULL;

-- ============================================================================
-- SECTION 3: OPTIONS DAILY SUMMARY TABLE
-- ============================================================================

-- Drop if exists to ensure clean creation
DROP TABLE IF EXISTS options_daily_summary CASCADE;

CREATE TABLE options_daily_summary (
    time TIMESTAMPTZ NOT NULL,
    symbol_id UUID NOT NULL REFERENCES tickers(id),
    
    -- Aggregate Open Interest
    total_call_oi INTEGER,
    total_put_oi INTEGER,
    total_oi INTEGER GENERATED ALWAYS AS (COALESCE(total_call_oi, 0) + COALESCE(total_put_oi, 0)) STORED,
    
    -- Aggregate Volume
    total_call_volume INTEGER,
    total_put_volume INTEGER,
    total_volume INTEGER GENERATED ALWAYS AS (COALESCE(total_call_volume, 0) + COALESCE(total_put_volume, 0)) STORED,
    
    -- Ratios (calculated in application, not generated to avoid division issues)
    put_call_oi_ratio NUMERIC(6,4),
    put_call_volume_ratio NUMERIC(6,4),
    
    -- Weighted Average IV
    weighted_avg_iv NUMERIC(6,4),
    
    -- Top Call Strikes by OI (resistance levels)
    top_call_strike_1 NUMERIC(12,2),
    top_call_oi_1 INTEGER,
    top_call_strike_2 NUMERIC(12,2),
    top_call_oi_2 INTEGER,
    top_call_strike_3 NUMERIC(12,2),
    top_call_oi_3 INTEGER,
    
    -- Top Put Strikes by OI (support levels)
    top_put_strike_1 NUMERIC(12,2),
    top_put_oi_1 INTEGER,
    top_put_strike_2 NUMERIC(12,2),
    top_put_oi_2 INTEGER,
    top_put_strike_3 NUMERIC(12,2),
    top_put_oi_3 INTEGER,
    
    -- Greeks Aggregates (for GEX calculation)
    total_call_gamma NUMERIC(18,8),
    total_put_gamma NUMERIC(18,8),
    total_call_delta NUMERIC(18,8),
    total_put_delta NUMERIC(18,8),
    
    -- GEX Calculation (stored after calculation in Python)
    calculated_gex NUMERIC(18,2),
    calculated_net_gex NUMERIC(18,2),
    
    -- Expirations Summary
    nearest_expiry DATE,
    expirations_count INTEGER,
    contracts_analyzed INTEGER,
    
    -- Data Quality
    data_completeness NUMERIC(4,3),
    source VARCHAR(50) DEFAULT 'polygon_api',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (time, symbol_id)
);

-- Convert to hypertable
SELECT create_hypertable('options_daily_summary', 'time', if_not_exists => TRUE);

-- Indexes for options summary
CREATE INDEX IF NOT EXISTS idx_options_summary_symbol ON options_daily_summary(symbol_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_options_summary_pcr ON options_daily_summary(put_call_oi_ratio, time DESC);
CREATE INDEX IF NOT EXISTS idx_options_summary_gex ON options_daily_summary(calculated_gex, time DESC);

-- Retention policy (90 days per spec)
SELECT add_retention_policy('options_daily_summary', INTERVAL '90 days', if_not_exists => TRUE);

-- Comments
COMMENT ON TABLE options_daily_summary IS 'Daily aggregated options metrics per symbol for dealer analysis';
COMMENT ON COLUMN options_daily_summary.top_call_strike_1 IS 'Highest OI call strike - primary resistance';
COMMENT ON COLUMN options_daily_summary.top_put_strike_1 IS 'Highest OI put strike - primary support';
COMMENT ON COLUMN options_daily_summary.calculated_gex IS 'Gamma Exposure calculated from Greeks + OI';

-- ============================================================================
-- SECTION 4: OHLCV TABLE ENHANCEMENTS
-- ============================================================================

-- Add data quality flag if not exists
ALTER TABLE ohlcv_daily ADD COLUMN IF NOT EXISTS is_adjusted BOOLEAN DEFAULT true;

COMMENT ON COLUMN ohlcv_daily.is_adjusted IS 'Whether prices are split/dividend adjusted';

-- ============================================================================
-- SECTION 5: OPTIONS CHAINS TABLE ENHANCEMENTS  
-- ============================================================================

-- Add open interest change tracking
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS oi_change INTEGER;
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS volume_oi_ratio NUMERIC(8,4);

-- Add moneyness classification
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS moneyness VARCHAR(10);

DO $$
BEGIN
    ALTER TABLE options_chains ADD CONSTRAINT chk_moneyness 
        CHECK (moneyness IS NULL OR moneyness IN ('ITM', 'ATM', 'OTM', 'DITM', 'DOTM'));
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'Constraint chk_moneyness already exists';
END $$;

COMMENT ON COLUMN options_chains.oi_change IS 'Change in OI from previous day';
COMMENT ON COLUMN options_chains.volume_oi_ratio IS 'Volume / Open Interest ratio';
COMMENT ON COLUMN options_chains.moneyness IS 'ITM/ATM/OTM classification';

-- ============================================================================
-- SECTION 6: UNIVERSE SEED DATA
-- ============================================================================

-- Insert common ETFs and indexes for universe tracking
INSERT INTO tickers (symbol, name, sector, universe_tier, is_active, options_enabled) VALUES
    ('SPY', 'SPDR S&P 500 ETF', 'ETF', 'etf', true, true),
    ('QQQ', 'Invesco QQQ Trust', 'ETF', 'etf', true, true),
    ('IWM', 'iShares Russell 2000 ETF', 'ETF', 'etf', true, true),
    ('DIA', 'SPDR Dow Jones Industrial Average ETF', 'ETF', 'etf', true, true),
    ('TLT', 'iShares 20+ Year Treasury Bond ETF', 'ETF', 'etf', true, true),
    ('GLD', 'SPDR Gold Shares', 'ETF', 'etf', true, true),
    ('XLF', 'Financial Select Sector SPDR', 'ETF', 'etf', true, true),
    ('XLK', 'Technology Select Sector SPDR', 'ETF', 'etf', true, true),
    ('XLE', 'Energy Select Sector SPDR', 'ETF', 'etf', true, true),
    ('XLV', 'Health Care Select Sector SPDR', 'ETF', 'etf', true, true),
    ('SMH', 'VanEck Semiconductor ETF', 'ETF', 'etf', true, true)
ON CONFLICT (symbol) DO UPDATE SET
    universe_tier = EXCLUDED.universe_tier,
    options_enabled = EXCLUDED.options_enabled;

-- ============================================================================
-- SECTION 7: HELPER VIEWS (Using symbol_id foreign key)
-- ============================================================================

-- Drop existing views to recreate them
DROP VIEW IF EXISTS v_exit_signals CASCADE;
DROP VIEW IF EXISTS v_entry_signals CASCADE;
DROP VIEW IF EXISTS v_wyckoff_events CASCADE;
DROP VIEW IF EXISTS v_alerts CASCADE;
DROP VIEW IF EXISTS v_latest_snapshots CASCADE;
DROP VIEW IF EXISTS v_watchlist_tickers CASCADE;

-- View: Latest snapshot per symbol with key metrics
CREATE OR REPLACE VIEW v_latest_snapshots AS
SELECT DISTINCT ON (ds.symbol_id)
    ds.symbol_id,
    t.symbol,
    ds.time,
    ds.wyckoff_phase,
    ds.phase_confidence,
    ds.primary_event,
    ds.bc_score,
    ds.spring_score,
    ds.rsi_14,
    ds.adx_14,
    ds.rvol,
    ds.vsi,
    ds.dgpi,
    ds.dealer_position,
    ds.gamma_flip_level,
    ds.put_call_ratio_oi,
    ds.average_iv,
    ds.iv_hv_diff
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
ORDER BY ds.symbol_id, ds.time DESC;

COMMENT ON VIEW v_latest_snapshots IS 'Most recent snapshot per symbol with key metrics';

-- View: Tickers requiring analysis (in watchlist, have fresh OHLCV)
CREATE OR REPLACE VIEW v_watchlist_tickers AS
SELECT 
    t.id,
    t.symbol,
    t.name,
    t.sector,
    t.options_enabled,
    t.last_ohlcv_date,
    t.last_analysis_date,
    pt.priority,
    p.name as portfolio_name
FROM tickers t
JOIN portfolio_tickers pt ON t.id = pt.ticker_id
JOIN portfolios p ON pt.portfolio_id = p.id
WHERE t.is_active = true
ORDER BY pt.priority, t.symbol;

COMMENT ON VIEW v_watchlist_tickers IS 'Tickers in portfolios requiring daily analysis';

-- View: High-alert conditions with ENTRY/EXIT signal classification
CREATE OR REPLACE VIEW v_alerts AS
-- CRITICAL: BC Exit Signal
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'EXIT_CRITICAL' as signal_type,
    'BC_CRITICAL' as alert_type,
    ds.bc_score::NUMERIC as alert_value,
    '🔴 EXIT IMMEDIATELY - BC Score >= 24' as alert_message,
    1 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.bc_score >= 24
    AND ds.time > NOW() - INTERVAL '7 days'

UNION ALL

-- HIGH: Entry Signal (SPRING + SOS confirmed)
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'ENTRY_SIGNAL' as signal_type,
    'SPRING_SOS' as alert_type,
    ds.spring_score::NUMERIC as alert_value,
    '🟢 ENTRY SIGNAL - Spring confirmed with SOS' as alert_message,
    2 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE 'SPRING' = ANY(ds.events_detected) 
    AND 'SOS' = ANY(ds.events_detected)
    AND ds.bc_score < 12
    AND ds.time > NOW() - INTERVAL '14 days'

UNION ALL

-- HIGH: Strong Entry Setup (SPRING confirmed, high spring score)
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'ENTRY_SETUP' as signal_type,
    'SPRING_CONFIRMED' as alert_type,
    ds.spring_score::NUMERIC as alert_value,
    '🟢 ENTRY SETUP - Spring Score >= 9, favorable entry' as alert_message,
    3 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.spring_score >= 9
    AND ds.bc_score < 12
    AND ds.time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: BC Exit Warning
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'EXIT_WARNING' as signal_type,
    'BC_WARNING' as alert_type,
    ds.bc_score::NUMERIC as alert_value,
    '🟡 CAUTION - BC Score >= 20, prepare exit orders' as alert_message,
    4 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.bc_score >= 20 AND ds.bc_score < 24
    AND ds.time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: Sign of Weakness (distribution warning)
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'EXIT_WARNING' as signal_type,
    'SOW_DETECTED' as alert_type,
    ds.primary_event_confidence as alert_value,
    '🟡 CAUTION - Sign of Weakness detected' as alert_message,
    5 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.primary_event = 'SOW'
    AND ds.time > NOW() - INTERVAL '7 days'

UNION ALL

-- LOW: Volume Surge (potential event confirmation)
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    'INFO' as signal_type,
    'VOLUME_SURGE' as alert_type,
    ds.vsi as alert_value,
    '🔵 INFO - Volume Surge Index > 2, significant activity' as alert_message,
    6 as priority
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE ds.vsi > 2
    AND ds.time > NOW() - INTERVAL '7 days'

ORDER BY priority, time DESC;

COMMENT ON VIEW v_alerts IS 'Active alert conditions with ENTRY/EXIT signal classification';

-- View: Wyckoff event status for all watchlist tickers (dashboard display)
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    t.symbol,
    ds.symbol_id,
    ds.time,
    ds.wyckoff_phase,
    ds.phase_confidence,
    ds.events_detected,
    ds.primary_event,
    ds.primary_event_confidence,
    ds.bc_score,
    ds.spring_score,
    -- Signal classification
    CASE 
        WHEN ds.bc_score >= 24 THEN 'EXIT_CRITICAL'
        WHEN ds.bc_score >= 20 THEN 'EXIT_WARNING'
        WHEN ds.spring_score >= 9 AND ds.bc_score < 12 THEN 'ENTRY_SIGNAL'
        WHEN ds.events_detected IS NOT NULL AND 'SPRING' = ANY(ds.events_detected) AND 'SOS' = ANY(ds.events_detected) THEN 'ENTRY_SIGNAL'
        WHEN ds.events_detected IS NOT NULL AND 'SPRING' = ANY(ds.events_detected) THEN 'ENTRY_SETUP'
        WHEN ds.events_detected IS NOT NULL AND 'SOS' = ANY(ds.events_detected) THEN 'ENTRY_SIGNAL'
        WHEN ds.events_detected IS NOT NULL AND 'SOW' = ANY(ds.events_detected) THEN 'EXIT_WARNING'
        WHEN ds.events_detected IS NOT NULL AND 'BC' = ANY(ds.events_detected) THEN 'EXIT_WARNING'
        ELSE 'NEUTRAL'
    END as signal_type,
    -- Signal message for display
    CASE 
        WHEN ds.bc_score >= 24 THEN '🔴 EXIT IMMEDIATELY'
        WHEN ds.bc_score >= 20 THEN '🟡 Prepare Exit'
        WHEN ds.spring_score >= 9 AND ds.bc_score < 12 THEN '🟢 ENTRY - Spring Confirmed'
        WHEN ds.events_detected IS NOT NULL AND 'SPRING' = ANY(ds.events_detected) AND 'SOS' = ANY(ds.events_detected) THEN '🟢 ENTRY - Spring + SOS'
        WHEN ds.events_detected IS NOT NULL AND 'SOS' = ANY(ds.events_detected) THEN '🟢 ENTRY - Sign of Strength'
        WHEN ds.events_detected IS NOT NULL AND 'SPRING' = ANY(ds.events_detected) THEN '🟢 Setup - Spring Detected'
        WHEN ds.events_detected IS NOT NULL AND 'SOW' = ANY(ds.events_detected) THEN '🟡 Caution - Sign of Weakness'
        ELSE '⚪ Neutral'
    END as signal_message,
    -- Individual event detection status (for timeline display)
    CASE WHEN ds.events_detected IS NOT NULL THEN 'SC' = ANY(ds.events_detected) ELSE false END as has_sc,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'AR' = ANY(ds.events_detected) ELSE false END as has_ar,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'ST' = ANY(ds.events_detected) ELSE false END as has_st,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'SPRING' = ANY(ds.events_detected) ELSE false END as has_spring,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'TEST' = ANY(ds.events_detected) ELSE false END as has_test,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'SOS' = ANY(ds.events_detected) ELSE false END as has_sos,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'BC' = ANY(ds.events_detected) ELSE false END as has_bc,
    CASE WHEN ds.events_detected IS NOT NULL THEN 'SOW' = ANY(ds.events_detected) ELSE false END as has_sow,
    -- Event count for sequence tracking
    COALESCE(array_length(ds.events_detected, 1), 0) as events_count,
    -- Full event details
    ds.events_json
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.id
WHERE (ds.symbol_id, ds.time) IN (
    SELECT symbol_id, MAX(time) 
    FROM daily_snapshots 
    GROUP BY symbol_id
);

COMMENT ON VIEW v_wyckoff_events IS 'Current Wyckoff event status per ticker with ENTRY/EXIT signals for dashboard';

-- View: Entry signals only (for quick entry opportunity scanning)
CREATE OR REPLACE VIEW v_entry_signals AS
SELECT * FROM v_wyckoff_events
WHERE signal_type IN ('ENTRY_SIGNAL', 'ENTRY_SETUP')
ORDER BY 
    CASE signal_type 
        WHEN 'ENTRY_SIGNAL' THEN 1 
        WHEN 'ENTRY_SETUP' THEN 2 
    END,
    spring_score DESC;

COMMENT ON VIEW v_entry_signals IS 'Tickers with active entry signals (SPRING, SOS)';

-- View: Exit signals only (for position monitoring)
CREATE OR REPLACE VIEW v_exit_signals AS
SELECT * FROM v_wyckoff_events
WHERE signal_type IN ('EXIT_CRITICAL', 'EXIT_WARNING')
ORDER BY 
    CASE signal_type 
        WHEN 'EXIT_CRITICAL' THEN 1 
        WHEN 'EXIT_WARNING' THEN 2 
    END,
    bc_score DESC;

COMMENT ON VIEW v_exit_signals IS 'Tickers with active exit signals (BC, SOW)';

-- ============================================================================
-- SECTION 8: HELPER FUNCTIONS
-- ============================================================================

-- Function: Get tickers needing OHLCV update
CREATE OR REPLACE FUNCTION fn_symbols_needing_ohlcv(target_date DATE DEFAULT CURRENT_DATE - 1)
RETURNS TABLE(symbol VARCHAR, ticker_id UUID, last_date DATE, days_behind INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
        t.id as ticker_id,
        t.last_ohlcv_date,
        (target_date - COALESCE(t.last_ohlcv_date, '2020-01-01'::DATE))::INTEGER as days_behind
    FROM tickers t
    WHERE t.is_active = true
        AND (t.last_ohlcv_date IS NULL OR t.last_ohlcv_date < target_date)
    ORDER BY days_behind DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get watchlist symbols needing analysis
CREATE OR REPLACE FUNCTION fn_watchlist_needing_analysis(target_date DATE DEFAULT CURRENT_DATE - 1)
RETURNS TABLE(symbol VARCHAR, ticker_id UUID, priority INTEGER, last_analysis DATE, has_ohlcv BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
        t.id as ticker_id,
        MIN(pt.priority) as priority,
        t.last_analysis_date,
        (t.last_ohlcv_date >= target_date) as has_ohlcv
    FROM tickers t
    JOIN portfolio_tickers pt ON t.id = pt.ticker_id
    WHERE t.is_active = true
        AND (t.last_analysis_date IS NULL OR t.last_analysis_date < target_date)
        AND t.last_ohlcv_date >= target_date  -- Only if OHLCV is fresh
    GROUP BY t.id, t.symbol, t.last_analysis_date, t.last_ohlcv_date
    ORDER BY priority, symbol;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 9: RECORD MIGRATION
-- ============================================================================

-- Record migration in model_parameters
INSERT INTO model_parameters (model_name, version, parameters_json, notes)
VALUES (
    'schema_migration',
    '004',
    '{"changes": ["enhanced_metrics_columns", "options_daily_summary", "ticker_universe", "helper_views", "symbol_id_foreign_key"]}',
    'Sprint 1 refactor: Added structured columns for TA, dealer, volatility, price metrics. Uses symbol_id UUID foreign key pattern.'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- MIGRATION COMPLETE - VERIFICATION
-- ============================================================================

DO $$
DECLARE
    col_count INTEGER;
    view_count INTEGER;
    ticker_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count 
    FROM information_schema.columns 
    WHERE table_name = 'daily_snapshots';
    
    SELECT COUNT(*) INTO view_count 
    FROM pg_views 
    WHERE schemaname = 'public' AND viewname LIKE 'v_%';
    
    SELECT COUNT(*) INTO ticker_count 
    FROM tickers 
    WHERE universe_tier IS NOT NULL;
    
    RAISE NOTICE '';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'MIGRATION 004 COMPLETE';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'daily_snapshots columns: %', col_count;
    RAISE NOTICE 'Views created: %', view_count;
    RAISE NOTICE 'Seeded tickers: %', ticker_count;
    RAISE NOTICE '===========================================';
    RAISE NOTICE '';
END $$;
