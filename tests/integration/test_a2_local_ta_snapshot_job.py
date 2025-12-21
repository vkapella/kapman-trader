from __future__ import annotations

import json
import os
from datetime import date, timedelta
from decimal import Decimal

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.ohlcv.db import upsert_ohlcv_rows
from core.ingestion.ohlcv.parser import OhlcvRow
from core.metrics.a2_local_ta_job import run_a2_local_ta_job


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _seed_ticker_and_ohlcv(conn, *, symbol: str, start: date, days: int) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
    conn.commit()

    rows: list[OhlcvRow] = []
    for i in range(days):
        d = start + timedelta(days=i)
        price = Decimal("100.0") + Decimal(i)
        rows.append(
            OhlcvRow(
                ticker_id=ticker_id,
                date=d,
                open=price,
                high=price + Decimal("1.0"),
                low=price - Decimal("1.0"),
                close=price + Decimal("0.5"),
                volume=1_000_000 + i * 10_000,
            )
        )

    upsert_ohlcv_rows(conn, rows)
    return ticker_id


@pytest.mark.integration
@pytest.mark.db
def test_a2_job_writes_snapshot_and_is_idempotent() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_date = date(2025, 12, 5)
    with psycopg2.connect(db_url) as conn:
        ticker_id = _seed_ticker_and_ohlcv(conn, symbol="AAPL", start=date(2025, 11, 1), days=40)

        run_a2_local_ta_job(conn, snapshot_dates=[snapshot_date])

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_snapshots")
            assert int(cur.fetchone()[0]) == 1

            cur.execute(
                """
                SELECT time::date,
                       technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE ticker_id = %s
                """,
                (ticker_id,),
            )
            row_date, tech_text_a, price_text_a = cur.fetchone()

        assert row_date == snapshot_date

        tech_a = json.loads(tech_text_a)
        price_a = json.loads(price_text_a)

        assert set(price_a.keys()) == {"rvol", "vsi", "hv"}
        assert "trend" in tech_a and "sma" in tech_a["trend"]
        assert all(k in tech_a["trend"]["sma"] for k in ("sma_14", "sma_20", "sma_50", "sma_200"))
        assert "pattern_recognition" in tech_a

        run_a2_local_ta_job(conn, snapshot_dates=[snapshot_date])

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_snapshots")
            assert int(cur.fetchone()[0]) == 1

            cur.execute(
                """
                SELECT technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE ticker_id = %s AND time::date = %s
                """,
                (ticker_id, snapshot_date),
            )
            tech_text_b, price_text_b = cur.fetchone()

        tech_b = json.loads(tech_text_b)
        price_b = json.loads(price_text_b)

        assert tech_b == tech_a
        assert price_b == price_a

