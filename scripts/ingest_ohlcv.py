#!/usr/bin/env python3
from __future__ import annotations

import sys
from argparse import ArgumentParser
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from core.ingestion.ohlcv import db as ohlcv_db
from core.ingestion.ohlcv.pipeline import (
    IngestionError,
    default_base_days,
    ingest_ohlcv,
    resolve_calendar_dates_to_ingest,
)
from core.ingestion.ohlcv.s3_flatfiles import default_s3_flatfiles_config, get_s3_client, list_latest_available_dates
from core.ingestion.tickers.loader import TickerBootstrapError, ensure_universe_loaded


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid date {s!r}; expected YYYY-MM-DD") from e


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        description=(
            "Canonical OHLCV ingestion pipeline (A0). "
            "Reads Polygon S3 flat files and upserts into public.ohlcv."
        )
    )
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")

    sub = p.add_subparsers(dest="mode", required=True)

    def add_common_flags(sp: ArgumentParser) -> None:
        sp.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
        sp.add_argument(
            "--symbols",
            default=None,
            help="Comma-separated symbol subset (NON-AUTHORITATIVE; default: full universe from tickers table)",
        )
        sp.add_argument(
            "--strict-missing-symbols",
            action="store_true",
            help="Fail if flatfile contains symbols missing from tickers (default: base load skips missing symbols)",
        )
        sp.add_argument(
            "--no-ticker-bootstrap",
            action="store_true",
            help="Disable automatic ticker bootstrapping; if tickers is empty, fail as-is",
        )

    base = sub.add_parser("base", help="Full-universe base load (last N available trading days)")
    add_common_flags(base)
    base.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of available daily files to ingest (default: OHLCV_HISTORY_DAYS or 730)",
    )
    base.add_argument(
        "--as-of",
        type=_parse_date,
        default=None,
        help="Latest date to consider (default: yesterday)",
    )

    inc = sub.add_parser("incremental", help="Incremental daily ingestion")
    add_common_flags(inc)
    inc.add_argument("--date", type=_parse_date, default=None, help="Single date (YYYY-MM-DD)")
    inc.add_argument("--start", type=_parse_date, default=None, help="Start date (YYYY-MM-DD)")
    inc.add_argument("--end", type=_parse_date, default=None, help="End date (YYYY-MM-DD)")

    backfill = sub.add_parser("backfill", help="Bounded historical backfill")
    add_common_flags(backfill)
    backfill.add_argument("--start", type=_parse_date, required=True, help="Start date (YYYY-MM-DD)")
    backfill.add_argument("--end", type=_parse_date, required=True, help="End date (YYYY-MM-DD)")

    return p


def main(argv: list[str]) -> int:
    load_dotenv()

    args = build_parser().parse_args(argv)

    db_url = args.db_url or ohlcv_db.default_db_url()

    requested_symbols: set[str] | None = None
    if args.symbols:
        requested_symbols = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        if not requested_symbols:
            raise SystemExit("--symbols provided but no valid symbols parsed")
        print(
            f"⚠️ NON-AUTHORITATIVE subset mode enabled: symbols={sorted(requested_symbols)}",
            file=sys.stderr,
        )

    with ohlcv_db.connect(db_url) as conn:
        tickers_count = ohlcv_db.count_table(conn, "tickers")
        if tickers_count == 0 and not args.no_ticker_bootstrap:
            try:
                ensure_universe_loaded(conn, force=False)
            except TickerBootstrapError as e:
                raise SystemExit(f"Ticker bootstrap failed: {e}") from e

        tickers_count = ohlcv_db.count_table(conn, "tickers")
        if tickers_count == 0:
            raise IngestionError("tickers table is empty; load ticker universe before OHLCV")

        if requested_symbols is not None:
            symbol_map = ohlcv_db.load_symbol_map(conn)
            existing = set(symbol_map.keys())
            missing = sorted(requested_symbols - existing)
            if missing:
                print(
                    f"⚠️ Requested symbols missing from tickers and will be ignored: {missing[:50]}",
                    file=sys.stderr,
                )
            requested_symbols = requested_symbols & existing

    s3_cfg = default_s3_flatfiles_config()
    s3 = get_s3_client(s3_cfg)

    if args.mode == "base":
        days = args.days if args.days is not None else default_base_days()
        as_of = args.as_of or _yesterday()
        dates = list_latest_available_dates(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            limit=days,
            as_of=as_of,
        )
    elif args.mode == "incremental":
        if args.date and (args.start or args.end):
            raise SystemExit("Use either --date or --start/--end (not both)")
        if args.date:
            start = end = args.date
        else:
            start = args.start or _yesterday()
            end = args.end or start
        dates = resolve_calendar_dates_to_ingest(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            start=start,
            end=end,
        )
    elif args.mode == "backfill":
        start = args.start
        end = args.end
        dates = resolve_calendar_dates_to_ingest(
            s3,
            bucket=s3_cfg.bucket,
            prefix=s3_cfg.prefix,
            start=start,
            end=end,
        )
    else:
        raise SystemExit(f"Unknown mode: {args.mode!r}")

    report = ingest_ohlcv(
        db_url=db_url,
        s3_cfg=s3_cfg,
        mode=args.mode,
        dates=dates,
        symbols=requested_symbols,
        strict_missing_symbols=bool(args.strict_missing_symbols or args.mode != "base"),
    )

    print(
        f"✅ OHLCV ingestion complete: mode={report.requested.mode} "
        f"dates={report.requested.start.isoformat()}..{report.requested.end.isoformat()} "
        f"({len(report.ingested_dates)} files), rows_written={report.total_rows_written} "
        f"missing_symbols={report.missing_symbols_count} "
        f"duplicates_seen={report.duplicate_rows_seen} "
        f"duplicates_resolved={report.duplicate_rows_resolved}"
    )
    if report.missing_symbols_count:
        print(
            f"⚠️ Missing symbol sample (skipped): {sorted(report.missing_symbols_examples)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except IngestionError as e:
        print(f"❌ OHLCV ingestion failed: {e}", file=sys.stderr)
        raise SystemExit(2)
