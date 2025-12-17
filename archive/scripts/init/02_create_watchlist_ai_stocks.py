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
    """
    Insert ticker_id rows into portfolio_tickers for the given portfolio.
    """
    session = get_db_session()
    try:
        # Fetch ticker_id for each symbol
        ticker_rows = session.execute(
            text("""
                SELECT id, symbol
                FROM tickers
                WHERE symbol = ANY(:symbols)
            """),
            {"symbols": symbols}
        ).fetchall()

        ticker_map = {row.symbol: row.id for row in ticker_rows}

        missing = [s for s in symbols if s not in ticker_map]
        if missing:
            logger.warning(f"Symbols not found in tickers table: {missing}")

        # Fetch existing rows to avoid duplicates
        existing = session.execute(
            text("""
                SELECT ticker_id
                FROM portfolio_tickers
                WHERE portfolio_id = :pid
            """),
            {"pid": portfolio_id}
        ).fetchall()

        existing_ids = {row.ticker_id for row in existing}

        inserted = 0
        duplicates = 0
        for sym in symbols:
            tid = ticker_map.get(sym)
            if not tid:
                continue
            if tid in existing_ids:
                duplicates += 1
                continue

            session.execute(
                text("""
                    INSERT INTO portfolio_tickers (portfolio_id, ticker_id)
                    VALUES (:pid, :tid)
                """),
                {"pid": portfolio_id, "tid": tid}
            )
            inserted += 1

        session.commit()
        return {"inserted": inserted, "duplicates": duplicates}

    except Exception as e:
        logger.error(f"Error loading AI stocks: {e}", exc_info=True)
        session.rollback()
        return {"inserted": 0, "duplicates": 0}
    finally:
        session.close()

def main():
    logger.info("Starting AI_STOCKS watchlist creation")

    portfolio_id = ensure_portfolio_exists("AI_STOCKS")
    logger.info(f"Portfolio ID = {portfolio_id}")

    result = load_ai_stocks_watchlist(portfolio_id, AI_STOCKS)
    logger.info(f"Insert summary: {result}")

if __name__ == "__main__":
    main()
