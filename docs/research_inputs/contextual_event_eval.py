from __future__ import annotations

from typing import List, Optional

import pandas as pd


def attach_prior_regime(
    events_df: pd.DataFrame,
    regime_df: pd.DataFrame,
    lookback: int = 1,
    events: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Adds prior_regime column to each event (optionally filtered by event type).
    """
    columns = ["symbol", "date", "event", "prior_regime"]
    if events_df is None or events_df.empty:
        return pd.DataFrame(columns=columns)

    data = events_df.copy()
    if "symbol" not in data.columns or "date" not in data.columns or "event" not in data.columns:
        return pd.DataFrame(columns=columns)

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data["event"] = data["event"].astype(str).str.upper()
    if events is None:
        events = ["SOS", "SOW", "BC", "SPRING"]
    allowed_events = {str(event).upper() for event in events}
    data = data[data["event"].isin(allowed_events)]
    if data.empty:
        return pd.DataFrame(columns=columns)

    if regime_df is None or regime_df.empty:
        data["prior_regime"] = pd.NA
        return data.reindex(columns=columns)

    regimes = regime_df.copy()
    if "symbol" not in regimes.columns or "date" not in regimes.columns or "regime" not in regimes.columns:
        data["prior_regime"] = pd.NA
        return data.reindex(columns=columns)

    regimes["date"] = pd.to_datetime(regimes["date"], errors="coerce")
    regimes = regimes.dropna(subset=["date"])
    regimes["regime"] = regimes["regime"].astype(str).str.upper()
    regimes = regimes.sort_values(["symbol", "date"]).reset_index(drop=True)

    lookback = max(1, int(lookback))
    regimes["prior_regime"] = regimes.groupby("symbol", sort=False)["regime"].shift(lookback)
    prior_regimes = regimes[["symbol", "date", "prior_regime"]]

    merged = data.merge(prior_regimes, on=["symbol", "date"], how="left")
    return merged.reindex(columns=columns)
