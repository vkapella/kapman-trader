from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Dict, List, Any

import numpy as np
import pandas as pd


PhaseName = Literal["Accumulation", "Markup", "Distribution", "Markdown"]


@dataclass
class WyckoffStructuralConfig:
    """
    Configuration for structural Wyckoff analysis based on OHLCV only.

    This will later be driven by the Kapman registry service. For Step 1,
    we hard-code reasonable defaults.
    """

    # Windowing
    lookback_trend: int = 20
    vol_lookback: int = 40
    range_lookback: int = 40
    min_bars_in_range: int = 20

    # Core z-score thresholds (pre-scaled)
    sc_tr_z: float = 2.0
    sc_vol_z: float = 2.0
    bc_tr_z: float = 2.0
    bc_vol_z: float = 2.0
    sow_tr_z: float = 1.5
    sos_tr_z: float = 1.5
    spring_vol_z: float = 0.8

    # Global sensitivity multipliers
    range_z_scale: float = 1.0
    volume_z_scale: float = 1.0

    # Springs / Upthrusts geometry
    spring_break_pct: float = 0.01
    spring_reentry_bars: int = 2
    spring_close_pos: float = 0.6  # close above 60% of range
    ut_break_pct: float = 0.01
    ut_reentry_bars: int = 2
    ut_close_pos: float = 0.4      # close below 40% of range

    # Tests
    max_st_deviation_pct: float = 0.01
    test_low_vol_factor: float = 0.7

    # Phase construction rules
    require_prior_trend_for_sc_bc: bool = True
    allow_soft_markdown_without_sow: bool = False
    extend_last_phase_to_end: bool = True
    extend_first_phase_to_start: bool = True
    min_phase_bars: int = 2


def _compute_zscore(series: pd.Series, window: int) -> pd.Series:
    """Rolling z-score helper."""
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std(ddof=0)
    return (series - rolling_mean) / (rolling_std.replace(0, np.nan))


