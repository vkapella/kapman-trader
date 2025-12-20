from __future__ import annotations

import os

import psycopg2
import pytest

from core.db.a6_migrations import default_migrations_dir, reset_and_migrate


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.db
def test_a6_1_options_chains_is_hypertable_with_policies() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            # hypertable exists
            cur.execute(
                """
                SELECT 1
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                  AND hypertable_name = 'options_chains'
                """
            )
            assert cur.fetchone() is not None

            # retention policy
            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_retention'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'options_chains'
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0].get("drop_after") == "730 days"

            # compression policy
            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_compression'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'options_chains'
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0].get("compress_after") == "120 days"


@pytest.mark.integration
@pytest.mark.db
def test_a6_1_options_chains_schema_and_indexes_match_contract() -> None:
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")

    reset_and_migrate(db_url, default_migrations_dir())

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            # --- columns ---
            cur.execute(
                """
                SELECT column_name, data_type, udt_name, is_nullable, column_default,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'options_chains'
                ORDER BY ordinal_position
                """
            )
            cols = cur.fetchall()
            names = [c[0] for c in cols]

            assert names == [
                "time",
                "ticker_id",
                "expiration_date",
                "strike_price",
                "option_type",
                "bid",
                "ask",
                "last",
                "volume",
                "open_interest",
                "implied_volatility",
                "delta",
                "gamma",
                "theta",
                "vega",
                "created_at",
            ]

            strike = next(c for c in cols if c[0] == "strike_price")
            assert strike[1] == "numeric"
            assert int(strike[6]) == 12
            assert int(strike[7]) == 4

            option_type = next(c for c in cols if c[0] == "option_type")
            assert option_type[3] == "NO"
            assert int(option_type[5]) == 1

            created_at = next(c for c in cols if c[0] == "created_at")
            assert created_at[3] == "NO"
            assert created_at[4] is not None

            # --- indexes ---
            cur.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'options_chains'
                """
            )
            index_defs = [r[0].lower().replace('"', '') for r in cur.fetchall()]

            # unique snapshot identity index
            assert any(
                "create unique index" in d
                and "time" in d
                and "ticker_id" in d
                and "expiration_date" in d
                and "strike_price" in d
                and "option_type" in d
                for d in index_defs
            ), "Expected unique index enforcing snapshot identity"

            # supporting indexes
            def has_index(*cols: str) -> bool:
                for d in index_defs:
                    if "using btree" not in d:
                        continue
                    if all(c in d for c in cols):
                        return True
                return False

            assert has_index("ticker_id", "time")
            assert has_index("expiration_date")
            assert has_index("time")