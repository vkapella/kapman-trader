from __future__ import annotations

import argparse
import logging
import sys

import psycopg2

from core.ingestion.options.db import default_db_url
from core.metrics.b1_wyckoff_regime_job import DEFAULT_HEARTBEAT_TICKERS, run_wyckoff_regime_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan B1: Persist daily Wyckoff regime state into daily_snapshots"
    )
    parser.add_argument("--watchlist", action="store_true", help="Restrict to active watchlist symbols")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols (e.g., AAPL,MSFT)")
    parser.add_argument("--verbose", action="store_true", help="Enable step-level logging")
    parser.add_argument("--heartbeat", action="store_true", help="Emit periodic progress logs")
    parser.add_argument("--workers", type=str, default="auto", help="Worker processes (default: auto)")
    parser.add_argument("--max-workers", type=int, default=6, help="Hard cap on workers (default: 6)")
    return parser


def _configure_logging(verbose: bool) -> logging.Logger:
    log = logging.getLogger("kapman.b1")
    log.handlers.clear()
    log.propagate = False
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(logging.INFO if verbose else logging.INFO)
    log.addHandler(handler)
    log.setLevel(logging.INFO if verbose else logging.INFO)
    return log


def _parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [sym.strip().upper() for sym in value.split(",") if sym.strip()]


def _parse_workers(value: str | None) -> int | None:
    if value is None:
        return None
    if str(value).strip().lower() == "auto":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise SystemExit("--workers must be an integer or 'auto'") from exc
    if parsed <= 0:
        raise SystemExit("--workers must be >= 1")
    return parsed


def _validate_max_workers(value: int) -> int:
    if int(value) <= 0:
        raise SystemExit("--max-workers must be >= 1")
    return int(value)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.watchlist and args.symbols:
        raise SystemExit("--watchlist and --symbols are mutually exclusive")

    log = _configure_logging(bool(args.verbose))
    symbols = _parse_symbols(args.symbols)
    heartbeat_every = DEFAULT_HEARTBEAT_TICKERS if args.heartbeat else 0
    workers = _parse_workers(args.workers)
    max_workers = _validate_max_workers(args.max_workers)

    db_url = default_db_url()
    with psycopg2.connect(db_url) as conn:
        run_wyckoff_regime_job(
            conn,
            symbols=symbols,
            use_watchlist=bool(args.watchlist),
            heartbeat_every=heartbeat_every,
            verbose=bool(args.verbose),
            log=log,
            workers=workers,
            max_workers=max_workers,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
