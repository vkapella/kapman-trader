from __future__ import annotations

import pandas as pd


def _id_column(df: pd.DataFrame) -> str:
    if "symbol" in df.columns:
        return "symbol"
    if "ticker" in df.columns:
        return "ticker"
    raise KeyError("Expected symbol or ticker column in events_df.")


def apply_experiment(events_df: pd.DataFrame, ohlcv_by_symbol: dict, cfg: dict) -> pd.DataFrame:
    """
    SPRING -> TEST -> SOS sequence experiment.
    Returns accepted SOS rows with minimal metadata added.
    """
    spring_to_test_max = int(cfg.get("spring_to_test_max_bars", 30))
    test_to_sos_max = int(cfg.get("test_to_sos_max_bars", 30))
    spring_to_sos_max = int(cfg.get("spring_to_sos_max_bars", 80))
    test_event_names = cfg.get("test_event_names", ["TEST"]) or ["TEST"]
    use_bc_invalidator = bool(cfg.get("use_bc_invalidator", True))

    df = events_df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"])
    id_col = _id_column(df)

    has_bar_index = "bar_index" in df.columns
    results = []

    for symbol, sym_events in df.groupby(id_col):
        sym_events = sym_events.copy()
        if has_bar_index:
            sym_events = sym_events.sort_values("bar_index")
            idx_col = "bar_index"
        else:
            sym_events = sym_events.sort_values("event_date").reset_index(drop=True)
            sym_events["order_index"] = sym_events.index
            idx_col = "order_index"

        sos_events = sym_events[(sym_events["event"] == "SOS") & sym_events[idx_col].notna()]
        test_events = sym_events[sym_events["event"].isin(test_event_names) & sym_events[idx_col].notna()]
        spring_events = sym_events[(sym_events["event"] == "SPRING") & sym_events[idx_col].notna()]
        bc_events = sym_events[(sym_events["event"] == "BC") & sym_events[idx_col].notna()]

        if sos_events.empty or test_events.empty or spring_events.empty:
            continue

        for _, sos_row in sos_events.iterrows():
            sos_idx = sos_row[idx_col]
            if pd.isna(sos_idx):
                continue
            sos_idx = int(sos_idx)

            tests = test_events[(test_events[idx_col] < sos_idx) & ((sos_idx - test_events[idx_col]) <= test_to_sos_max)]
            if tests.empty:
                continue
            test_row = tests.iloc[-1]
            test_idx = int(test_row[idx_col])

            springs = spring_events[
                (spring_events[idx_col] < test_idx)
                & ((test_idx - spring_events[idx_col]) <= spring_to_test_max)
                & ((sos_idx - spring_events[idx_col]) <= spring_to_sos_max)
            ]
            if springs.empty:
                continue
            spring_row = springs.iloc[-1]
            spring_idx = int(spring_row[idx_col])

            if use_bc_invalidator:
                blocked = bc_events[(bc_events[idx_col] > spring_idx) & (bc_events[idx_col] <= sos_idx)]
                if not blocked.empty:
                    continue

            keep = sos_row.copy()
            keep["matched_spring_bar_index"] = spring_row["bar_index"] if "bar_index" in spring_row else None
            keep["matched_spring_date"] = spring_row.get("event_date")
            keep["matched_test_bar_index"] = test_row["bar_index"] if "bar_index" in test_row else None
            keep["matched_test_date"] = test_row.get("event_date")
            keep["bars_since_spring"] = sos_idx - spring_idx
            keep["bars_since_test"] = sos_idx - test_idx
            results.append(keep)

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        sort_cols = [id_col, "event_date"] if id_col in result_df.columns else ["event_date"]
        result_df = result_df.sort_values(sort_cols).reset_index(drop=True)
    return result_df


__all__ = ["apply_experiment"]
