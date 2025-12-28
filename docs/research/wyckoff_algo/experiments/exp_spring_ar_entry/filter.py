from __future__ import annotations

import pandas as pd


def apply_experiment(
    events_df: pd.DataFrame,
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    config: dict,
) -> pd.DataFrame:
    """
    Keep AR events that occur shortly after a SPRING for the same symbol.
    - Finds the first AR after each SPRING within spring_to_ar_max_bars.
    - Emits only the AR rows (ENTRY/UP).
    """
    max_gap = int(config.get("spring_to_ar_max_bars", 15))
    experiment_id = config.get("experiment_id", "exp_spring_ar_entry_v1")

    events_df = events_df.copy()
    events_df["event_date"] = pd.to_datetime(events_df["event_date"])

    filtered_rows = []

    for symbol, events_symbol in events_df.groupby("symbol"):
        events_symbol = events_symbol.sort_values("bar_index")
        springs = events_symbol[
            (events_symbol["event"] == "SPRING") & events_symbol["bar_index"].notna()
        ]
        ars = events_symbol[
            (events_symbol["event"] == "AR") & events_symbol["bar_index"].notna()
        ]
        if springs.empty or ars.empty:
            continue

        matched_ar_indices: set[int] = set()
        for _, spring_row in springs.iterrows():
            spring_idx = int(spring_row["bar_index"])
            window_end = spring_idx + max_gap
            candidates = ars[
                (ars["bar_index"] > spring_idx)
                & (ars["bar_index"] <= window_end)
                & (~ars.index.isin(matched_ar_indices))
            ]
            if candidates.empty:
                continue
            ar_row = candidates.iloc[0]
            matched_ar_indices.add(ar_row.name)

            keep = ar_row.copy()
            keep["direction"] = "UP"
            keep["role"] = "ENTRY"
            keep["experiment_id"] = experiment_id
            filtered_rows.append(keep)

    result = pd.DataFrame(filtered_rows)
    if not result.empty:
        result = result.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    return result


__all__ = ["apply_experiment"]
