from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import psycopg2

from core.ingestion.options.db import default_db_url
from core.metrics.dealer_metrics_job import run_dealer_metrics_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KapMan A3: Compute dealer metrics into daily_snapshots"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--date", type=_parse_date, default=None, help="Single trading date (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start trading date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End trading date (YYYY-MM-DD)")
    parser.add_argument(
        "--fill-missing",
        action="store_true",
        help="Ensure a snapshot exists for every watchlist ticker",
    )
    parser.add_argument("--verbose", action="store_true", help="INFO-level per-ticker logging")
    parser.add_argument("--debug", action="store_true", help="DEBUG-level per-metric detail (implies --verbose)")
    parser.add_argument("--quiet", action="store_true", help="Only warnings + summaries")
    parser.add_argument("--heartbeat", type=int, default=50, help="Heartbeat every N tickers (default: 50)")
    parser.add_argument("--max-dte-days", type=int, default=90, help="Max DTE days (default 90)")
    parser.add_argument(
        "--min-open-interest",
        type=int,
        default=100,
        help="Min open interest per contract (default 100)",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=1,
        help="Min volume per contract (default 1)",
    )
    parser.add_argument(
        "--walls-top-n",
        type=int,
        default=3,
        help="Number of call/put walls to retain (default 3)",
    )
    parser.add_argument(
        "--gex-slope-range-pct",
        type=float,
        default=0.02,
        help="Price window percentage for GEX slope (default 0.02)",
    )
    parser.add_argument(
        "--max-moneyness",
        type=float,
        default=0.2,
        help="Max moneyness fraction for wall eligibility (default 0.2)",
    )
    parser.add_argument(
        "--spot-override",
        type=float,
        default=None,
        help="Override spot price for all tickers (diagnostics only)",
    )
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


def _resolve_snapshot_dates(
    conn, *, date_value: date | None, start_date: date | None, end_date: date | None
) -> list[date]:
    if date_value is not None:
        return [date_value]
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError("--start-date and --end-date must be provided together")
        return _ohlcv_dates_in_range(conn, start_date, end_date)
    latest = _latest_ohlcv_date(conn)
    if latest is None:
        return []
    return [latest]


class _QuietFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return bool(getattr(record, "a3_summary", False)) or record.levelno >= logging.WARNING


def _configure_logging(*, quiet: bool, debug: bool) -> logging.Logger:
    log = logging.getLogger("kapman.a3")
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
        try:
            snapshot_dates = _resolve_snapshot_dates(
                conn,
                date_value=args.date,
                start_date=args.start_date,
                end_date=args.end_date,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

        if not snapshot_dates:
            if args.start_date is not None or args.end_date is not None:
                log.warning("[A3] No trading dates found in the requested range")
            else:
                log.warning("[A3] ohlcv is empty; nothing to compute")
            return 0

        run_dealer_metrics_job(
            conn,
            snapshot_dates=snapshot_dates,
            fill_missing=args.fill_missing,
            heartbeat_every=int(args.heartbeat),
            verbose=verbose,
            debug=debug,
            max_dte_days=args.max_dte_days,
            min_open_interest=args.min_open_interest,
            min_volume=args.min_volume,
            walls_top_n=args.walls_top_n,
            gex_slope_range_pct=args.gex_slope_range_pct,
            max_moneyness=args.max_moneyness,
            spot_override=args.spot_override,
            log=log,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
