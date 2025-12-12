#!/usr/bin/env python3
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

AI_STOCKS = [
    "NVDA","AMD","INTC","QCOM","AVGO","TXN","MRVL","LSCC","MCHP","ADI",
    "SWKS","QRVO","NXPI","ON","MPWR","CRUS","SLAB","POWI","DIOD","RMBS",
    "ASML","LRCX","AMAT","KLAC","TER","ENTG","COHU","CAMT","ACMR","ICHR",
    "MSFT","GOOGL","AMZN","META","ORCL","IBM","SAP","CRM","ADBE","INTU"
]

def get_db_session():
    engine = create_engine(os.getenv("DATABASE_URL"), future=True)
    return Session(engine)

def ensure_portfolio_exists(name):
    session = get_db_session()
    result = session.execute(text(
        "SELECT id FROM portfolios WHERE name=:name"
    ), {"name": name}).fetchone()

    if result:
        return result[0]

    new_id = session.execute(text(
        "INSERT INTO portfolios (name) VALUES (:name) RETURNING id"
    ), {"name": name}).fetchone()[0]

    session.commit()
    return new_id

def load_ai_stocks_watchlist(portfolio_id, symbols):
    session = get_db_session()

    rows = session.execute(text("""
        SELECT symbol
        FROM tickers
        WHERE symbol = ANY(:symbols)
    """), {"symbols": symbols}).fetchall()

    found_symbols = [r[0] for r in rows]

    if not found_symbols:
        logger.warning("None of the AI stock tickers exist in the ticker universe.")
        return {"inserted": 0, "duplicates": 0}

    inserted = 0
    duplicates = 0

    for sym in found_symbols:
        try:
            session.execute(text("""
                INSERT INTO portfolio_tickers (portfolio_id, symbol)
                VALUES (:pid, :symbol)
                ON CONFLICT DO NOTHING
            """), {"pid": portfolio_id, "symbol": sym})
            inserted += 1
        except Exception:
            duplicates += 1

    session.commit()

    return {"inserted": inserted, "duplicates": duplicates}

def main():
    logger.info("Starting AI_STOCKS watchlist creation")

    portfolio_id = ensure_portfolio_exists("AI_STOCKS")
    logger.info(f"Portfolio ID = {portfolio_id}")

    result = load_ai_stocks_watchlist(portfolio_id, AI_STOCKS)
    logger.info(f"Insert summary: {result}")

if __name__ == "__main__":
    main()
