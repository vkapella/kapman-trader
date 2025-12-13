from datetime import datetime

from research.wyckoff_bench.harness.contract import (
    EventCode,
    ScoreName,
    WyckoffSignal,
    clamp_score,
    normalize_event_map,
    normalize_scores,
    signal_rows,
)


def test_normalize_event_map_and_scores():
    events = normalize_event_map({"SC": True, "BC": "yes", "UNKNOWN": True})
    assert events[EventCode.SC] is True
    assert events[EventCode.BC] is True
    assert all(code in events for code in EventCode)

    scores = normalize_scores({"bc_score": 120, "spring_score": -5, "bad": 10})
    assert scores[ScoreName.BC_SCORE] == 100
    assert scores[ScoreName.SPRING_SCORE] == 0
    assert scores[ScoreName.COMPOSITE_SCORE] == 0


def test_signal_rows_flattening():
    sig = WyckoffSignal(
        symbol="AAPL",
        time=datetime(2023, 1, 1),
        events={EventCode.SPRING: True},
        scores={ScoreName.SPRING_SCORE: 42},
        debug={"note": "test"},
    )
    rows = signal_rows([sig], "impl_a")
    assert rows[0]["impl"] == "impl_a"
    assert rows[0]["event_spring"] is True
    assert rows[0]["spring_score"] == 42
    assert rows[0]["debug"]["note"] == "test"
