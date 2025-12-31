from __future__ import annotations

import os
from datetime import date, datetime, timezone

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.b1_wyckoff_regime_job import (
    REGIME_MARKDOWN,
    REGIME_MARKUP,
    REGIME_UNKNOWN,
    run_wyckoff_regime_job,
)


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
                ("b1_test", symbol, "integration", snapshot_date),
            )
    conn.commit()


def _seed_ohlcv(conn, *, ticker_id: str, snapshot_date: date) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ticker_id,
                snapshot_date,
                100,
                105,
                95,
                102,
                1_000_000,
                _snapshot_time_for_date(snapshot_date),
            ),
        )
    conn.commit()


def _seed_events(
    conn,
    *,
    ticker_id: str,
    snapshot_date: date,
    events: list[str] | None,
    primary_event: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO daily_snapshots (time, ticker_id, events_detected, primary_event, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (time, ticker_id) DO NOTHING
            """,
            (
                _snapshot_time_for_date(snapshot_date),
                ticker_id,
                events,
                primary_event,
                _snapshot_time_for_date(snapshot_date),
            ),
        )
    conn.commit()


def _fetch_regimes(conn, ticker_id: str) -> dict[date, str | None]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT time::date, wyckoff_regime
            FROM daily_snapshots
            WHERE ticker_id = %s
            ORDER BY time ASC
            """,
            (ticker_id,),
        )
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


@pytest.mark.integration
@pytest.mark.db
def test_b1_all_ticker_execution_path() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    snapshot_date = date(2025, 12, 1)
    next_date = date(2025, 12, 2)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        ticker_b = _insert_ticker(conn, "MSFT")

        for d in (snapshot_date, next_date):
            _seed_ohlcv(conn, ticker_id=ticker_a, snapshot_date=d)
            _seed_ohlcv(conn, ticker_id=ticker_b, snapshot_date=d)

        _seed_events(conn, ticker_id=ticker_a, snapshot_date=snapshot_date, events=["SOS"], primary_event="SOS")
        _seed_events(conn, ticker_id=ticker_b, snapshot_date=snapshot_date, events=["SOW"], primary_event="SOW")

        run_wyckoff_regime_job(conn)

        regimes_a = _fetch_regimes(conn, ticker_a)
        regimes_b = _fetch_regimes(conn, ticker_b)

        assert regimes_a[snapshot_date] == REGIME_MARKUP
        assert regimes_a[next_date] == REGIME_MARKUP
        assert regimes_b[snapshot_date] == REGIME_MARKDOWN
        assert regimes_b[next_date] == REGIME_MARKDOWN


@pytest.mark.integration
@pytest.mark.db
def test_b1_watchlist_scoping() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    snapshot_date = date(2025, 12, 3)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        ticker_b = _insert_ticker(conn, "MSFT")
        _seed_watchlist(conn, ["AAPL"], snapshot_date)

        _seed_ohlcv(conn, ticker_id=ticker_a, snapshot_date=snapshot_date)
        _seed_ohlcv(conn, ticker_id=ticker_b, snapshot_date=snapshot_date)
        _seed_events(conn, ticker_id=ticker_a, snapshot_date=snapshot_date, events=["SOS"], primary_event="SOS")

        run_wyckoff_regime_job(conn, use_watchlist=True)

        regimes_a = _fetch_regimes(conn, ticker_a)
        regimes_b = _fetch_regimes(conn, ticker_b)
        assert regimes_a[snapshot_date] == REGIME_MARKUP
        assert snapshot_date not in regimes_b or regimes_b[snapshot_date] is None


@pytest.mark.integration
@pytest.mark.db
def test_b1_symbols_scoping_and_logging(caplog) -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    snapshot_date = date(2025, 12, 4)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        _seed_ohlcv(conn, ticker_id=ticker_a, snapshot_date=snapshot_date)
        _seed_events(conn, ticker_id=ticker_a, snapshot_date=snapshot_date, events=["SOS"], primary_event="SOS")

        with caplog.at_level("INFO"):
            run_wyckoff_regime_job(conn, symbols=["AAPL", "MISSING"], heartbeat_every=1, verbose=True)

        regimes_a = _fetch_regimes(conn, ticker_a)
        assert regimes_a[snapshot_date] == REGIME_MARKUP

        assert any("Symbols missing ticker_id" in record.message for record in caplog.records)
        assert any("Heartbeat" in record.message for record in caplog.records)
        assert any("Processing AAPL" in record.message for record in caplog.records)


@pytest.mark.integration
@pytest.mark.db
def test_b1_non_regime_events_default_unknown() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    snapshot_date = date(2025, 12, 5)

    with psycopg2.connect(db_url) as conn:
        ticker_a = _insert_ticker(conn, "AAPL")
        _seed_ohlcv(conn, ticker_id=ticker_a, snapshot_date=snapshot_date)
        _seed_events(conn, ticker_id=ticker_a, snapshot_date=snapshot_date, events=["SC"], primary_event="SC")

        run_wyckoff_regime_job(conn)

        regimes = _fetch_regimes(conn, ticker_a)
        assert regimes[snapshot_date] == REGIME_UNKNOWN
