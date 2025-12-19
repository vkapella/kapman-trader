import os

import pytest
import psycopg2
from typing import Optional

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate


def _test_db_url() -> Optional[str]:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = _test_db_url()
    if not url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session", autouse=True)
def _reset_and_migrate_once(test_db_url: str) -> None:
    reset_and_migrate(test_db_url, default_migrations_dir())


def _public_tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        return {row[0] for row in cur.fetchall()}


def _table_counts(conn, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cur.fetchone()[0])
    return counts


def test_schema_applies_from_scratch(test_db_url: str) -> None:
    reset_and_migrate(test_db_url, default_migrations_dir())
    with psycopg2.connect(test_db_url) as conn:
        assert "tickers" in _public_tables(conn)


def test_tables_exist(test_db_url: str) -> None:
    with psycopg2.connect(test_db_url) as conn:
        assert _public_tables(conn) == {
            "tickers",
            "ohlcv",
            "options_chains",
            "daily_snapshots",
            "recommendations",
            "recommendation_outcomes",
        }


def test_tables_are_empty(test_db_url: str) -> None:
    with psycopg2.connect(test_db_url) as conn:
        counts = _table_counts(
            conn,
            [
                "tickers",
                "ohlcv",
                "options_chains",
                "daily_snapshots",
                "recommendations",
                "recommendation_outcomes",
            ],
        )
        assert all(v == 0 for v in counts.values())


def test_ohlcv_is_hypertable(test_db_url: str) -> None:
    with psycopg2.connect(test_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM timescaledb_information.hypertables "
                "WHERE hypertable_schema = 'public' AND hypertable_name = 'ohlcv'"
            )
            assert cur.fetchone() is not None


def test_ohlcv_has_retention_policy_730_days(test_db_url: str) -> None:
    with psycopg2.connect(test_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_retention'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'ohlcv'
                """,
            )
            row = cur.fetchone()
            assert row is not None, "Expected TimescaleDB retention policy job for public.ohlcv"
            config = row[0] or {}
            assert config.get("drop_after") == "730 days"


def test_no_extra_tables(test_db_url: str) -> None:
    with psycopg2.connect(test_db_url) as conn:
        assert _public_tables(conn) == {
            "tickers",
            "ohlcv",
            "options_chains",
            "daily_snapshots",
            "recommendations",
            "recommendation_outcomes",
        }
