from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.b2_wyckoff_structural_events_job import MODEL_VERSION, run_wyckoff_structural_events_job


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _snapshot_time_for_date(snapshot_date: date) -> datetime:
    return datetime(
        snapshot_date.year,
        snapshot_date.month,
        snapshot_date.day,
        23,
        59,
        59,
        999999,
        tzinfo=timezone.utc,
    )


def _insert_ticker(conn, symbol: str) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", (symbol,))
        ticker_id = cur.fetchone()[0]
    conn.commit()
    return ticker_id


def _seed_watchlist(conn, symbols: list[str], snapshot_date: date) -> None:
    with conn.cursor() as cur:
        for symbol in symbols:
            cur.execute(
                """
                INSERT INTO watchlists (watchlist_id, symbol, active, source, effective_date)
                VALUES (%s, %s, TRUE, %s, %s)
                """,
                ("b2_test", symbol, "integration", snapshot_date),
            )
    conn.commit()


def _seed_snapshot_row(conn, *, ticker_id: str, snapshot_date: date) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (time, ticker_id, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (time, ticker_id) DO NOTHING
            """,
            (
                _snapshot_time_for_date(snapshot_date),
                ticker_id,
                _snapshot_time_for_date(snapshot_date),
            ),
        )
    conn.commit()


def _seed_ohlcv(conn, *, ticker_id: str, start_date: date, days: int) -> None:
    rows: list[tuple] = []
    for offset in range(days):
        trading_date = start_date + timedelta(days=offset)
        rows.append(
            (
                ticker_id,
                trading_date,
                100 + offset,
                101 + offset,
                99 + offset,
                100.5 + offset,
                1_000_000 + offset,
                _snapshot_time_for_date(trading_date),
            )
        )

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    conn.commit()


def _count_b2_rows(conn, *, ticker_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM daily_snapshots
            WHERE ticker_id = %s
              AND model_version = %s
            """,
            (ticker_id, MODEL_VERSION),
        )
        return int(cur.fetchone()[0])


def _count_snapshot_rows_on_date(conn, *, ticker_id: str, snapshot_date: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM daily_snapshots
            WHERE ticker_id = %s
              AND (time AT TIME ZONE 'America/New_York')::date = %s
            """,
            (ticker_id, snapshot_date),
        )
        return int(cur.fetchone()[0])


@pytest.mark.integration
@pytest.mark.db
def test_b2_full_history_watchlist_rerun_succeeds_for_mixed_history_symbols() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    start = date(2025, 1, 1)
    second = date(2025, 1, 2)
    third = date(2025, 1, 3)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        ticker_b = _insert_ticker(conn, "MSFT")
        _seed_watchlist(conn, ["AAPL", "MSFT"], start)

        _seed_ohlcv(conn, ticker_id=ticker_a, start_date=start - timedelta(days=80), days=90)
        _seed_ohlcv(conn, ticker_id=ticker_b, start_date=start - timedelta(days=80), days=90)

        for snapshot_date in (start, second, third):
            _seed_snapshot_row(conn, ticker_id=ticker_a, snapshot_date=snapshot_date)
        for snapshot_date in (second, third):
            _seed_snapshot_row(conn, ticker_id=ticker_b, snapshot_date=snapshot_date)

        stats = run_wyckoff_structural_events_job(conn, use_watchlist=True)

        assert stats["errors"] == 0
        assert stats["missing_history"] == 0
        assert stats["processed"] == 2
        assert stats["snapshots_written"] == 5
        assert _count_b2_rows(conn, ticker_id=ticker_a) == 3
        assert _count_b2_rows(conn, ticker_id=ticker_b) == 2
        assert _count_snapshot_rows_on_date(conn, ticker_id=ticker_b, snapshot_date=start) == 0


@pytest.mark.integration
@pytest.mark.db
def test_b2_skips_symbol_with_no_snapshot_rows_without_aborting_peer() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    start = date(2025, 2, 3)
    second = date(2025, 2, 4)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        ticker_b = _insert_ticker(conn, "MSFT")

        _seed_ohlcv(conn, ticker_id=ticker_a, start_date=start - timedelta(days=80), days=90)
        _seed_ohlcv(conn, ticker_id=ticker_b, start_date=start - timedelta(days=80), days=90)

        _seed_snapshot_row(conn, ticker_id=ticker_a, snapshot_date=start)
        _seed_snapshot_row(conn, ticker_id=ticker_a, snapshot_date=second)

        stats = run_wyckoff_structural_events_job(conn, symbols=["AAPL", "MSFT"])

        assert stats["errors"] == 0
        assert stats["missing_history"] == 1
        assert stats["processed"] == 1
        assert stats["snapshots_written"] == 2
        assert _count_b2_rows(conn, ticker_id=ticker_a) == 2
        assert _count_b2_rows(conn, ticker_id=ticker_b) == 0
