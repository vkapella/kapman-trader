from __future__ import annotations

from datetime import date

from core.metrics.b1_wyckoff_regime_job import (
    REGIME_MARKDOWN,
    REGIME_MARKUP,
    REGIME_UNKNOWN,
    RegimeState,
    _resolve_regime_for_date,
)


def _apply_events(events_by_date: dict[date, list[str]]) -> list[RegimeState]:
    current = RegimeState(regime=REGIME_UNKNOWN, confidence=None, set_by_event=None)
    outputs: list[RegimeState] = []
    for key in sorted(events_by_date.keys()):
        current = _resolve_regime_for_date(events_by_date[key], current)
        outputs.append(current)
    return outputs


def test_regime_transitions_on_sos_and_sow() -> None:
    events = {
        date(2025, 1, 1): ["SOS"],
        date(2025, 1, 2): ["SOW"],
    }
    outputs = _apply_events(events)
    assert outputs[0].regime == REGIME_MARKUP
    assert outputs[0].set_by_event == "SOS"
    assert outputs[1].regime == REGIME_MARKDOWN
    assert outputs[1].set_by_event == "SOW"


def test_non_regime_events_do_not_change_state() -> None:
    prior = RegimeState(regime=REGIME_MARKUP, confidence=1.0, set_by_event="SOS")
    for event in ["SC", "BC", "SPRING", "UT"]:
        next_state = _resolve_regime_for_date([event], prior)
        assert next_state == prior


def test_carry_forward_across_days() -> None:
    events = {
        date(2025, 1, 1): ["SOS"],
        date(2025, 1, 2): [],
        date(2025, 1, 3): [],
    }
    outputs = _apply_events(events)
    assert all(state.regime == REGIME_MARKUP for state in outputs)
    assert all(state.set_by_event == "SOS" for state in outputs)


def test_determinism_across_repeated_runs() -> None:
    events = {
        date(2025, 1, 1): ["SOS"],
        date(2025, 1, 2): [],
        date(2025, 1, 3): ["SOW"],
    }
    first = _apply_events(events)
    second = _apply_events(events)
    assert first == second
