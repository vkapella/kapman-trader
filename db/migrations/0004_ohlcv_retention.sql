-- A6 baseline invariant: enforce bounded OHLCV history via TimescaleDB retention policy.
-- Keep exactly 730 days of data in the `ohlcv` hypertable.
SELECT add_retention_policy('ohlcv', INTERVAL '730 days', if_not_exists => TRUE);
