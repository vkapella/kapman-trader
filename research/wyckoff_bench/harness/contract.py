"""
Canonical Wyckoff benchmarking contract (research-only).
Defines event/score enums, signal structure, and helpers for adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Protocol

import pandas as pd


class EventCode(str, Enum):
    SC = "SC"
    AR = "AR"
    ST = "ST"
    SPRING = "SPRING"
    TEST = "TEST"
    SOS = "SOS"
    BC = "BC"
    SOW = "SOW"


EVENT_ORDER: List[EventCode] = [
    EventCode.SC,
    EventCode.AR,
    EventCode.ST,
    EventCode.SPRING,
    EventCode.TEST,
    EventCode.SOS,
    EventCode.BC,
    EventCode.SOW,
]


class ScoreName(str, Enum):
    BC_SCORE = "bc_score"
    SPRING_SCORE = "spring_score"
    COMPOSITE_SCORE = "composite_score"


SCORE_ORDER: List[ScoreName] = [
    ScoreName.BC_SCORE,
    ScoreName.SPRING_SCORE,
    ScoreName.COMPOSITE_SCORE,
]


@dataclass
class WyckoffSignal:
    symbol: str
    time: datetime
    events: Dict[EventCode, bool] = field(default_factory=dict)
    scores: Dict[ScoreName, float] = field(default_factory=dict)
    debug: Dict[str, Any] | None = None
    direction: str | None = None
    role: str | None = None


class WyckoffImplementation(Protocol):
    name: str

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        ...


def normalize_event_map(events: Mapping[Any, Any] | None) -> Dict[EventCode, bool]:
    """Convert arbitrary mapping to EventCode -> bool with defaults."""
    normalized: Dict[EventCode, bool] = {code: False for code in EVENT_ORDER}
    if not events:
        return normalized
    for key, val in events.items():
        try:
            code = EventCode(key) if not isinstance(key, EventCode) else key
        except ValueError:
            continue
        normalized[code] = bool(val)
    return normalized


def normalize_scores(scores: Mapping[Any, Any] | None) -> Dict[ScoreName, float]:
    """Clamp score mapping to 0-100 per ScoreName."""
    normalized: Dict[ScoreName, float] = {name: 0.0 for name in SCORE_ORDER}
    if not scores:
        return normalized
    for key, val in scores.items():
        try:
            name = ScoreName(key) if not isinstance(key, ScoreName) else key
        except ValueError:
            continue
        normalized[name] = clamp_score(val)
    return normalized


def clamp_score(value: Any) -> float:
    """Normalize numeric score to 0..100 range."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric != numeric:  # NaN guard
        return 0.0
    return float(max(0.0, min(100.0, numeric)))


def signal_rows(signals: Iterable[WyckoffSignal], impl_name: str) -> List[Dict[str, Any]]:
    """Flatten signals into row dicts ready for DataFrame/Parquet."""
    rows: List[Dict[str, Any]] = []
    for sig in signals:
        events = normalize_event_map(sig.events)
        scores = normalize_scores(sig.scores)
        row: Dict[str, Any] = {
            "impl": impl_name,
            "symbol": sig.symbol,
            "time": pd.Timestamp(sig.time),
        }
        if sig.direction:
            row["direction"] = sig.direction
        if sig.role:
            row["role"] = sig.role
        for code in EVENT_ORDER:
            row[f"event_{code.value.lower()}"] = events.get(code, False)
        for name in SCORE_ORDER:
            row[name.value] = scores.get(name, 0.0)
        if sig.debug:
            row["debug"] = sig.debug
        rows.append(row)
    return rows


def empty_signal(symbol: str, when: datetime) -> WyckoffSignal:
    """Helper for adapters to emit a no-op signal."""
    return WyckoffSignal(symbol=symbol, time=when, events={}, scores={})
