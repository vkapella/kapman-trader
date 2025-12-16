import argparse
import logging
from datetime import datetime

from core.metrics.batch_runner import BatchConfig, MetricsBatchRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute local TA metrics and persist to daily_snapshots.")
    parser.add_argument("--date", type=str, help="Target trading date (YYYY-MM-DD). Defaults to latest in ohlcv_daily.")
    parser.add_argument("--symbols", type=str, help="Comma-separated list of symbols. Defaults to watchlist.")
    parser.add_argument("--lookback-days", type=int, default=60, help="Lookback window in calendar days (>=50).")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level.")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None

    config = BatchConfig(target_date=target_date, symbols=symbols, lookback_days=args.lookback_days)
    runner = MetricsBatchRunner()
    runner.run(config)


if __name__ == "__main__":
    main()

