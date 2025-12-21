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
        tickers = [
            _seed_ticker_and_ohlcv(conn, symbol="AAPL", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="MSFT", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="NVDA", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="TSLA", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="XOM", start=date(2025, 11, 1), days=40),
        ]

        run_a2_local_ta_job(conn, snapshot_dates=[snapshot_date], ticker_chunk_size=2)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_snapshots")
            assert int(cur.fetchone()[0]) == len(tickers)

            cur.execute(
                """
                SELECT ticker_id::text,
                       time::date,
                       technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE time::date = %s
                ORDER BY ticker_id
                """,
                (snapshot_date,),
            )
            rows_a = cur.fetchall()

        assert len(rows_a) == len(tickers)
        for ticker_id, row_date, tech_text_a, price_text_a in rows_a:
            assert row_date == snapshot_date
            tech_a = json.loads(tech_text_a)
            price_a = json.loads(price_text_a)

            assert set(price_a.keys()) == {"rvol", "vsi", "hv"}
            assert "trend" in tech_a and "sma" in tech_a["trend"]
            assert all(k in tech_a["trend"]["sma"] for k in ("sma_14", "sma_20", "sma_50", "sma_200"))
            assert "pattern_recognition" in tech_a

        # Rerun with different chunk size; results must be identical for a deterministic sample.
        run_a2_local_ta_job(conn, snapshot_dates=[snapshot_date], ticker_chunk_size=3)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_snapshots")
            assert int(cur.fetchone()[0]) == len(tickers)

            cur.execute(
                """
                SELECT ticker_id::text,
                       technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE time::date = %s
                ORDER BY ticker_id
                """,
                (snapshot_date,),
            )
            rows_b = cur.fetchall()

        a_map = {tid: (tech, price) for (tid, _, tech, price) in rows_a}
        b_map = {tid: (tech, price) for (tid, tech, price) in rows_b}

        # Deterministic sample comparison (not all tickers).
        for tid in sorted(tickers)[:3]:
            tech_a, price_a = a_map[tid]
            tech_b, price_b = b_map[tid]
            assert json.loads(tech_b) == json.loads(tech_a)
            assert json.loads(price_b) == json.loads(price_a)


@pytest.mark.integration
@pytest.mark.db
def test_a2_job_parallel_workers_produce_identical_json() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")
    if os.getenv("KAPMAN_RUN_A2_PARALLEL_TEST") not in {"1", "true", "TRUE", "yes", "YES"}:
        pytest.skip("Set KAPMAN_RUN_A2_PARALLEL_TEST=1 to enable multiprocessing integration test")

    reset_and_migrate(db_url, default_migrations_dir())

    snapshot_date = date(2025, 12, 5)
    with psycopg2.connect(db_url) as conn:
        tickers = [
            _seed_ticker_and_ohlcv(conn, symbol="AAPL", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="MSFT", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="NVDA", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="TSLA", start=date(2025, 11, 1), days=40),
            _seed_ticker_and_ohlcv(conn, symbol="XOM", start=date(2025, 11, 1), days=40),
        ]

        run_a2_local_ta_job(conn, snapshot_dates=[snapshot_date], ticker_chunk_size=1, workers=1)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker_id::text,
                       technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE time::date = %s
                ORDER BY ticker_id
                """,
                (snapshot_date,),
            )
            rows_a = cur.fetchall()

        run_a2_local_ta_job(
            conn,
            snapshot_dates=[snapshot_date],
            ticker_chunk_size=1,
            workers=4,
            db_url=db_url,
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker_id::text,
                       technical_indicators_json::text,
                       price_metrics_json::text
                FROM daily_snapshots
                WHERE time::date = %s
                ORDER BY ticker_id
                """,
                (snapshot_date,),
            )
            rows_b = cur.fetchall()

        a_map = {tid: (tech, price) for (tid, tech, price) in rows_a}
        b_map = {tid: (tech, price) for (tid, tech, price) in rows_b}

        for tid in sorted(tickers):
            tech_a, price_a = a_map[tid]
            tech_b, price_b = b_map[tid]
            assert json.loads(tech_b) == json.loads(tech_a)
            assert json.loads(price_b) == json.loads(price_a)
