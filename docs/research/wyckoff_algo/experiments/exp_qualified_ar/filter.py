from __future__ import annotations

import numpy as np
import pandas as pd


def _atr_series(df: pd.DataFrame, window: int) -> pd.Series:
    """Compute rolling ATR for a symbol."""
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    tr_components = pd.concat(
        [
            (high - low).abs(),
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    atr = tr.rolling(window, min_periods=window).mean()
    return atr


def _percentile_rank_series(values: pd.Series) -> pd.Series:
    """Expanding percentile rank using only historical values (no lookahead)."""
    arr = values.to_numpy()
    out = np.full_like(arr, np.nan, dtype="float64")
    for idx, val in enumerate(arr):
        if np.isnan(val):
            continue
        window = arr[: idx + 1]
        window = window[~np.isnan(window)]
        if window.size == 0:
            continue
        pct = (window <= val).sum() / window.size * 100.0
        out[idx] = pct
    return pd.Series(out, index=values.index)


def _structural_ok(events_symbol: pd.DataFrame, bar_idx: int, lookback: int) -> bool:
    """Check for prior SC or SPRING within lookback bars."""
    window_start = bar_idx - lookback
    prior = events_symbol[
        (events_symbol["bar_index"].notna())
        & (events_symbol["bar_index"] >= window_start)
        & (events_symbol["bar_index"] < bar_idx)
        & (events_symbol["event"].isin(["SC", "SPRING"]))
    ]
    return not prior.empty


def apply_experiment(
    events_df: pd.DataFrame,
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    config: dict,
) -> pd.DataFrame:
    """
    Filter AR events that meet structural + ATR percentile qualifications.
    """
    lookback_bars = int(config.get("lookback_bars", 20))
    atr_lookback = int(config.get("atr_lookback", 14))
    atr_percentile_min = float(config.get("atr_percentile_min", 50))
    experiment_id = config.get("experiment_id", "exp_qualified_ar_v1")

    events_df = events_df.copy()
    events_df["event_date"] = pd.to_datetime(events_df["event_date"])

    qualified_rows = []

    for symbol, events_symbol in events_df.groupby("symbol"):
        events_symbol = events_symbol.sort_values("bar_index")
        ohlcv = ohlcv_by_symbol.get(symbol)
        if ohlcv is None or ohlcv.empty:
            continue

        atr = _atr_series(ohlcv.reset_index(drop=True), atr_lookback)
        atr_pct = _percentile_rank_series(atr)

        for _, row in events_symbol.iterrows():
            if row.get("event") != "AR":
                continue
            bar_idx = row.get("bar_index")
            if pd.isna(bar_idx):
                continue
            bar_idx = int(bar_idx)
            if not _structural_ok(events_symbol, bar_idx, lookback_bars):
                continue
            atr_value = atr_pct.iloc[bar_idx] if bar_idx < len(atr_pct) else np.nan
            if pd.isna(atr_value) or atr_value < atr_percentile_min:
                continue

            qualified = row.copy()
            qualified["experiment_id"] = experiment_id
            qualified_rows.append(qualified)

    result = pd.DataFrame(qualified_rows)
    if not result.empty:
        result = result.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    return result


__all__ = ["apply_experiment"]
