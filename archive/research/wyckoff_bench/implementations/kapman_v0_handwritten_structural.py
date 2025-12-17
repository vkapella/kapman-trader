"""
Adapter for handwritten structural Wyckoff logic (research inputs).
Wraps `structural.detect_structural_wyckoff` without refactoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.wyckoff_bench.harness.contract import (
    EventCode,
    ScoreName,
    WyckoffImplementation,
    WyckoffSignal,
    clamp_score,
)


INPUTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "research_inputs"
if str(INPUTS_DIR) not in sys.path:
    sys.path.insert(0, str(INPUTS_DIR))

import structural  # type: ignore  # noqa: E402


class KapmanV0HandwrittenStructural(WyckoffImplementation):
    name = "kapman_v0_handwritten_structural"
    SUPPORTED_EVENTS = [
        EventCode.SC,
        EventCode.AR,
        EventCode.BC,
        EventCode.SPRING,
        EventCode.SOS,
        EventCode.SOW,
        EventCode.ST,
        EventCode.TEST,
    ]

    @staticmethod
    def _map_label(label: str) -> EventCode | None:
        mapping = {
            "SC": EventCode.SC,
            "AR": EventCode.AR,
            "BC": EventCode.BC,
            "SPRING": EventCode.SPRING,
            "SOS": EventCode.SOS,
            "SOW": EventCode.SOW,
            "ST": EventCode.ST,
            "TEST": EventCode.TEST,
        }
        return mapping.get(label.upper())

    @staticmethod
    def _score_for_event(code: EventCode, raw_score: Any) -> Dict[ScoreName, float]:
        base = clamp_score(raw_score) * 10 if isinstance(raw_score, (int, float)) else 0.0
        bc = base if code == EventCode.BC else 0.0
        spring = base if code in {EventCode.SPRING, EventCode.TEST} else 0.0
        composite = max(bc, spring)
        return {
            ScoreName.BC_SCORE: clamp_score(bc),
            ScoreName.SPRING_SCORE: clamp_score(spring),
            ScoreName.COMPOSITE_SCORE: clamp_score(composite),
        }

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        signals: List[WyckoffSignal] = []
        wyckoff_cfg_path = cfg.get("wyckoff_config")
        phases_path = cfg.get("phases_config")
        debug_meta: Dict[str, Any] = {}

        if wyckoff_cfg_path:
            try:
                with open(wyckoff_cfg_path, "r", encoding="utf-8") as f:
                    debug_meta["wyckoff_config"] = json.load(f)
            except FileNotFoundError:
                debug_meta["wyckoff_config_error"] = "missing"

        if phases_path:
            debug_meta["phases_config"] = phases_path

        result = structural.detect_structural_wyckoff(df_symbol)
        for ev in result.get("events", []):
            code = self._map_label(ev.get("label", ""))
            if not code:
                continue
            when = pd.to_datetime(ev.get("date", df_symbol.iloc[0]["time"])).to_pydatetime()
            scores = self._score_for_event(code, ev.get("score"))
            signals.append(
                WyckoffSignal(
                    symbol=str(df_symbol.iloc[0]["symbol"]),
                    time=when,
                    events={code: True},
                    scores=scores,
                    debug={**debug_meta, "raw_event": ev},
                )
            )
        return signals


def build() -> KapmanV0HandwrittenStructural:
    return KapmanV0HandwrittenStructural()
