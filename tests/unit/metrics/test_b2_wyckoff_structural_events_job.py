from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import core.metrics.b2_wyckoff_structural_events_job as b2_module
import core.metrics.structural as structural


def _make_ohlcv_rows(start: date, days: int) -> list[tuple]:
    rows: list[tuple] = []
    price = 100.0
    for i in range(days - 1):
        day = start + timedelta(days=i)
        open_price = price
        close_price = price - 0.5
        high = max(open_price, close_price) + 1 + (i % 2) * 0.1
        low = min(open_price, close_price) - 1 - (i % 3) * 0.2
        volume = 100 + (i % 10)
        rows.append((day, open_price, high, low, close_price, volume))
        price = close_price
    day = start + timedelta(days=days - 1)
    open_price = price
    low = price - 10
    high = price + 2
    close_price = price - 3
    volume = 1000
    rows.append((day, open_price, high, low, close_price, volume))
    return rows


def test_b2_reads_from_public_ohlcv_table() -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.return_value = []

    b2_module._fetch_ohlcv_history(conn, ticker_id="t1", start_date=None, end_date=None)

    sql = cur.execute.call_args[0][0]
    assert "FROM public.ohlcv" in sql
    assert "daily_snapshots" not in sql


def test_b2_imports_structural_logic_from_runtime_module() -> None:
    assert b2_module.detect_structural_wyckoff is structural.detect_structural_wyckoff


def test_b2_insufficient_bars_are_explicit(monkeypatch) -> None:
    conn = MagicMock()
    log = MagicMock()

    monkeypatch.setattr(b2_module, "_fetch_active_tickers", lambda _conn: [("t1", "ABC")])
    monkeypatch.setattr(
        b2_module,
        "_fetch_ohlcv_history",
        lambda *args, **kwargs: _make_ohlcv_rows(date(2024, 1, 1), 5),
    )

    stats = b2_module.run_wyckoff_structural_events_job(conn, log=log)

    assert stats["insufficient_bars"] == 1
    assert log.warning.call_count >= 1


def test_b2_emits_structural_events_for_valid_fixture(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    captured: dict[str, list[tuple]] = {"context": [], "snapshots": []}

    def _fake_execute_values(cursor, sql, values, page_size=None) -> None:
        if "wyckoff_context_events" in sql:
            captured["context"].extend(values)
        if "daily_snapshots" in sql:
            captured["snapshots"].extend(values)
        cursor.rowcount = len(values)

    monkeypatch.setattr(b2_module, "execute_values", _fake_execute_values)
    monkeypatch.setattr(b2_module, "_fetch_active_tickers", lambda _conn: [("t1", "ABC")])
    monkeypatch.setattr(
        b2_module,
        "_fetch_ohlcv_history",
        lambda *args, **kwargs: _make_ohlcv_rows(date(2024, 1, 1), 60),
    )

    stats = b2_module.run_wyckoff_structural_events_job(conn, log=MagicMock())

    assert stats["snapshots_written"] >= 1
    assert len(captured["context"]) >= 1
