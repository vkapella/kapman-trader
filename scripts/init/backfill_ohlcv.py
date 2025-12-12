#!/usr/bin/env python3
import os
import logging
from datetime import date, timedelta
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
    engine = create_engine(os.getenv("DATABASE_URL"), future=True)
    return Session(engine)


def get_ai_stocks(session: Session):
    """Return list of symbols in the AI_STOCKS portfolio."""
    result = session.execute(text("""
        SELECT t.symbol
        FROM tickers t
        JOIN portfolio_tickers pt ON t.symbol = pt.symbol
        JOIN portfolios p ON p.id = pt.portfolio_id
        WHERE p.name = 'AI_STOCKS'
    """))

    return [row[0] for row in result.fetchall()]


def get_backfill_dates(num_days):
    end = date.today()
    start = end - timedelta(days=num_days)
    return start, end


def insert_ohlcv_rows(session, symbol, rows):
    insert_sql = text("""
        INSERT INTO ohlcv (symbol, date, open, high, low, close, volume)
        VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
        ON CONFLICT (symbol, date) DO NOTHING
    """)

    for row in rows:
        session.execute(insert_sql, {
            "symbol": symbol,
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"]
        })

    session.commit()


def fetch_from_s3(symbol, start_date, end_date):
    # Placeholder: Your S3 loader implementation goes here
    # For now, I'll leave this unchanged
    raise NotImplementedError("S3 loader not implemented in this stub")


def main():
    logger.info("Starting OHLCV backfill for AI_STOCKS portfolio")

    session = get_db_session()
    symbols = get_ai_stocks(session)

    logger.info(f"Found {len(symbols)} AI_STOCKS symbols")

    start_date, end_date = get_backfill_dates(int(os.getenv("ENV_DEPTH", 30)))
    logger.info(f"Fetching data from {start_date} to {end_date}")

    for sym in symbols:
        try:
            logger.info(f"Loading OHLCV for {sym}")
            rows = fetch_from_s3(sym, start_date, end_date)
            insert_ohlcv_rows(session, sym, rows)
        except Exception as e:
            logger.error(f"Error loading OHLCV for {sym}: {e}")

    logger.info("Backfill complete.")


if __name__ == "__main__":
    main()