def _prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize and enrich OHLCV data for structural analysis.

    Required columns (case-insensitive):
      - date, open, high, low, close, volume
    """
    df = df.copy()

    # Normalize column names to lowercase
    rename_map: Dict[str, str] = {}
    for col in df.columns:
        lc = col.lower()
        if lc in {"open", "high", "low", "close", "volume", "date"} and lc != col:
            rename_map[col] = lc
    if rename_map:
        df = df.rename(columns=rename_map)

    # Research harness uses `time`; structural logic normalizes to `date`.
    if "date" not in df.columns and "time" in df.columns:
        df["date"] = df["time"]

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values("date").reset_index(drop=True)

    # True range etc.
    df["tr"] = (df["high"] - df["low"]).abs()
    df["body"] = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    df["close_pos"] = (df["close"] - df["low"]) / rng

    return df


def detect_structural_wyckoff(
    df: pd.DataFrame,
    cfg: Optional[WyckoffStructuralConfig] = None,
) -> Dict[str, Any]:
    """
    Detect structural Wyckoff events + phases from OHLCV.

    Returns:
        {
          "events": [ { "idx": int, "date": str, "label": str, "score": float }, ... ],
          "phases": {
             "accumulation": { "name": "Accumulation", "start_idx": int, "end_idx": int,
                               "start_date": str, "end_date": str },
             ...
          },
          "bands": [ { "name": str, "start": str, "end": str, "color": str }, ... ],
          "per_bar_phase": [ "Accumulation" | "Markup" | "Distribution" | "Markdown" | None, ... ]
        }
    """
    if cfg is None:
        cfg = WyckoffStructuralConfig()

    df = _prepare_ohlcv(df)

    n = len(df)
    if n < cfg.min_bars_in_range:
        return {"events": [], "phases": {}, "bands": [], "per_bar_phase": [None] * n}

    # Rolling z-scores
    tr_series: pd.Series = df["tr"]
    vol_series: pd.Series = df["volume"]
    df["tr_z"] = _compute_zscore(tr_series, cfg.range_lookback) * cfg.range_z_scale
    df["vol_z"] = _compute_zscore(vol_series, cfg.vol_lookback) * cfg.volume_z_scale

    # Simple trend proxy: SMA slope
    df["sma_trend"] = df["close"].rolling(cfg.lookback_trend).mean()
    df["sma_slope"] = df["sma_trend"].diff()

    events: List[Dict[str, Any]] = []

    def add_event(
        idx: int,
        label: str,
        score: float = 1.0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        ev: Dict[str, Any] = {
            "idx": int(idx),
            "date": df.loc[idx, "date"].strftime("%Y-%m-%d"),
            "label": label,
            "score": float(score),
        }
        if extra:
            ev.update(extra)
        events.append(ev)

    # --- Selling Climax (SC) ---
    sc_candidates = df[
        (df["tr_z"] >= cfg.sc_tr_z)
        & (df["vol_z"] >= cfg.sc_vol_z)
        & (df["close_pos"] >= 0.5)  # closes off the low
    ].index.tolist()

    sc_idx: Optional[int] = None
    if sc_candidates:
        # pick latest candidate that sits after a downtrend if required
        for idx in reversed(sc_candidates):
            if not cfg.require_prior_trend_for_sc_bc:
                sc_idx = int(idx)
                break
            # crude downtrend: SMA slope negative going into SC
            if df.loc[idx, "sma_slope"] < 0:
                sc_idx = int(idx)
                break
        if sc_idx is not None:
            add_event(sc_idx, "SC", score=float(df.loc[sc_idx, "vol_z"]))

    # --- Buying Climax (BC) ---
    bc_candidates = df[
        (df["tr_z"] >= cfg.bc_tr_z)
        & (df["vol_z"] >= cfg.bc_vol_z)
        & (df["close_pos"] >= 0.6)  # closes near high
    ].index.tolist()

    bc_idx: Optional[int] = None
    if bc_candidates:
        for idx in reversed(bc_candidates):
            if not cfg.require_prior_trend_for_sc_bc:
                bc_idx = int(idx)
                break
            if df.loc[idx, "sma_slope"] > 0:  # crude uptrend
                bc_idx = int(idx)
                break
        if bc_idx is not None:
            add_event(bc_idx, "BC", score=float(df.loc[bc_idx, "vol_z"]))

    # --- Simple AR / AR_TOP (first strong reaction after climax) ---
    ar_idx: Optional[int] = None
    ar_top_idx: Optional[int] = None

    if sc_idx is not None:
        window = range(sc_idx + 1, min(sc_idx + cfg.min_bars_in_range, n))
        ar_candidates = [
            i
            for i in window
            if df.loc[i, "close"] > df.loc[i - 1, "close"] and df.loc[i, "tr_z"] > 0.5
        ]
        if ar_candidates:
            ar_idx = ar_candidates[0]
            add_event(ar_idx, "AR", score=float(df.loc[ar_idx, "tr_z"]))

    if bc_idx is not None:
        window = range(bc_idx + 1, min(bc_idx + cfg.min_bars_in_range, n))
        ar_top_candidates = [
            i
            for i in window
            if df.loc[i, "close"] < df.loc[i - 1, "close"] and df.loc[i, "tr_z"] > 0.5
        ]
        if ar_top_candidates:
            ar_top_idx = ar_top_candidates[0]
            add_event(ar_top_idx, "AR_TOP", score=float(df.loc[ar_top_idx, "tr_z"]))

    # --- Springs and Upthrusts (simplified) ---
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None

    if sc_idx is not None and ar_idx is not None:
        support_level = float(df.loc[sc_idx:ar_idx, "low"].min())
    if bc_idx is not None and ar_top_idx is not None:
        resistance_level = float(df.loc[bc_idx:ar_top_idx, "high"].max())

    # Detect Springs: break below support then re-enter
    if support_level is not None:
        for i in range(cfg.min_bars_in_range, n):
            low = float(df.loc[i, "low"])
            if low < support_level * (1 - cfg.spring_break_pct):
                # need close back into range within spring_reentry_bars
                reentry = False
                for j in range(i, min(i + cfg.spring_reentry_bars + 1, n)):
                    if float(df.loc[j, "close"]) >= support_level:
                        reentry = True
                        break
                if not reentry:
                    continue

                # close position high in bar
                if float(df.loc[i, "close_pos"]) < cfg.spring_close_pos:
                    continue

                if float(df.loc[i, "vol_z"]) < cfg.spring_vol_z:
                    continue

                add_event(i, "SPRING", score=float(df.loc[i, "vol_z"]))
                break  # only mark first Spring for now

    # Detect Upthrusts: break above resistance then fall back
    if resistance_level is not None:
        for i in range(cfg.min_bars_in_range, n):
            high = float(df.loc[i, "high"])
            if high > resistance_level * (1 + cfg.ut_break_pct):
                reentry = False
                for j in range(i, min(i + cfg.ut_reentry_bars + 1, n)):
                    if float(df.loc[j, "close"]) <= resistance_level:
                        reentry = True
                        break
                if not reentry:
                    continue

                if float(df.loc[i, "close_pos"]) > cfg.ut_close_pos:
                    continue

                add_event(i, "UT", score=float(df.loc[i, "tr_z"]))
                break

    # --- SOW (Sign of Weakness) & SOS (Sign of Strength) proxies ---
    sow_idx: Optional[int] = None
    sos_idx: Optional[int] = None

    if resistance_level is not None:
        candidates = df[
            (df["close"] > resistance_level) & (df["tr_z"] >= cfg.sos_tr_z)
        ].index.tolist()
        if candidates:
            sos_idx = int(candidates[0])
            add_event(sos_idx, "SOS", score=float(df.loc[sos_idx, "tr_z"]))

    if support_level is not None:
        candidates = df[
            (df["close"] < support_level) & (df["tr_z"] >= cfg.sow_tr_z)
        ].index.tolist()
        if candidates:
            sow_idx = int(candidates[0])
            add_event(sow_idx, "SOW", score=float(df.loc[sow_idx, "tr_z"]))

    # --- Phase construction (v1) ---
    phases: Dict[str, Dict[str, Any]] = {}

    def _make_phase(name: PhaseName, start_idx: int, end_idx: int) -> Dict[str, Any]:
        start_idx = int(start_idx)
        end_idx = int(end_idx)
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx
        if end_idx - start_idx + 1 < cfg.min_phase_bars:
            return {}
        return {
            "name": name,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "start_date": df.loc[start_idx, "date"].strftime("%Y-%m-%d"),
            "end_date": df.loc[end_idx, "date"].strftime("%Y-%m-%d"),
        }

    # Accumulation: SC → (SOS or AR)
    if sc_idx is not None:
        acc_end = sos_idx if sos_idx is not None else (ar_idx if ar_idx is not None else sc_idx)
        phase = _make_phase("Accumulation", sc_idx, acc_end)
        if phase:
            phases["accumulation"] = phase

    # Markup: end(Accum) → BC
    if "accumulation" in phases and bc_idx is not None:
        start = phases["accumulation"]["end_idx"]
        phase = _make_phase("Markup", start, bc_idx)
        if phase:
            phases["markup"] = phase

    # Distribution: BC → (SOW or AR_TOP)
    if bc_idx is not None:
        if sow_idx is not None:
            dist_end = sow_idx
        elif ar_top_idx is not None:
            dist_end = ar_top_idx
        else:
            dist_end = bc_idx
        phase = _make_phase("Distribution", bc_idx, dist_end)
        if phase:
            phases["distribution"] = phase

    # Markdown: SOW → end or next SC
    if sow_idx is not None:
        later_sc = [e for e in events if e["label"] == "SC" and e["idx"] > sow_idx]
        if later_sc:
            md_end = later_sc[0]["idx"]
        else:
            md_end = n - 1
        phase = _make_phase("Markdown", sow_idx, md_end)
        if phase:
            phases["markdown"] = phase
    elif cfg.allow_soft_markdown_without_sow and bc_idx is not None:
        md_start = phases.get("distribution", {}).get("end_idx", bc_idx)
        md_end = n - 1
        phase = _make_phase("Markdown", md_start, md_end)
        if phase:
            phases["markdown"] = phase

    # Optionally extend phases to cover all bars
    if phases:
        if cfg.extend_first_phase_to_start:
            first_key = min(phases.keys(), key=lambda k: phases[k]["start_idx"])
            phases[first_key]["start_idx"] = 0
            phases[first_key]["start_date"] = df.loc[0, "date"].strftime("%Y-%m-%d")
        
        if cfg.extend_last_phase_to_end:
            last_key = max(phases.keys(), key=lambda k: phases[k]["end_idx"])
            phases[last_key]["end_idx"] = n - 1
            phases[last_key]["end_date"] = df.loc[n - 1, "date"].strftime("%Y-%m-%d")

    # Build bands for chart shading
    phase_colors = {
        "Accumulation": "rgba(0, 128, 255, 0.20)",
        "Markup": "rgba(0, 200, 120, 0.18)",
        "Distribution": "rgba(255, 165, 0, 0.22)",
        "Markdown": "rgba(255, 80, 80, 0.20)",
    }
    bands: List[Dict[str, Any]] = []
    for key, info in phases.items():
        nm: PhaseName = info["name"]  # type: ignore
        bands.append(
            {
                "name": nm,
                "start": info["start_date"],
                "end": info["end_date"],
                "color": phase_colors.get(nm, "rgba(255,255,255,0.10)"),
            }
        )

    # Per-bar phase label
    per_bar_phase: List[Optional[PhaseName]] = [None] * n
    for info in phases.values():
        nm2: PhaseName = info["name"]  # type: ignore
        for i in range(info["start_idx"], info["end_idx"] + 1):
            per_bar_phase[i] = nm2

    return {
        "events": events,
        "phases": phases,
        "bands": bands,
        "per_bar_phase": per_bar_phase,
    }
