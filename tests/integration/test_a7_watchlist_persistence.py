from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate
from core.ingestion.watchlists.loader import reconcile_watchlists


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


def _watchlists_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "watchlists"


@pytest.mark.integration
@pytest.mark.db
def test_a7_reconcile_persists_multiple_watchlists_is_idempotent_and_soft_deactivates() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    watchlists_dir = _watchlists_dir()
    wl1 = watchlists_dir / "a7_test_one.txt"
    wl2 = watchlists_dir / "a7_test_two.txt"

    try:
        wl1.write_text("AAPL\nMSFT\nAAPL\nINVALID$\n", encoding="utf-8")
        wl2.write_text("# comment\nTSLA\nGOOG\n", encoding="utf-8")

        reconcile_watchlists(db_url=db_url, effective_date=date(2025, 12, 19))

        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT symbol, active FROM watchlists WHERE watchlist_id = %s ORDER BY symbol",
                    ("a7_test_one",),
                )
                assert cur.fetchall() == [("AAPL", True), ("MSFT", True)]

                cur.execute(
                    "SELECT symbol, active FROM watchlists WHERE watchlist_id = %s ORDER BY symbol",
                    ("a7_test_two",),
                )
                assert cur.fetchall() == [("GOOG", True), ("TSLA", True)]

        reconcile_watchlists(db_url=db_url, effective_date=date(2025, 12, 19))

        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM watchlists WHERE watchlist_id IN (%s, %s)",
                    ("a7_test_one", "a7_test_two"),
                )
                assert int(cur.fetchone()[0]) == 4

        wl1.write_text("AAPL\n", encoding="utf-8")
        reconcile_watchlists(db_url=db_url, effective_date=date(2025, 12, 20))

        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT symbol, active FROM watchlists WHERE watchlist_id = %s ORDER BY symbol",
                    ("a7_test_one",),
                )
                assert cur.fetchall() == [("AAPL", True), ("MSFT", False)]
    finally:
        try:
            wl1.unlink(missing_ok=True)
        except TypeError:
            if wl1.exists():
                wl1.unlink()
        try:
            wl2.unlink(missing_ok=True)
        except TypeError:
            if wl2.exists():
                wl2.unlink()

        if db_url:
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE watchlists")
                conn.commit()

