-- ============================================================================
-- Pre-Sprint 2 Database Cleanup
-- ============================================================================
-- Purpose: Fix missing columns and recreate dependent views
-- Date: 2025-12-09
-- Author: Victor/Claude
-- ============================================================================

-- Step 1: Add missing events_json column to daily_snapshots
-- ----------------------------------------------------------------------------
ALTER TABLE daily_snapshots 
ADD COLUMN IF NOT EXISTS events_json JSONB;

COMMENT ON COLUMN daily_snapshots.events_json IS 
'JSON array of Wyckoff events detected on this date. Each event contains: event_type, confidence, price_level, volume_context';

-- Step 2: Add missing notes column to model_parameters
-- ----------------------------------------------------------------------------
ALTER TABLE model_parameters 
ADD COLUMN IF NOT EXISTS notes TEXT;

COMMENT ON COLUMN model_parameters.notes IS 
'Free-form notes about parameter configuration, rationale, or observations';

-- Step 3: Drop dependent views (if they exist) to recreate them
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_exit_signals CASCADE;
DROP VIEW IF EXISTS v_entry_signals CASCADE;
DROP VIEW IF EXISTS v_wyckoff_events CASCADE;

-- Step 4: Recreate v_wyckoff_events view
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    ds.symbol_id,
    t.symbol,
    ds.date,
    ds.events_json,
    ds.wyckoff_phase,
    ds.phase_confidence,
    ds.current_price,
    ds.volume,
    ds.volume_ma_20,
    ds.dealer_net_gex,
    ds.dealer_gamma_flip
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.symbol_id
WHERE ds.events_json IS NOT NULL 
  AND jsonb_array_length(ds.events_json) > 0
ORDER BY ds.date DESC, t.symbol;

COMMENT ON VIEW v_wyckoff_events IS 
'View of all Wyckoff events detected across symbols. Used for event analysis and signal generation.';

-- Step 5: Recreate v_entry_signals view
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_entry_signals AS
SELECT 
    ds.symbol_id,
    t.symbol,
    ds.date,
    ds.wyckoff_phase,
    ds.phase_confidence,
    ds.current_price,
    ds.volume,
    ds.rsi_14,
    ds.dealer_net_gex,
    ds.dealer_gamma_flip,
    ds.events_json,
    -- Entry signal logic
    CASE 
        WHEN ds.wyckoff_phase IN ('ACCUMULATION_PHASE_A', 'ACCUMULATION_PHASE_B') 
             AND ds.events_json::text LIKE '%SPRING%'
             AND ds.rsi_14 < 40
        THEN 'BULLISH_SPRING'
        
        WHEN ds.wyckoff_phase = 'ACCUMULATION_PHASE_C'
             AND ds.events_json::text LIKE '%TEST%'
             AND ds.dealer_net_gex > 0
        THEN 'BULLISH_TEST'
        
        WHEN ds.wyckoff_phase IN ('DISTRIBUTION_PHASE_A', 'DISTRIBUTION_PHASE_B')
             AND ds.events_json::text LIKE '%UPTHRUST%'
             AND ds.rsi_14 > 60
        THEN 'BEARISH_UPTHRUST'
        
        WHEN ds.wyckoff_phase = 'DISTRIBUTION_PHASE_C'
             AND ds.events_json::text LIKE '%SPRING%'
             AND ds.dealer_net_gex < 0
        THEN 'BEARISH_SPRING'
        
        ELSE NULL
    END as signal_type,
    
    -- Signal strength (1-5 scale)
    CASE 
        WHEN ds.phase_confidence > 0.8 AND ABS(ds.dealer_net_gex) > 1000000
        THEN 5
        WHEN ds.phase_confidence > 0.7 AND ABS(ds.dealer_net_gex) > 500000
        THEN 4
        WHEN ds.phase_confidence > 0.6
        THEN 3
        WHEN ds.phase_confidence > 0.5
        THEN 2
        ELSE 1
    END as signal_strength
    
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.symbol_id
WHERE ds.events_json IS NOT NULL
  AND ds.phase_confidence > 0.5
  AND (
      (ds.wyckoff_phase LIKE 'ACCUMULATION%' AND ds.rsi_14 < 50)
      OR
      (ds.wyckoff_phase LIKE 'DISTRIBUTION%' AND ds.rsi_14 > 50)
  )
