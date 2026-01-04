from __future__ import annotations

from datetime import date

from core.metrics.b4_1_wyckoff_sequences_job import (
    StructuralEvent,
    _compute_confidence,
    _derive_sequences_for_events,
)


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def test_terminal_only_anchoring() -> None:
    events = [
        StructuralEvent(event_date=_d("2024-01-02"), event_type="SC"),
        StructuralEvent(event_date=_d("2024-01-03"), event_type="AR"),
    ]
    regimes = {_d("2024-01-03"): "ACCUMULATION"}

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert sequences == []


def test_sos_only_assembly() -> None:
    terminal_date = _d("2024-02-01")
    events = [StructuralEvent(event_date=terminal_date, event_type="SOS")]
    regimes = {terminal_date: "ACCUMULATION"}

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.sequence_type == "ACCUMULATION_BREAKOUT"
    assert seq.terminal_event == "SOS"
    assert seq.start_date == terminal_date
    assert seq.terminal_date == terminal_date
    assert len(seq.events) == 1
    assert seq.events[0].event_role == "TERMINAL"
    assert seq.events[0].event_order == 1


def test_sos_assembly_with_gaps() -> None:
    events = [
        StructuralEvent(event_date=_d("2024-03-01"), event_type="SC"),
        StructuralEvent(event_date=_d("2024-03-03"), event_type="SPRING"),
        StructuralEvent(event_date=_d("2024-03-05"), event_type="SOS"),
    ]
    regimes = {_d("2024-03-05"): "ACCUMULATION"}

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.start_date == _d("2024-03-01")
    assert seq.terminal_date == _d("2024-03-05")
    assert [ev.event_type for ev in seq.events] == ["SC", "SPRING", "SOS"]
    assert [ev.event_order for ev in seq.events] == [1, 2, 3]


def test_sow_only_assembly() -> None:
    terminal_date = _d("2024-04-01")
    events = [StructuralEvent(event_date=terminal_date, event_type="SOW")]
    regimes = {terminal_date: "DISTRIBUTION"}

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.sequence_type == "DISTRIBUTION_BREAKDOWN"
    assert seq.terminal_event == "SOW"
    assert len(seq.events) == 1
    assert seq.events[0].event_role == "TERMINAL"


def test_regime_eligibility_gates() -> None:
    sos_date = _d("2024-05-01")
    sow_date = _d("2024-05-02")
    events = [
        StructuralEvent(event_date=sos_date, event_type="SOS"),
        StructuralEvent(event_date=sow_date, event_type="SOW"),
    ]
    regimes = {
        sos_date: "MARKUP",
        sow_date: "ACCUMULATION",
    }

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert sequences == []


def test_invalidation_flags() -> None:
    terminal_date = _d("2024-06-05")
    events = [
        StructuralEvent(event_date=_d("2024-06-01"), event_type="SC"),
        StructuralEvent(event_date=terminal_date, event_type="SOS"),
    ]
    regimes = {terminal_date: "ACCUMULATION"}
    transitions = [
        {
            "date": _d("2024-06-03"),
            "prior_regime": "ACCUMULATION",
            "new_regime": "MARKUP",
            "duration_bars": 5,
        }
    ]

    sequences = _derive_sequences_for_events(
        events=events,
        regimes_by_date=regimes,
        transitions=transitions,
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.invalidated is True
    assert seq.invalidated_reason is not None
    assert "MARKUP" in seq.invalidated_reason


def test_confidence_determinism_and_monotonicity() -> None:
    terminal_date = _d("2024-07-10")
    events_terminal_only = [
        StructuralEvent(event_date=terminal_date, event_type="SOS"),
    ]
    regimes = {terminal_date: "ACCUMULATION"}

    seqs_a = _derive_sequences_for_events(
        events=events_terminal_only,
        regimes_by_date=regimes,
        transitions=[],
    )
    seqs_b = _derive_sequences_for_events(
        events=events_terminal_only,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert len(seqs_a) == 1
    assert seqs_a[0].confidence == seqs_b[0].confidence

    events_with_support = [
        StructuralEvent(event_date=_d("2024-07-07"), event_type="SC"),
        StructuralEvent(event_date=terminal_date, event_type="SOS"),
    ]
    seqs_support = _derive_sequences_for_events(
        events=events_with_support,
        regimes_by_date=regimes,
        transitions=[],
    )

    assert len(seqs_support) == 1
    assert seqs_a[0].confidence < seqs_support[0].confidence
    assert _compute_confidence(0) < _compute_confidence(1)
