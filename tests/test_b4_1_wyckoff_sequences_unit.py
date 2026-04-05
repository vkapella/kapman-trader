from __future__ import annotations

from datetime import date

from core.metrics.b4_1_wyckoff_sequences_job import (
    StructuralEvent,
    _compute_confidence,
    _derive_sequences_for_events,
)


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _derive(
    *,
    events: list[StructuralEvent],
    entry_regimes: dict[date, str | None],
    post_terminal_regimes: dict[date, str | None] | None = None,
    transitions: list[dict] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    return _derive_sequences_for_events(
        events=events,
        entry_regimes_by_date=entry_regimes,
        post_terminal_regimes_by_date=post_terminal_regimes or {},
        transitions=transitions or [],
        terminal_start_date=start_date,
        terminal_end_date=end_date,
    )


def test_terminal_only_anchoring() -> None:
    events = [
        StructuralEvent(event_date=_d("2024-01-02"), event_type="SC"),
        StructuralEvent(event_date=_d("2024-01-03"), event_type="AR"),
    ]
    regimes = {_d("2024-01-03"): "ACCUMULATION"}

    sequences = _derive_sequences_for_events(
        events=events,
        entry_regimes_by_date=regimes,
        post_terminal_regimes_by_date={},
        transitions=[],
        terminal_start_date=None,
        terminal_end_date=None,
    )

    assert sequences == []


def test_sos_only_assembly() -> None:
    terminal_date = _d("2024-02-01")
    events = [StructuralEvent(event_date=terminal_date, event_type="SOS")]
    regimes = {terminal_date: "ACCUMULATION"}

    sequences = _derive(
        events=events,
        entry_regimes=regimes,
        post_terminal_regimes={terminal_date: "MARKUP"},
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.sequence_type == "ACCUMULATION_BREAKOUT"
    assert seq.terminal_event == "SOS"
    assert seq.start_date == terminal_date
    assert seq.terminal_date == terminal_date
    assert seq.prior_regime == "ACCUMULATION"
    assert seq.post_terminal_regime == "MARKUP"
    assert seq.supporting_event_count == 0
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

    sequences = _derive(
        events=events,
        entry_regimes=regimes,
        post_terminal_regimes={_d("2024-03-05"): "MARKUP"},
    )

    assert len(sequences) == 1
    seq = sequences[0]
    assert seq.start_date == _d("2024-03-01")
    assert seq.terminal_date == _d("2024-03-05")
    assert seq.supporting_event_count == 2
    assert [ev.event_type for ev in seq.events] == ["SC", "SPRING", "SOS"]
    assert [ev.event_order for ev in seq.events] == [1, 2, 3]


def test_sow_only_assembly() -> None:
    terminal_date = _d("2024-04-01")
    events = [StructuralEvent(event_date=terminal_date, event_type="SOW")]
    regimes = {terminal_date: "DISTRIBUTION"}

    sequences = _derive(
        events=events,
        entry_regimes=regimes,
        post_terminal_regimes={terminal_date: "MARKDOWN"},
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

    sequences = _derive(
        events=events,
        entry_regimes=regimes,
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

    sequences = _derive(
        events=events,
        entry_regimes=regimes,
        post_terminal_regimes={terminal_date: "MARKUP"},
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

    seqs_a = _derive(
        events=events_terminal_only,
        entry_regimes=regimes,
    )
    seqs_b = _derive(
        events=events_terminal_only,
        entry_regimes=regimes,
    )

    assert len(seqs_a) == 1
    assert seqs_a[0].confidence == seqs_b[0].confidence

    events_with_support = [
        StructuralEvent(event_date=_d("2024-07-07"), event_type="SC"),
        StructuralEvent(event_date=terminal_date, event_type="SOS"),
    ]
    seqs_support = _derive(
        events=events_with_support,
        entry_regimes=regimes,
    )

    assert len(seqs_support) == 1
    assert seqs_a[0].confidence < seqs_support[0].confidence
    assert _compute_confidence(0) < _compute_confidence(1)


def test_no_prior_regime_means_skip() -> None:
    terminal_date = _d("2024-08-01")
    events = [StructuralEvent(event_date=terminal_date, event_type="SOS")]

    sequences = _derive(
        events=events,
        entry_regimes={},
    )

    assert sequences == []


def test_terminal_date_transition_is_not_self_invalidation() -> None:
    terminal_date = _d("2024-09-05")
    events = [
        StructuralEvent(event_date=_d("2024-09-01"), event_type="SC"),
        StructuralEvent(event_date=terminal_date, event_type="SOS"),
    ]
    transitions = [
        {
            "date": terminal_date,
            "prior_regime": "ACCUMULATION",
            "new_regime": "MARKUP",
            "duration_bars": 4,
        }
    ]

    sequences = _derive(
        events=events,
        entry_regimes={terminal_date: "ACCUMULATION"},
        post_terminal_regimes={terminal_date: "MARKUP"},
        transitions=transitions,
    )

    assert len(sequences) == 1
    assert sequences[0].invalidated is False
    assert sequences[0].invalidated_reason is None
