from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg2
from psycopg2 import sql


@dataclass(frozen=True)
class DbUrlParts:
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

    @property
    def dbname(self) -> str:
        return (self.path or "").lstrip("/")

    def with_dbname(self, dbname: str) -> "DbUrlParts":
        return DbUrlParts(
            scheme=self.scheme,
            netloc=self.netloc,
            path=f"/{dbname}",
            params=self.params,
            query=self.query,
            fragment=self.fragment,
        )

    def to_url(self) -> str:
        return urlunparse(
            (self.scheme, self.netloc, self.path, self.params, self.query, self.fragment)
        )


def _normalize_psycopg2_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    if "+" in parsed.scheme:
        parsed = parsed._replace(scheme=parsed.scheme.split("+", 1)[0])
    return urlunparse(parsed)


def _parse_db_url(db_url: str) -> DbUrlParts:
    normalized = _normalize_psycopg2_url(db_url)
    parsed = urlparse(normalized)
    return DbUrlParts(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        params=parsed.params,
        query=parsed.query,
        fragment=parsed.fragment,
    )


def _maintenance_url(db_url: str) -> str:
    parts = _parse_db_url(db_url)
    return parts.with_dbname("postgres").to_url()


def _connect_maintenance(db_url: str):
    maintenance_url = _maintenance_url(db_url)
    try:
        return psycopg2.connect(maintenance_url)
    except psycopg2.OperationalError:
        parts = _parse_db_url(db_url)
        return psycopg2.connect(parts.with_dbname("template1").to_url())


def list_sql_migrations(migrations_dir: str | Path) -> list[Path]:
    migrations_dir = Path(migrations_dir)
    if not migrations_dir.exists():
        return []
    return sorted([p for p in migrations_dir.iterdir() if p.is_file() and p.suffix == ".sql"])


def apply_sql_migrations(db_url: str, migrations_dir: str | Path) -> None:
    db_url = _normalize_psycopg2_url(db_url)
    migration_files = list_sql_migrations(migrations_dir)
    if not migration_files:
        raise RuntimeError(f"No SQL migrations found in {Path(migrations_dir)}")

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            for path in migration_files:
                cur.execute(path.read_text(encoding="utf-8"))


def reset_database(db_url: str) -> None:
    parts = _parse_db_url(db_url)
    target_db = parts.dbname
    if not target_db:
        raise ValueError("DATABASE_URL is missing database name")

    conn = _connect_maintenance(db_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                (target_db,),
            )
            owner_row = cur.fetchone()
            owner = owner_row[0] if owner_row and owner_row[0] else None

            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (target_db,),
            )
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(target_db)))

            if owner:
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(target_db), sql.Identifier(owner)
                    )
                )
            else:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
    finally:
        conn.close()


def reset_and_migrate(db_url: str, migrations_dir: str | Path) -> None:
    reset_database(db_url)
    apply_sql_migrations(db_url, migrations_dir)


def default_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url


def default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "migrations"
