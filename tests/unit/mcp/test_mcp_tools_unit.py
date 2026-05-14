from __future__ import annotations

import pytest

from core.mcp.tools.metrics import get_metrics
from core.mcp.tools.metrics_batch import get_metrics_batch
from core.mcp.tools.screen_symbols import screen_symbols
from core.mcp.tools.screen_watchlist import screen_watchlist
from core.mcp.tools.wyckoff_proposal import get_wyckoff_proposal_context


def test_invalid_date_validation():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        get_metrics("AMD", as_of_date="2026/01/01")


def test_missing_symbol_validation():
    with pytest.raises(ValueError, match="symbol is required"):
        get_wyckoff_proposal_context("", lookback_days=90)


def test_screen_limit_validation():
    with pytest.raises(ValueError, match="limit"):
        screen_watchlist(limit=0)


def test_metrics_include_validation():
    with pytest.raises(ValueError, match="unsupported include"):
        get_metrics("AMD", include=["foo"])


def _metrics_result(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "ticker_id": f"{symbol}-id",
        "effective_as_of_date": "2026-05-13",
        "latest_eligible_snapshot_date": "2026-05-12",
        "metrics": {"price": {"rvol": 1.2}},
        "data_quality_flags": {"missing_snapshot": False},
    }


def test_get_metrics_batch_all_symbols_found(monkeypatch):
    def fake_get_metrics(symbol, as_of_date=None):
        return _metrics_result(symbol)

    monkeypatch.setattr("core.mcp.tools.metrics_batch.get_metrics", fake_get_metrics)

    result = get_metrics_batch(["AMD", "NVDA"], as_of_date="2026-05-13")

    assert set(result["results"].keys()) == {"AMD", "NVDA"}
    assert result["missing_symbols"] == []
    assert result["as_of_date"] == "2026-05-13"


def test_get_metrics_batch_some_symbols_missing(monkeypatch):
    def fake_get_metrics(symbol, as_of_date=None):
        if symbol == "MISSING":
            raise ValueError("unknown symbol")
        return _metrics_result(symbol)

    monkeypatch.setattr("core.mcp.tools.metrics_batch.get_metrics", fake_get_metrics)

    result = get_metrics_batch(["AMD", "MISSING"], as_of_date="2026-05-13")

    assert list(result["results"].keys()) == ["AMD"]
    assert result["missing_symbols"] == ["MISSING"]


def test_get_metrics_batch_cap_exceeded(monkeypatch):
    calls = []

    def fake_get_metrics(symbol, as_of_date=None):
        calls.append(symbol)
        return _metrics_result(symbol)

    monkeypatch.setattr("core.mcp.tools.metrics_batch.get_metrics", fake_get_metrics)

    result = get_metrics_batch([f"S{i}" for i in range(31)], as_of_date="2026-05-13")

    assert result == {"error": "BATCH_CAP_EXCEEDED", "max": 30, "received": 31}
    assert calls == []


def test_get_metrics_batch_all_symbols_missing(monkeypatch):
    def fake_get_metrics(symbol, as_of_date=None):
        raise ValueError("unknown symbol")

    monkeypatch.setattr("core.mcp.tools.metrics_batch.get_metrics", fake_get_metrics)

    result = get_metrics_batch(["AAA", "BBB"], as_of_date="2026-05-13")

    assert result["results"] == {}
    assert result["missing_symbols"] == ["AAA", "BBB"]


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _screen_row(symbol: str, dgpi: float | None = 1.0, has_snapshot: bool = True) -> dict:
    return {
        "symbol": symbol,
        "ticker_id": f"{symbol}-id",
        "snapshot_date": "2026-05-12" if has_snapshot else None,
        "regime": "MARKUP" if has_snapshot else None,
        "primary_event": "SOS" if has_snapshot else None,
        "dgpi": dgpi,
        "iv_rank": 0.5 if has_snapshot else None,
        "rvol": 1.4 if has_snapshot else None,
        "has_snapshot": has_snapshot,
    }


def _patch_screen_symbols(monkeypatch, rows):
    conn = _FakeConnection(rows)
    monkeypatch.setattr("core.mcp.tools.screen_symbols.readonly_connection", lambda: conn)
    monkeypatch.setattr("core.mcp.tools.screen_symbols.queries.screen_rows_for_symbols", lambda _conn, symbols, as_of_date: rows)


def test_screen_symbols_all_symbols_found(monkeypatch):
    _patch_screen_symbols(monkeypatch, [_screen_row("AMD", dgpi=2.0), _screen_row("NVDA", dgpi=1.0)])

    result = screen_symbols(["AMD", "NVDA"], as_of_date="2026-05-13")

    assert [row["symbol"] for row in result["results"]] == ["AMD", "NVDA"]
    assert result["missing_symbols"] == []
    assert result["count"] == 2


def test_screen_symbols_some_symbols_missing(monkeypatch):
    _patch_screen_symbols(monkeypatch, [_screen_row("AMD")])

    result = screen_symbols(["AMD", "MISSING"], as_of_date="2026-05-13")

    assert [row["symbol"] for row in result["results"]] == ["AMD"]
    assert result["missing_symbols"] == ["MISSING"]


def test_screen_symbols_cap_exceeded(monkeypatch):
    calls = []

    def fake_screen_rows_for_symbols(_conn, symbols, as_of_date):
        calls.append(symbols)
        return []

    monkeypatch.setattr("core.mcp.tools.screen_symbols.readonly_connection", lambda: _FakeConnection([]))
    monkeypatch.setattr("core.mcp.tools.screen_symbols.queries.screen_rows_for_symbols", fake_screen_rows_for_symbols)

    result = screen_symbols([f"S{i}" for i in range(31)], as_of_date="2026-05-13")

    assert result == {"error": "BATCH_CAP_EXCEEDED", "max": 30, "received": 31}
    assert calls == []


def test_screen_symbols_all_symbols_missing(monkeypatch):
    _patch_screen_symbols(monkeypatch, [])

    result = screen_symbols(["AAA", "BBB"], as_of_date="2026-05-13")

    assert result["results"] == []
    assert result["missing_symbols"] == ["AAA", "BBB"]
