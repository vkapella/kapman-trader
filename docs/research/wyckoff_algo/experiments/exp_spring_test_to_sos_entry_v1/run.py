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
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "exp_spring_test_to_sos_entry_v1"


def _load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = _load_config()
    experiment_id = cfg.get("experiment_id", "unknown_experiment")

    source_events_path = (Path(__file__).resolve().parent / cfg["source_events"]).resolve()
    logger.info("Loading raw events from %s", source_events_path)
    events_df = pd.read_parquet(source_events_path)

    logger.info("Loading OHLCV data.")
    ohlcv_by_symbol = load_ohlcv()

    logger.info("Applying SPRING -> TEST -> SOS experiment filter.")
    filtered = apply_experiment(events_df, ohlcv_by_symbol, cfg)

    if filtered.empty:
        logger.warning("No events produced for %s. Exiting.", experiment_id)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events_out_parquet = OUTPUT_DIR / f"events_{experiment_id}.parquet"
    events_out_csv = OUTPUT_DIR / f"events_{experiment_id}.csv"

    filtered.to_parquet(events_out_parquet, index=False)

    if "symbol" in filtered.columns:
        id_col = "symbol"
    elif "ticker" in filtered.columns:
        id_col = "ticker"
    else:
        id_col = None
    sort_cols = [id_col, "event_date"] if id_col else ["event_date"]
    filtered.sort_values(sort_cols).to_csv(events_out_csv, index=False)

    logger.info(
        "Wrote %s events to %s (csv=%s)",
        len(filtered),
        events_out_parquet,
        events_out_csv,
    )

    logger.info("Running benchmark for %s.", experiment_id)

    bench_parquet = OUTPUT_DIR / f"benchmark_results_{experiment_id}.parquet"
    bench_csv = OUTPUT_DIR / f"benchmark_results_{experiment_id}.csv"

    run_bench(events_path=events_out_parquet, output_path=bench_parquet)

    if bench_parquet.exists():
        pd.read_parquet(bench_parquet).to_csv(bench_csv, index=False)

    logger.info(
        "Benchmark complete for %s (parquet=%s, csv=%s).",
        experiment_id,
        bench_parquet,
        bench_csv,
    )


if __name__ == "__main__":
    main()
