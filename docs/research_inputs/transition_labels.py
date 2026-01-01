from __future__ import annotations

from typing import List, Tuple

import pandas as pd


_ALLOWED_TRANSITIONS: List[Tuple[str, str]] = [
    ("ACCUMULATION", "MARKUP"),
    ("MARKUP", "DISTRIBUTION"),
    ("DISTRIBUTION", "MARKDOWN"),
    ("MARKDOWN", "ACCUMULATION"),
]


def label_regime_transitions(regime_df: pd.DataFrame, min_prior_bars: int = 5) -> pd.DataFrame:
    """
    Input: per-symbol daily regime labels.
    Output: sparse transition events on the first bar of a new regime.
    """
    columns = ["symbol", "date", "transition", "prior_regime", "new_regime"]
    if regime_df is None or regime_df.empty:
        return pd.DataFrame(columns=columns)

    data = regime_df.copy()
    if "symbol" not in data.columns or "date" not in data.columns or "regime" not in data.columns:
        return pd.DataFrame(columns=columns)

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data["regime"] = data["regime"].astype(str).str.upper()
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)

    min_prior_bars = max(1, int(min_prior_bars))
    transitions: List[dict] = []

    for symbol, group in data.groupby("symbol", sort=False):
        prior_regime = None
        prior_count = 0

        for row in group.itertuples(index=False):
            current_regime = row.regime
            if prior_regime is None:
                prior_regime = current_regime
                prior_count = 1
                continue

            if current_regime == prior_regime:
                prior_count += 1
                continue

            if (
                (prior_regime, current_regime) in _ALLOWED_TRANSITIONS
                and prior_regime != "UNKNOWN"
                and current_regime != "UNKNOWN"
                and prior_count >= min_prior_bars
            ):
                transitions.append(
                    {
                        "symbol": symbol,
                        "date": row.date,
                        "transition": f"{prior_regime}->{current_regime}",
                        "prior_regime": prior_regime,
                        "new_regime": current_regime,
                    }
                )

            prior_regime = current_regime
            prior_count = 1

    return pd.DataFrame(transitions, columns=columns)
