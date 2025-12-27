from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Make archived research harness importable (benchmark math/evaluator).
REPO_ROOT = Path(__file__).resolve().parents[4]
ARCHIVE_PATH = REPO_ROOT / "archive"
if str(ARCHIVE_PATH) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_PATH))

# Allow direct imports from docs/research/wyckoff_algo without package execution.
WYCKOFF_ROOT = Path(__file__).resolve().parents[1]
if str(WYCKOFF_ROOT) not in sys.path:
    sys.path.insert(0, str(WYCKOFF_ROOT))

from research.wyckoff_bench.harness import evaluator
from research.wyckoff_bench.harness.contract import EVENT_ORDER

from runner import load_ohlcv

logger = logging.getLogger(__name__)

EVENTS_PATH = Path(__file__).resolve().parents[1] / "outputs" / "events.parquet"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "benchmark_results.parquet"


def _precompute_ta(df: pd.DataFrame) -> pd.DataFrame:
    """Clone of the research harness TA precomputation for parity."""
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    df["rsi_14"] = rsi.fillna(50.0).astype("float64")

    plus_dm = (high.diff().where(lambda x: x > low.diff(), 0)).fillna(0.0)
    minus_dm = (low.diff().where(lambda x: x > high.diff(), 0) * -1).fillna(0.0)
    tr_components = pd.concat(
        [(high - low).abs(), (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx = dx.ewm(alpha=1 / 14, adjust=False, min_periods=1).mean()
    df["adx_14"] = adx.fillna(20.0).astype("float64")

    df["atr_14"] = atr.fillna(0.0).astype("float64")
    df["vol_ma_20"] = volume.rolling(20, min_periods=1).mean().fillna(0.0).astype("float64")
    return df


def _load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Events parquet not found: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise RuntimeError("Events parquet is empty; cannot run benchmark.")

    df["time"] = pd.to_datetime(df.get("time", df.get("event_date")))
    if "impl" not in df.columns:
        df["impl"] = "kapman_v0_handwritten_structural"

    # Ensure event flag columns exist for evaluator compatibility.
    for code in EVENT_ORDER:
        col = f"event_{code.value.lower()}"
        if col not in df.columns:
            if "event" in df.columns:
                df[col] = df["event"].str.upper() == code.value
            else:
                df[col] = False

    for col in ["bc_score", "spring_score", "composite_score"]:
        if col not in df.columns:
            df[col] = 0.0

    return df


def _prepare_price_df(ohlcv_map: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for sym, df_sym in ohlcv_map.items():
        df_sym = df_sym.copy()
        df_sym["symbol"] = sym
        df_sym["time"] = pd.to_datetime(df_sym["time"])
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_sym.columns:
                df_sym[col] = pd.to_numeric(df_sym[col], errors="coerce")
        frames.append(df_sym)
    price_df = pd.concat(frames, ignore_index=True)
    price_df = price_df.sort_values(["symbol", "time"]).reset_index(drop=True)

    enriched: List[pd.DataFrame] = []
    for sym, df_sym in price_df.groupby("symbol"):
        enriched.append(_precompute_ta(df_sym.reset_index(drop=True)))
    return pd.concat(enriched, ignore_index=True)


def _print_console_summary(summary_df: pd.DataFrame) -> None:
    if summary_df.empty:
        print("No benchmark rows produced.")
        return
    cols = ["impl", "event", "horizon", "count", "density", "mean_return", "mae_mean"]
    display = summary_df[cols].sort_values(["event", "horizon"])
    fmt = {
        "density": lambda x: f"{x:.6f}",
        "mean_return": lambda x: f"{x: .2f}",
        "mae_mean": lambda x: f"{x: .2f}",
    }
    print("\nBenchmark summary (kapman_v0_handwritten_structural):")
    print(display.to_string(index=False, formatters=fmt))


def run_bench(
    events_path: Path = EVENTS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    """Reuse original benchmark math over precomputed events + dev DB OHLCV."""
    events_df = _load_events(events_path)
    ohlcv_map = load_ohlcv()
    if not ohlcv_map:
        raise RuntimeError("No OHLCV data available; aborting benchmark.")

    price_df = _prepare_price_df(ohlcv_map)
    evaluated_df, summary_df, directional_summary_df = evaluator.evaluate_signals(events_df, price_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_parquet(output_path, index=False)
    summary_df.sort_values(["event", "horizon"]).to_csv(
        output_path.with_suffix(".csv"),
        index=False,
    )

    logger.info(
        "Benchmark complete. signals=%s price_rows=%s summary_rows=%s -> %s",
        len(events_df),
        len(price_df),
        len(summary_df),
        output_path,
    )
    _print_console_summary(summary_df)
    return summary_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_bench()
