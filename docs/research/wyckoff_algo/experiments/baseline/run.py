from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

# Allow imports from archive research harness and local runner.
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

from benchmark.run_bench import run_bench
from runner.load_ohlcv import load_ohlcv

from filter import apply_experiment

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "baseline"


def _load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = _load_config()

    source_events_path = (Path(__file__).resolve().parent / cfg["source_events"]).resolve()
    logger.info("Loading baseline events from %s", source_events_path)
    events_df = pd.read_parquet(source_events_path)

    logger.info("Loading OHLCV from dev DB via existing loader.")
    ohlcv_by_symbol = load_ohlcv()

    logger.info("Applying Qualified AR experiment filter.")
    filtered = apply_experiment(events_df, ohlcv_by_symbol, cfg)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events_out_parquet = OUTPUT_DIR / "events.parquet"
    events_out_csv = OUTPUT_DIR / "events.csv"
    filtered.to_parquet(events_out_parquet, index=False)
    filtered.sort_values(["symbol", "event_date"]).to_csv(events_out_csv, index=False)
    logger.info("Wrote %s qualified events to %s (csv=%s)", len(filtered), events_out_parquet, events_out_csv)

    logger.info("Running benchmark on qualified events.")
    bench_parquet = OUTPUT_DIR / "benchmark_results.parquet"
    run_bench(events_path=events_out_parquet, output_path=bench_parquet)
    logger.info("Benchmark complete for experiment output.")


if __name__ == "__main__":
    main()
