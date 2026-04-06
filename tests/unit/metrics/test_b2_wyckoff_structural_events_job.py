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

    b2_module._fetch_ohlcv_history(conn, ticker_id="t1", start_date=date(2023, 12, 31), end_date=date(2024, 1, 1))

    sql = cur.execute.call_args[0][0]
    assert "FROM public.ohlcv" in sql
    assert "daily_snapshots" not in sql


def test_b2_imports_structural_logic_from_runtime_module() -> None:
    assert b2_module.detect_structural_wyckoff is structural.detect_structural_wyckoff


def test_b2_ohlcv_fetch_is_backlooking(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    # Rows are returned newest-first from the DB; we reverse in memory.
    cur.fetchall.return_value = [
        (date(2024, 1, 2), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 3), 1, 2, 0.5, 1.5, 100),
    ]

    rows = b2_module._fetch_ohlcv_history(
        conn,
        ticker_id="t1",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
    )

    sql = cur.execute.call_args[0][0]
    params = cur.execute.call_args[0][1]
    assert "ORDER BY date ASC" in sql
    assert "LIMIT" not in sql
    # Snapshot cutoff is end_date
    assert params[2] == date(2024, 1, 3)
    # Returned in chronological order
    assert rows[0][0] == date(2024, 1, 2)
    assert rows[1][0] == date(2024, 1, 3)


def test_b2_ohlcv_covers_all_target_dates(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    start = date(2024, 1, 1)
    end = date(2024, 1, 5)

    rows = [
        (date(2023, 12, 15), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 1), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 2), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 3), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 4), 1, 2, 0.5, 1.5, 100),
        (date(2024, 1, 5), 1, 2, 0.5, 1.5, 100),
    ]
    cur.fetchall.return_value = rows

    out = b2_module._fetch_ohlcv_history(
        conn,
        ticker_id="t1",
        start_date=start,
        end_date=end,
    )

    dates = [r[0] for r in out]
    for d in (start, start + timedelta(days=1), end):
        assert d in dates


def test_b2_insufficient_bars_are_explicit(monkeypatch) -> None:
    conn = MagicMock()
    log = MagicMock()

    monkeypatch.setattr(b2_module, "_fetch_active_tickers", lambda _conn: [("t1", "ABC")])
    monkeypatch.setattr(
        b2_module,
        "_fetch_snapshot_dates_by_ticker",
        lambda *args, **kwargs: {"t1": [date(2024, 1, 1)]},
    )
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
        "_fetch_snapshot_dates_by_ticker",
        lambda *args, **kwargs: {"t1": [date(2024, 1, 1), date(2024, 1, 2)]},
    )
    monkeypatch.setattr(
        b2_module,
        "_fetch_ohlcv_history",
        lambda *args, **kwargs: _make_ohlcv_rows(date(2024, 1, 1), 60),
    )

    # Force deterministic events on both target dates
    monkeypatch.setattr(
        b2_module,
        "detect_structural_wyckoff",
        lambda *_args, **_kwargs: {
            "events": [
                {"date": "2024-01-01", "label": "SC", "score": 1.0},
                {"date": "2024-01-02", "label": "UT", "score": 0.8},
            ]
        },
    )

    stats = b2_module.run_wyckoff_structural_events_job(conn, log=MagicMock())

    assert stats["snapshots_written"] >= 1
    assert len(captured["context"]) >= 1


