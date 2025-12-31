from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from . import structural


def run_baseline_structural(
    df: pd.DataFrame, symbol: str, cfg: Optional[Any] = None
) -> pd.DataFrame:
    result = structural.detect_structural_wyckoff(df, cfg)
    events: List[Dict[str, Any]] = result.get("events", [])

    rows: List[Dict[str, Any]] = []
    for ev in events:
        rows.append(
            {
                "symbol": symbol,
                "date": ev.get("date"),
                "event": ev.get("label"),
                "score": ev.get("score"),
            }
        )

    events_df = pd.DataFrame(rows, columns=["symbol", "date", "event", "score"])
    return events_df
