import os
import uuid
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from core.metrics.batch_runner import BatchConfig, MetricsBatchRunner


def _create_schema(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tickers (
                    id TEXT PRIMARY KEY,
                    symbol TEXT UNIQUE NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE ohlcv_daily (
                    time DATE NOT NULL,
                    symbol_id TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE daily_snapshots (
                    time DATE NOT NULL,
                    symbol_id TEXT NOT NULL,
                    rsi_14 REAL,
                    macd_line REAL,
                    macd_signal REAL,
                    macd_histogram REAL,
                    sma_20 REAL,
                    sma_50 REAL,
                    ema_12 REAL,
                    ema_26 REAL,
                    rvol REAL,
                    vsi REAL,
                    hv_20 REAL,
                    PRIMARY KEY (time, symbol_id)
                );
                """
            )
        )


def _seed_ohlcv(engine, symbol: str, days: int, start_price: float = 100.0, include_target: bool = True):
    ticker_id = str(uuid.uuid4())
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(days)]
    if not include_target and dates:
        dates = dates[:-1]

    df = pd.DataFrame(
        {
            "time": dates,
            "symbol_id": ticker_id,
            "open": [start_price + i * 0.5 for i in range(len(dates))],
            "high": [start_price + i * 0.5 + 1 for i in range(len(dates))],
            "low": [start_price + i * 0.5 - 1 for i in range(len(dates))],
            "close": [start_price + i * 0.5 for i in range(len(dates))],
            "volume": [1_000_000 + i * 1000 for i in range(len(dates))],
        }
    )

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tickers (id, symbol, created_at, updated_at) VALUES (:id, :symbol, '2024-01-01', '2024-01-01')"),
            {"id": ticker_id, "symbol": symbol},
        )
        df.to_sql("ohlcv_daily", conn, if_exists="append", index=False)
    return df, ticker_id


@pytest.fixture()
def sqlite_env(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _create_schema(engine)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return engine


def test_metrics_written_for_target_date(sqlite_env):
    engine = sqlite_env
    df, _ = _seed_ohlcv(engine, "AAPL", 60)
    target = df["time"].max()

    runner = MetricsBatchRunner(engine=engine)
    runner.run(BatchConfig(target_date=target, symbols=["AAPL"], lookback_days=70))

    with engine.connect() as conn:
        row = conn.execute(text("SELECT rsi_14, macd_line, sma_20, ema_12, rvol, vsi, hv_20 FROM daily_snapshots")).first()
    assert row is not None
    assert row.rsi_14 is not None
    assert row.macd_line is not None
    assert row.sma_20 is not None
    assert row.ema_12 is not None
    assert row.rvol is not None
    assert row.vsi is not None
    assert row.hv_20 is not None


def test_idempotent_upsert_rerun(sqlite_env):
    engine = sqlite_env
    df, _ = _seed_ohlcv(engine, "MSFT", 55)
    target = df["time"].max()
    runner = MetricsBatchRunner(engine=engine)

    runner.run(BatchConfig(target_date=target, symbols=["MSFT"], lookback_days=70))
    runner.run(BatchConfig(target_date=target, symbols=["MSFT"], lookback_days=70))

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM daily_snapshots")).scalar()
        row = conn.execute(text("SELECT macd_histogram FROM daily_snapshots")).scalar()
    assert count == 1
    assert row is not None


def test_missing_target_date_ohlcv_skips_symbol(sqlite_env):
    engine = sqlite_env
    _seed_ohlcv(engine, "GOOG", 30, include_target=False)
    runner = MetricsBatchRunner(engine=engine)
    target_date = date(2024, 1, 30)

    runner.run(BatchConfig(target_date=target_date, symbols=["GOOG"], lookback_days=40))

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM daily_snapshots")).scalar()
    assert count == 0


def test_partial_history_writes_nulls(sqlite_env):
    engine = sqlite_env
    df, _ = _seed_ohlcv(engine, "IBM", 10)
    target = df["time"].max()
    runner = MetricsBatchRunner(engine=engine)

    runner.run(BatchConfig(target_date=target, symbols=["IBM"], lookback_days=15))

    with engine.connect() as conn:
        row = conn.execute(text("SELECT rsi_14, macd_line, sma_50 FROM daily_snapshots")).first()
    assert row is not None
    assert row.rsi_14 is None
    assert row.macd_line is None
    assert row.sma_50 is None


def test_one_symbol_failure_does_not_abort(sqlite_env):
    engine = sqlite_env
    df, _ = _seed_ohlcv(engine, "TSLA", 60)
    target = df["time"].max()

    # Invalid close for second symbol
    bad_df, _ = _seed_ohlcv(engine, "AMZN", 60)
    bad_df.loc[bad_df.index[-1], "close"] = -1
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ohlcv_daily WHERE symbol_id = :sid"), {"sid": bad_df["symbol_id"].iloc[0]})
        bad_df.to_sql("ohlcv_daily", conn, if_exists="append", index=False)

    runner = MetricsBatchRunner(engine=engine)
    runner.run(BatchConfig(target_date=target, symbols=["TSLA", "AMZN"], lookback_days=70))

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol_id, hv_20 FROM daily_snapshots")).fetchall()
    assert len(rows) == 1  # TSLA only
    assert rows[0].hv_20 is not None