def test_b2_skips_zero_event_days_but_advances(monkeypatch) -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    captured_snapshots: list[tuple] = []

    def _fake_execute_values(cursor, sql, values, page_size=None):
        if "daily_snapshots" in sql:
            captured_snapshots.extend(values)

    monkeypatch.setattr(b2_module, "execute_values", _fake_execute_values)
    monkeypatch.setattr(b2_module, "_fetch_active_tickers", lambda _conn: [("t1", "ABC")])
    monkeypatch.setattr(
        b2_module,
        "_fetch_snapshot_dates_by_ticker",
        lambda *args, **kwargs: {"t1": [date(2024, 1, 1), date(2024, 1, 2)]},
    )
    monkeypatch.setattr(
        b2_module,
        "_fetch_ohlcv_history",
        lambda *args, **kwargs: _make_ohlcv_rows(date(2023, 12, 15), 60),
    )

    # Force no events on first day, one event on second day
    def _fake_detect(df, cfg):
        return {
            "events": [
                {"date": "2024-01-02", "label": "SC", "score": 1.0},
            ]
        }

    monkeypatch.setattr(b2_module, "detect_structural_wyckoff", _fake_detect)

    stats = b2_module.run_wyckoff_structural_events_job(conn, log=MagicMock())

    dates_upserted = sorted({row[0].date() for row in captured_snapshots})
    assert dates_upserted == [date(2024, 1, 1), date(2024, 1, 2)]
    assert stats["snapshots_written"] == len(captured_snapshots)


def test_b2_fetch_snapshot_dates_by_ticker_returns_per_ticker_ny_dates() -> None:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.return_value = [
        ("t1", date(2024, 1, 1)),
        ("t1", date(2024, 1, 2)),
        ("t2", date(2024, 1, 2)),
    ]

    result = b2_module._fetch_snapshot_dates_by_ticker(
        conn,
        ticker_ids=["t1", "t2", "t3"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
    )

    sql = cur.execute.call_args[0][0]
    params = cur.execute.call_args[0][1]
    assert "ticker_id::text = ANY(%s)" in sql
    assert "(time AT TIME ZONE 'America/New_York')::date >= %s" in sql
    assert "(time AT TIME ZONE 'America/New_York')::date <= %s" in sql
    assert params[0] == ["t1", "t2", "t3"]
    assert params[1] == date(2024, 1, 1)
    assert params[2] == date(2024, 1, 2)
    assert result == {
        "t1": [date(2024, 1, 1), date(2024, 1, 2)],
        "t2": [date(2024, 1, 2)],
        "t3": [],
    }


def test_b2_skips_zero_snapshot_ticker_without_aborting_valid_peers(monkeypatch) -> None:
    conn = MagicMock()
    log = MagicMock()
    captured_snapshots: list[tuple] = []
    seen_fetches: list[str] = []

    def _fake_execute_values(cursor, sql, values, page_size=None):
        if "daily_snapshots" in sql:
            captured_snapshots.extend(values)

    def _fake_fetch_ohlcv(*_args, **kwargs):
        seen_fetches.append(kwargs["ticker_id"])
        return _make_ohlcv_rows(date(2024, 1, 1), 60)

    monkeypatch.setattr(b2_module, "execute_values", _fake_execute_values)
    monkeypatch.setattr(b2_module, "_fetch_active_tickers", lambda _conn: [("t1", "AAA"), ("t2", "BBB")])
    monkeypatch.setattr(
        b2_module,
        "_fetch_snapshot_dates_by_ticker",
        lambda *args, **kwargs: {
            "t1": [date(2024, 1, 1), date(2024, 1, 2)],
            "t2": [],
        },
    )
    monkeypatch.setattr(b2_module, "_fetch_ohlcv_history", _fake_fetch_ohlcv)
    monkeypatch.setattr(b2_module, "detect_structural_wyckoff", lambda *_args, **_kwargs: {"events": []})

    stats = b2_module.run_wyckoff_structural_events_job(conn, log=log)

    assert stats["processed"] == 1
    assert stats["missing_history"] == 1
    assert seen_fetches == ["t1"]
    assert sorted({row[0].date() for row in captured_snapshots}) == [date(2024, 1, 1), date(2024, 1, 2)]
    warnings = [call.args[0] for call in log.warning.call_args_list]
    assert any("has no authoritative daily_snapshots in requested window" in msg for msg in warnings)
