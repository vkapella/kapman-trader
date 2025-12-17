"""
TradingView-style heuristic baseline.
Uses moving average context + breakouts/breakdowns to tag events.
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


class BaselineTVHeuristic(WyckoffImplementation):
    name = "baseline_tv_heuristic"
    SUPPORTED_EVENTS = [
        EventCode.SC,
        EventCode.BC,
        EventCode.SOS,
        EventCode.SOW,
    ]

    def analyze(self, df_symbol: pd.DataFrame, cfg: Dict[str, Any]) -> List[WyckoffSignal]:
        df = df_symbol.copy().reset_index(drop=True)
        if df.empty:
            return []

        short_ma = df["close"].rolling(20).mean()
        long_ma = df["close"].rolling(50).mean()
        volume_mean = df["volume"].rolling(30).mean()

        signals: List[WyckoffSignal] = []
        for idx, row in df.iterrows():
            events: Dict[EventCode, bool] = {}
            price = row["close"]
            vol = row["volume"]
            gap_from_long = (price - long_ma.iloc[idx]) / long_ma.iloc[idx] if long_ma.iloc[idx] else 0

            if gap_from_long < -0.08 and vol > volume_mean.iloc[idx] * 1.5:
                events[EventCode.SC] = True
            if gap_from_long > 0.1 and vol > volume_mean.iloc[idx] * 1.5:
                events[EventCode.BC] = True
            if short_ma.iloc[idx] > long_ma.iloc[idx] and price > short_ma.iloc[idx] and vol > volume_mean.iloc[idx]:
                events[EventCode.SOS] = True
            if short_ma.iloc[idx] < long_ma.iloc[idx] and price < short_ma.iloc[idx] and vol > volume_mean.iloc[idx]:
                events[EventCode.SOW] = True
            if events:
                score = clamp_score(abs(gap_from_long) * 100)
                signals.append(
                    WyckoffSignal(
                        symbol=str(df_symbol.iloc[0]["symbol"]),
                        time=pd.to_datetime(row["time"]).to_pydatetime(),
                        events=events,
                        scores={
                            ScoreName.BC_SCORE: score if EventCode.BC in events else 0.0,
                            ScoreName.SPRING_SCORE: score if EventCode.SC in events else 0.0,
                            ScoreName.COMPOSITE_SCORE: score,
                        },
                        debug={
                            "gap_from_long": gap_from_long,
                            "short_ma": short_ma.iloc[idx],
                            "long_ma": long_ma.iloc[idx],
                            "volume_mean": volume_mean.iloc[idx],
                        },
                    )
                )
        return signals


def build() -> BaselineTVHeuristic:
    return BaselineTVHeuristic()
