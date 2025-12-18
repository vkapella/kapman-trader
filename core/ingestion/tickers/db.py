from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extras import execute_values

from .polygon_reference import PolygonTicker


@dataclass(frozen=True)
class UpsertTickersResult:
    rows_upserted: int


def upsert_tickers(conn, tickers: list[PolygonTicker], *, batch_size: int = 5000) -> UpsertTickersResult:
    if not tickers:
        return UpsertTickersResult(rows_upserted=0)

    insert_sql = """
        INSERT INTO tickers (symbol, name, is_active)
        VALUES %s
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            is_active = EXCLUDED.is_active
    """

    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            values = [
                (t.symbol, t.name, t.is_active) for t in batch
            ]
            execute_values(cur, insert_sql, values, page_size=len(values))
            total += len(values)
    conn.commit()
    return UpsertTickersResult(rows_upserted=total)
