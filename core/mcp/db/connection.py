from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2

from core.db.a6_migrations import default_database_url


def _readonly_database_url() -> str:
    return os.getenv("DATABASE_URL") or default_database_url()


@contextmanager
def readonly_connection():
    conn = psycopg2.connect(_readonly_database_url())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        yield conn
    finally:
        conn.rollback()
        conn.close()
