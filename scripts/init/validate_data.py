import os
from datetime import date, timedelta
from sqlalchemy import text
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

def load_env_settings():
    env = os.getenv("ENV", "dev")
    if env == "dev":
        return 30
    if env == "test":
        return 90
    return 730

@contextmanager
def get_db_session():
    db_url = os.getenv("DATABASE_URL")
    engine = create_engine(db_url, future=True)
    with Session(engine) as session:
        yield session

def validate_universe(session: Session):
    result = {
        "universe_count": 0,
        "missing_required_columns": [],
        "exit_code": 0,
    }

    count_res = session.execute(text("SELECT COUNT(*) FROM tickers"))
    result["universe_count"] = count_res.scalar()

    missing_res = session.execute(text("""
        SELECT symbol
        FROM tickers
        WHERE name IS NULL
           OR exchange IS NULL
           OR updated_at IS NULL
    """))
    missing = [row[0] for row in missing_res.fetchall()]

    if missing:
        result["missing_required_columns"] = missing
        result["exit_code"] = 1

    return result

def validate_watchlist(session: Session):
    result = {
        "watchlist_count": 0,
        "missing_watchlist_symbols": [],
        "exit_code": 0,
    }

    portfolio = session.execute(
        text("SELECT id FROM portfolios WHERE name='AI_STOCKS'")
    ).fetchone()

    if not portfolio:
        result["exit_code"] = 1
        return result

    watchlist_rows = session.execute(text("""
        SELECT DISTINCT t.symbol
        FROM portfolio_tickers pt
        JOIN tickers t ON t.id = pt.ticker_id
        WHERE pt.portfolio_id = :pid
    """), {"pid": portfolio[0]})

    watchlist = [row[0] for row in watchlist_rows.fetchall()]
    result["watchlist_count"] = len(watchlist)

    tickers = session.execute(text("SELECT symbol FROM tickers")).fetchall()
    tickers = {row[0] for row in tickers}

    missing = [sym for sym in watchlist if sym not in tickers]

    if missing:
        result["missing_watchlist_symbols"] = missing
        result["exit_code"] = 1

    return result

def validate_ohlcv(session: Session, expected_days: int):
    result = {
        "symbols_with_incomplete_ohlcv": [],
        "symbols_with_bad_ohlcv_values": [],
        "missing_dates": {},
        "exit_code": 0,
    }

    symbol_rows = session.execute(text("""
        SELECT DISTINCT t.symbol
        FROM portfolio_tickers pt
        JOIN tickers t ON t.id = pt.ticker_id
    """))
    symbols = [row[0] for row in symbol_rows.fetchall()]

    for sym in symbols:

        count_rows = session.execute(text("""
            SELECT :sym AS symbol, COUNT(*) AS count
            FROM ohlcv_daily
            WHERE symbol = :sym
        """), {"sym": sym}).fetchall()

        # FIX: dict access instead of .count
        count = count_rows[0]["count"] if count_rows else 0

        if count < expected_days:
            result["symbols_with_incomplete_ohlcv"].append(sym)
            result["exit_code"] = 1

        rows = session.execute(text("""
            SELECT date, open, high, low, close, volume
            FROM ohlcv_daily
            WHERE symbol = :sym
        """), {"sym": sym}).fetchall()

        dates = sorted([r[0] for r in rows])

        if dates:
            min_d, max_d = min(dates), max(dates)
            full_range = [(max_d - timedelta(days=i)) for i in range(expected_days)]
            missing = [d for d in full_range if d not in dates]

            if missing:
                result["missing_dates"][sym] = missing
                result["exit_code"] = 1

        for d, o, h, l, c, v in rows:
            if h < l or not(l <= o <= h) or not(l <= c <= h) or v < 0:
                result["symbols_with_bad_ohlcv_values"].append(sym)
                result["exit_code"] = 1
                break

    return result

def validate_all():
    expected_days = load_env_settings()

    with get_db_session() as session:
        uni = validate_universe(session)
        watch = validate_watchlist(session)
        ohlcv = validate_ohlcv(session, expected_days)

    exit_code = max(uni["exit_code"], watch["exit_code"], ohlcv["exit_code"])

    return {
        **uni,
        **watch,
        **ohlcv,
        "exit_code": exit_code
    }

if __name__ == "__main__":
    result = validate_all()
    print(result)
    exit(result["exit_code"])
