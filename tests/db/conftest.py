import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="function")
def db_session():
    """
    Provides a transactional SQLAlchemy session for DB invariant tests.

    - Uses DATABASE_URL from environment
    - Wraps each test in a transaction
    - Rolls back after test completes
    """

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(db_url, future=True)

    connection = engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(bind=connection, future=True)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()