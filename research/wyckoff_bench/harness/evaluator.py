"""
Signal evaluator: forward returns + MAE/MFE summaries for Wyckoff benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd
import json

from .contract import EVENT_ORDER


DEFAULT_HORIZONS: Tuple[int, ...] = (5, 10, 20, 40)
MAE_MFE_WINDOW = 20
DIRECTION_ROLES_PATH = Path(__file__).resolve().parents[1] / "config" / "event_direction_roles.json"


@dataclass
class ForwardMetrics:
    forward_return: float | None
    mae: float | None
    mfe: float | None


def _load_event_role_direction_map(path: Path | str | None = None) -> Dict[str, Dict[str, str]]:
    cfg_path = Path(path) if path else Path(__file__).resolve().parents[1] / "config" / "event_role_direction_map.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_direction_roles(path: Path | str | None = None) -> Dict[str, Dict[str, str]]:
    cfg_path = Path(path) if path else DIRECTION_ROLES_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _directional_adjustment(event: str, direction_roles: Dict[str, Dict[str, str]]) -> Tuple[str | None, str | None]:
    info = direction_roles.get(event.upper())
    if not info:
        return None, None
    return info.get("direction"), info.get("role")


def _compute_forward_metrics(
    df_symbol: pd.DataFrame, idx: int, horizons: Sequence[int]
) -> Dict[int, ForwardMetrics]:
    metrics: Dict[int, ForwardMetrics] = {}
    entry_close = float(df_symbol.iloc[idx]["close"])
    future = df_symbol.iloc[idx + 1 :]

    for horizon in horizons:
        window = future.iloc[:horizon]
        if window.empty:
            metrics[horizon] = ForwardMetrics(None, None, None)
            continue

        terminal_close = float(window.iloc[-1]["close"])
        forward_return = ((terminal_close - entry_close) / entry_close) * 100

        mae_slice = window.iloc[:MAE_MFE_WINDOW]
        mae = None
        mfe = None
        if not mae_slice.empty:
            mae = ((mae_slice["low"].min() - entry_close) / entry_close) * 100
            mfe = ((mae_slice["high"].max() - entry_close) / entry_close) * 100

        metrics[horizon] = ForwardMetrics(forward_return, mae, mfe)

    return metrics


def evaluate_signals(
    signals_df: pd.DataFrame,
    price_df: pd.DataFrame,
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    direction_roles_path: Path | str | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Expand signal records into per-event/horizon metrics and aggregate summaries.
    """
    if signals_df.empty:
        empty = pd.DataFrame(
            columns=["impl", "event", "horizon", "count", "density", "mean_return", "mae_mean", "mfe_mean"]
        )
        return signals_df, empty, empty

    price_by_symbol = {sym: df.reset_index(drop=True) for sym, df in price_df.groupby("symbol")}
    total_bars = sum(len(df) for df in price_by_symbol.values()) or 1
    direction_roles = _load_direction_roles(direction_roles_path)

    eval_rows: List[Dict] = []
    for _, row in signals_df.iterrows():
        symbol = row["symbol"]
        impl = row["impl"]
        sym_df = price_by_symbol.get(symbol)
        if sym_df is None:
            continue
        time_val = pd.Timestamp(row["time"])
        matches = sym_df.index[sym_df["time"] == time_val].tolist()
        if not matches:
            continue
        idx = matches[0]
        forward = _compute_forward_metrics(sym_df, idx, horizons)
        for code in EVENT_ORDER:
            event_flag = bool(row.get(f"event_{code.value.lower()}", False))
            if not event_flag:
                continue
            direction, role = _directional_adjustment(code.value, direction_roles)
            if direction is None or role is None:
                continue
            if direction.upper() == "CONTEXT":
                continue
            for horizon, metrics in forward.items():
                fwd_ret = metrics.forward_return
                mae = metrics.mae
                mfe = metrics.mfe
                if direction.upper() == "DOWN":
                    fwd_ret = -fwd_ret if fwd_ret is not None else None
                    mae = -mae if mae is not None else None
                    mfe = -mfe if mfe is not None else None
                eval_rows.append(
                    {
                        "impl": impl,
                        "symbol": symbol,
                        "time": time_val,
                        "event": code.value,
                        "direction": direction,
                        "role": role,
                        "horizon": horizon,
                        "forward_return": fwd_ret,
                        "mae": mae,
                        "mfe": mfe,
                        "bc_score": row.get("bc_score"),
                        "spring_score": row.get("spring_score"),
                        "composite_score": row.get("composite_score"),
                    }
                )

    evaluated_df = pd.DataFrame(eval_rows)
    if evaluated_df.empty:
        empty = pd.DataFrame(
            columns=["impl", "event", "horizon", "count", "density", "mean_return", "mae_mean", "mfe_mean"]
        )
        return evaluated_df, empty, empty

    agg = (
        evaluated_df.groupby(["impl", "event", "horizon"])
        .agg(
            count=("forward_return", "count"),
            mean_return=("forward_return", "mean"),
            median_return=("forward_return", "median"),
            mae_mean=("mae", "mean"),
            mfe_mean=("mfe", "mean"),
            bc_score_mean=("bc_score", "mean"),
            spring_score_mean=("spring_score", "mean"),
            composite_score_mean=("composite_score", "mean"),
        )
        .reset_index()
    )
    agg["density"] = agg["count"] / total_bars
    directional_agg = (
        evaluated_df.groupby(["impl", "event", "direction", "role", "horizon"])
        .agg(
            signal_count=("forward_return", "count"),
            mean_return=("forward_return", "mean"),
            median_return=("forward_return", "median"),
            mae_mean=("mae", "mean"),
            mfe_mean=("mfe", "mean"),
            bc_score_mean=("bc_score", "mean"),
            spring_score_mean=("spring_score", "mean"),
            composite_score_mean=("composite_score", "mean"),
        )
        .reset_index()
    )
    return evaluated_df, agg, directional_agg


