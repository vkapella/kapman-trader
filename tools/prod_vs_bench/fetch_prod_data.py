from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

import pandas as pd
import psycopg2

from core.ingestion.ohlcv import db as ohlcv_db


@dataclass
class ProdData:
    ohlcv: pd.DataFrame
    snapshots: pd.DataFrame


def _normalize_symbols(symbols: Optional[Iterable[str]]) -> List[str]:
    if not symbols:
        return []
    normalized = sorted({str(sym).strip().upper() for sym in symbols if str(sym).strip()})
    return normalized


def _build_date_clause(start_date: Optional[date], end_date: Optional[date]) -> tuple[str, list]:
    clauses = []
    params: list = []
    if start_date:
        clauses.append("date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("date <= %s")
        params.append(end_date)
    if not clauses:
        return "TRUE", params
    return " AND ".join(clauses), params


def _build_snapshot_date_clause(start_date: Optional[date], end_date: Optional[date]) -> tuple[str, list]:
    clauses = []
    params: list = []
    if start_date:
        clauses.append("ds.time::date >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("ds.time::date <= %s")
        params.append(end_date)
    if not clauses:
        return "TRUE", params
    return " AND ".join(clauses), params


def fetch_prod_data(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    symbols: Optional[Iterable[str]] = None,
    db_url: Optional[str] = None,
) -> ProdData:
    db_url = db_url or ohlcv_db.default_db_url()
    normalized_symbols = _normalize_symbols(symbols)

    ohlcv_columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    snapshot_columns = [
        "symbol",
        "date",
        "events_detected",
        "primary_event",
        "events_json",
        "wyckoff_regime",
    ]

    with psycopg2.connect(db_url) as conn:
        ohlcv_clause, ohlcv_params = _build_date_clause(start_date, end_date)
        if normalized_symbols:
            symbol_clause = "UPPER(t.symbol) = ANY(%s)"
            ohlcv_params = [normalized_symbols] + ohlcv_params
        else:
            symbol_clause = "t.is_active = TRUE"

        ohlcv_sql = f"""
            SELECT UPPER(t.symbol) AS symbol,
                   o.date,
                   o.open,
                   o.high,
                   o.low,
                   o.close,
                   o.volume
            FROM ohlcv o
            JOIN tickers t ON o.ticker_id = t.id
            WHERE {symbol_clause} AND {ohlcv_clause}
            ORDER BY UPPER(t.symbol), o.date
        """
        with conn.cursor() as cur:
            cur.execute(ohlcv_sql, ohlcv_params)
            ohlcv_rows = cur.fetchall()

        snapshot_clause, snapshot_params = _build_snapshot_date_clause(start_date, end_date)
        if normalized_symbols:
            snapshot_symbol_clause = "UPPER(t.symbol) = ANY(%s)"
            snapshot_params = [normalized_symbols] + snapshot_params
        else:
            snapshot_symbol_clause = "t.is_active = TRUE"

        snapshot_sql = f"""
            SELECT UPPER(t.symbol) AS symbol,
                   ds.time::date AS date,
                   ds.events_detected,
                   ds.primary_event,
                   ds.events_json,
                   ds.wyckoff_regime
            FROM daily_snapshots ds
            JOIN tickers t ON ds.ticker_id = t.id
            WHERE {snapshot_symbol_clause} AND {snapshot_clause}
            ORDER BY UPPER(t.symbol), ds.time::date
        """
        with conn.cursor() as cur:
            cur.execute(snapshot_sql, snapshot_params)
            snapshot_rows = cur.fetchall()

    ohlcv_df = pd.DataFrame(ohlcv_rows, columns=ohlcv_columns)
    snapshots_df = pd.DataFrame(snapshot_rows, columns=snapshot_columns)
    return ProdData(ohlcv=ohlcv_df, snapshots=snapshots_df)
