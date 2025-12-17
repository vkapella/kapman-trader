"""
CLI for running the Wyckoff research benchmark.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Sequence

from research.wyckoff_bench.harness.runner import load_bench_config, run_benchmark


def _parse_symbols(raw: str | Iterable[str] | None) -> List[str] | None:
    if raw is None:
        return None
    items: List[str] = []
    if isinstance(raw, str):
        items = raw.split(",")
    else:
        for item in raw:
            items.extend(item.split(","))
    parsed = [s.strip().upper() for s in items if s.strip()]
    return parsed or None


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Wyckoff research benchmark (research-only).")
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols (overrides config)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--impl",
        action="append",
        help="Implementation ID (use multiple flags or comma-separated list); default 'all'",
        default=None,
    )
    parser.add_argument("--cfg", type=str, default="research/wyckoff_bench/config/bench.default.yaml", help="Benchmark config path")
    parser.add_argument("--output-dir", type=str, default="research/wyckoff_bench/outputs", help="Output directory")
    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
        help="Run implementations for coverage/diagnostics only (no returns/summary outputs)",
    )
    parser.add_argument(
        "--entry-only",
        action="store_true",
        help="Compute entry-only, direction-aware returns/MAE summaries (keeps normal outputs too)",
    )
    args = parser.parse_args(argv)

    cfg = load_bench_config(args.cfg)
    symbols = _parse_symbols(args.symbols) or cfg.get("symbols")
    if not symbols:
        raise SystemExit("No symbols provided (via --symbols or config).")

    impl_names = _parse_symbols(args.impl) or ["all"]
    loader_cfg = cfg.get("loader", {})
    impl_cfg = cfg.get("impl_cfg", {})
    run_id = cfg.get("run_id")

    signals_df, price_df, signals_path, summary_path, comparison_path = run_benchmark(
        symbols,
        start=args.start,
        end=args.end,
        impl_names=impl_names,
        impl_cfg=impl_cfg,
        loader_cfg=loader_cfg,
        output_dir=args.output_dir,
        run_id=run_id,
        diagnostics_only=args.diagnostics_only,
        entry_only=args.entry_only,
    )

    if args.diagnostics_only:
        coverage_path = Path(args.output_dir) / "consolidated_implementation_coverage.csv"
        diagnostics_path = Path(args.output_dir) / "consolidated_implementation_diagnostics.csv"
        print("Diagnostics-only run complete.")
        print(f"Coverage: {coverage_path}")
        print(f"Diagnostics: {diagnostics_path}")
    else:
        print(f"Wrote signals to {signals_path}")
        print(f"Wrote summary to {summary_path}")
        print(f"Wrote comparison to {comparison_path}")
        print(f"Signals rows: {len(signals_df)}  Price rows: {len(price_df)}")


if __name__ == "__main__":
    main()
