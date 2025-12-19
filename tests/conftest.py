import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import os

import pytest

_SCHEMA_BOOTSTRAPPED = False


def _ensure_ohlcv_daily_compat(db_url: str) -> None:
    import psycopg2

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", ("public.ohlcv_daily",))
            has_ohlcv_daily = cur.fetchone()[0] is not None
            if has_ohlcv_daily:
                return

            cur.execute("SELECT to_regclass(%s)", ("public.ohlcv",))
            has_ohlcv = cur.fetchone()[0] is not None
            if not has_ohlcv:
                return

            cur.execute(
                """
                CREATE OR REPLACE VIEW ohlcv_daily AS
                SELECT ticker_id, date, open, high, low, close, volume, created_at
                FROM ohlcv
                """
            )
        conn.commit()


# Ensure any test-side calls to reset_and_migrate also create `ohlcv_daily`
import core.db.a6_migrations as _a6_migrations

_ORIGINAL_RESET_AND_MIGRATE = _a6_migrations.reset_and_migrate


def _reset_and_migrate_with_test_compat(db_url: str, migrations_dir) -> None:
    _ORIGINAL_RESET_AND_MIGRATE(db_url, migrations_dir)
    _ensure_ohlcv_daily_compat(db_url)


_a6_migrations.reset_and_migrate = _reset_and_migrate_with_test_compat


def _verify_required_relations(db_url: str) -> None:
    import psycopg2

    required = ("tickers", "ohlcv_daily")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            for name in required:
                cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
                if cur.fetchone()[0] is None:
                    raise RuntimeError(f"Missing required relation after A6 bootstrap: public.{name}")


def _bootstrap_a6_schema_once() -> None:
    global _SCHEMA_BOOTSTRAPPED
    if _SCHEMA_BOOTSTRAPPED:
        return

    test_db_url = os.getenv("KAPMAN_TEST_DATABASE_URL")
    if not test_db_url:
        return

    from core.db.a6_migrations import default_migrations_dir, reset_and_migrate

    reset_and_migrate(test_db_url, default_migrations_dir())
    _verify_required_relations(test_db_url)
    _SCHEMA_BOOTSTRAPPED = True


def pytest_sessionstart(session: pytest.Session) -> None:
    _bootstrap_a6_schema_once()
