\pset tuples_only on
\set ON_ERROR_STOP on

-- Sprint 2.0.1 Base OHLCV Foundation
-- Invariants: (1) ohlcv_daily table exists, (2) ohlcv_daily is a Timescale hypertable

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ohlcv_daily'
    ) THEN
        RAISE EXCEPTION 'SMOKE FAIL (Sprint 2.0.1): table public.ohlcv_daily is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.hypertables
        WHERE hypertable_schema = 'public'
  AND hypertable_name = 'ohlcv_daily'
    ) THEN
        RAISE EXCEPTION 'SMOKE FAIL (Sprint 2.0.1): ohlcv_daily is not a Timescale hypertable';
    END IF;
END
$$ LANGUAGE plpgsql;
