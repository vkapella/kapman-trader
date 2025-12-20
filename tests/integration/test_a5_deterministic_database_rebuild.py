from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import psycopg2
import pytest
from psycopg2 import sql

from core.db.a6_migrations import default_migrations_dir, list_sql_migrations, reset_and_migrate


EXPECTED_PUBLIC_TABLES: set[str] = {
    "tickers",
    "watchlists",
    "ohlcv",
    "options_chains",
    "daily_snapshots",
    "recommendations",
    "recommendation_outcomes",
}

EXPECTED_ENUM_TYPES: set[str] = {
    "option_type",
    "recommendation_status",
    "recommendation_direction",
    "recommendation_action",
    "option_strategy",
    "outcome_status",
}

EXPECTED_EXTENSIONS: set[str] = {"uuid-ossp", "timescaledb"}


def _test_db_url() -> str | None:
    return os.getenv("KAPMAN_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = _test_db_url()
    if not url:
        pytest.skip("KAPMAN_TEST_DATABASE_URL is not set")
    return url


def _public_tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return {row[0] for row in cur.fetchall()}


def _table_counts(conn, tables: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table in sorted(tables):
            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            )
            counts[table] = int(cur.fetchone()[0])
    return counts


def _extensions(conn) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname")
        rows = cur.fetchall()
    return [{"name": name, "version": version} for (name, version) in rows]


def _public_enum_types(conn) -> dict[str, list[str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT t.typname, e.enumlabel "
            "FROM pg_type t "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "JOIN pg_enum e ON e.enumtypid = t.oid "
            "WHERE n.nspname = 'public' "
            "ORDER BY t.typname, e.enumsortorder"
        )
        rows = cur.fetchall()

    enums: dict[str, list[str]] = {}
    for typname, enumlabel in rows:
        enums.setdefault(typname, []).append(enumlabel)
    return enums


def _public_columns(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, ordinal_position, data_type, udt_name, "
            "is_nullable, column_default, character_maximum_length, "
            "numeric_precision, numeric_scale, datetime_precision "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        )
        rows = cur.fetchall()

    cols: list[dict[str, Any]] = []
    for (
        table_name,
        column_name,
        ordinal_position,
        data_type,
        udt_name,
        is_nullable,
        column_default,
        character_maximum_length,
        numeric_precision,
        numeric_scale,
        datetime_precision,
    ) in rows:
        cols.append(
            {
                "table": table_name,
                "column": column_name,
                "position": int(ordinal_position),
                "data_type": data_type,
                "udt_name": udt_name,
                "nullable": is_nullable,
                "default": column_default,
                "char_max_len": character_maximum_length,
                "numeric_precision": numeric_precision,
                "numeric_scale": numeric_scale,
                "datetime_precision": datetime_precision,
            }
        )
    return cols


def _public_constraints(conn) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT conrelid::regclass::text AS table_name, conname, contype, "
            "pg_get_constraintdef(c.oid, true) AS constraint_def "
            "FROM pg_constraint c "
            "JOIN pg_class r ON r.oid = c.conrelid "
            "JOIN pg_namespace n ON n.oid = r.relnamespace "
            "WHERE n.nspname = 'public' AND r.relkind = 'r' "
            "ORDER BY table_name, conname"
        )
        rows = cur.fetchall()

    return [
        {
            "table": table_name,
            "name": conname,
            "type": contype,
            "def": constraint_def,
        }
        for (table_name, conname, contype, constraint_def) in rows
    ]


def _hypertables(conn) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT hypertable_schema, hypertable_name, column_name, time_interval::text "
            "FROM timescaledb_information.dimensions "
            "WHERE dimension_type = 'Time' "
            "ORDER BY hypertable_schema, hypertable_name, dimension_number"
        )
        rows = cur.fetchall()

    return [
        {
            "schema": hypertable_schema,
            "name": hypertable_name,
            "time_column": column_name,
            "chunk_interval": time_interval,
        }
        for (hypertable_schema, hypertable_name, column_name, time_interval) in rows
    ]


def _schema_fingerprint(conn) -> dict[str, Any]:
    fingerprint: dict[str, Any] = {
        "public_tables": sorted(_public_tables(conn)),
        "public_columns": _public_columns(conn),
        "public_constraints": _public_constraints(conn),
        "extensions": _extensions(conn),
        "public_enums": _public_enum_types(conn),
        "hypertables": _hypertables(conn),
    }
    encoded = json.dumps(fingerprint, sort_keys=True, default=str).encode("utf-8")
    fingerprint["sha256"] = hashlib.sha256(encoded).hexdigest()
    return fingerprint


@pytest.mark.integration
@pytest.mark.db
def test_a5_deterministic_rebuild_and_baseline_invariants(test_db_url: str) -> None:
    migrations_dir = default_migrations_dir()
    migration_files = list_sql_migrations(migrations_dir)
    assert [p.name for p in migration_files] == [
        "0001_extensions.sql",
        "0002_types.sql",
        "0003_mvp_schema.sql",
        "0004_ohlcv_retention.sql",
        "0005_watchlists.sql",
        "0006_options_chains_timescaledb.sql",
    ]

    fingerprints: list[dict[str, Any]] = []
    for _ in range(3):
        reset_and_migrate(test_db_url, migrations_dir)
        with psycopg2.connect(test_db_url) as conn:
            assert _public_tables(conn) == EXPECTED_PUBLIC_TABLES

            counts = _table_counts(conn, EXPECTED_PUBLIC_TABLES)
            assert all(v == 0 for v in counts.values())

            extensions = {e["name"] for e in _extensions(conn)}
            assert EXPECTED_EXTENSIONS.issubset(extensions)

            enums = set(_public_enum_types(conn).keys())
            assert EXPECTED_ENUM_TYPES.issubset(enums)

            hypertables = _hypertables(conn)
            assert any(
                ht["schema"] == "public"
                and ht["name"] == "ohlcv"
                and ht["time_column"] == "date"
                for ht in hypertables
            )
            assert any(
                ht["schema"] == "public"
                and ht["name"] == "options_chains"
                and ht["time_column"] == "time"
                for ht in hypertables
            )

            fingerprints.append(_schema_fingerprint(conn))

    assert all(fp == fingerprints[0] for fp in fingerprints[1:])
