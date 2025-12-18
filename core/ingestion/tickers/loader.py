from __future__ import annotations

import os
from dataclasses import dataclass

from core.ingestion.ohlcv import db as ohlcv_db

from . import db as tickers_db
from .polygon_reference import PolygonReferenceError, PolygonTicker, fetch_all_active_tickers


class TickerBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnsureUniverseResult:
    fetched: int
    upserted: int
    final_count: int


def ensure_universe_loaded(
    conn,
    *,
    api_key: str | None = None,
    force: bool = False,
) -> EnsureUniverseResult:
    api_key = api_key or os.environ.get("POLYGON_API_KEY")
    if not api_key:
        raise TickerBootstrapError("POLYGON_API_KEY is not set")

    current = ohlcv_db.count_table(conn, "tickers")
    if current > 0 and not force:
        return EnsureUniverseResult(fetched=0, upserted=0, final_count=current)

    try:
        tickers: list[PolygonTicker] = fetch_all_active_tickers(api_key=api_key)
    except PolygonReferenceError as exc:
        raise TickerBootstrapError(str(exc)) from exc

    result = tickers_db.upsert_tickers(conn, tickers)
    final_count = ohlcv_db.count_table(conn, "tickers")
    return EnsureUniverseResult(fetched=len(tickers), upserted=result.rows_upserted, final_count=final_count)

