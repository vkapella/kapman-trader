import pytest
from sqlalchemy import text

@pytest.mark.db
def test_algorithm_git_sha_is_part_of_identity(db_session):
    db_session.execute(text("""
        INSERT INTO dim_symbol (symbol_id) VALUES ('NVDA')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO config_set (config_id, config_hash, config_type)
        VALUES ('cfg2', 'hash2', 'dealer_metrics')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO etl_run (run_id, run_type)
        VALUES ('run3', 'batch')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO fact_dealer_metrics_daily
        (symbol_id, trading_date, config_id, algo_version, algo_git_sha, etl_run_id)
        VALUES
        ('NVDA', '2024-01-04', 'cfg2', 'v1', 'shaA', 'run3'),
        ('NVDA', '2024-01-04', 'cfg2', 'v1', 'shaB', 'run3');
    """))

    rows = db_session.execute(text("""
        SELECT COUNT(*) FROM fact_dealer_metrics_daily
        WHERE symbol_id = 'NVDA'
          AND trading_date = '2024-01-04';
    """)).scalar()

    assert rows == 2