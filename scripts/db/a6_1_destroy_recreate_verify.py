from __future__ import annotations

import json
import sys

import psycopg2

from core.db.a6_migrations import default_database_url, default_migrations_dir, reset_and_migrate


def _fetchone_dict(cur) -> dict:
    row = cur.fetchone()
    return row[0] if row and row[0] else {}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(db_url: str) -> None:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM timescaledb_information.hypertables "
                "WHERE hypertable_schema = 'public' AND hypertable_name = 'ohlcv'"
            )
            _require(cur.fetchone() is not None, "Missing TimescaleDB hypertable: public.ohlcv")

            cur.execute(
                "SELECT 1 FROM timescaledb_information.hypertables "
                "WHERE hypertable_schema = 'public' AND hypertable_name = 'options_chains'"
            )
            _require(cur.fetchone() is not None, "Missing TimescaleDB hypertable: public.options_chains")

            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_retention'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'ohlcv'
                """
            )
            ohlcv_retention = _fetchone_dict(cur)
            _require(ohlcv_retention.get("drop_after") == "730 days", "ohlcv retention must be 730 days")

            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_retention'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'options_chains'
                """
            )
            options_retention = _fetchone_dict(cur)
            _require(options_retention.get("drop_after") == "730 days", "options_chains retention must be 730 days")

            cur.execute(
                """
                SELECT config
                FROM timescaledb_information.jobs
                WHERE proc_name = 'policy_compression'
                  AND hypertable_schema = 'public'
                  AND hypertable_name = 'options_chains'
                """
            )
            options_compression = _fetchone_dict(cur)
            _require(
                options_compression.get("compress_after") == "120 days",
                "options_chains compression must be enabled with compress_after=120 days",
            )

            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'options_contracts'
                """
            )
            _require(cur.fetchone() is None, "options_contracts table must not exist")

    print(
        json.dumps(
            {
                "ok": True,
                "hypertables": ["ohlcv", "options_chains"],
                "retention_days": 730,
                "options_compression_after_days": 120,
            }
        )
    )


def main(argv: list[str]) -> int:
    db_url = default_database_url()
    reset_and_migrate(db_url, default_migrations_dir())
    verify(db_url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)
