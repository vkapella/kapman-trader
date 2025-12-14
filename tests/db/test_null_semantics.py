import pytest
from sqlalchemy import text

@pytest.mark.db
def test_nulls_are_preserved(db_session):
    db_session.execute(text("""
        INSERT INTO dim_symbol (symbol_id) VALUES ('TSLA')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO config_set (config_id, config_hash, config_type)
        VALUES ('cfg3', 'hash3', 'implied_volatility')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO etl_run (run_id, run_type)
        VALUES ('run5', 'batch')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO fact_implied_volatility_daily
        (symbol_id, trading_date, config_id, algo_version, algo_git_sha, etl_run_id)
        VALUES
        ('TSLA', '2024-01-06', 'cfg3', 'v1', 'sha1', 'run5');
    """))

    row = db_session.execute(text("""
        SELECT * FROM fact_implied_volatility_daily
        WHERE symbol_id = 'TSLA';
    """)).first()

    assert row is not None