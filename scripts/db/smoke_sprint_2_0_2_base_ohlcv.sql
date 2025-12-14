\pset tuples_only on
\set ON_ERROR_STOP on

-- Sprint 2.0.2 Base OHLCV Lifecycle
-- Invariants:
-- 1) Retention policy exists on ohlcv_daily with drop_after = 730 days
-- 2) Compression is enabled on ohlcv_daily
-- 3) Compression policy exists on ohlcv_daily with compress_after ≈ 365 days

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_retention'
          AND hypertable_name = 'ohlcv_daily'
          AND (config->>'drop_after') = '730 days'
    ) THEN
        RAISE EXCEPTION 'Sprint 2.0.2 invariant violated: retention policy must be 730 days on ohlcv_daily';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.hypertables
        WHERE hypertable_schema = 'public'
          AND hypertable_name = 'ohlcv_daily'
          AND compression_enabled IS TRUE
    ) THEN
        RAISE EXCEPTION 'SMOKE FAIL (Sprint 2.0.2): compression not enabled on ohlcv_daily';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_compression'
          AND hypertable_name = 'ohlcv_daily'
          AND (config->>'compress_after') IN ('365 days', '1 year')
    ) THEN
    RAISE EXCEPTION 'Sprint 2.0.2 invariant violated: compression policy missing or incorrect on ohlcv_daily';
    END IF;
END
$$ LANGUAGE plpgsql;
