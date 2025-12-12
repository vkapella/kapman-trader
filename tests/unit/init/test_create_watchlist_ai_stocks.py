import sys
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Load the script module
def load_script():
    module_path = "scripts.init.02_create_watchlist_ai_stocks"
    return __import__(module_path, fromlist=[''])

# Test data
SAMPLE_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSM', 'ASML', 'AVGO', 'INTC', 'QCOM', 'AMD',
                 'ADBE', 'CRM', 'ORCL', 'IBM', 'CSCO', 'ACN', 'NOW', 'SNPS', 'CDNS', 'ANSS',
                 'INTU', 'ADSK', 'ADP', 'FIS', 'FISV', 'GPN', 'PYPL', 'SQ', 'MELI', 'SHOP',
                 'CRWD', 'ZS', 'NET', 'OKTA', 'PANW', 'FTNT', 'CHKP', 'VRSN', 'AKAM', 'FFIV',
                 'NTAP', 'WDC', 'STX', 'MU', 'LRCX', 'AMAT', 'KLAC', 'TER', 'MCHP', 'NXPI',
                 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS',
                 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO',
                 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI',
                 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL',
                 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN',
                 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO',
                 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM',
                 'TXN', 'ADI', 'SWKS', 'QRVO', 'MRVL', 'AVGO', 'QCOM', 'TXN', 'ADI', 'SWKS']

# Test database setup
@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine('sqlite:///:memory:')
    with engine.connect() as conn:
        conn.execute("""
            CREATE TABLE portfolios (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE portfolio_tickers (
                portfolio_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (portfolio_id, symbol),
                FOREIGN KEY (symbol) REFERENCES tickers(symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE tickers (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                exchange TEXT,
                asset_type TEXT,
                currency TEXT,
                is_active BOOLEAN
            )
        """)
        # Insert some test tickers
        for symbol in SAMPLE_TICKERS[:10]:  # Just insert first 10 for testing
            conn.execute(
                "INSERT INTO tickers (symbol, is_active) VALUES (?, ?)",
                (symbol, True)
            )
        conn.commit()
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

# Test cases
def test_ensure_portfolio_exists_creates_new():
    module = load_script()
    with patch('sqlalchemy.orm.Session') as mock_session:
        mock_conn = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.scalar.return_value = None
        mock_conn.execute.return_value.inserted_primary_key = [1]
        
        portfolio_id = module.ensure_portfolio_exists("AI_STOCKS")
        assert portfolio_id == 1
        assert mock_conn.execute.call_count >= 2  # Should have at least a select and insert

def test_ensure_portfolio_exists_returns_existing():
    module = load_script()
    with patch('sqlalchemy.orm.Session') as mock_session:
        mock_conn = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.scalar.return_value = 5
        
        portfolio_id = module.ensure_portfolio_exists("AI_STOCKS")
        assert portfolio_id == 5
        mock_conn.execute.assert_called_once()  # Should only do a select

@patch('sqlalchemy.orm.Session')
def test_load_ai_stocks_watchlist_new_tickers(mock_session, db_engine):
    module = load_script()
    mock_conn = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_conn
    
    # Mock ticker existence check
    def mock_execute(stmt, params=None):
        mock_result = MagicMock()
        if params and 'symbol' in params[0] and params[0]['symbol'] in ['AAPL', 'MSFT', 'GOOGL']:
            mock_result.scalar.return_value = True
        else:
            mock_result.scalar.return_value = False
        return mock_result
    
    mock_conn.execute.side_effect = mock_execute
    
    result = module.load_ai_stocks_watchlist(1, ['AAPL', 'MSFT', 'GOOGL', 'INVALID'])
    assert result['inserted'] == 3
    assert result['skipped'] == 0

@patch('sqlalchemy.orm.Session')
def test_load_ai_stocks_watchlist_duplicates(mock_session):
    module = load_script()
    mock_conn = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_conn
    
    # Mock ticker existence check to return True for all
    mock_conn.execute.return_value.scalar.return_value = True
    
    # Mock the count of existing portfolio tickers
    mock_conn.execute.return_value.scalar.return_value = 1
    
    result = module.load_ai_stocks_watchlist(1, ['AAPL', 'MSFT'])
    assert result['inserted'] == 0
    assert result['skipped'] == 2

@patch('scripts.init.02_create_watchlist_ai_stocks.load_ai_stocks_watchlist')
@patch('scripts.init.02_create_watchlist_ai_stocks.ensure_portfolio_exists')
def test_main_success(mock_ensure, mock_load):
    module = load_script()
    
    # Setup mocks
    mock_ensure.return_value = 1
    mock_load.return_value = {'inserted': 10, 'skipped': 5}
    
    # Mock the AI_STOCKS list
    with patch.object(module, 'AI_STOCKS', ['AAPL', 'MSFT']):
        result = module.main()
    
    assert result == {
        'portfolio_id': 1,
        'inserted': 10,
        'skipped': 5
    }
    mock_ensure.assert_called_once_with('AI_STOCKS')
    mock_load.assert_called_once_with(1, ['AAPL', 'MSFT'])

def test_script_loads():
    module = load_script()
    assert hasattr(module, 'main')
    assert hasattr(module, 'ensure_portfolio_exists')
    assert hasattr(module, 'load_ai_stocks_watchlist')
    assert hasattr(module, 'AI_STOCKS')
    assert len(module.AI_STOCKS) > 0
