import pytest
from sqlalchemy import text

@pytest.mark.db
def test_derived_metrics_idempotent_overwrite(db_session):
    db_session.execute(text("""
        INSERT INTO dim_symbol (symbol_id) VALUES ('MSFT')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO config_set (config_id, config_hash, config_type)
        VALUES ('cfg1', 'hash1', 'realized_volatility')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO etl_run (run_id, run_type)
        VALUES ('run2', 'batch')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO fact_realized_volatility_daily
        (symbol_id, trading_date, config_id, algo_version, algo_git_sha, etl_run_id)
        VALUES
        ('MSFT', '2024-01-03', 'cfg1', 'v1', 'sha1', 'run2');
    """))

    db_session.execute(text("""
        INSERT INTO fact_realized_volatility_daily
        (symbol_id, trading_date, config_id, algo_version, algo_git_sha, etl_run_id)
        VALUES
        ('MSFT', '2024-01-03', 'cfg1', 'v1', 'sha1', 'run2')
        ON CONFLICT DO NOTHING;
    """))

    rows = db_session.execute(text("""
        SELECT COUNT(*) FROM fact_realized_volatility_daily;
    """)).scalar()

    assert rows == 1