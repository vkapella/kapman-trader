from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import pandas as pd
import sqlalchemy as sa

logger = logging.getLogger(__name__)

WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "data" / "watchlist_105.txt"


def _read_watchlist(path: Path = WATCHLIST_PATH) -> List[str]:
    """Load symbols from the research watchlist, preserving file order."""
    if not path.exists():
        raise FileNotFoundError(f"Watchlist not found: {path}")
    symbols: List[str] = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            sym = line.strip().upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            symbols.append(sym)
    if not symbols:
        raise RuntimeError(f"No symbols parsed from watchlist: {path}")
    return symbols


def _make_engine() -> sa.Engine:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to load OHLCV data.")
    return sa.create_engine(url)


def _lookup_date_bounds(engine: sa.Engine) -> tuple[datetime, datetime]:
    """Use the latest available date as the anchor, limiting to ~2 years."""
    with engine.connect() as conn:
        max_date = conn.execute(sa.text("SELECT max(date) FROM ohlcv")).scalar()
    if not max_date:
        raise RuntimeError("Could not determine max(date) from ohlcv; table may be empty.")
    end_ts = pd.to_datetime(max_date)
    start_ts = end_ts - pd.DateOffset(years=2)
    return start_ts.to_pydatetime(), end_ts.to_pydatetime()


def load_ohlcv(
    symbols: Sequence[str] | None = None,
    *,
    engine: sa.Engine | None = None,
    watchlist_path: Path | None = None,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
    min_days: int | None = None,
) -> Dict[str, pd.DataFrame]:
    """
    Load daily OHLCV for the requested symbols (or watchlist) directly from Postgres.

    Returns:
        dict[symbol, DataFrame] with ascending dates and no caching.
    """
    engine = engine or _make_engine()
    wl_path = watchlist_path or WATCHLIST_PATH
    if symbols is None:
        symbols = _read_watchlist(wl_path)
    symbols = [s.upper() for s in symbols]
    if not symbols:
        logger.warning("No symbols provided to load_ohlcv.")
        return {}

    start_ts, end_ts = (
        _lookup_date_bounds(engine) if start_ts is None or end_ts is None else (start_ts, end_ts)
    )

    query = (
        sa.text(
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
              AND o.date >= :start
              AND o.date <= :end
            ORDER BY t.symbol, o.date
            """
        ).bindparams(sa.bindparam("symbols", expanding=True))
    )

    params = {"symbols": tuple(symbols), "start": start_ts, "end": end_ts}
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty:
        logger.warning("No OHLCV rows loaded for %s symbols.", len(symbols))
        return {}

    df["time"] = pd.to_datetime(df["time"])
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["symbol", "time"]).reset_index(drop=True)

    ohlcv_map: Dict[str, pd.DataFrame] = {}
    for sym, df_sym in df.groupby("symbol"):
        if min_days is not None and len(df_sym) < min_days:
            continue
        df_sym = df_sym.reset_index(drop=True)
        ohlcv_map[sym] = df_sym
        min_dt = df_sym["time"].min()
        max_dt = df_sym["time"].max()
        logger.info(
            "Loaded %s rows for %s (%s → %s)",
            len(df_sym),
            sym,
            min_dt.date() if isinstance(min_dt, pd.Timestamp) else min_dt,
            max_dt.date() if isinstance(max_dt, pd.Timestamp) else max_dt,
        )

    logger.info("Loaded OHLCV for %s symbols (requested=%s).", len(ohlcv_map), len(symbols))
    return ohlcv_map


__all__ = ["load_ohlcv", "_make_engine", "_lookup_date_bounds", "_read_watchlist"]
