#!/usr/bin/env python3
import os
import logging
import requests
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


POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")


def fetch_all_tickers():
    if not POLYGON_API_KEY:
        raise ValueError("POLYGON_API_KEY environment variable not set")

    logger.info("Fetching tickers from Polygon...")

    base_url = "https://api.polygon.io/v3/reference/tickers"
    params = {
        "active": "true",
        "limit": 1000,
        "apiKey": POLYGON_API_KEY
    }

    tickers = []
    next_url = base_url

    while next_url:
        if next_url == base_url:
            resp = requests.get(next_url, params=params)
        else:
            resp = requests.get(f"{next_url}&apiKey={POLYGON_API_KEY}")

        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        for item in results:
            tickers.append({
                "symbol": item.get("ticker"),
                "name": item.get("name"),
                "exchange": item.get("primary_exchange"),
                "asset_type": item.get("type"),
                "currency": (item.get("currency_name") or "").upper(),
                "is_active": item.get("active", True),
            })

        next_url = data.get("next_url")

    logger.info(f"Fetched {len(tickers)} tickers.")
    return tickers


def fetch_tickers():
    try:
        return fetch_all_tickers()
    except Exception as e:
        raise Exception("API Error") from e


def upsert_tickers(session, tickers):
    if not tickers:
        return {"count": 0}

    logger.info(f"Upserting {len(tickers)} tickers into 'tickers' table...")

    insert_sql = text("""
        INSERT INTO tickers (symbol, name, exchange, asset_type, currency, is_active)
        VALUES (:symbol, :name, :exchange, :asset_type, :currency, :is_active)
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            exchange = EXCLUDED.exchange,
            asset_type = EXCLUDED.asset_type,
            currency = EXCLUDED.currency,
            is_active = EXCLUDED.is_active,
            updated_at = NOW();
    """)

    session.execute(insert_sql, tickers)
    session.commit()

    logger.info("Ticker universe upsert completed successfully.")
    return {"count": len(tickers)}


def main():
    logger.info("Starting ticker universe load...")

    try:
        tickers = fetch_tickers()
        if not tickers:
            raise ValueError("No tickers returned from Polygon API")

        session = get_db_session()
        result = upsert_tickers(session, tickers)
        logger.info("Ticker universe load complete.")
        return result

    except Exception as e:
        logger.error(f"Error loading ticker universe: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
