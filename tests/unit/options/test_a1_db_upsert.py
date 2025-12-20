from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ingestion.options import db as options_db


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[tuple]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.cur = _FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self) -> None:
        self.commits += 1


@pytest.mark.unit
def test_upsert_batches_and_commits(monkeypatch) -> None:
    recorded: list[tuple[str, list[tuple]]] = []

    def fake_execute_values(cur, sql, values, page_size=None):
        recorded.append((sql, list(values)))

    monkeypatch.setattr(options_db, "execute_values", fake_execute_values)

    conn = _FakeConn()
    snapshot_time = datetime(2025, 12, 20, tzinfo=timezone.utc)
    res = options_db.upsert_options_chains_rows(
        conn,
        rows=[
            {
                "time": snapshot_time,
                "ticker_id": "uuid",
                "expiration_date": datetime(2026, 1, 16).date(),
                "strike_price": Decimal("100.0"),
                "option_type": "C",
                "bid": Decimal("1.0"),
            }
        ],
    )

    assert res.rows_written == 1
    assert conn.commits == 1
    assert len(recorded) == 1
    sql, values = recorded[0]
    assert "INSERT INTO options_chains" in sql
    assert values[0][0] == snapshot_time
    assert values[0][1] == "uuid"

