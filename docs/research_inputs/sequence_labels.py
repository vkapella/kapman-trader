from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd


_SEQUENCES = {
    "SEQ_ACCUM_BREAKOUT": ["SC", "AR", "SPRING", "SOS"],
    "SEQ_DISTRIBUTION_TOP": ["BC", "AR_TOP"],
    "SEQ_MARKDOWN_START": ["BC", "AR_TOP", "SOW"],
    "SEQ_FAILED_ACCUM": ["SC", "AR", "SPRING"],
    "SEQ_RECOVERY": ["SOW", "SC"],
}


def _find_sequence_positions(
    events: List[Tuple[pd.Timestamp, str]], pattern: List[str], max_gap: int
) -> List[int]:
    positions: List[int] = []
    i = 0
    max_gap = max(1, int(max_gap))

    while i < len(events):
        start_date, start_event = events[i]
        if start_event != pattern[0]:
            i += 1
            continue

        current_idx = i
        valid = True
        for step in pattern[1:]:
            j = current_idx + 1
            while j < len(events) and events[j][1] != step:
                j += 1
            if j >= len(events):
                valid = False
                break
            if (events[j][0] - start_date).days > max_gap:
                valid = False
                break
            current_idx = j

        if valid:
            positions.append(current_idx)
            i = current_idx + 1
        else:
            i += 1

    return positions


def _find_failed_accum_positions(
    events: List[Tuple[pd.Timestamp, str]], max_gap: int
) -> List[int]:
    positions: List[int] = []
    i = 0
    max_gap = max(1, int(max_gap))

    while i < len(events):
        start_date, start_event = events[i]
        if start_event != "SC":
            i += 1
            continue

        ar_idx = None
        for j in range(i + 1, len(events)):
            if events[j][1] == "AR":
                ar_idx = j
                break
        if ar_idx is None or (events[ar_idx][0] - start_date).days > max_gap:
            i += 1
            continue

        spring_idx = None
        for j in range(ar_idx + 1, len(events)):
            if events[j][1] == "SPRING":
                spring_idx = j
                break
        if spring_idx is None or (events[spring_idx][0] - start_date).days > max_gap:
            i += 1
            continue

        has_sos = False
        for j in range(spring_idx + 1, len(events)):
            if (events[j][0] - start_date).days > max_gap:
                break
            if events[j][1] == "SOS":
                has_sos = True
                break

        if not has_sos:
            positions.append(spring_idx)

        i = spring_idx + 1

    return positions


def label_event_sequences(
    events_df: pd.DataFrame,
    max_gap_default: int = 30,
    max_gap_map: Optional[Dict[str, int]] = None,
    disabled_sequences: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Emits sequence completion events when ordered patterns occur within a rolling window.
    """
    columns = ["symbol", "date", "sequence_id"]
    if events_df is None or events_df.empty:
        return pd.DataFrame(columns=columns)

    data = events_df.copy()
    if "symbol" not in data.columns or "date" not in data.columns or "event" not in data.columns:
        return pd.DataFrame(columns=columns)

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data["event"] = data["event"].astype(str).str.upper()
    data["_order"] = range(len(data))
    data = data.sort_values(["symbol", "date", "_order"]).reset_index(drop=True)

    rows: List[dict] = []

    max_gap_default = max(1, int(max_gap_default))
    gap_map = {}
    if isinstance(max_gap_map, dict):
        gap_map = {str(k).upper(): max(1, int(v)) for k, v in max_gap_map.items() if v is not None}
    disabled = {str(seq).upper() for seq in (disabled_sequences or [])}

    for symbol, group in data.groupby("symbol", sort=False):
        events = list(zip(group["date"].tolist(), group["event"].tolist()))

        for sequence_id, pattern in _SEQUENCES.items():
            if sequence_id in disabled:
                continue
            sequence_max_gap = gap_map.get(sequence_id, max_gap_default)
            if sequence_id == "SEQ_FAILED_ACCUM":
                positions = _find_failed_accum_positions(events, sequence_max_gap)
            else:
                positions = _find_sequence_positions(events, pattern, sequence_max_gap)

            for idx in positions:
                rows.append(
                    {
                        "symbol": symbol,
                        "date": events[idx][0],
                        "sequence_id": sequence_id,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=columns)

    result = pd.DataFrame(rows, columns=columns)
    return result.sort_values(["symbol", "date", "sequence_id"]).reset_index(drop=True)
