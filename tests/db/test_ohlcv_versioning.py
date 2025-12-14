import pytest
from sqlalchemy import text

@pytest.mark.db
def test_ohlcv_allows_multiple_source_versions(db_session):
    db_session.execute(text("""
        INSERT INTO dim_symbol (symbol_id) VALUES ('AAPL')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO etl_run (run_id, run_type)
        VALUES ('run1', 'batch')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO fact_ohlcv_daily
        (symbol_id, trading_date, source_version, etl_run_id)
        VALUES
        ('AAPL', '2024-01-02', 'polygon@v1', 'run1'),
        ('AAPL', '2024-01-02', 'polygon@v2', 'run1');
    """))

    rows = db_session.execute(text("""
        SELECT COUNT(*) FROM fact_ohlcv_daily
        WHERE symbol_id = 'AAPL'
          AND trading_date = '2024-01-02';
    """)).scalar()

    assert rows == 2