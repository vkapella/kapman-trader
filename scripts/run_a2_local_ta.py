from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import psycopg2

from core.ingestion.ohlcv.db import default_db_url
from core.metrics.a2_local_ta_job import run_a2_local_ta_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan A2: Compute local TA + price metrics into daily_snapshots"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--date", type=_parse_date, default=None, help="Single trading date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start trading date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End trading date (YYYY-MM-DD)")
    parser.add_argument("--fill-missing", action="store_true", help="Only compute rows missing in daily_snapshots")

    parser.add_argument("--verbose", action="store_true", help="INFO-level per-ticker logging")
    parser.add_argument("--debug", action="store_true", help="DEBUG-level indicator logging (implies --verbose)")
    parser.add_argument("--quiet", action="store_true", help="Only warnings + final summary")
    parser.add_argument("--heartbeat", type=int, default=50, help="Heartbeat every N tickers (default: 50)")

    return parser


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


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


def _latest_ohlcv_date(conn) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(date) FROM ohlcv")
        return cur.fetchone()[0]


class _QuietFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return bool(getattr(record, "a2_summary", False)) or record.levelno >= logging.WARNING


def _configure_logging(*, quiet: bool, debug: bool) -> logging.Logger:
    log = logging.getLogger("kapman.a2")
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


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    debug = bool(args.debug)
    verbose = bool(args.verbose) or debug
    quiet = bool(args.quiet)

    if quiet:
        debug = False
        verbose = False

    log = _configure_logging(quiet=quiet, debug=debug)

    db_url = args.db_url or default_db_url()

    with psycopg2.connect(db_url) as conn:
        if args.date is not None:
            dates = [args.date]
        elif args.start_date is not None or args.end_date is not None:
            if args.start_date is None or args.end_date is None:
                raise SystemExit("--start-date and --end-date must be provided together")
            dates = _ohlcv_dates_in_range(conn, args.start_date, args.end_date)
        else:
            latest = _latest_ohlcv_date(conn)
            if latest is None:
                log.warning("[A2] ohlcv is empty; nothing to compute")
                return 0
            dates = [latest]

        run_a2_local_ta_job(
            conn,
            snapshot_dates=dates,
            fill_missing=args.fill_missing,
            heartbeat_every=int(args.heartbeat),
            verbose=verbose,
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
