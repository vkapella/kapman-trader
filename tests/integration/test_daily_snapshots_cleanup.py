from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import psycopg2
import pytest
from psycopg2.extras import Json

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.metrics.daily_snapshots_cleanup import cleanup_split_daily_snapshots


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _canonical_time(snapshot_date: date) -> datetime:
    return datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


def _split_time(snapshot_date: date) -> datetime:
    next_day = snapshot_date + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, 4, 59, 59, 999999, tzinfo=timezone.utc)


@pytest.mark.integration
@pytest.mark.db
def test_cleanup_split_daily_snapshots_moves_payload_and_deletes_duplicate() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())
    snapshot_date = date(2025, 12, 5)

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tickers (symbol) VALUES (%s) RETURNING id::text", ("AAPL",))
            ticker_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO daily_snapshots (time, ticker_id, technical_indicators_json, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    _canonical_time(snapshot_date),
                    ticker_id,
                    Json({"adx": 25}),
                    _canonical_time(snapshot_date),
                ),
            )
            cur.execute(
                """
                INSERT INTO daily_snapshots (time, ticker_id, dealer_metrics_json, model_version, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    _split_time(snapshot_date),
                    ticker_id,
                    Json({"spot_price": 185.5}),
                    "A3-dealer-metrics-v2",
                    _split_time(snapshot_date),
                ),
            )
        conn.commit()

        dry_run = cleanup_split_daily_snapshots(conn, start_date=snapshot_date, end_date=snapshot_date, apply=False)
        assert dry_run.split_rows == 1
        assert dry_run.split_rows_with_canonical == 1
        assert dry_run.canonical_rows_missing_dealer_metrics == 1

        applied = cleanup_split_daily_snapshots(conn, start_date=snapshot_date, end_date=snapshot_date, apply=True)
        assert applied.canonical_rows_updated == 1
        assert applied.split_rows_deleted == 1

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT time, dealer_metrics_json, technical_indicators_json
                FROM daily_snapshots
                WHERE ticker_id = %s
                ORDER BY time ASC
                """,
                (ticker_id,),
            )
            rows = cur.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == _canonical_time(snapshot_date)
    assert rows[0][1]["spot_price"] == 185.5
    assert rows[0][2]["adx"] == 25
