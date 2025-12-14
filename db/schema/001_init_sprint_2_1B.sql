-- ============================================================
-- SPIKE 2.1.B — Metric Storage Schema (Authoritative)
-- ============================================================

-- ----------------------------
-- Dimension Tables
-- ----------------------------

CREATE TABLE IF NOT EXISTS dim_symbol (
    symbol_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS config_set (
    config_id   TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL UNIQUE,
    config_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_run (
    run_id     TEXT PRIMARY KEY,
    run_type   TEXT NOT NULL,              -- event | batch | backfill
    source     TEXT,                       -- free-text provenance (optional)
    started_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------
-- OHLCV (Versioned Inputs)
-- ----------------------------

CREATE TABLE IF NOT EXISTS fact_ohlcv_daily (
    symbol_id      TEXT NOT NULL REFERENCES dim_symbol(symbol_id),
    trading_date   DATE NOT NULL,
    source_version TEXT NOT NULL,
    etl_run_id     TEXT NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (symbol_id, trading_date, source_version)
);

CREATE INDEX IF NOT EXISTS fact_ohlcv_daily_symbol_date_idx
    ON fact_ohlcv_daily (symbol_id, trading_date);

CREATE INDEX IF NOT EXISTS fact_ohlcv_daily_trading_date_idx
    ON fact_ohlcv_daily (trading_date);

CREATE INDEX IF NOT EXISTS fact_ohlcv_daily_etl_run_id_idx
    ON fact_ohlcv_daily (etl_run_id);

-- ----------------------------
-- Realized Volatility
-- ----------------------------

CREATE TABLE IF NOT EXISTS fact_realized_volatility_daily (
    symbol_id     TEXT NOT NULL REFERENCES dim_symbol(symbol_id),
    trading_date  DATE NOT NULL,
    config_id     TEXT NOT NULL REFERENCES config_set(config_id),
    algo_version  TEXT NOT NULL,
    algo_git_sha  TEXT NOT NULL,
    etl_run_id    TEXT NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (symbol_id, trading_date, config_id, algo_version, algo_git_sha)
);

CREATE INDEX IF NOT EXISTS fact_realized_volatility_daily_symbol_date_idx
    ON fact_realized_volatility_daily (symbol_id, trading_date);

CREATE INDEX IF NOT EXISTS fact_realized_volatility_daily_config_id_idx
    ON fact_realized_volatility_daily (config_id);

CREATE INDEX IF NOT EXISTS fact_realized_volatility_daily_etl_run_id_idx
    ON fact_realized_volatility_daily (etl_run_id);

-- ----------------------------
-- Implied Volatility
-- ----------------------------

CREATE TABLE IF NOT EXISTS fact_implied_volatility_daily (
    symbol_id     TEXT NOT NULL REFERENCES dim_symbol(symbol_id),
    trading_date  DATE NOT NULL,
    config_id     TEXT NOT NULL REFERENCES config_set(config_id),
    algo_version  TEXT NOT NULL,
    algo_git_sha  TEXT NOT NULL,
    etl_run_id    TEXT NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (symbol_id, trading_date, config_id, algo_version, algo_git_sha)
);

CREATE INDEX IF NOT EXISTS fact_implied_volatility_daily_symbol_date_idx
    ON fact_implied_volatility_daily (symbol_id, trading_date);

CREATE INDEX IF NOT EXISTS fact_implied_volatility_daily_config_id_idx
    ON fact_implied_volatility_daily (config_id);

CREATE INDEX IF NOT EXISTS fact_implied_volatility_daily_etl_run_id_idx
    ON fact_implied_volatility_daily (etl_run_id);

-- ----------------------------
-- Dealer / Market Structure Metrics
-- ----------------------------

CREATE TABLE IF NOT EXISTS fact_dealer_metrics_daily (
    symbol_id     TEXT NOT NULL REFERENCES dim_symbol(symbol_id),
    trading_date  DATE NOT NULL,
    config_id     TEXT NOT NULL REFERENCES config_set(config_id),
    algo_version  TEXT NOT NULL,
    algo_git_sha  TEXT NOT NULL,
    etl_run_id    TEXT NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (symbol_id, trading_date, config_id, algo_version, algo_git_sha)
);

CREATE INDEX IF NOT EXISTS fact_dealer_metrics_daily_symbol_date_idx
    ON fact_dealer_metrics_daily (symbol_id, trading_date);

CREATE INDEX IF NOT EXISTS fact_dealer_metrics_daily_config_id_idx
    ON fact_dealer_metrics_daily (config_id);

CREATE INDEX IF NOT EXISTS fact_dealer_metrics_daily_etl_run_id_idx
    ON fact_dealer_metrics_daily (etl_run_id);

-- ----------------------------
-- Options Chain Snapshot Metadata
-- ----------------------------

CREATE TABLE IF NOT EXISTS fact_options_chain_snapshot_meta (
    symbol_id      TEXT NOT NULL REFERENCES dim_symbol(symbol_id),
    trading_date   DATE NOT NULL,
    source_version TEXT NOT NULL,
    etl_run_id     TEXT NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (symbol_id, trading_date, source_version)
);

CREATE INDEX IF NOT EXISTS fact_options_chain_snapshot_meta_symbol_date_idx
    ON fact_options_chain_snapshot_meta (symbol_id, trading_date);

CREATE INDEX IF NOT EXISTS fact_options_chain_snapshot_meta_trading_date_idx
    ON fact_options_chain_snapshot_meta (trading_date);

CREATE INDEX IF NOT EXISTS fact_options_chain_snapshot_meta_etl_run_id_idx
    ON fact_options_chain_snapshot_meta (etl_run_id);