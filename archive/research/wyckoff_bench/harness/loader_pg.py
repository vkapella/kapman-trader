"""
Postgres/Timescale OHLCV loader with parquet caching (research-only).
Reads from `ohlcv_daily` and returns a DataFrame sorted by symbol/time.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence, Tuple

import pandas as pd
import sqlalchemy as sa


DEFAULT_LOOKBACK_TRADING_DAYS = 730
DEFAULT_CACHE_DIR = Path("research/wyckoff_bench/outputs/cache")


def _parse_date(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value)
    return parsed.to_pydatetime()


def _make_engine(database_url: str | None) -> sa.Engine:
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to load OHLCV data.")
    return sa.create_engine(url)


def _default_range(engine: sa.Engine) -> Tuple[datetime | None, datetime | None]:
    """Derive default start/end from latest available date."""
    with engine.connect() as conn:
        max_time = conn.execute(sa.text("SELECT max(date) FROM ohlcv")).scalar()
    if not max_time:
        return None, None
    end_ts = pd.to_datetime(max_time).to_pydatetime()
    # Approximate 730 trading days with 1.5x calendar days to cover weekends/holidays
    start_ts = end_ts - timedelta(days=int(DEFAULT_LOOKBACK_TRADING_DAYS * 1.5))
    return start_ts, end_ts


def _cache_path(cache_dir: Path, symbols: Sequence[str], start: datetime | None, end: datetime | None) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = f"{','.join(sorted(symbols))}|{start}|{end}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return cache_dir / f"ohlcv_{digest}.parquet"


def load_ohlcv(
    symbols: Sequence[str],
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    *,
    cache_dir: Path | str | None = None,
    database_url: str | None = None,
) -> pd.DataFrame:
    """
    Load OHLCV rows for the requested symbols/date range.

    - Reads from Postgres/Timescale table `ohlcv_daily`.
    - Default range: last ~730 trading days based on table max date.
    - Caches parquet under `research/wyckoff_bench/outputs/cache/`.
    """
    if not symbols:
        raise ValueError("At least one symbol is required.")

    cache_dir_path = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    engine = _make_engine(database_url)

    start_ts = _parse_date(start)
    end_ts = _parse_date(end)
    if start_ts is None or end_ts is None:
        derived_start, derived_end = _default_range(engine)
        start_ts = start_ts or derived_start
        end_ts = end_ts or derived_end

    cache_path = _cache_path(cache_dir_path, symbols, start_ts, end_ts)
    if cache_path.exists():
        try:
            return pd.read_parquet(cache_path)
        except Exception:
            cache_path.unlink(missing_ok=True)

    # Research loader joins Massive daily aggregates via ticker_id → tickers.symbol.
    query = sa.text(
        """
        SELECT
          o.date AS time,
          o.open,
          o.high,
          o.low,
          o.close,
          o.volume,
          t.symbol AS symbol
        FROM ohlcv o
        JOIN tickers t ON o.ticker_id = t.id
        WHERE t.symbol IN :symbols
          AND (:start IS NULL OR o.date >= :start)
          AND (:end IS NULL OR o.date <= :end)
        ORDER BY t.symbol, o.date
        """
    ).bindparams(sa.bindparam("symbols", expanding=True))

    params = {"symbols": tuple(symbols), "start": start_ts, "end": end_ts}
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty:
        cache_path.touch()
        return df

    df["time"] = pd.to_datetime(df["time"])
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)
    df.to_parquet(cache_path, index=False)
    return df
