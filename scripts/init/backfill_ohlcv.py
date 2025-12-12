#!/usr/bin/env python3
import os
import csv
import gzip
import io
import logging
from datetime import date, timedelta, datetime

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


def get_db_session():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    engine = create_engine(db_url, future=True)
    return Session(engine)


def get_ai_stocks(session: Session):
    result = session.execute(text("""
        SELECT t.id, t.symbol
        FROM tickers t
        JOIN portfolio_tickers pt ON t.id = pt.ticker_id
        JOIN portfolios p ON p.id = pt.portfolio_id
        WHERE p.name = 'AI_STOCKS'
        ORDER BY t.symbol;
    """))
    return [{"id": row[0], "symbol": row[1]} for row in result.fetchall()]


def get_backfill_dates(num_days: int):
    end = date.today()
    start = end - timedelta(days=num_days)
    return start, end


def insert_ohlcv_rows(session, ticker_id, rows):
    insert_sql = text("""
        INSERT INTO ohlcv (ticker_id, date, open, high, low, close, volume)
        VALUES (:ticker_id, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (ticker_id, date) DO NOTHING
    """)

    for row in rows:
        session.execute(insert_sql, {
            "ticker_id": ticker_id,
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"]
        })

    session.commit()


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


def fetch_from_s3(symbol, start_date, end_date):
    """
    Fetch daily OHLCV rows for a symbol from Massive flat files in S3.
    Returns list of dicts.
    """
    s3 = get_s3_client()

    bucket = os.getenv("S3_BUCKET")
    rows = []

    # Massive layout: stocks/ohlcv/day/YYYY/MM/SYMBOL.csv.gz
    cur = start_date.replace(day=1)
    while cur <= end_date:
        key = f"stocks/ohlcv/day/{cur.year}/{cur.month:02d}/{symbol}.csv.gz"
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            with gzip.GzipFile(fileobj=obj["Body"]) as gz:
                reader = csv.DictReader(io.TextIOWrapper(gz))
                for r in reader:
                    ts = datetime.fromisoformat(r["timestamp"]).date()
                    if start_date <= ts <= end_date:
                        rows.append({
                            "date": ts,
                            "open": float(r["open"]),
                            "high": float(r["high"]),
                            "low": float(r["low"]),
                            "close": float(r["close"]),
                            "volume": int(r["volume"]),
                        })
        except s3.exceptions.NoSuchKey:
            pass
        except Exception as e:
            logger.warning(f"S3 read failed for {symbol} {key}: {e}")

        # advance month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    return rows


def main(num_days: int):
    logger.info("Starting OHLCV backfill for AI_STOCKS portfolio")

    session = get_db_session()
    symbols = get_ai_stocks(session)

    logger.info(f"Found {len(symbols)} AI_STOCKS symbols")

    start_date, end_date = get_backfill_dates(num_days)
    logger.info(f"Fetching data from {start_date} to {end_date}")

    for sym in symbols:
        try:
            logger.info(f"Loading OHLCV for {sym['symbol']}")
            rows = fetch_from_s3(sym["symbol"], start_date, end_date)
            insert_ohlcv_rows(session, sym["id"], rows)
        except Exception as e:
            logger.error(f"Error loading OHLCV for {sym['symbol']}: {e}")

    logger.info("Backfill complete.")


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    main(args.days)
