#!/usr/bin/env python3
from __future__ import annotations

import sys
from argparse import ArgumentParser

from dotenv import load_dotenv

from core.ingestion.ohlcv.db import connect, default_db_url
from core.ingestion.tickers.loader import TickerBootstrapError, ensure_universe_loaded


def build_parser() -> ArgumentParser:
    p = ArgumentParser(description="Bootstrap the full ticker universe from Polygon Reference API.")
    p.add_argument("--db-url", default=None, help="Overrides DATABASE_URL (default: env DATABASE_URL)")
    p.add_argument("--force", action="store_true", help="Re-fetch and upsert even if tickers is non-empty")
    return p


def main(argv: list[str]) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    db_url = args.db_url or default_db_url()
    with connect(db_url) as conn:
        res = ensure_universe_loaded(conn, force=bool(args.force))
    print(f"✅ tickers loaded: fetched={res.fetched}, upserted={res.upserted}, final_count={res.final_count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TickerBootstrapError as e:
        print(f"❌ ticker bootstrap failed: {e}", file=sys.stderr)
        raise SystemExit(2)

