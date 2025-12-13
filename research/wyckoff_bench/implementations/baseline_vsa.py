"""
Public-style Volume Spread Analysis baseline.
Uses simple range/volume heuristics to tag Wyckoff events.
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


class BaselineVSA(WyckoffImplementation):
    name = "baseline_vsa"
    SUPPORTED_EVENTS = [
        EventCode.SC,
        EventCode.BC,
        EventCode.TEST,
        EventCode.SOS,
        EventCode.SOW,
    ]

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        df = df_symbol.copy().reset_index(drop=True)
        if df.empty:
            return []

        vol_mean = df["volume"].rolling(30).mean()
        vol_std = df["volume"].rolling(30).std(ddof=0) + 1e-6
        range_series = df["high"] - df["low"]
        range_mean = range_series.rolling(30).mean()
        range_std = range_series.rolling(30).std(ddof=0) + 1e-6
        vol_z = (df["volume"] - vol_mean) / vol_std
        range_z = (range_series - range_mean) / range_std

        signals: List[WyckoffSignal] = []
        for idx, row in df.iterrows():
            events: Dict[EventCode, bool] = {}
            if vol_z.iloc[idx] > 1.8 and range_z.iloc[idx] > 1.5:
                if row["close"] < row["open"]:
                    events[EventCode.SC] = True
                else:
                    events[EventCode.BC] = True

            if vol_z.iloc[idx] < -0.5 and range_z.iloc[idx] < -0.2:
                events[EventCode.TEST] = True

            if range_z.iloc[idx] > 1.0 and vol_z.iloc[idx] > 0.5 and row["close"] > range_mean.iloc[idx]:
                events[EventCode.SOS] = True
            if range_z.iloc[idx] > 1.0 and vol_z.iloc[idx] > 0.5 and row["close"] < range_mean.iloc[idx]:
                events[EventCode.SOW] = True

            if not events:
                continue

            score = clamp_score(max(vol_z.iloc[idx], range_z.iloc[idx]) * 12)
            scores = {
                ScoreName.BC_SCORE: score if EventCode.BC in events else 0.0,
                ScoreName.SPRING_SCORE: score if EventCode.SC in events else 0.0,
                ScoreName.COMPOSITE_SCORE: score,
            }
            signals.append(
                WyckoffSignal(
                    symbol=str(df_symbol.iloc[0]["symbol"]),
                    time=pd.to_datetime(row["time"]).to_pydatetime(),
                    events=events,
                    scores=scores,
                    debug={
                        "vol_z": float(vol_z.iloc[idx]),
                        "range_z": float(range_z.iloc[idx]),
                    },
                )
            )
        return signals


def build() -> BaselineVSA:
    return BaselineVSA()
