import importlib
import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load the script module
def load_script():
    module_path = "scripts.init.01_load_ticker_universe"
    return importlib.import_module(module_path)

# Test that the script loads correctly
def test_script_loads():
    module = load_script()
    assert hasattr(module, "main")
    assert hasattr(module, "fetch_tickers")

# Test database setup fixture
@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine('sqlite:///:memory:')
    
    # Create test tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE tickers (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) UNIQUE NOT NULL,
                name TEXT,
                exchange VARCHAR(10),
                asset_type VARCHAR(20),
                currency VARCHAR(3),
                is_active BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    
    yield engine
    engine.dispose()

# Test session fixture
@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

# Test environment variables
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('POLYGON_API_KEY', 'test_key')

# Test successful fetch of tickers
@patch('requests.get')
def test_fetch_tickers_success(mock_get):
    """Test successful fetching of tickers from Polygon."""
    # Mock response from Polygon API
    mock_response = {
        'results': [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'currency_name': 'usd',
                'active': True
            }
        ],
        'count': 1
    }
    
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status.return_value = None
    
    module = load_script()
    result = module.fetch_tickers()
    
    assert len(result) == 1
    assert result[0]['symbol'] == 'AAPL'
    assert result[0]['name'] == 'Apple Inc.'
    assert result[0]['exchange'] == 'XNAS'
    assert result[0]['asset_type'] == 'CS'
    assert result[0]['currency'] == 'USD'
    assert result[0]['is_active'] is True

# Test API error handling
@patch('requests.get')
def test_fetch_tickers_api_error(mock_get):
    """Test handling of API errors."""
    mock_get.return_value.raise_for_status.side_effect = Exception("API Error")
    
    module = load_script()
    with pytest.raises(Exception, match="API Error"):
        module.fetch_tickers()

# Test main function with mock database
@patch('scripts.init.01_load_ticker_universe.upsert_tickers')
@patch('scripts.init.01_load_ticker_universe.fetch_tickers')
def test_main_success(mock_fetch_tickers, mock_upsert_tickers):
    """Test the main function successfully processes and loads tickers."""
    # Setup mock data
    test_tickers = [{
        'symbol': 'AAPL',
        'name': 'Apple Inc.',
        'exchange': 'XNAS',
        'asset_type': 'CS',
        'currency': 'USD',
        'is_active': True
    }]
    
    # Configure mocks
    mock_fetch_tickers.return_value = test_tickers
    mock_upsert_tickers.return_value = test_tickers  # Return the same tickers that were passed in
    
    module = load_script()
    result = module.main()
    
    # Verify the result is what we expect
    assert len(result) == 1
    assert result[0]['symbol'] == 'AAPL'
    
    # Verify the mocks were called correctly
    mock_fetch_tickers.assert_called_once()
    mock_upsert_tickers.assert_called_once()

# Test empty ticker list handling
@patch('scripts.init.01_load_ticker_universe.fetch_tickers')
def test_main_empty_tickers(mock_fetch_tickers):
    """Test handling of empty ticker list."""
    mock_fetch_tickers.return_value = []
    
    module = load_script()
    with pytest.raises(ValueError, match="No tickers returned from Polygon API"):
        module.main()
