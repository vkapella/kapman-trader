import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

@pytest.mark.db
def test_config_id_is_required(db_session):
    db_session.execute(text("""
        INSERT INTO dim_symbol (symbol_id) VALUES ('GOOG')
        ON CONFLICT DO NOTHING;
    """))

    db_session.execute(text("""
        INSERT INTO etl_run (run_id, run_type)
        VALUES ('run4', 'batch')
        ON CONFLICT DO NOTHING;
    """))

    with pytest.raises(IntegrityError):
        db_session.execute(text("""
            INSERT INTO fact_implied_volatility_daily
            (symbol_id, trading_date, algo_version, algo_git_sha, etl_run_id)
            VALUES
            ('GOOG', '2024-01-05', 'v1', 'sha1', 'run4');
        """))