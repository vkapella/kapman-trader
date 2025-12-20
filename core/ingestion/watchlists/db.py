from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2.extras import execute_values


def _normalize_psycopg2_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    if "+" in parsed.scheme:
        parsed = parsed._replace(scheme=parsed.scheme.split("+", 1)[0])
    return urlunparse(parsed)


def connect(db_url: str):
    return psycopg2.connect(_normalize_psycopg2_url(db_url))


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


def fetch_memberships(conn, watchlist_id: str) -> dict[str, bool]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, active FROM watchlists WHERE watchlist_id = %s",
            (watchlist_id,),
        )
        rows = cur.fetchall()
    return {symbol.upper(): bool(active) for (symbol, active) in rows}


@dataclass(frozen=True)
class ReconcileDbResult:
    symbols_inserted: list[str]
    symbols_reactivated: list[str]
    symbols_deactivated: list[str]
    active_total: int


def upsert_active_symbols(
    conn,
    *,
    watchlist_id: str,
    symbols: Iterable[str],
    source: str,
    effective_date: date,
) -> None:
    symbols = list(symbols)
    if not symbols:
        return

    insert_sql = """
        INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
        VALUES %s
        ON CONFLICT (watchlist_id, symbol) DO UPDATE SET
            active = EXCLUDED.active,
            source = EXCLUDED.source,
            effective_date = EXCLUDED.effective_date,
            updated_at = NOW()
        WHERE watchlists.active IS DISTINCT FROM EXCLUDED.active
           OR watchlists.source IS DISTINCT FROM EXCLUDED.source
           OR watchlists.effective_date IS DISTINCT FROM EXCLUDED.effective_date
    """
    values = [(watchlist_id, sym.upper(), True, source, effective_date) for sym in symbols]
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values, page_size=len(values))
    conn.commit()


def deactivate_symbols(
    conn,
    *,
    watchlist_id: str,
    symbols: Iterable[str],
    effective_date: date,
) -> int:
    symbols = [s.upper() for s in symbols]
    if not symbols:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE watchlists
            SET active = FALSE,
                updated_at = NOW(),
                effective_date = %s
            WHERE watchlist_id = %s
              AND symbol = ANY(%s)
              AND active = TRUE
            """,
            (effective_date, watchlist_id, symbols),
        )
        updated = int(cur.rowcount)
    conn.commit()
    return updated


def count_active(conn, watchlist_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM watchlists WHERE watchlist_id = %s AND active = TRUE",
            (watchlist_id,),
        )
        return int(cur.fetchone()[0])
