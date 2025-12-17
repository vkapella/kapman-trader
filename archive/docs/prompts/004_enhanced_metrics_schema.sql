-- ============================================================================
-- MIGRATION 004: Enhanced Metrics Schema
-- Kapman Trading System v2
-- Date: December 9, 2025
-- Purpose: Add structured columns for technical indicators, dealer metrics,
--          volatility metrics, and price metrics to support efficient querying
--          and alerting. Also adds ticker universe classification and options
--          daily summary table.
-- ============================================================================

-- ============================================================================
-- SECTION 1: TICKER UNIVERSE CLASSIFICATION
-- ============================================================================

-- Add universe tier to track where ticker came from
ALTER TABLE tickers ADD COLUMN IF NOT EXISTS 
    universe_tier VARCHAR(20) DEFAULT 'custom'
    CHECK (universe_tier IN ('sp500', 'russell3000', 'polygon_full', 'custom', 'etf', 'index'));

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

-- Constraint for dealer position values
ALTER TABLE daily_snapshots DROP CONSTRAINT IF EXISTS chk_dealer_position;
ALTER TABLE daily_snapshots ADD CONSTRAINT chk_dealer_position 
    CHECK (dealer_position IS NULL OR dealer_position IN ('long_gamma', 'short_gamma', 'neutral'));

-- Constraint for DGPI range
ALTER TABLE daily_snapshots DROP CONSTRAINT IF EXISTS chk_dgpi_range;
ALTER TABLE daily_snapshots ADD CONSTRAINT chk_dgpi_range 
    CHECK (dgpi IS NULL OR (dgpi >= -100 AND dgpi <= 100));

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

-- Composite index for Wyckoff event + volume confirmation
CREATE INDEX IF NOT EXISTS idx_snapshots_wyckoff_volume ON daily_snapshots(symbol, time DESC, primary_event, rvol) 
    WHERE primary_event IS NOT NULL;

