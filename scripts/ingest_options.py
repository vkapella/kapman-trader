#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
import sys
from argparse import ArgumentParser
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from core.ingestion.options import OptionsIngestionError, ingest_options_chains_from_watchlists


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid date {s!r}; expected YYYY-MM-DD") from e


def _parse_snapshot_time(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise SystemExit(f"Invalid --snapshot-time {s!r}; expected ISO-8601") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        description=(
            "A1 options chain ingestion (watchlists -> options_chains). "
            "Reads active symbols from public.watchlists, fetches options snapshots from the selected provider, "
            "and upserts into public.options_chains."
        )
    )
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
    p.add_argument(
        "--api-key",
        default=None,
        help="Overrides provider API key (default: env POLYGON_API_KEY or UNICORN_API_TOKEN depending on provider)",
    )
    p.add_argument("--as-of", default=None, type=_parse_date, help="Provider as_of date (YYYY-MM-DD)")
    p.add_argument(
        "--snapshot-time",
        default=None,
        type=_parse_snapshot_time,
        help="Snapshot time used for idempotent re-runs (ISO-8601; default: now UTC)",
    )
    p.add_argument("--concurrency", default=5, type=int, help="Max concurrent symbols (default: 5)")
    p.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated subset of symbols (still intersected with active watchlists)",
    )
    p.add_argument(
        "--provider",
        choices=["unicorn", "polygon"],
        default=None,
        help="Options provider (override env OPTIONS_PROVIDER; default: unicorn)",
    )
    return p


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    args = build_parser().parse_args(argv)
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    report = ingest_options_chains_from_watchlists(
        db_url=args.db_url,
        api_key=args.api_key,
        as_of_date=args.as_of,
        snapshot_time=args.snapshot_time,
        concurrency=int(args.concurrency),
        symbols=symbols,
        provider_name=args.provider,
    )

    ok = sum(1 for o in report.outcomes if o.ok)
    failed = sum(1 for o in report.outcomes if not o.ok)
    print(
        f"✅ options ingestion complete: provider={report.provider} snapshot_time={report.snapshot_time.isoformat()} "
        f"symbols={len(report.symbols)} ok={ok} failed={failed} rows_written={report.total_rows_persisted}"
    )
    if failed:
        for o in report.outcomes:
            if not o.ok:
                print(f"⚠️ {o.symbol}: {o.error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except asyncio.CancelledError:
        raise SystemExit(130)
    except OptionsIngestionError as e:
        print(f"❌ options ingestion failed: {e}", file=sys.stderr)
        raise SystemExit(2)
