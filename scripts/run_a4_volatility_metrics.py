from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import psycopg2

from core.ingestion.options.db import default_db_url
from core.metrics.a4_volatility_metrics_job import run_volatility_metrics_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan A4: Compute volatility metrics into daily_snapshots"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--date", type=_parse_date, default=None, help="Single trading date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start trading date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End trading date (YYYY-MM-DD)")
    parser.add_argument("--fill-missing", action="store_true", help="Ensure a snapshot exists for every watchlist ticker")
    parser.add_argument("--verbose", action="store_true", help="INFO-level per-ticker logging")
    parser.add_argument("--debug", action="store_true", help="DEBUG-level per-metric detail (implies --verbose)")
    parser.add_argument("--quiet", action="store_true", help="Only warnings + summaries")
    parser.add_argument("--heartbeat", type=int, default=50, help="Heartbeat every N tickers (default: 50)")
    return parser


def _resolve_verbosity(verbose_flag: bool, debug_flag: bool, quiet_flag: bool) -> tuple[bool, bool]:
    debug = bool(debug_flag)
    verbose = bool(verbose_flag) or debug
    if quiet_flag:
        return False, False
    return debug, verbose


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from exc


def _latest_ohlcv_date(conn) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(date) FROM ohlcv")
        return cur.fetchone()[0]


def _ohlcv_dates_in_range(conn, start: date, end: date) -> list[date]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT date
            FROM ohlcv
            WHERE date >= %s AND date <= %s
            ORDER BY date ASC
            """,
            (start, end),
        )
        return [r[0] for r in cur.fetchall()]


class _QuietFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return bool(getattr(record, "a4_summary", False)) or record.levelno >= logging.WARNING


def _configure_logging(*, quiet: bool, debug: bool) -> logging.Logger:
    log = logging.getLogger("kapman.a4")
    log.handlers.clear()
    log.propagate = False

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    if quiet:
        handler.addFilter(_QuietFilter())

    log.addHandler(handler)
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    return log


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    quiet = bool(args.quiet)
    debug, verbose = _resolve_verbosity(args.verbose, args.debug, quiet)

    log = _configure_logging(quiet=quiet, debug=debug)

    db_url = args.db_url or default_db_url()
    with psycopg2.connect(db_url) as conn:
        snapshot_dates: list[date] = []
        if args.date is not None:
            snapshot_dates = [args.date]
        elif args.start_date is not None or args.end_date is not None:
            if args.start_date is None or args.end_date is None:
                raise SystemExit("--start-date and --end-date must be provided together")
            snapshot_dates = _ohlcv_dates_in_range(conn, args.start_date, args.end_date)
        else:
            latest = _latest_ohlcv_date(conn)
            if latest is None:
                log.warning("[A4] ohlcv is empty; nothing to compute")
                return 0
            snapshot_dates = [latest]

        if not snapshot_dates:
            log.warning("[A4] No trading dates found in the requested range")
            return 0

        run_volatility_metrics_job(
            conn,
            snapshot_dates=snapshot_dates,
            fill_missing=args.fill_missing,
            heartbeat_every=int(args.heartbeat),
            verbose=verbose,
            debug=debug,
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
