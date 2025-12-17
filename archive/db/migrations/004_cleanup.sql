-- ============================================================================
-- CLEANUP SCRIPT: Remove Partial Migration 004 Changes
-- Kapman Trading System
-- Date: December 9, 2025
--
-- Run this BEFORE re-applying 004_enhanced_metrics_schema.sql
-- This safely removes columns/tables added by the failed migration
-- ============================================================================

-- ============================================================================
-- SECTION 1: DROP VIEWS (order matters due to dependencies)
-- ============================================================================

DROP VIEW IF EXISTS v_exit_signals CASCADE;
DROP VIEW IF EXISTS v_entry_signals CASCADE;
DROP VIEW IF EXISTS v_wyckoff_events CASCADE;
DROP VIEW IF EXISTS v_alerts CASCADE;
DROP VIEW IF EXISTS v_latest_snapshots CASCADE;
DROP VIEW IF EXISTS v_watchlist_tickers CASCADE;

RAISE NOTICE 'Views dropped';

-- ============================================================================
-- SECTION 2: DROP FUNCTIONS
-- ============================================================================

DROP FUNCTION IF EXISTS fn_symbols_needing_ohlcv(DATE);
DROP FUNCTION IF EXISTS fn_watchlist_needing_analysis(DATE);
DROP FUNCTION IF EXISTS temp_column_exists(TEXT, TEXT);

RAISE NOTICE 'Functions dropped';

-- ============================================================================
-- SECTION 3: DROP NEW TABLE
-- ============================================================================

DROP TABLE IF EXISTS options_daily_summary CASCADE;

RAISE NOTICE 'options_daily_summary table dropped';

-- ============================================================================
-- SECTION 4: REMOVE COLUMNS FROM daily_snapshots
-- ============================================================================

-- Technical Indicators
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS rsi_14;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS macd_line;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS macd_signal;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS macd_histogram;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS stoch_k;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS stoch_d;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS mfi_14;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS sma_20;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS sma_50;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS sma_200;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS ema_12;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS ema_26;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS adx_14;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS atr_14;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS bbands_upper;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS bbands_middle;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS bbands_lower;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS bbands_width;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS obv;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS vwap;

-- Dealer Metrics
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS gex_total;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS gex_net;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS gamma_flip_level;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS call_wall_primary;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS call_wall_primary_oi;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS put_wall_primary;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS put_wall_primary_oi;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS dgpi;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS dealer_position;

-- Volatility Metrics
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS iv_skew_25d;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS iv_term_structure;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS put_call_ratio_oi;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS put_call_ratio_volume;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS average_iv;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS iv_rank;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS iv_percentile;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS volatility_metrics_json;

-- Price Metrics
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS rvol;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS vsi;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS hv_20;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS hv_60;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS iv_hv_diff;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS price_vs_sma20;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS price_vs_sma50;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS price_vs_sma200;

RAISE NOTICE 'daily_snapshots columns removed';

-- ============================================================================
-- SECTION 5: REMOVE COLUMNS FROM tickers
-- ============================================================================

ALTER TABLE tickers DROP COLUMN IF EXISTS universe_tier;
ALTER TABLE tickers DROP COLUMN IF EXISTS last_ohlcv_date;
ALTER TABLE tickers DROP COLUMN IF EXISTS last_analysis_date;
ALTER TABLE tickers DROP COLUMN IF EXISTS options_enabled;

RAISE NOTICE 'tickers columns removed';

-- ============================================================================
-- SECTION 6: REMOVE COLUMNS FROM ohlcv_daily
-- ============================================================================

ALTER TABLE ohlcv_daily DROP COLUMN IF EXISTS is_adjusted;

RAISE NOTICE 'ohlcv_daily columns removed';

-- ============================================================================
-- SECTION 7: REMOVE COLUMNS FROM options_chains
-- ============================================================================

ALTER TABLE options_chains DROP COLUMN IF EXISTS oi_change;
ALTER TABLE options_chains DROP COLUMN IF EXISTS volume_oi_ratio;
ALTER TABLE options_chains DROP COLUMN IF EXISTS moneyness;

RAISE NOTICE 'options_chains columns removed';

-- ============================================================================
-- SECTION 8: DROP CONSTRAINTS (if they exist)
-- ============================================================================

DO $$
BEGIN
    ALTER TABLE tickers DROP CONSTRAINT IF EXISTS chk_universe_tier;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE daily_snapshots DROP CONSTRAINT IF EXISTS chk_dealer_position;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE daily_snapshots DROP CONSTRAINT IF EXISTS chk_dgpi_range;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE options_chains DROP CONSTRAINT IF EXISTS chk_moneyness;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

RAISE NOTICE 'Constraints removed';

-- ============================================================================
-- SECTION 9: DROP INDEXES
-- ============================================================================

DROP INDEX IF EXISTS idx_tickers_universe;
DROP INDEX IF EXISTS idx_snapshots_rsi;
DROP INDEX IF EXISTS idx_snapshots_adx;
DROP INDEX IF EXISTS idx_snapshots_dgpi;
DROP INDEX IF EXISTS idx_snapshots_gamma_flip;
DROP INDEX IF EXISTS idx_snapshots_iv;
DROP INDEX IF EXISTS idx_snapshots_pcr;
DROP INDEX IF EXISTS idx_snapshots_rvol;
DROP INDEX IF EXISTS idx_snapshots_vsi;
DROP INDEX IF EXISTS idx_options_summary_symbol;
DROP INDEX IF EXISTS idx_options_summary_pcr;
DROP INDEX IF EXISTS idx_options_summary_gex;

RAISE NOTICE 'Indexes removed';

-- ============================================================================
-- SECTION 10: REMOVE SEED DATA (optional - comment out if you want to keep)
-- ============================================================================

-- Remove the ETF seed data added by migration 004
-- Comment these out if you want to keep the ETF tickers
DELETE FROM tickers WHERE symbol IN ('SPY', 'QQQ', 'IWM', 'DIA', 'TLT', 'GLD', 'XLF', 'XLK', 'XLE', 'XLV', 'SMH')
    AND name LIKE '%ETF%';

RAISE NOTICE 'Seed data removed (if present)';

-- ============================================================================
-- SECTION 11: REMOVE MIGRATION RECORD
-- ============================================================================

DELETE FROM model_parameters WHERE model_name = 'schema_migration' AND version = '004';

RAISE NOTICE 'Migration record removed';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    col_count INTEGER;
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count 
    FROM information_schema.columns 
    WHERE table_name = 'daily_snapshots';
    
    SELECT COUNT(*) INTO view_count 
    FROM pg_views 
    WHERE schemaname = 'public' AND viewname LIKE 'v_%';
    
    RAISE NOTICE '';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'CLEANUP COMPLETE';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'daily_snapshots columns: % (should be ~15-20)', col_count;
    RAISE NOTICE 'Views remaining: % (should be 0)', view_count;
    RAISE NOTICE '===========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'You can now apply the corrected migration 004';
END $$;
