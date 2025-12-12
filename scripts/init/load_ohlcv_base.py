#!/usr/bin/env python3
import csv
import gzip
import io
import logging
import os
from datetime import date, timedelta
from typing import Dict, Iterable, List, Set, Tuple

import boto3
from botocore.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_session() -> Session:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    engine = create_engine(db_url, future=True)
    return Session(engine)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def compute_date_range(days: int, end_date: date | None = None) -> Tuple[date, date]:
    end = end_date or date.today()
    start = end - timedelta(days=days - 1)
    return start, end


def iter_dates(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def build_s3_key(current_date: date) -> str:
    return f"us_stocks_sip/day_aggs_v1/{current_date.year}/{current_date.month:02d}/{current_date.isoformat()}.csv.gz"


def load_symbol_map(session: Session) -> Dict[str, str]:
    rows = session.execute(text("SELECT id, symbol FROM tickers")).fetchall()
    return {row.symbol.upper(): str(row.id) for row in rows}


def _get_float(record: dict, keys: List[str]) -> float | None:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            try:
                return float(record[key])
            except (TypeError, ValueError):
                return None
    return None


def _get_int(record: dict, keys: List[str]) -> int | None:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            try:
                return int(float(record[key]))
            except (TypeError, ValueError):
                return None
    return None


def parse_csv_rows(body, current_date: date, symbol_map: Dict[str, str]) -> Tuple[List[dict], Set[str]]:
    rows: List[dict] = []
    missing: Set[str] = set()

    with gzip.GzipFile(fileobj=body) as gz:
        reader = csv.DictReader(io.TextIOWrapper(gz))
        for record in reader:
            symbol = (record.get("ticker") or record.get("symbol") or "").upper()
            if not symbol:
                continue

            ticker_id = symbol_map.get(symbol)
            if not ticker_id:
                missing.add(symbol)
                continue

            open_price = _get_float(record, ["open", "o"])
            high_price = _get_float(record, ["high", "h"])
            low_price = _get_float(record, ["low", "l"])
            close_price = _get_float(record, ["close", "c"])
            volume = _get_int(record, ["volume", "v"])

            if None in (open_price, high_price, low_price, close_price, volume):
                continue

            rows.append({
                "ticker_id": ticker_id,
                "date": current_date,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            })

    return rows, missing


def fetch_daily_rows(s3, bucket: str, current_date: date, symbol_map: Dict[str, str]) -> Tuple[List[dict], Set[str]]:
    key = build_s3_key(current_date)
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except getattr(s3, "exceptions", object()).NoSuchKey:
        logger.warning(f"No S3 object for {current_date} ({key})")
        return [], set()
    except Exception as e:
        logger.error(f"S3 get_object failed for {key}: {e}")
        return [], set()

    try:
        rows, missing = parse_csv_rows(obj["Body"], current_date, symbol_map)
        return rows, missing
    except Exception as e:
        logger.error(f"Failed to parse {key}: {e}", exc_info=True)
        return [], set()


def insert_ohlcv(session: Session, rows: List[dict]) -> int:
    if not rows:
        return 0

    insert_sql = text("""
        INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume)
        VALUES (:ticker_id, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (ticker_id, date) DO NOTHING
    """)
    session.execute(insert_sql, rows)
    session.commit()
    return len(rows)


def enforce_retention(session: Session, days: int = 730, as_of: date | None = None) -> int:
    cutoff = (as_of or date.today()) - timedelta(days=days)
    result = session.execute(text("DELETE FROM ohlcv WHERE date < :cutoff"), {"cutoff": cutoff})
    session.commit()
    return result.rowcount if result.rowcount is not None else 0


def process_day(session: Session, s3, bucket: str, current_date: date, symbol_map: Dict[str, str]) -> Tuple[int, Set[str]]:
    rows, missing = fetch_daily_rows(s3, bucket, current_date, symbol_map)
    inserted = insert_ohlcv(session, rows)
    if inserted:
        logger.info(f"{current_date}: inserted {inserted} rows")
    if missing:
        logger.warning(f"{current_date}: missing {len(missing)} tickers (not in DB)")
    return inserted, missing


def main(days: int):
    logger.info("Starting Base OHLCV load")
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET is not set")

    session = get_db_session()
    symbol_map = load_symbol_map(session)
    logger.info(f"Loaded {len(symbol_map)} ticker IDs into memory")

    s3 = get_s3_client()
    start, end = compute_date_range(days)
    logger.info(f"Processing Massive daily files from {start} to {end}")

    total_inserted = 0
    total_missing: Set[str] = set()

    for current_date in iter_dates(start, end):
        inserted, missing = process_day(session, s3, bucket, current_date, symbol_map)
        total_inserted += inserted
        total_missing.update(missing)

    removed = enforce_retention(session, days=730)
    logger.info(f"Retention cleanup removed {removed} rows older than 730 trading days")
    logger.info(f"Base OHLCV load complete. Inserted rows: {total_inserted}. Missing tickers: {len(total_missing)}.")


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Load 2-year OHLCV base for all tickers from Massive.")
    parser.add_argument("--days", type=int, default=730, help="Number of days to backfill (default: 730)")
    args = parser.parse_args()
    main(args.days)
