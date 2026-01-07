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
        "wyckoff_regime": "MARKUP",
        "wyckoff_regime_confidence": 0.5,
        "wyckoff_regime_set_by_event": "SOS",
        "events_json": {"events": ["SOS"]},
        "bc_score": 10,
        "spring_score": 4,
        "composite_score": 12.5,
        "technical_indicators_json": {"adx": 25},
        "dealer_metrics_json": {"gamma_flip": 150.0},
        "volatility_metrics_json": {"iv_rank": 55},
        "price_metrics_json": {"close": 185.5},
    }


def _patch_dependencies(monkeypatch, tickers, seen) -> None:
    import core.metrics.c4_batch_ai_screening_job as c4_job

    monkeypatch.setattr(c4_job, "_resolve_snapshot_time", lambda conn, snapshot_time: datetime(2024, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(c4_job, "_fetch_watchlist_tickers", lambda conn: tickers)
    monkeypatch.setattr(c4_job, "_load_daily_snapshot", lambda conn, ticker_id, snapshot_time: _stub_snapshot())
    monkeypatch.setattr(c4_job, "_load_wyckoff_regime_transitions", lambda conn, ticker_id, snapshot_date: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_sequences", lambda conn, ticker_id, snapshot_date: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_sequence_events", lambda conn, ticker_id, snapshot_date: [])
    monkeypatch.setattr(c4_job, "_load_wyckoff_snapshot_evidence", lambda conn, ticker_id, snapshot_date: [])

    def _stub_invoke_planning_agent(**kwargs):
        symbol = kwargs.get("snapshot_payload", {}).get("symbol")
        seen.append(symbol)
        return {
            "context_label": "MARKUP",
            "confidence_score": 0.5,
            "metric_assessment": {"supporting": [], "contradicting": [], "neutral": []},
            "metric_weights": {},
            "discarded_metrics": [],
            "conditional_recommendation": {
                "direction": "NEUTRAL",
                "action": "HOLD",
                "option_type": None,
                "option_strategy": None,
            },
        }

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


def test_build_context_payload_includes_all_sections() -> None:
    import core.metrics.c4_batch_ai_screening_job as c4_job

    daily_snapshot = _stub_snapshot()
    transitions = [{"date": "2026-01-01", "prior_regime": "ACCUMULATION", "new_regime": "MARKUP", "duration_bars": 12}]
    sequences = [
        {
            "sequence_id": "SEQ1",
            "start_date": "2026-01-01",
            "completion_date": "2026-01-10",
            "events_in_sequence": {"terminal_event": "SOS"},
        }
    ]
    sequence_events = [
        {
            "sequence_id": "SEQ1",
            "completion_date": "2026-01-10",
            "event_type": "SOS",
            "event_date": "2026-01-10",
            "event_role": "terminal",
            "event_order": 3,
        }
    ]
    snapshot_evidence = [{"date": "2026-01-10", "evidence_json": {"duration_bars": 12}}]

    payload = c4_job._build_context_payload(
        ticker_id="ticker-1",
        symbol="AAPL",
        snapshot_time=datetime(2026, 1, 10, tzinfo=timezone.utc),
        daily_snapshot=daily_snapshot,
        regime_transitions=transitions,
        sequences=sequences,
        sequence_events=sequence_events,
        snapshot_evidence=snapshot_evidence,
    )

    assert payload["daily_snapshot"] == daily_snapshot
    assert payload["wyckoff_regime_transitions"] == transitions
    assert payload["wyckoff_sequences"] == sequences
    assert payload["wyckoff_sequence_events"] == sequence_events
    assert payload["wyckoff_snapshot_evidence"] == snapshot_evidence
