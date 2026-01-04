from __future__ import annotations

from datetime import date, timedelta

from core.metrics.b1_wyckoff_regime_job import (
    REGIME_ACCUMULATION,
    REGIME_MARKDOWN,
    REGIME_MARKUP,
    REGIME_UNKNOWN,
)
from core.metrics.b4_wyckoff_derived_job import (
    FAILED_ACCUM_SEQUENCE_ID,
    CanonicalEvent,
    _derive_context_events,
    _derive_regime_transitions,
    _derive_sequences,
)


def test_transition_detection_min_duration() -> None:
    start = date(2025, 1, 1)
    snapshot_rows = []
    for offset in range(5):
        snapshot_rows.append((start + timedelta(days=offset), REGIME_ACCUMULATION))
    snapshot_rows.append((start + timedelta(days=5), REGIME_MARKUP))
    snapshot_rows.append((start + timedelta(days=6), REGIME_MARKUP))

    transitions = _derive_regime_transitions(snapshot_rows)
    assert len(transitions) == 1
    transition = transitions[0]
    assert transition["date"] == start + timedelta(days=5)
    assert transition["prior_regime"] == REGIME_ACCUMULATION
    assert transition["new_regime"] == REGIME_MARKUP
    assert transition["duration_bars"] == 5


def test_sequence_completion_patterns() -> None:
    events = [
        CanonicalEvent(date(2025, 1, 1), "SC", 0),
        CanonicalEvent(date(2025, 1, 2), "AR", 1),
        CanonicalEvent(date(2025, 1, 3), "SPRING", 2),
        CanonicalEvent(date(2025, 1, 5), "SOS", 3),
    ]
    sequences = _derive_sequences(events)
    seq_ids = {seq["sequence_id"] for seq in sequences}
    assert "SEQ_ACCUM_BREAKOUT" in seq_ids


def test_failed_accum_sequence_without_sos() -> None:
    events = [
        CanonicalEvent(date(2025, 2, 1), "SC", 0),
        CanonicalEvent(date(2025, 2, 2), "AR", 1),
        CanonicalEvent(date(2025, 2, 3), "SPRING", 2),
    ]
    sequences = _derive_sequences(events)
    seq_ids = {seq["sequence_id"] for seq in sequences}
    assert FAILED_ACCUM_SEQUENCE_ID in seq_ids


def test_context_labeling_uses_prior_regime() -> None:
    snapshot_rows = [
        (date(2025, 3, 1), REGIME_ACCUMULATION),
        (date(2025, 3, 2), REGIME_ACCUMULATION),
        (date(2025, 3, 3), REGIME_MARKDOWN),
        (date(2025, 3, 4), REGIME_UNKNOWN),
    ]
    events = [
        CanonicalEvent(date(2025, 3, 2), "SOS", 0),
        CanonicalEvent(date(2025, 3, 4), "BC", 1),
    ]
    context_events = _derive_context_events(events, snapshot_rows)
    assert any(
        context["event_type"] == "SOS"
        and context["prior_regime"] == REGIME_ACCUMULATION
        and context["context_label"] == "SOS_after_ACCUMULATION"
        for context in context_events
    )
