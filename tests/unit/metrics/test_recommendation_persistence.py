from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from core.metrics import c4_batch_ai_screening_job as c4_module


def _sample_row() -> tuple:
    return (
        "00000000-0000-0000-0000-000000000000",
        datetime(2026, 1, 10, tzinfo=timezone.utc),
        "ticker-id",
        date(2026, 1, 10),
        "LONG",
        "BUY",
        Decimal("0.800"),
        "Test rationale.",
        None,
        None,
        None,
        None,
        Decimal("150.0000"),
        date(2026, 1, 17),
        "C",
        "LONG_CALL",
        "active",
        "c4-test",
        datetime(2026, 1, 10, tzinfo=timezone.utc),
    )


def test_single_valid_recommendation_persists_successfully(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    def _fake_execute_values(cursor, _sql, values, page_size=None) -> None:
        cursor.rowcount = len(values)

    monkeypatch.setattr(c4_module, "execute_values", _fake_execute_values)

    rows = [_sample_row()]
    inserted = c4_module._persist_recommendations(conn, rows=rows, dry_run=False)

    assert inserted == 1
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_duplicate_persistence_attempt_does_not_create_second_row(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    def _fake_execute_values(cursor, _sql, _values, page_size=None) -> None:
        cursor.rowcount = 0

    monkeypatch.setattr(c4_module, "execute_values", _fake_execute_values)

    rows = [_sample_row()]
    inserted = c4_module._persist_recommendations(conn, rows=rows, dry_run=False)

    assert inserted == 0
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_persistence_skipped_when_dry_run_enabled() -> None:
    conn = MagicMock()
    rows = [_sample_row()]

    inserted = c4_module._persist_recommendations(conn, rows=rows, dry_run=True)

    assert inserted == 0
    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()
