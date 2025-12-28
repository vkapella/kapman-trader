from __future__ import annotations

import pandas as pd


def apply_experiment(events_df: pd.DataFrame, ohlcv_by_symbol: dict, cfg: dict) -> pd.DataFrame:
    """
    AR → SOS sequence experiment.

    Emits SOS events only if preceded by an AR within a fixed lookback window.
    Preserves the original event schema EXACTLY.
    """

    # Detect identifier column once
    if "symbol" in events_df.columns:
        id_col = "symbol"
    elif "ticker" in events_df.columns:
        id_col = "ticker"
    else:
        raise ValueError("events_df must contain either 'symbol' or 'ticker' column")

    max_bars = int(cfg.get("ar_to_sos_max_bars", 40))
    use_bc = bool(cfg.get("use_bc_invalidator", True))

    accepted_rows = []

    for ident, df in events_df.groupby(id_col):
        if "bar_index" in df.columns:
            df = df.sort_values("bar_index")
        else:
            df = df.sort_values("event_date")

        ars = df[df["event"] == "AR"]
        soss = df[df["event"] == "SOS"]
        bcs = df[df["event"] == "BC"] if use_bc else pd.DataFrame()

        if ars.empty or soss.empty:
            continue

        for _, sos in soss.iterrows():
            sos_bar = sos["bar_index"]

            prior_ars = ars[
                (ars["bar_index"] < sos_bar) &
                (ars["bar_index"] >= sos_bar - max_bars)
            ]

            if prior_ars.empty:
                continue

            ar = prior_ars.iloc[-1]

            if use_bc and not bcs.empty:
                invalid_bc = bcs[
                    (bcs["bar_index"] > ar["bar_index"]) &
                    (bcs["bar_index"] <= sos_bar)
                ]
                if not invalid_bc.empty:
                    continue

            row = sos.copy()
            row["matched_ar_bar_index"] = ar["bar_index"]
            row["matched_ar_date"] = ar["event_date"]
            row["bars_since_ar"] = sos_bar - ar["bar_index"]

            accepted_rows.append(row)

    return pd.DataFrame(accepted_rows)