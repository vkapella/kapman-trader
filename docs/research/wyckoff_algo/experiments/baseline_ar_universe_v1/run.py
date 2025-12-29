from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

# -----------------------------------------------------------------------------
# Path wiring
# -----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVE_PATH = REPO_ROOT / "archive"
if str(ARCHIVE_PATH) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_PATH))

WYCKOFF_ROOT = Path(__file__).resolve().parents[2]
if str(WYCKOFF_ROOT) not in sys.path:
    sys.path.insert(0, str(WYCKOFF_ROOT))

EXPERIMENT_ROOT = Path(__file__).resolve().parent
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

from benchmark.run_bench import run_bench
from runner.load_ohlcv import load_ohlcv
from filter import apply_experiment

logger = logging.getLogger(__name__)

CONFIG_PATH = EXPERIMENT_ROOT / "config.yaml"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_output_dir(experiment_id: str) -> Path:
    """
    Centralized output location for all experiments.
    """
    return WYCKOFF_ROOT / "outputs" / experiment_id


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = _load_config()
    experiment_id = cfg.get("experiment_id")
    if not experiment_id:
        raise ValueError("config.yaml must define `experiment_id`")

    output_dir = _resolve_output_dir(experiment_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Load source events
    # -------------------------------------------------------------------------

    source_events_path = (EXPERIMENT_ROOT / cfg["source_events"]).resolve()
    logger.info("Loading source events from %s", source_events_path)
    events_df = pd.read_parquet(source_events_path)

    # -------------------------------------------------------------------------
    # Load OHLCV
    # -------------------------------------------------------------------------

    logger.info("Loading OHLCV data.")
    ohlcv_by_symbol = load_ohlcv()

    # -------------------------------------------------------------------------
    # Apply experiment filter
    # -------------------------------------------------------------------------

    logger.info("Applying experiment filter: %s", experiment_id)
    filtered = apply_experiment(events_df, ohlcv_by_symbol, cfg)

    if filtered.empty:
        logger.warning("No events produced for %s. Exiting.", experiment_id)
        return

    # -------------------------------------------------------------------------
    # Write experiment outputs
    # -------------------------------------------------------------------------

    events_parquet = output_dir / "events.parquet"
    events_csv = output_dir / "events.csv"

    filtered.to_parquet(events_parquet, index=False)
    sort_cols = [c for c in ["symbol", "event_date"] if c in filtered.columns]
    if sort_cols:
        filtered = filtered.sort_values(sort_cols)
    filtered.to_csv(events_csv, index=False)
    logger.info(
        "Wrote %s events to %s (csv=%s)",
        len(filtered),
        events_parquet,
        events_csv,
    )

    # -------------------------------------------------------------------------
    # Run benchmark
    # -------------------------------------------------------------------------

    logger.info("Running benchmark for %s", experiment_id)

    bench_parquet = output_dir / "benchmark_results.parquet"
    bench_csv = output_dir / "benchmark_results.csv"

    run_bench(events_path=events_parquet, output_path=bench_parquet)

    if bench_parquet.exists():
        pd.read_parquet(bench_parquet).to_csv(bench_csv, index=False)

    logger.info(
        "Benchmark complete for %s (parquet=%s, csv=%s)",
        experiment_id,
        bench_parquet,
        bench_csv,
    )


if __name__ == "__main__":
    main()