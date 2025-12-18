from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from .parser import OhlcvRow


def _normalize_psycopg2_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    if "+" in parsed.scheme:
        parsed = parsed._replace(scheme=parsed.scheme.split("+", 1)[0])
    return urlunparse(parsed)


def default_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url


def connect(db_url: str):
    return psycopg2.connect(_normalize_psycopg2_url(db_url))


def load_symbol_map(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id::text, symbol FROM tickers ORDER BY symbol")
        rows = cur.fetchall()
    return {symbol.upper(): ticker_id for (ticker_id, symbol) in rows}


def count_table(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
        return int(cur.fetchone()[0])


def count_ohlcv_for_date(conn, d: date) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ohlcv_daily WHERE date = %s", (d,))
        return int(cur.fetchone()[0])


def count_ohlcv_in_range(conn, start: date, end: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM ohlcv_daily WHERE date >= %s AND date <= %s",
            (start, end),
        )
        return int(cur.fetchone()[0])


@dataclass(frozen=True)
class UpsertResult:
    inserted_or_updated: int


def upsert_ohlcv_rows(conn, rows: list[OhlcvRow], *, batch_size: int = 5000) -> UpsertResult:
    if not rows:
        return UpsertResult(inserted_or_updated=0)

    insert_sql = """
        INSERT INTO ohlcv_daily (ticker_id, date, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker_id, date) DO UPDATE
        SET open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        WHERE (ohlcv_daily.open, ohlcv_daily.high, ohlcv_daily.low, ohlcv_daily.close, ohlcv_daily.volume)
              IS DISTINCT FROM
              (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close, EXCLUDED.volume)
    """

    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            values = [
                (r.ticker_id, r.date, r.open, r.high, r.low, r.close, r.volume) for r in batch
            ]
            execute_values(cur, insert_sql, values, page_size=len(values))
            total += len(values)
    conn.commit()
    return UpsertResult(inserted_or_updated=total)
