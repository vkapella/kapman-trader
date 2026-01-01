from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def add_forward_returns_daily(price_df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    data = price_df.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.sort_values("date").reset_index(drop=True)

    for window in sorted({int(w) for w in windows}):
        data[f"fwd_{window}"] = data["close"].shift(-window) / data["close"] - 1.0

    cols = ["date"] + [c for c in data.columns if c.startswith("fwd_")]
    if "symbol" in data.columns:
        cols = ["symbol"] + cols

    return data[cols]


def summarize_regimes(regime_daily_df: pd.DataFrame, daily_fwd_df: pd.DataFrame) -> pd.DataFrame:
    if regime_daily_df is None or daily_fwd_df is None or regime_daily_df.empty or daily_fwd_df.empty:
        return pd.DataFrame(columns=["regime", "window", "count", "median", "win_rate", "p5"])

    join_cols = ["date"]
    if "symbol" in regime_daily_df.columns and "symbol" in daily_fwd_df.columns:
        join_cols = ["symbol", "date"]

    merged = regime_daily_df.merge(daily_fwd_df, on=join_cols, how="inner")
    fwd_cols = [c for c in merged.columns if c.startswith("fwd_")]

    rows = []
    for col in sorted(fwd_cols, key=lambda x: int(x.split("_")[1])):
        window = int(col.split("_")[1])
        for regime, grp in merged.groupby("regime", sort=False):
            vals = grp[col].dropna()
            rows.append(
                {
                    "regime": regime,
                    "window": window,
                    "count": int(vals.shape[0]),
                    "median": vals.median() if not vals.empty else np.nan,
                    "win_rate": (vals > 0).mean() if not vals.empty else np.nan,
                    "p5": vals.quantile(0.05) if not vals.empty else np.nan,
                }
            )

    return pd.DataFrame(rows)


def pairwise_vs_baseline(
    summary_df: pd.DataFrame, baseline_regime: str = "UNKNOWN"
) -> pd.DataFrame:
    if summary_df is None or summary_df.empty:
        return pd.DataFrame(columns=["regime", "window", "baseline_regime", "median_delta", "win_rate_delta", "p5_delta"])

    baseline = summary_df[summary_df["regime"] == baseline_regime].set_index("window")
    rows = []

    for _, row in summary_df.iterrows():
        base = baseline.loc[row["window"]] if row["window"] in baseline.index else None
        if base is None or base.empty:
            median_delta = np.nan
            win_rate_delta = np.nan
            p5_delta = np.nan
        else:
            median_delta = row["median"] - base["median"]
            win_rate_delta = row["win_rate"] - base["win_rate"]
            p5_delta = row["p5"] - base["p5"]

        rows.append(
            {
                "regime": row["regime"],
                "window": int(row["window"]),
                "baseline_regime": baseline_regime,
                "median_delta": median_delta,
                "win_rate_delta": win_rate_delta,
                "p5_delta": p5_delta,
            }
        )

    return pd.DataFrame(rows)