-- ============================================================================
-- SECTION 3: OPTIONS DAILY SUMMARY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS options_daily_summary (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Aggregate Open Interest
    total_call_oi INTEGER,
    total_put_oi INTEGER,
    total_oi INTEGER GENERATED ALWAYS AS (COALESCE(total_call_oi, 0) + COALESCE(total_put_oi, 0)) STORED,
    
    -- Aggregate Volume
    total_call_volume INTEGER,
    total_put_volume INTEGER,
    total_volume INTEGER GENERATED ALWAYS AS (COALESCE(total_call_volume, 0) + COALESCE(total_put_volume, 0)) STORED,
    
    -- Ratios
    put_call_oi_ratio NUMERIC(6,4) GENERATED ALWAYS AS (
        CASE WHEN COALESCE(total_call_oi, 0) > 0 
        THEN ROUND(COALESCE(total_put_oi, 0)::NUMERIC / total_call_oi, 4) 
        ELSE NULL END
    ) STORED,
    put_call_volume_ratio NUMERIC(6,4) GENERATED ALWAYS AS (
        CASE WHEN COALESCE(total_call_volume, 0) > 0 
        THEN ROUND(COALESCE(total_put_volume, 0)::NUMERIC / total_call_volume, 4) 
        ELSE NULL END
    ) STORED,
    
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
    
    -- GEX Calculation (Gamma × OI × 100 × Spot)
    -- Note: Stored after calculation in Python, not computed here
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
    
    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('options_daily_summary', 'time', if_not_exists => TRUE);

-- Indexes for options summary
CREATE INDEX IF NOT EXISTS idx_options_summary_symbol ON options_daily_summary(symbol, time DESC);
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

-- Add symbol_id foreign key for referential integrity (optional, for joins)
-- Note: We keep symbol VARCHAR for hypertable partitioning efficiency
ALTER TABLE ohlcv_daily ADD COLUMN IF NOT EXISTS ticker_id UUID;

-- Add index for ticker_id lookups
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_id ON ohlcv_daily(ticker_id, time DESC) 
    WHERE ticker_id IS NOT NULL;

-- Add data quality flag
ALTER TABLE ohlcv_daily ADD COLUMN IF NOT EXISTS is_adjusted BOOLEAN DEFAULT true;

COMMENT ON COLUMN ohlcv_daily.ticker_id IS 'Optional FK to tickers table for joins';
COMMENT ON COLUMN ohlcv_daily.is_adjusted IS 'Whether prices are split/dividend adjusted';

-- ============================================================================
-- SECTION 5: OPTIONS CHAINS TABLE ENHANCEMENTS  
-- ============================================================================

-- Add open interest change tracking
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS oi_change INTEGER;
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS volume_oi_ratio NUMERIC(8,4);

-- Add moneyness classification
ALTER TABLE options_chains ADD COLUMN IF NOT EXISTS moneyness VARCHAR(10);
ALTER TABLE options_chains DROP CONSTRAINT IF EXISTS chk_moneyness;
ALTER TABLE options_chains ADD CONSTRAINT chk_moneyness 
    CHECK (moneyness IS NULL OR moneyness IN ('ITM', 'ATM', 'OTM', 'DITM', 'DOTM'));

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
    ('VIX', 'CBOE Volatility Index', 'Index', 'index', true, false),
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
-- SECTION 7: HELPER VIEWS
-- ============================================================================

-- View: Latest snapshot per symbol with key metrics
CREATE OR REPLACE VIEW v_latest_snapshots AS
SELECT DISTINCT ON (symbol)
    symbol,
    time,
    wyckoff_phase,
    phase_confidence,
    primary_event,
    bc_score,
    spring_score,
    rsi_14,
    adx_14,
    rvol,
    vsi,
    dgpi,
    dealer_position,
    gamma_flip_level,
    put_call_ratio_oi,
    average_iv,
    iv_hv_diff
FROM daily_snapshots
ORDER BY symbol, time DESC;

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
    symbol,
    time,
    'EXIT_CRITICAL' as signal_type,
    'BC_CRITICAL' as alert_type,
    bc_score as alert_value,
    '🔴 EXIT IMMEDIATELY - BC Score >= 24' as alert_message,
    1 as priority
FROM daily_snapshots
WHERE bc_score >= 24
    AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- HIGH: Entry Signal (SPRING + SOS confirmed)
SELECT 
    symbol,
    time,
    'ENTRY_SIGNAL' as signal_type,
    'SPRING_SOS' as alert_type,
    spring_score as alert_value,
    '🟢 ENTRY SIGNAL - Spring confirmed with SOS' as alert_message,
    2 as priority
FROM daily_snapshots
WHERE 'SPRING' = ANY(events_detected) 
    AND 'SOS' = ANY(events_detected)
    AND bc_score < 12
    AND time > NOW() - INTERVAL '14 days'

UNION ALL

-- HIGH: Strong Entry Setup (SPRING confirmed, high spring score)
SELECT 
    symbol,
    time,
    'ENTRY_SETUP' as signal_type,
    'SPRING_CONFIRMED' as alert_type,
    spring_score as alert_value,
    '🟢 ENTRY SETUP - Spring Score >= 9, favorable entry' as alert_message,
    3 as priority
FROM daily_snapshots
WHERE spring_score >= 9
    AND bc_score < 12
    AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: BC Exit Warning
SELECT 
    symbol,
    time,
    'EXIT_WARNING' as signal_type,
    'BC_WARNING' as alert_type,
    bc_score as alert_value,
    '🟡 CAUTION - BC Score >= 20, prepare exit orders' as alert_message,
    4 as priority
FROM daily_snapshots
WHERE bc_score >= 20 AND bc_score < 24
    AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: Sign of Weakness (distribution warning)
SELECT 
    symbol,
    time,
    'EXIT_WARNING' as signal_type,
    'SOW_DETECTED' as alert_type,
    primary_event_confidence as alert_value,
    '🟡 CAUTION - Sign of Weakness detected' as alert_message,
    5 as priority
FROM daily_snapshots
WHERE primary_event = 'SOW'
    AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- LOW: Volume Surge (potential event confirmation)
SELECT 
    symbol,
    time,
    'INFO' as signal_type,
    'VOLUME_SURGE' as alert_type,
    vsi as alert_value,
    '🔵 INFO - Volume Surge Index > 2, significant activity' as alert_message,
    6 as priority
FROM daily_snapshots
WHERE vsi > 2
    AND time > NOW() - INTERVAL '7 days'

ORDER BY priority, time DESC;

COMMENT ON VIEW v_alerts IS 'Active alert conditions with ENTRY/EXIT signal classification';

-- View: Wyckoff event status for all watchlist tickers (dashboard display)
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    s.symbol,
    s.time,
    s.wyckoff_phase,
    s.phase_confidence,
    s.events_detected,
    s.primary_event,
    s.primary_event_confidence,
    s.bc_score,
    s.spring_score,
    -- Signal classification
    CASE 
        WHEN s.bc_score >= 24 THEN 'EXIT_CRITICAL'
        WHEN s.bc_score >= 20 THEN 'EXIT_WARNING'
        WHEN s.spring_score >= 9 AND s.bc_score < 12 THEN 'ENTRY_SIGNAL'
        WHEN 'SPRING' = ANY(s.events_detected) AND 'SOS' = ANY(s.events_detected) THEN 'ENTRY_SIGNAL'
        WHEN 'SPRING' = ANY(s.events_detected) THEN 'ENTRY_SETUP'
        WHEN 'SOS' = ANY(s.events_detected) THEN 'ENTRY_SIGNAL'
        WHEN 'SOW' = ANY(s.events_detected) THEN 'EXIT_WARNING'
        WHEN 'BC' = ANY(s.events_detected) THEN 'EXIT_WARNING'
        ELSE 'NEUTRAL'
    END as signal_type,
    -- Signal message for display
    CASE 
        WHEN s.bc_score >= 24 THEN '🔴 EXIT IMMEDIATELY'
        WHEN s.bc_score >= 20 THEN '🟡 Prepare Exit'
        WHEN s.spring_score >= 9 AND s.bc_score < 12 THEN '🟢 ENTRY - Spring Confirmed'
        WHEN 'SPRING' = ANY(s.events_detected) AND 'SOS' = ANY(s.events_detected) THEN '🟢 ENTRY - Spring + SOS'
        WHEN 'SOS' = ANY(s.events_detected) THEN '🟢 ENTRY - Sign of Strength'
        WHEN 'SPRING' = ANY(s.events_detected) THEN '🟢 Setup - Spring Detected'
        WHEN 'SOW' = ANY(s.events_detected) THEN '🟡 Caution - Sign of Weakness'
        ELSE '⚪ Neutral'
    END as signal_message,
    -- Individual event detection status (for timeline display)
    'SC' = ANY(s.events_detected) as has_sc,
    'AR' = ANY(s.events_detected) as has_ar,
    'ST' = ANY(s.events_detected) as has_st,
    'SPRING' = ANY(s.events_detected) as has_spring,
    'TEST' = ANY(s.events_detected) as has_test,
    'SOS' = ANY(s.events_detected) as has_sos,
    'BC' = ANY(s.events_detected) as has_bc,
    'SOW' = ANY(s.events_detected) as has_sow,
    -- Event count for sequence tracking
    COALESCE(array_length(s.events_detected, 1), 0) as events_count,
    -- Full event details
    s.events_json
FROM daily_snapshots s
WHERE (s.symbol, s.time) IN (
    SELECT symbol, MAX(time) 
    FROM daily_snapshots 
    GROUP BY symbol
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
-- SECTION 8: FUNCTIONS FOR COMMON QUERIES
-- ============================================================================

-- Function: Get symbols needing OHLCV update
CREATE OR REPLACE FUNCTION fn_symbols_needing_ohlcv(target_date DATE DEFAULT CURRENT_DATE - 1)
RETURNS TABLE(symbol VARCHAR, last_date DATE, days_behind INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
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
RETURNS TABLE(symbol VARCHAR, priority INTEGER, last_analysis DATE, has_ohlcv BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
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
-- MIGRATION COMPLETE
-- ============================================================================

-- Record migration
INSERT INTO model_parameters (model_name, version, parameters_json, notes)
VALUES (
    'schema_migration',
    '004',
    '{"changes": ["enhanced_metrics_columns", "options_daily_summary", "ticker_universe", "helper_views"]}',
    'Sprint 1 refactor: Added structured columns for TA, dealer, volatility, price metrics'
);
