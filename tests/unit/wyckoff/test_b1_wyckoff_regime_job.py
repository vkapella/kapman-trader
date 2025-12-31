from __future__ import annotations

from datetime import date

from core.metrics.b1_wyckoff_regime_job import (
    REGIME_ACCUMULATION,
    REGIME_DISTRIBUTION,
    REGIME_MARKDOWN,
    REGIME_MARKUP,
    REGIME_UNKNOWN,
    RegimeState,
    _resolve_worker_count,
    _resolve_regime_for_date,
)


def _apply_events(events_by_date: dict[date, list[str]]) -> list[RegimeState]:
    current = RegimeState(regime=REGIME_UNKNOWN, confidence=None, set_by_event=None)
    outputs: list[RegimeState] = []
    for key in sorted(events_by_date.keys()):
        current = _resolve_regime_for_date(events_by_date[key], current)
        outputs.append(current)
    return outputs


def test_event_to_regime_mapping() -> None:
    mapping = {
        "SC": REGIME_ACCUMULATION,
        "SPRING": REGIME_ACCUMULATION,
        "SOS": REGIME_MARKUP,
        "BC": REGIME_DISTRIBUTION,
        "UT": REGIME_DISTRIBUTION,
        "SOW": REGIME_MARKDOWN,
    }
    for event, regime in mapping.items():
        state = _resolve_regime_for_date([event], RegimeState(REGIME_UNKNOWN, None, None))
        assert state.regime == regime
        assert state.set_by_event == event


def test_same_day_precedence() -> None:
    prior = RegimeState(regime=REGIME_UNKNOWN, confidence=None, set_by_event=None)
    next_state = _resolve_regime_for_date(["SC", "SOS", "SPRING"], prior)
    assert next_state.regime == REGIME_ACCUMULATION
    assert next_state.set_by_event == "SC"


def test_carry_forward_across_days() -> None:
    events = {
        date(2025, 1, 1): ["SC"],
        date(2025, 1, 2): [],
        date(2025, 1, 3): [],
    }
    outputs = _apply_events(events)
    assert all(state.regime == REGIME_ACCUMULATION for state in outputs)
    assert outputs[0].set_by_event == "SC"
    assert outputs[1].set_by_event is None
    assert outputs[2].set_by_event is None


def test_initialization_unknown_without_events() -> None:
    events = {
        date(2025, 1, 1): [],
    }
    outputs = _apply_events(events)
    assert outputs[0].regime == REGIME_UNKNOWN
    assert outputs[0].set_by_event is None


def test_resolve_workers_single_symbol() -> None:
    assert _resolve_worker_count(requested=None, max_workers=6, total_tickers=1) == 1


def test_resolve_workers_fewer_symbols_than_workers() -> None:
    assert _resolve_worker_count(requested=10, max_workers=20, total_tickers=3) == 3


def test_resolve_workers_respects_max_workers() -> None:
    assert _resolve_worker_count(requested=10, max_workers=2, total_tickers=10) == 2
