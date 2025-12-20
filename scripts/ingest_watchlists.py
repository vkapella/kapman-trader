#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser
from datetime import datetime

from dotenv import load_dotenv

from core.ingestion.ohlcv.db import default_db_url
from core.ingestion.watchlists.loader import WatchlistLoadError, WatchlistReconcileError, reconcile_watchlists


def build_parser() -> ArgumentParser:
    p = ArgumentParser(
        description=(
            "Persist deterministic MVP watchlists (A7). "
            "Reads data/watchlists/*.txt and reconciles into public.watchlists."
        )
    )
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
    p.add_argument(
        "--effective-date",
        default=None,
        help="Effective date (YYYY-MM-DD) applied during reconciliation (default: today)",
    )
    return p


def _parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid --effective-date {s!r}; expected YYYY-MM-DD") from e


def main(argv: list[str]) -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    args = build_parser().parse_args(argv)
    db_url = args.db_url or default_db_url()
    effective_date = _parse_date(args.effective_date) if args.effective_date else None

    res = reconcile_watchlists(db_url=db_url, effective_date=effective_date)
    print(f"✅ watchlists reconciled: watchlists={len(res.processed)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (WatchlistLoadError, WatchlistReconcileError) as e:
        print(f"❌ watchlist reconcile failed: {e}", file=sys.stderr)
        raise SystemExit(2)
