from __future__ import annotations

import pandas as pd


def apply_experiment(events_df: pd.DataFrame, ohlcv_by_symbol: dict, cfg: dict) -> pd.DataFrame:
    """
    Baseline SOS experiment:
    - Return all SOS events
    - No filtering, no sequencing
    """
    filtered = events_df.copy()
    filtered = filtered[filtered["event"] == "SOS"]
    filtered = filtered.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    return filtered


__all__ = ["apply_experiment"]
