from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .metrics import EvalMetrics

@dataclass
class RunMetadata:
    start_date: str
    end_date: str
    git_sha: str
    run_timestamp: str


SUMMARY_METRICS = [
    ("density", 20),
    ("median_fwd_20", 20),
    ("win_rate_20", 20),
    ("p5_fwd_20", 20),
    ("stability_delta", 20),
]


def _read_csv(path: Path, metrics: Optional[EvalMetrics] = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if metrics is not None:
            metrics.tick_rows(len(df))
        return df
    except Exception:
        return pd.DataFrame()


def _extract_metadata(df: pd.DataFrame) -> Optional[RunMetadata]:
    if df is None or df.empty:
        return None
    cols = {"start_date", "end_date", "git_sha", "run_timestamp"}
    if not cols.issubset(set(df.columns)):
        return None
    row = df.iloc[0]
    return RunMetadata(
        start_date=str(row["start_date"]),
        end_date=str(row["end_date"]),
        git_sha=str(row["git_sha"]),
        run_timestamp=str(row["run_timestamp"]),
    )


def _add_metadata(df: pd.DataFrame, meta: Optional[RunMetadata]) -> pd.DataFrame:
    if meta is None:
        return df
    data = df.copy()
    data["start_date"] = meta.start_date
    data["end_date"] = meta.end_date
    data["git_sha"] = meta.git_sha
    data["run_timestamp"] = meta.run_timestamp
    return data


def _event_col(df: pd.DataFrame) -> str:
    if "event" in df.columns:
        return "event"
    if "sequence_id" in df.columns:
        return "sequence_id"
    if "transition" in df.columns:
        return "transition"
    return "event"


def _forward_stats(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["dataset", "detector", "event_type", "horizon", "median", "win_rate"])

    event_col = _event_col(df)
    if event_col not in df.columns:
        return pd.DataFrame(columns=["dataset", "detector", "event_type", "horizon", "median", "win_rate"])

    if "detector" not in df.columns:
        df = df.copy()
        df["detector"] = "baseline"

    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    rows = []
    grouped = df.groupby(["detector", event_col], dropna=False)
    for (detector, event_val), grp in grouped:
        for col in fwd_cols:
            horizon = int(col.split("_")[1])
            vals = grp[col].dropna()
            rows.append(
                {
                    "dataset": dataset,
                    "detector": detector,
                    "event_type": event_val,
                    "horizon": horizon,
                    "median": vals.median() if not vals.empty else pd.NA,
                    "win_rate": (vals > 0).mean() if not vals.empty else pd.NA,
                }
            )
    return pd.DataFrame(rows)


def _compare_metric(
    prod_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    value_col: str,
    metric_name: str,
) -> pd.DataFrame:
    if prod_df is None:
        prod_df = pd.DataFrame()
    if bench_df is None:
        bench_df = pd.DataFrame()

    merge_cols = ["dataset", "detector", "event_type", "horizon"]
    prod = prod_df.rename(columns={value_col: "prod"})[merge_cols + ["prod"]]
    bench = bench_df.rename(columns={value_col: "benchmark"})[merge_cols + ["benchmark"]]

    merged = bench.merge(prod, on=merge_cols, how="outer")
    merged["delta"] = merged["prod"] - merged["benchmark"]
    merged["metric"] = metric_name
    merged["missing_in"] = ""
    merged.loc[merged["prod"].isna() & merged["benchmark"].notna(), "missing_in"] = "prod"
    merged.loc[merged["benchmark"].isna() & merged["prod"].notna(), "missing_in"] = "benchmark"
    return merged[merge_cols + ["metric", "benchmark", "prod", "delta", "missing_in"]]


def _summary_diff(prod_df: pd.DataFrame, bench_df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    if prod_df is None:
        prod_df = pd.DataFrame()
    if bench_df is None:
        bench_df = pd.DataFrame()

    prod = prod_df.rename(columns={"event": "event_type"})
    bench = bench_df.rename(columns={"event": "event_type"})
    if "detector" not in prod.columns:
        prod = prod.copy()
        prod["detector"] = "baseline"
    if "detector" not in bench.columns:
        bench = bench.copy()
        bench["detector"] = "baseline"
    merge_cols = ["detector", "event_type"]

    for metric, horizon in SUMMARY_METRICS:
        if metric not in prod.columns and metric not in bench.columns:
            continue
        prod_slice = prod[merge_cols + [metric]].rename(columns={metric: "prod"})
        bench_slice = bench[merge_cols + [metric]].rename(columns={metric: "benchmark"})
        merged = bench_slice.merge(prod_slice, on=merge_cols, how="outer")
        merged["dataset"] = dataset
        merged["horizon"] = horizon
        merged["metric"] = metric
        merged["delta"] = merged["prod"] - merged["benchmark"]
        merged["missing_in"] = ""
        merged.loc[merged["prod"].isna() & merged["benchmark"].notna(), "missing_in"] = "prod"
        merged.loc[merged["benchmark"].isna() & merged["prod"].notna(), "missing_in"] = "benchmark"
        rows.append(
            merged[
                ["dataset", "detector", "event_type", "horizon", "metric", "benchmark", "prod", "delta", "missing_in"]
            ]
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "dataset",
                "detector",
                "event_type",
                "horizon",
                "metric",
                "benchmark",
                "prod",
                "delta",
                "missing_in",
            ]
        )
    return pd.concat(rows, ignore_index=True)


def _missing_sequences(prod_df: pd.DataFrame, bench_df: pd.DataFrame) -> pd.DataFrame:
    prod_events = _extract_sequences(prod_df)
    bench_events = _extract_sequences(bench_df)

    missing = []
    for seq in sorted(bench_events - prod_events):
        missing.append({"sequence_id": seq, "missing_in": "prod"})
    for seq in sorted(prod_events - bench_events):
        missing.append({"sequence_id": seq, "missing_in": "benchmark"})
    return pd.DataFrame(missing, columns=["sequence_id", "missing_in"])


def _extract_sequences(df: pd.DataFrame) -> set[str]:
    if df is None or df.empty:
        return set()
    if "sequence_id" in df.columns:
        values = df["sequence_id"]
    elif "event" in df.columns:
        values = df["event"]
    else:
        return set()
    return {str(val) for val in values.dropna().unique() if str(val).strip()}


def compare_outputs(
    *, prod_dir: Path, bench_dir: Path, output_dir: Path, verbose_metrics: bool = False
) -> None:
    logger = logging.getLogger("prod_vs_bench.compare")
    metrics = EvalMetrics(verbose=verbose_metrics, heartbeat_every=0, logger=logger)
    output_dir.mkdir(parents=True, exist_ok=True)

    prod_any = None
    if prod_dir.exists():
        for item in prod_dir.iterdir():
            if item.is_file() and item.suffix.lower() == ".csv":
                prod_any = _read_csv(item, metrics)
                break
    meta = _extract_metadata(prod_any) if prod_any is not None else None

    forward_files = {
        "baseline": "baseline_forward_returns.csv",
        "transition": "transition_forward_returns.csv",
        "sequence": "sequence_forward_returns.csv",
        "contextual": "contextual_forward_returns.csv",
    }
    summary_files = {
        "baseline": "incremental_baseline_comparison.csv",
        "transition": "transition_summary.csv",
        "sequence": "sequence_summary.csv",
        "contextual": "contextual_summary.csv",
    }

    prod_forward = []
    bench_forward = []
    for dataset, filename in forward_files.items():
        prod_df = _read_csv(prod_dir / filename, metrics)
        bench_df = _read_csv(bench_dir / filename, metrics)
        metrics.tick_events(len(prod_df))
        metrics.tick_events(len(bench_df))
        fwd_cols = [c for c in prod_df.columns if c.startswith("fwd_")]
        if not fwd_cols:
            fwd_cols = [c for c in bench_df.columns if c.startswith("fwd_")]
        metrics.set_forward_windows(len(fwd_cols))
        prod_forward.append(_forward_stats(prod_df, dataset))
        bench_forward.append(_forward_stats(bench_df, dataset))

    prod_forward_df = pd.concat(prod_forward, ignore_index=True) if prod_forward else pd.DataFrame()
    bench_forward_df = pd.concat(bench_forward, ignore_index=True) if bench_forward else pd.DataFrame()

    forward_return_deltas = _compare_metric(prod_forward_df, bench_forward_df, "median", "median")
    win_rate_deltas = _compare_metric(prod_forward_df, bench_forward_df, "win_rate", "win_rate")

    summary_rows = []
    for dataset, filename in summary_files.items():
        prod_df = _read_csv(prod_dir / filename, metrics)
        bench_df = _read_csv(bench_dir / filename, metrics)
        summary_rows.append(_summary_diff(prod_df, bench_df, dataset))
    summary_diff = pd.concat(summary_rows, ignore_index=True) if summary_rows else pd.DataFrame()

    mae_deltas = pd.DataFrame(
        columns=[
            "dataset",
            "detector",
            "event_type",
            "horizon",
            "metric",
            "benchmark",
            "prod",
            "delta",
            "missing_in",
        ]
    )

    missing_sequences = _missing_sequences(
        _read_csv(prod_dir / "sequence_events.csv", metrics),
        _read_csv(bench_dir / "sequence_events.csv", metrics),
    )

    forward_return_deltas = _add_metadata(forward_return_deltas, meta)
    win_rate_deltas = _add_metadata(win_rate_deltas, meta)
    summary_diff = _add_metadata(summary_diff, meta)
    mae_deltas = _add_metadata(mae_deltas, meta)
    missing_sequences = _add_metadata(missing_sequences, meta)

    forward_return_deltas.to_csv(output_dir / "forward_return_deltas.csv", index=False)
    metrics.tick_csv_written("forward_return_deltas.csv", len(forward_return_deltas))
    win_rate_deltas.to_csv(output_dir / "win_rate_deltas.csv", index=False)
    metrics.tick_csv_written("win_rate_deltas.csv", len(win_rate_deltas))
    summary_diff.to_csv(output_dir / "summary_diff.csv", index=False)
    metrics.tick_csv_written("summary_diff.csv", len(summary_diff))
    mae_deltas.to_csv(output_dir / "mae_deltas.csv", index=False)
    metrics.tick_csv_written("mae_deltas.csv", len(mae_deltas))
    missing_sequences.to_csv(output_dir / "missing_sequences.csv", index=False)
    metrics.tick_csv_written("missing_sequences.csv", len(missing_sequences))
    metrics.log_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare benchmark vs production outputs.")
    parser.add_argument(
        "--prod-dir",
        default="tools/prod_vs_bench/outputs/prod",
        help="Directory containing production outputs",
    )
    parser.add_argument(
        "--bench-dir",
        default="tools/prod_vs_bench/outputs/bench",
        help="Directory containing benchmark outputs",
    )
    parser.add_argument(
        "--output-dir",
        default="tools/prod_vs_bench/outputs/comparison",
        help="Directory to write comparison outputs",
    )
    parser.add_argument("--verbose-metrics", action="store_true", help="Enable verbose progress metrics logging")
    args = parser.parse_args()
    if args.verbose_metrics:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    compare_outputs(
        prod_dir=Path(args.prod_dir),
        bench_dir=Path(args.bench_dir),
        output_dir=Path(args.output_dir),
        verbose_metrics=args.verbose_metrics,
    )


if __name__ == "__main__":
    main()
