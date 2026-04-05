from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import psycopg2

from core.ingestion.options.db import default_db_url
from core.metrics.daily_snapshots_cleanup import cleanup_split_daily_snapshots


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize split A3 daily_snapshots rows onto canonical stored snapshot rows"
    )
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL")
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Start NY trading date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="End NY trading date (YYYY-MM-DD)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the cleanup; omit for dry-run summary only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.start_date is None) != (args.end_date is None):
        raise SystemExit("--start-date and --end-date must be provided together")

    db_url = args.db_url or default_db_url()
    with psycopg2.connect(db_url) as conn:
        report = cleanup_split_daily_snapshots(
            conn,
            start_date=args.start_date,
            end_date=args.end_date,
            apply=bool(args.apply),
        )

    payload = report.to_dict()
    payload["mode"] = "apply" if args.apply else "dry_run"
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
