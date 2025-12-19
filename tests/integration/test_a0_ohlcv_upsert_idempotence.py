from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.ohlcv.db import upsert_ohlcv_rows
from core.ingestion.ohlcv.parser import OhlcvRow


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.db
def test_a0_upsert_is_idempotent() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tickers (symbol) VALUES ('AAPL') RETURNING id::text")
            ticker_id = cur.fetchone()[0]
        conn.commit()

        rows = [
            OhlcvRow(
                ticker_id=ticker_id,
                date=date(2025, 12, 5),
                open=Decimal("150.0"),
                high=Decimal("153.0"),
                low=Decimal("149.5"),
                close=Decimal("152.0"),
                volume=100,
            )
        ]

        upsert_ohlcv_rows(conn, rows)
        upsert_ohlcv_rows(conn, rows)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ohlcv")
            assert int(cur.fetchone()[0]) == 1

            cur.execute(
                "SELECT open, high, low, close, volume FROM ohlcv WHERE ticker_id = %s AND date = %s",
                (ticker_id, date(2025, 12, 5)),
            )
            open_, high_, low_, close_, volume = cur.fetchone()

        assert open_ == Decimal("150.0")
        assert high_ == Decimal("153.0")
        assert low_ == Decimal("149.5")
        assert close_ == Decimal("152.0")
        assert int(volume) == 100