ORDER BY ds.date DESC, signal_strength DESC, t.symbol;

COMMENT ON VIEW v_entry_signals IS 
'Filtered view of potential entry signals based on Wyckoff events and technical indicators. Used by AI recommendation engine.';

-- Step 6: Recreate v_exit_signals view
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_exit_signals AS
SELECT 
    ds.symbol_id,
    t.symbol,
    ds.date,
    ds.wyckoff_phase,
    ds.phase_confidence,
    ds.current_price,
    ds.volume,
    ds.rsi_14,
    ds.dealer_net_gex,
    ds.dealer_gamma_flip,
    ds.events_json,
    -- Exit signal logic
    CASE 
        WHEN ds.wyckoff_phase = 'MARKUP'
             AND ds.events_json::text LIKE '%SOW%'
             AND ds.rsi_14 > 70
        THEN 'TAKE_PROFIT_SOW'
        
        WHEN ds.wyckoff_phase LIKE 'DISTRIBUTION%'
             AND ds.events_json::text LIKE '%SC%'
        THEN 'EXIT_DISTRIBUTION'
        
        WHEN ds.wyckoff_phase = 'MARKDOWN'
             AND ds.dealer_gamma_flip IS NOT NULL
             AND ds.current_price < ds.dealer_gamma_flip
        THEN 'STOP_LOSS_GAMMA_FLIP'
        
        WHEN ds.rsi_14 > 80
        THEN 'OVERBOUGHT_EXIT'
        
        WHEN ds.rsi_14 < 20
        THEN 'OVERSOLD_BOUNCE'
        
        ELSE NULL
    END as exit_type,
    
    -- Exit urgency (1-5 scale, 5 = most urgent)
    CASE 
        WHEN ds.rsi_14 > 80 OR ds.rsi_14 < 20
        THEN 5
        WHEN ds.events_json::text LIKE '%SOW%' AND ds.rsi_14 > 70
        THEN 4
        WHEN ds.wyckoff_phase LIKE 'DISTRIBUTION%'
        THEN 3
        WHEN ds.phase_confidence < 0.6
        THEN 2
        ELSE 1
    END as exit_urgency
    
FROM daily_snapshots ds
JOIN tickers t ON ds.symbol_id = t.symbol_id
WHERE ds.events_json IS NOT NULL
  AND (
      ds.wyckoff_phase IN ('MARKUP', 'MARKDOWN')
      OR ds.wyckoff_phase LIKE 'DISTRIBUTION%'
      OR ds.rsi_14 > 70
      OR ds.rsi_14 < 30
  )
ORDER BY ds.date DESC, exit_urgency DESC, t.symbol;

COMMENT ON VIEW v_exit_signals IS 
'Filtered view of potential exit signals based on Wyckoff phase transitions and overbought/oversold conditions.';

-- Step 7: Verify the cleanup
-- ----------------------------------------------------------------------------
-- Check column existence
SELECT 
    'daily_snapshots.events_json' as check_item,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM information_schema.columns 
WHERE table_name = 'daily_snapshots' 
  AND column_name = 'events_json'

UNION ALL

SELECT 
    'model_parameters.notes' as check_item,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM information_schema.columns 
WHERE table_name = 'model_parameters' 
  AND column_name = 'notes'

UNION ALL

-- Check view existence
SELECT 
    'v_wyckoff_events' as check_item,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM information_schema.views 
WHERE table_name = 'v_wyckoff_events'

UNION ALL

SELECT 
    'v_entry_signals' as check_item,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM information_schema.views 
WHERE table_name = 'v_entry_signals'

UNION ALL

SELECT 
    'v_exit_signals' as check_item,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ EXISTS'
        ELSE '✗ MISSING'
    END as status
FROM information_schema.views 
WHERE table_name = 'v_exit_signals';

-- ============================================================================
-- End of Pre-Sprint 2 Cleanup
-- ============================================================================