def evaluate_entry_directional(
    signals_df: pd.DataFrame,
    price_df: pd.DataFrame,
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    mapping_path: Path | str | None = None,
    min_count: int = 5,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Entry-only, direction-aware scoring.
    Returns scored per-signal DataFrame and aggregated summary.
    """
    if signals_df.empty:
        empty = pd.DataFrame(
            columns=[
                "impl",
                "event",
                "direction",
                "role",
                "horizon",
                "ret_dir",
                "mae_dir",
                "symbol",
                "time",
            ]
        )
        return empty, empty

    mapping = _load_event_role_direction_map(mapping_path)
    price_by_symbol = {sym: df.reset_index(drop=True) for sym, df in price_df.groupby("symbol")}

    scored_rows: List[Dict] = []

    for _, row in signals_df.iterrows():
        symbol = row["symbol"]
        impl = row["impl"]
        sym_df = price_by_symbol.get(symbol)
        if sym_df is None:
            continue
        time_val = pd.Timestamp(row["time"])
        matches = sym_df.index[sym_df["time"] == time_val].tolist()
        if not matches:
            continue
        idx = matches[0]

        for code in EVENT_ORDER:
            event_flag = bool(row.get(f"event_{code.value.lower()}", False))
            if not event_flag:
                continue

            direction = row.get("direction")
            role = row.get("role")
            if not direction or not role:
                mapped = mapping.get(code.value)
                if mapped:
                    direction = direction or mapped.get("direction")
                    role = role or mapped.get("role")
            if not direction or not role:
                continue
            if role.upper() != "ENTRY":
                continue
            if direction.upper() == "NA" or role.upper() == "IGNORE":
                continue

            entry_close = float(sym_df.iloc[idx]["close"])
            for horizon in horizons:
                window = sym_df.iloc[idx : idx + horizon + 1]
                if window.empty or len(window) < horizon + 1:
                    continue
                terminal_close = float(window.iloc[-1]["close"])

                if direction.upper() == "UP":
                    ret_dir = (terminal_close / entry_close) - 1
                    min_close = float(window["close"].min())
                    mae_dir = (min_close / entry_close) - 1
                else:  # DOWN
                    ret_dir = (entry_close / terminal_close) - 1
                    max_close = float(window["close"].max())
                    mae_dir = (entry_close / max_close) - 1

                scored_rows.append(
                    {
                        "impl": impl,
                        "event": code.value,
                        "direction": direction.upper(),
                        "role": role.upper(),
                        "horizon": horizon,
                        "ret_dir": ret_dir,
                        "mae_dir": mae_dir,
                        "symbol": symbol,
                        "time": time_val,
                    }
                )

    scored_df = pd.DataFrame(scored_rows)
    if scored_df.empty:
        empty = pd.DataFrame(
            columns=[
                "impl",
                "event",
                "direction",
                "role",
                "horizon",
                "mean_ret_dir",
                "median_ret_dir",
                "win_rate",
                "mae_mean_dir",
                "signal_count",
                "ret_p25",
                "ret_p75",
                "composite_rank",
            ]
        )
        return scored_df, empty

    summary = (
        scored_df.groupby(["impl", "event", "direction", "role", "horizon"])
        .agg(
            mean_ret_dir=("ret_dir", "mean"),
            median_ret_dir=("ret_dir", "median"),
            win_rate=("ret_dir", lambda x: (x > 0).mean() if len(x) else 0),
            mae_mean_dir=("mae_dir", "mean"),
            signal_count=("ret_dir", "count"),
            ret_p25=("ret_dir", lambda x: x.quantile(0.25)),
            ret_p75=("ret_dir", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )

    eligible = summary["signal_count"] >= min_count
    summary["composite_rank"] = None
    if eligible.any():
        rankable = summary[eligible].copy()
        rankable["rank_ret"] = rankable["mean_ret_dir"].rank(ascending=False, method="min")
        rankable["rank_win"] = rankable["win_rate"].rank(ascending=False, method="min")
        rankable["rank_mae"] = rankable["mae_mean_dir"].rank(ascending=False, method="min")
        rankable["composite_rank"] = (rankable["rank_ret"] + rankable["rank_win"] + rankable["rank_mae"]) / 3
        summary.loc[eligible, "composite_rank"] = rankable["composite_rank"].values

    return scored_df, summary
