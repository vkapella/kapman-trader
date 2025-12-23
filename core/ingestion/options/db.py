from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


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


def _lock_key(name: str) -> int:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def options_ingest_lock_key() -> int:
    return _lock_key("kapman:options_chains:ingest")


def try_advisory_lock(conn, key: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_try_advisory_lock(%s::int4, %s::int4)",
            ((key >> 32) & 0x7FFFFFFF, key & 0x7FFFFFFF),
        )
        return bool(cur.fetchone()[0])


def advisory_unlock(conn, key: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_unlock(%s::int4, %s::int4)",
            ((key >> 32) & 0x7FFFFFFF, key & 0x7FFFFFFF),
        )
    conn.commit()


def fetch_active_watchlist_symbols(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT symbol FROM watchlists WHERE active = TRUE ORDER BY symbol"
        )
        rows = cur.fetchall()
    return [str(r[0]).upper() for r in rows]


def fetch_ticker_ids(conn, symbols: Iterable[str]) -> dict[str, str]:
    syms = sorted({s.upper() for s in symbols})
    if not syms:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, id::text FROM tickers WHERE symbol = ANY(%s) ORDER BY symbol",
            (syms,),
        )
        rows = cur.fetchall()
    return {str(symbol).upper(): str(ticker_id) for (symbol, ticker_id) in rows}


def fetch_latest_snapshot_time(conn, *, ticker_id: str) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(time) FROM options_chains WHERE ticker_id = %s", (ticker_id,))
        row = cur.fetchone()
    return row[0] if row else None


def fetch_contract_keys_at_snapshot(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
) -> set[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT expiration_date, strike_price, option_type
            FROM options_chains
            WHERE ticker_id = %s AND time = %s
            """,
            (ticker_id, snapshot_time),
        )
        rows = cur.fetchall()
    keys: set[tuple] = set()
    for exp, strike_raw, opt_type in rows:
        strike = Decimal(str(strike_raw)).quantize(Decimal("0.0001"))
        keys.add((exp, strike, str(opt_type)))
    return keys


def has_snapshot_rows(
    conn,
    *,
    ticker_id: str,
    snapshot_time: datetime,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM options_chains WHERE ticker_id = %s AND time = %s LIMIT 1",
            (ticker_id, snapshot_time),
        )
        return cur.fetchone() is not None


@dataclass(frozen=True)
class UpsertOptionsResult:
    rows_written: int


def upsert_options_chains_rows(
    conn,
    *,
    rows: list[dict],
    batch_size: int = 2000,
) -> UpsertOptionsResult:
    if not rows:
        return UpsertOptionsResult(rows_written=0)

    insert_sql = """
        INSERT INTO options_chains (
            time,
            ticker_id,
            expiration_date,
            strike_price,
            option_type,
            bid,
            ask,
            last,
            volume,
            open_interest,
            implied_volatility,
            delta,
            gamma,
            theta,
            vega
        )
        VALUES %s
        ON CONFLICT (time, ticker_id, expiration_date, strike_price, option_type)
        DO UPDATE SET
            bid = EXCLUDED.bid,
            ask = EXCLUDED.ask,
            last = EXCLUDED.last,
            volume = EXCLUDED.volume,
            open_interest = EXCLUDED.open_interest,
            implied_volatility = EXCLUDED.implied_volatility,
            delta = EXCLUDED.delta,
            gamma = EXCLUDED.gamma,
            theta = EXCLUDED.theta,
            vega = EXCLUDED.vega
        WHERE (options_chains.bid, options_chains.ask, options_chains.last, options_chains.volume,
               options_chains.open_interest, options_chains.implied_volatility, options_chains.delta,
               options_chains.gamma, options_chains.theta, options_chains.vega)
              IS DISTINCT FROM
              (EXCLUDED.bid, EXCLUDED.ask, EXCLUDED.last, EXCLUDED.volume,
               EXCLUDED.open_interest, EXCLUDED.implied_volatility, EXCLUDED.delta,
               EXCLUDED.gamma, EXCLUDED.theta, EXCLUDED.vega)
    """

    values = [
        (
            r["time"],
            r["ticker_id"],
            r["expiration_date"],
            r["strike_price"],
            r["option_type"],
            r.get("bid"),
            r.get("ask"),
            r.get("last"),
            r.get("volume"),
            r.get("open_interest"),
            r.get("implied_volatility"),
            r.get("delta"),
            r.get("gamma"),
            r.get("theta"),
            r.get("vega"),
        )
        for r in rows
    ]

    total = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(values), batch_size):
                batch = values[i : i + batch_size]
                execute_values(cur, insert_sql, batch, page_size=len(batch))
                total += len(batch)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Options ingestion DB commit failed")
        raise
    return UpsertOptionsResult(rows_written=total)
