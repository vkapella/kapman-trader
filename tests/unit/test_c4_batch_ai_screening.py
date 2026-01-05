from datetime import datetime, timezone

import pytest

from core.metrics.c4_batch_ai_screening_job import (
    compute_backoff_seconds,
    partition_batches,
    run_batch_ai_screening,
    sort_tickers,
)


def test_partition_batches() -> None:
    items = [1, 2, 3, 4, 5]
    assert partition_batches(items, 2) == [[1, 2], [3, 4], [5]]

    with pytest.raises(ValueError):
        partition_batches(items, 0)


def test_compute_backoff_seconds() -> None:
    assert compute_backoff_seconds(attempt=1, base_seconds=1.0) == 1.0
    assert compute_backoff_seconds(attempt=2, base_seconds=1.0) == 2.0
    assert compute_backoff_seconds(attempt=3, base_seconds=1.0) == 4.0

    with pytest.raises(ValueError):
        compute_backoff_seconds(attempt=0, base_seconds=1.0)


def test_sort_tickers_is_deterministic() -> None:
    tickers = [("2", "msft"), ("1", "AAPL"), ("3", "aapl")]
    assert sort_tickers(tickers) == [("1", "AAPL"), ("3", "AAPL"), ("2", "MSFT")]


def _stub_snapshot() -> dict:
    return {
        "wyckoff_regime": "UPTREND",
        "wyckoff_regime_confidence": 0.5,
        "events_detected": [],
        "technical_summary": {},
        "volatility_summary": {},
        "dealer_summary": {"spot_price": 100.0},
        "price_summary": {},
    }


def _patch_dependencies(monkeypatch, tickers, seen) -> None:
    import core.metrics.c4_batch_ai_screening_job as c4_job

    monkeypatch.setattr(c4_job, "_resolve_snapshot_time", lambda conn, snapshot_time: datetime(2024, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(c4_job, "_fetch_watchlist_tickers", lambda conn: tickers)
    monkeypatch.setattr(c4_job, "_load_daily_snapshot", lambda conn, ticker_id, snapshot_time: _stub_snapshot())

    def _stub_invoke_planning_agent(**kwargs):
        symbol = kwargs.get("snapshot_payload", {}).get("symbol")
        seen.append(symbol)
        return {"snapshot_metadata": {"ticker": symbol}}

    monkeypatch.setattr(c4_job, "invoke_planning_agent", _stub_invoke_planning_agent)


def test_symbols_filter_limits_execution(monkeypatch) -> None:
    tickers = [("1", "AAPL"), ("2", "MSFT"), ("3", "NVDA")]
    seen = []
    _patch_dependencies(monkeypatch, tickers, seen)

    run_batch_ai_screening(
        None,
        snapshot_time=None,
        ai_provider="openai",
        ai_model="test-model",
        symbols=["AAPL", "NVDA"],
        batch_size=10,
        batch_wait_seconds=0.0,
        dry_run=True,
    )

    assert sorted(seen) == ["AAPL", "NVDA"]


def test_symbols_filter_absent_preserves_watchlist(monkeypatch) -> None:
    tickers = [("1", "AAPL"), ("2", "MSFT")]
    seen = []
    _patch_dependencies(monkeypatch, tickers, seen)

    run_batch_ai_screening(
        None,
        snapshot_time=None,
        ai_provider="openai",
        ai_model="test-model",
        symbols=None,
        batch_size=10,
        batch_wait_seconds=0.0,
        dry_run=True,
    )

    assert sorted(seen) == ["AAPL", "MSFT"]


def test_symbols_filter_ignores_unknown_symbols(monkeypatch) -> None:
    tickers = [("1", "AAPL"), ("2", "MSFT")]
    seen = []
    _patch_dependencies(monkeypatch, tickers, seen)

    run_batch_ai_screening(
        None,
        snapshot_time=None,
        ai_provider="openai",
        ai_model="test-model",
        symbols=["AAPL", "ZZZZ"],
        batch_size=10,
        batch_wait_seconds=0.0,
        dry_run=True,
    )

    assert seen == ["AAPL"]
