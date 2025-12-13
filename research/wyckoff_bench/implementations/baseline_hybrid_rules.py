"""
Hybrid rules baseline: combines support/resistance breaks with volume regime.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from research.wyckoff_bench.harness.contract import (
    EventCode,
    ScoreName,
    WyckoffImplementation,
    WyckoffSignal,
    clamp_score,
)


class BaselineHybridRules(WyckoffImplementation):
    name = "baseline_hybrid_rules"
    SUPPORTED_EVENTS = [
        EventCode.SPRING,
        EventCode.SOW,
        EventCode.SOS,
        EventCode.BC,
    ]

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        df = df_symbol.copy().reset_index(drop=True)
        if df.empty:
            return []

        lookback = int(cfg.get("lookback", 60))
        support = df["low"].rolling(lookback).min()
        resistance = df["high"].rolling(lookback).max()
        vol_mean = df["volume"].rolling(lookback // 2).mean()

        signals: List[WyckoffSignal] = []
        for idx, row in df.iterrows():
            events: Dict[EventCode, bool] = {}
            if pd.isna(support.iloc[idx]) or pd.isna(resistance.iloc[idx]):
                continue

            below_support = row["low"] < support.iloc[idx] * 0.995
            above_resistance = row["high"] > resistance.iloc[idx] * 1.005
            vol_regime = row["volume"] / max(vol_mean.iloc[idx], 1)

            if below_support and row["close"] > support.iloc[idx]:
                events[EventCode.SPRING] = True
            if below_support and row["close"] < support.iloc[idx] and vol_regime > 1.2:
                events[EventCode.SOW] = True
            if above_resistance and row["close"] > resistance.iloc[idx] and vol_regime > 1.1:
                events[EventCode.SOS] = True
            if above_resistance and row["close"] < resistance.iloc[idx] and vol_regime > 1.4:
                events[EventCode.BC] = True
            if events:
                score = clamp_score(vol_regime * 25)
                signals.append(
                    WyckoffSignal(
                        symbol=str(df_symbol.iloc[0]["symbol"]),
                        time=pd.to_datetime(row["time"]).to_pydatetime(),
                        events=events,
                        scores={
                            ScoreName.BC_SCORE: score if EventCode.BC in events else 0.0,
                            ScoreName.SPRING_SCORE: score if EventCode.SPRING in events else 0.0,
                            ScoreName.COMPOSITE_SCORE: score,
                        },
                        debug={
                            "support": support.iloc[idx],
                            "resistance": resistance.iloc[idx],
                            "vol_regime": vol_regime,
                        },
                    )
                )
        return signals


def build() -> BaselineHybridRules:
    return BaselineHybridRules()
