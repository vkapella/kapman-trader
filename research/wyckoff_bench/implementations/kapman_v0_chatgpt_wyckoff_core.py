"""
Deterministic ChatGPT Wyckoff core adapter.
Implements schematic-style rules from KapMan deterministic documents + wyckoff_config.json.
"""

from __future__ import annotations

import json
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
DEFAULT_CONFIG_PATH = INPUTS_DIR / "wyckoff_config.json"


def _load_config(path: str | Path | None) -> Dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _phase_from_config(rsi_val: float, adx_val: float, cfg: Dict[str, Any]) -> str:
    thresholds = cfg.get("phase_thresholds", {})
    for phase, info in thresholds.items():
        rsi_rng = info.get("rsi_range", {})
        adx_rng = info.get("adx_range", {})
        if rsi_rng.get("min", -1) <= rsi_val <= rsi_rng.get("max", 101) and adx_rng.get("min", -1) <= adx_val <= adx_rng.get("max", 200):
            return phase
    return "C"


def _score_from_phase(phase: str, vol_z: float) -> Dict[ScoreName, float]:
    scaled = clamp_score(abs(vol_z) * 12)
    bc = scaled if phase in {"E", "D"} else 0.0
    spring = scaled if phase in {"A", "C"} else 0.0
    composite = max(bc, spring)
    return {
        ScoreName.BC_SCORE: bc,
        ScoreName.SPRING_SCORE: spring,
        ScoreName.COMPOSITE_SCORE: composite,
    }


class KapmanV0ChatGPTWyckoffCore(WyckoffImplementation):
    name = "kapman_v0_chatgpt_wyckoff_core"
    SUPPORTED_EVENTS = [
        EventCode.SC,
        EventCode.AR,
        EventCode.SPRING,
        EventCode.TEST,
        EventCode.SOS,
        EventCode.BC,
        EventCode.ST,
        EventCode.SOW,
    ]

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        df = df_symbol.copy().reset_index(drop=True)
        if df.empty:
            return []

        required_cols = ["rsi_14", "adx_14", "atr_14", "vol_ma_20"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing precomputed indicators: {missing}")

        wyckoff_cfg = _load_config(cfg.get("wyckoff_config"))
        df["rsi"] = df["rsi_14"]
        df["adx"] = df["adx_14"]
        df["range"] = df["high"] - df["low"]
        df["range_z"] = (df["range"] - df["range"].rolling(20).mean()) / (df["range"].rolling(20).std(ddof=0) + 1e-6)
        df["vol_z"] = (df["volume"] - df["vol_ma_20"]) / (df["volume"].rolling(20).std(ddof=0) + 1e-6)

        signals: List[WyckoffSignal] = []
        support = df["low"].rolling(40).min()
        resistance = df["high"].rolling(40).max()

        last_sc_idx = None
        last_bc_idx = None
        last_spring_idx = None

        for idx, row in df.iterrows():
            phase = _phase_from_config(row["rsi"], row["adx"], wyckoff_cfg)
            events: Dict[EventCode, bool] = {}

            # Selling Climax: Phase A + wide range + volume spike
            if phase in {"A", "B"} and row["range_z"] > 1.5 and row["vol_z"] > 1.5 and row["close"] > row["low"] + row["range"] * 0.5:
                events[EventCode.SC] = True
                last_sc_idx = idx

            # Automatic Rally after SC
            if last_sc_idx is not None and idx > last_sc_idx and row["close"] > df.loc[last_sc_idx, "close"] * 1.02 and row["range_z"] > 0.3:
                events[EventCode.AR] = True

            # Spring: dip below support then close strong with volume confirmation
            if row["low"] < support.iloc[idx] * 0.99 and row["close"] > support.iloc[idx] and row["vol_z"] > 0:
                events[EventCode.SPRING] = True
                last_spring_idx = idx

            # Test: low-volume retest of spring zone
            if last_spring_idx is not None and idx > last_spring_idx and abs(row["low"] - support.iloc[idx]) / max(support.iloc[idx], 1e-6) < 0.01 and row["vol_z"] < 0.3:
                events[EventCode.TEST] = True

            # SOS: breakout above resistance with momentum
            if row["close"] > resistance.iloc[idx] * 0.995 and row["range_z"] > 1 and row["vol_z"] > 0.8:
                events[EventCode.SOS] = True

            # Buying Climax: late-phase spike
            if phase in {"D", "E"} and row["range_z"] > 1.5 and row["vol_z"] > 1.5 and row["close"] > row["open"]:
                events[EventCode.BC] = True
                last_bc_idx = idx

            # Secondary Test near BC
            if last_bc_idx is not None and idx > last_bc_idx and row["vol_z"] < 0.3 and row["close"] > resistance.iloc[idx] * 0.98:
                events[EventCode.ST] = True

            # SOW: break below support after BC
            if last_bc_idx is not None and row["close"] < support.iloc[idx] * 0.99 and row["range_z"] > 1:
                events[EventCode.SOW] = True

            if not events:
                continue

            scores = _score_from_phase(phase, row["vol_z"])
            signals.append(
                WyckoffSignal(
                    symbol=str(df_symbol.iloc[0]["symbol"]),
                    time=pd.to_datetime(row["time"]).to_pydatetime(),
                    events=events,
                    scores=scores,
                    debug={
                        "phase": phase,
                        "rsi": row["rsi"],
                        "adx": row["adx"],
                        "range_z": row["range_z"],
                        "vol_z": row["vol_z"],
                    },
                )
            )

        return signals


def build() -> KapmanV0ChatGPTWyckoffCore:
    return KapmanV0ChatGPTWyckoffCore()
