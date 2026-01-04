from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from typing import Optional

import psycopg2

from core.ingestion.options.db import default_db_url
from core.metrics.b4_wyckoff_derived_job import DEFAULT_HEARTBEAT_TICKERS, run_wyckoff_derived_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan B4: Persist derived Wyckoff transitions, sequences, and context events"
    )
    parser.add_argument("--watchlist", action="store_true", help="Restrict to active watchlist symbols")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols (e.g., AAPL,MSFT)")
    parser.add_argument("--start-date", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--verbose", action="store_true", help="Enable step-level logging")
    parser.add_argument("--heartbeat", action="store_true", help="Emit periodic progress logs")
    parser.add_argument(
        "--include-evidence",
        action="store_true",
        help="Persist per-day snapshot evidence block",
    )
    return parser


def _configure_logging(verbose: bool) -> logging.Logger:
    log = logging.getLogger("kapman.b4")
    log.handlers.clear()
    log.propagate = False
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    return log


def _parse_symbols(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [sym.strip().upper() for sym in value.split(",") if sym.strip()]


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.watchlist and args.symbols:
        raise SystemExit("--watchlist and --symbols are mutually exclusive")

    log = _configure_logging(bool(args.verbose))
    symbols = _parse_symbols(args.symbols)
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    heartbeat_every = DEFAULT_HEARTBEAT_TICKERS if args.heartbeat else 0

    db_url = default_db_url()
    with psycopg2.connect(db_url) as conn:
        run_wyckoff_derived_job(
            conn,
            symbols=symbols,
            use_watchlist=bool(args.watchlist),
            start_date=start_date,
            end_date=end_date,
            heartbeat_every=heartbeat_every,
            verbose=bool(args.verbose),
            include_evidence=bool(args.include_evidence),
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
