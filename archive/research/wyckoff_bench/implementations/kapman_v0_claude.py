"""
Deterministic Claude-style Wyckoff logic:
Volume + spread + location + structure with transparent debug output.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd

from research.wyckoff_bench.harness.contract import (
    EventCode,
    ScoreName,
    WyckoffImplementation,
    WyckoffSignal,
    clamp_score,
)


LOOKBACK = 60


@dataclass
class ClaudeBarContext:
    idx: int
    vol_z: float
    range_z: float
    close_pos: float
    trend_slope: float
    support: float
    resistance: float


def _compute_context(df: pd.DataFrame, i: int, lookback: int) -> ClaudeBarContext:
    window = df.iloc[max(0, i - lookback) : i + 1]
    vol_mean = window["volume"].mean()
    vol_std = window["volume"].std(ddof=0) or 1
    rng = (window["high"] - window["low"]).mean()
    rng_std = (window["high"] - window["low"]).std(ddof=0) or 1
    bar_range = float(df.iloc[i]["high"] - df.iloc[i]["low"])
    vol_z = float((df.iloc[i]["volume"] - vol_mean) / vol_std)
    range_z = float((bar_range - rng) / rng_std)
    close_pos = float((df.iloc[i]["close"] - df.iloc[i]["low"]) / max(bar_range, 1e-6))
    trend_slope = float(df["close"].rolling(10).mean().diff().iloc[i])
    support = float(window["low"].min())
    resistance = float(window["high"].max())
    return ClaudeBarContext(
        idx=i,
        vol_z=vol_z,
        range_z=range_z,
        close_pos=close_pos,
        trend_slope=trend_slope,
        support=support,
        resistance=resistance,
    )


def _normalize_score(raw: float, emphasis: float = 10.0) -> Dict[ScoreName, float]:
    scaled = clamp_score(raw * emphasis)
    return {
        ScoreName.BC_SCORE: scaled if raw > 0 else 0.0,
        ScoreName.SPRING_SCORE: scaled if raw > 0 else 0.0,
        ScoreName.COMPOSITE_SCORE: scaled,
    }


class KapmanV0Claude(WyckoffImplementation):
    name = "kapman_v0_claude"
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
        signals: List[WyckoffSignal] = []
        df = df_symbol.copy().reset_index(drop=True)
        if df.empty:
            return signals

        contexts: List[ClaudeBarContext] = []
        lookback = int(cfg.get("lookback", LOOKBACK))
        for i in range(len(df)):
            contexts.append(_compute_context(df, i, lookback))

        seen_sc = None
        seen_bc = None
        last_spring = None

        for ctx in contexts:
            events: Dict[EventCode, bool] = {}
            debug: Dict[str, Any] = {
                "vol_z": ctx.vol_z,
                "range_z": ctx.range_z,
                "close_pos": ctx.close_pos,
                "trend_slope": ctx.trend_slope,
                "support": ctx.support,
                "resistance": ctx.resistance,
            }

            # Selling Climax
            if ctx.vol_z > 2 and ctx.range_z > 2 and ctx.close_pos > 0.55 and ctx.trend_slope < 0:
                events[EventCode.SC] = True
                seen_sc = ctx

            # Automatic Rally after SC
            if seen_sc and ctx.idx > seen_sc.idx and ctx.range_z > 0.5 and df.loc[ctx.idx, "close"] > df.loc[ctx.idx - 1, "close"]:
                events[EventCode.AR] = True

            # Spring: breaks support then reclaims with high close position
            if seen_sc and df.loc[ctx.idx, "low"] < seen_sc.support * 0.99 and ctx.close_pos > 0.6 and ctx.vol_z > 0.5:
                events[EventCode.SPRING] = True
                last_spring = ctx

            # Test: low volume retest near spring
            if last_spring and ctx.idx > last_spring.idx and abs(df.loc[ctx.idx, "low"] - last_spring.support) / last_spring.support < 0.01 and ctx.vol_z < 0.5:
                events[EventCode.TEST] = True

            # SOS: break above resistance with expanding spread
            if ctx.range_z > 1 and ctx.vol_z > 1 and df.loc[ctx.idx, "close"] > ctx.resistance * 0.99:
                events[EventCode.SOS] = True

            # Buying Climax
            if ctx.vol_z > 2 and ctx.range_z > 2 and ctx.close_pos > 0.7 and ctx.trend_slope > 0:
                events[EventCode.BC] = True
                seen_bc = ctx

            # Secondary Test after BC (range contraction + low volume near highs)
            if seen_bc and ctx.idx > seen_bc.idx and ctx.vol_z < 0.5 and df.loc[ctx.idx, "close"] > seen_bc.resistance * 0.98:
                events[EventCode.ST] = True

            # SOW: range expansion down through support
            if seen_bc and ctx.vol_z > 1 and ctx.range_z > 1 and df.loc[ctx.idx, "close"] < ctx.support * 0.995:
                events[EventCode.SOW] = True

            if not events:
                continue

            score_seed = max(ctx.vol_z, ctx.range_z)
            scores = _normalize_score(score_seed)
            signals.append(
                WyckoffSignal(
                    symbol=str(df_symbol.iloc[0]["symbol"]),
                    time=pd.to_datetime(df.loc[ctx.idx, "time"]).to_pydatetime(),
                    events=events,
                    scores=scores,
                    debug=debug,
                )
            )
        return signals


def build() -> KapmanV0Claude:
    return KapmanV0Claude()
