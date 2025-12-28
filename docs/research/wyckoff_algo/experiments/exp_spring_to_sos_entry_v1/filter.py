from __future__ import annotations

import pandas as pd


def _symbol_column(df: pd.DataFrame) -> str:
    if "symbol" in df.columns:
        return "symbol"
    if "ticker" in df.columns:
        return "ticker"
    raise KeyError("Expected a symbol/ticker column in events_df.")


def apply_experiment(events_df: pd.DataFrame, ohlcv_by_symbol: dict, cfg: dict) -> pd.DataFrame:
    """
    SPRING -> SOS sequence experiment.

    Emit SOS events only if preceded by a SPRING within N bars, with optional BC invalidation.
    """
    max_gap = int(cfg.get("spring_to_sos_max_bars", 60))
    use_bc_invalidator = bool(cfg.get("use_bc_invalidator", True))

    df = events_df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"])
    sym_col = _symbol_column(df)

    has_bar_index = "bar_index" in df.columns
    output_rows = []

    for symbol, sym_events in df.groupby(sym_col):
        sym_events = sym_events.copy()
        if not has_bar_index:
            sym_events = sym_events.sort_values("event_date").reset_index(drop=True)
            sym_events["event_order"] = sym_events.index
            idx_col = "event_order"
        else:
            sym_events = sym_events.sort_values("bar_index")
            idx_col = "bar_index"

        springs = sym_events[(sym_events["event"] == "SPRING") & sym_events[idx_col].notna()]
        soses = sym_events[(sym_events["event"] == "SOS") & sym_events[idx_col].notna()]
        bcs = sym_events[(sym_events["event"] == "BC") & sym_events[idx_col].notna()]

        if springs.empty or soses.empty:
            continue

        for _, sos_row in soses.iterrows():
            sos_idx = sos_row[idx_col]
            if pd.isna(sos_idx):
                continue
            sos_idx = int(sos_idx)

            candidates = springs[springs[idx_col] < sos_idx]
            candidates = candidates[candidates[idx_col] >= sos_idx - max_gap]
            if candidates.empty:
                continue
            spring_row = candidates.iloc[-1]
            spring_idx = int(spring_row[idx_col])

            if use_bc_invalidator:
                blocked = bcs[(bcs[idx_col] > spring_idx) & (bcs[idx_col] <= sos_idx)]
                if not blocked.empty:
                    continue

            keep = sos_row.copy()
            keep["matched_spring_bar_index"] = spring_row["bar_index"] if "bar_index" in spring_row else None
            keep["matched_spring_date"] = spring_row.get("event_date")
            keep["bars_since_spring"] = sos_idx - spring_idx if pd.notna(spring_idx) else None
            output_rows.append(keep)

    result = pd.DataFrame(output_rows)
    if not result.empty:
        result = result.sort_values([sym_col, "event_date"]).reset_index(drop=True)
    return result


__all__ = ["apply_experiment"]
