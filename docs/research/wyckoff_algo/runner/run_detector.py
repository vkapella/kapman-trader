from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Ensure archive research package (benchmark contract/evaluator) is importable.
REPO_ROOT = Path(__file__).resolve().parents[4]
ARCHIVE_PATH = REPO_ROOT / "archive"
if str(ARCHIVE_PATH) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_PATH))

# Allow direct imports from docs/research/wyckoff_algo without package execution.
WYCKOFF_ROOT = Path(__file__).resolve().parents[1]
if str(WYCKOFF_ROOT) not in sys.path:
    sys.path.insert(0, str(WYCKOFF_ROOT))

RESEARCH_INPUTS = REPO_ROOT / "docs" / "research_inputs"
if str(RESEARCH_INPUTS) not in sys.path:
    sys.path.insert(0, str(RESEARCH_INPUTS))

from research.wyckoff_bench.harness.contract import EVENT_ORDER, signal_rows
from research.wyckoff_bench.harness.evaluator import _load_event_role_direction_map

from legacy.kapman_v0_handwritten_structural import KapmanV0HandwrittenStructural
from runner.load_ohlcv import load_ohlcv

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events.parquet"
OUTPUT_CSV_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events.csv"
OUTPUT_TIMELINE_CSV_PATH = Path(__file__).resolve().parents[1] / "outputs" / "raw" / "events_timeline.csv"


def _enrich_rows(
    raw_rows: List[Dict],
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    role_map: Dict[str, Dict[str, str]],
) -> List[Dict]:
    """Add event metadata required by downstream benchmarking."""
    enriched: List[Dict] = []
    for row in raw_rows:
        time_val = pd.to_datetime(row.get("time"))
        symbol = row.get("symbol")

        event_code = None
        for code in EVENT_ORDER:
            if bool(row.get(f"event_{code.value.lower()}", False)):
                event_code = code.value
                break
        if not event_code:
            continue

        df_sym = ohlcv_by_symbol.get(symbol)
        bar_index = None
        if df_sym is not None:
            matches = df_sym.index[df_sym["time"] == time_val].tolist()
            if matches:
                bar_index = int(matches[0])

        role_info = role_map.get(event_code, {})
        direction = row.get("direction") or role_info.get("direction")
        role = row.get("role") or role_info.get("role")

        enriched.append(
            {
                **row,
                "event": event_code,
                "direction": direction,
                "role": role,
                "event_date": time_val,
                "bar_index": bar_index,
                "impl": row.get("impl") or "kapman_v0_handwritten_structural",
            }
        )
    return enriched


def run_detector(output_path: Path = OUTPUT_PATH) -> pd.DataFrame:
    """Execute the legacy handwritten detector across the watchlist."""
    ohlcv_by_symbol = load_ohlcv()
    if not ohlcv_by_symbol:
        raise RuntimeError("No OHLCV data loaded; aborting detector run.")

    impl = KapmanV0HandwrittenStructural()
    role_map = _load_event_role_direction_map()

    all_rows: List[Dict] = []
    for symbol, df_sym in ohlcv_by_symbol.items():
        signals = impl.analyze(df_sym, cfg={})
        base_rows = signal_rows(signals, impl.name)
        enriched = _enrich_rows(base_rows, ohlcv_by_symbol, role_map)
        all_rows.extend(enriched)
        logger.info("Detected %s events for %s", len(enriched), symbol)

    events_df = pd.DataFrame(all_rows)
    events_df = events_df.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Parquet (existing behavior).
    events_df.to_parquet(output_path, index=False)

    # CSV mirror for chart inspection.
    csv_cols = ["symbol", "event", "direction", "role", "event_date", "bar_index", "impl"]
    events_df[csv_cols].to_csv(OUTPUT_CSV_PATH, index=False)

    # Timeline CSV (lightweight chart helper).
    timeline_cols = ["symbol", "event_date", "event", "direction", "role"]
    events_df[timeline_cols].to_csv(OUTPUT_TIMELINE_CSV_PATH, index=False)

    logger.info(
        "Wrote %s events to %s (csv=%s, timeline=%s)",
        len(events_df),
        output_path,
        OUTPUT_CSV_PATH,
        OUTPUT_TIMELINE_CSV_PATH,
    )

    return events_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_detector()
