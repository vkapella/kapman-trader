#!/usr/bin/env python3
"""
Load ticker universe from Polygon.io into the database.

This script fetches all available tickers from Polygon.io, normalizes the data,
and upserts them into the tickers table.
"""
import os
import sys
import logging
import requests
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
POLYGON_BASE_URL = "https://api.polygon.io"
BATCH_SIZE = 1000  # Number of tickers to fetch per request
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

def get_db_session():
    """Create and return a database session."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def fetch_all_tickers() -> List[Dict[str, Any]]:
    """
    Fetch all tickers from Polygon API.
    
    Returns:
        List of normalized ticker dictionaries.
    """
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable not set")
    
    url = f"{POLYGON_BASE_URL}/v3/reference/tickers"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "market": "stocks",
        "active": "true",
        "sort": "ticker",
        "limit": BATCH_SIZE
    }
    
    all_tickers = []
    next_url = url
    
    while next_url:
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(next_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'results' in data:
                    all_tickers.extend(data['results'])
                
                next_url = data.get('next_url')
                if next_url:
                    next_url = f"{next_url}&apiKey={api_key}"
                
                # Clear params after first request as they're included in next_url
                params = {}
                break
                
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to fetch tickers after {MAX_RETRIES} attempts: {e}")
                    raise
                time.sleep(RETRY_DELAY * (attempt + 1))
    
    # Normalize ticker data
    normalized_tickers = []
    for ticker in all_tickers:
        normalized = {
            'symbol': ticker.get('ticker', '').upper(),
            'name': ticker.get('name', ''),
            'exchange': ticker.get('primary_exchange', ''),
            'asset_type': ticker.get('type', ''),
            'currency': (ticker.get('currency_name') or '').upper(),
            'is_active': ticker.get('active', False)
        }
        normalized_tickers.append(normalized)
    
    return normalized_tickers

def fetch_tickers() -> List[Dict[str, Any]]:
    """Backward-compatible wrapper for tests that expect fetch_tickers()."""
    return fetch_all_tickers()

def upsert_tickers(session, tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Upsert tickers into the database.
    
    Args:
        session: Database session
        tickers: List of ticker dictionaries
    
    Returns:
        List of dictionaries representing the upserted rows
    """
    if not tickers:
        raise ValueError("No tickers to upsert")
    
    # Create a temporary table for bulk upsert
    temp_table = """
    CREATE TEMP TABLE temp_tickers (
        symbol VARCHAR(20) PRIMARY KEY,
        name TEXT,
        exchange VARCHAR(10),
        asset_type VARCHAR(20),
        currency VARCHAR(3),
        is_active BOOLEAN
    )
    """
    
    try:
        # Create the temp table
        session.execute(text(temp_table))
        
        # Insert data into temp table
        insert_sql = """
        INSERT INTO temp_tickers (symbol, name, exchange, asset_type, currency, is_active)
        VALUES (:symbol, :name, :exchange, :asset_type, :currency, :is_active)
        """
        session.execute(text(insert_sql), tickers)
        
        # Upsert from temp table to main table and return the results
        upsert_sql = """
        INSERT INTO tickers (symbol, name, exchange, asset_type, currency, is_active, updated_at)
        SELECT symbol, name, exchange, asset_type, currency, is_active, CURRENT_TIMESTAMP
        FROM temp_tickers
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            exchange = EXCLUDED.exchange,
            asset_type = EXCLUDED.asset_type,
            currency = EXCLUDED.currency,
            is_active = EXCLUDED.is_active,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id, symbol, name, exchange, asset_type, currency, is_active
        """
        
        result = session.execute(text(upsert_sql)).fetchall()
        return [dict(row._mapping) for row in result]
        
    finally:
        # Clean up temp table
        try:
            session.execute(text("DROP TABLE IF EXISTS temp_tickers"))
        except:
            pass

def main() -> List[Dict[str, Any]]:
    """Main function to fetch and load tickers."""
    try:
        logger.info("Starting ticker universe load...")
        
        # Fetch tickers from Polygon
        logger.info("Fetching tickers from Polygon...")
        tickers = fetch_tickers()
        
        if not tickers:
            raise ValueError("No tickers returned from Polygon API")
        
        # Upsert into database
        logger.info(f"Upserting {len(tickers)} tickers into database...")
        session = get_db_session()
        with session.begin():
            result = upsert_tickers(session, tickers)
        
        logger.info("Ticker universe load completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error loading ticker universe: {e}")
        raise

if __name__ == "__main__":
    main()
