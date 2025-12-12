import os
import sys
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import the module we're testing
import scripts.init.backfill_ohlcv as module

@pytest.fixture
def mock_env_dev(monkeypatch):
    """Set ENV=dev for testing."""
    monkeypatch.setenv('ENV', 'dev')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('POLYGON_API_KEY', 'test_key')

@pytest.fixture
def mock_env_prod(monkeypatch):
    """Set ENV=prod for testing."""
    monkeypatch.setenv('ENV', 'prod')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('POLYGON_API_KEY', 'test_key')

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    engine = MagicMock(spec=Engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

def test_env_depth_dev(mock_env_dev):
    """Test load_env_settings returns correct days for dev environment."""
    days = module.load_env_settings()
    assert days == 30

def test_env_depth_prod(mock_env_prod):
    """Test load_env_settings returns correct days for prod environment."""
    days = module.load_env_settings()
    assert days == 730

def test_get_ai_stocks(mock_db_session):
    """Test get_ai_stocks returns list of symbols."""
    # Setup mock return value
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [('AAPL',), ('NVDA',), ('MSFT',)]
    
    # Patch the session's execute method
    with patch.object(mock_db_session, 'execute', return_value=mock_result) as mock_execute:
        symbols = module.get_ai_stocks(mock_db_session)
        
        # Verify the function was called with the right query
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0][0].text
        assert 'portfolio_tickers' in call_args
        assert 'AI_STOCKS' in call_args
        
        # Verify the result
        assert symbols == ['AAPL', 'NVDA', 'MSFT']

@patch('os.getenv')
@patch('requests.get')
def test_fetch_ohlcv_polygon_success(mock_get, mock_getenv):
    """Test fetch_ohlcv_polygon with pagination."""
    # Mock environment variable
    mock_getenv.return_value = 'test_api_key'
    
    # Mock first page response
    mock_response1 = MagicMock()
    mock_response1.json.return_value = {
        'results': [
            {'t': 1672272000000, 'o': 100.0, 'h': 101.0, 'l': 99.0, 'c': 100.5, 'v': 1000}
        ],
        'next_url': 'http://next-page'
    }
    
    # Mock second page response
    mock_response2 = MagicMock()
    mock_response2.json.return_value = {
        'results': [
            {'t': 1672358400000, 'o': 100.5, 'h': 102.0, 'l': 100.0, 'c': 101.5, 'v': 1200}
        ]
    }
    
    # Set up the mock to return the responses in order
    mock_get.side_effect = [mock_response1, mock_response2]
    
    # Call the function with dates that match the timestamps
    start_date = date(2022, 12, 28)
    end_date = date(2022, 12, 29)
    result = module.fetch_ohlcv_polygon('AAPL', start_date, end_date)
    
    # Verify the results
    assert len(result) == 2
    assert result[0]['symbol'] == 'AAPL'
    assert result[0]['date'] == date(2022, 12, 28)
    assert result[0]['open'] == 100.0
    assert result[1]['date'] == date(2022, 12, 29)

def test_insert_ohlcv(mock_db_session):
    """Test insert_ohlcv executes correct SQL."""
    # Test data
    test_bars = [{
        'symbol': 'AAPL',
        'date': date(2023, 1, 1),
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000
    }]
    
    # Call the function
    with patch.object(mock_db_session, 'execute') as mock_execute:
        module.insert_ohlcv(mock_db_session, test_bars)
        
        # Verify the execute was called
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0][0].text
        assert 'ohlcv_daily' in call_args
        assert 'INSERT' in call_args
        assert 'ON CONFLICT (symbol, date) DO NOTHING' in call_args

@patch('os.getenv')
@patch('scripts.init.backfill_ohlcv.insert_ohlcv')
@patch('scripts.init.backfill_ohlcv.fetch_ohlcv_polygon')
@patch('scripts.init.backfill_ohlcv.get_ai_stocks')
@patch('scripts.init.backfill_ohlcv.load_env_settings')
@patch('scripts.init.backfill_ohlcv.get_db_session')
def test_main_success(mock_db_session, mock_load_env, mock_get_stocks, 
                     mock_fetch_ohlcv, mock_insert_ohlcv, mock_getenv):
    """Test main function with successful execution."""
    # Setup mocks
    mock_getenv.return_value = 'test_api_key'
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session
    mock_load_env.return_value = 30
    mock_get_stocks.return_value = ['AAPL', 'MSFT']
    
    # Mock OHLCV data
    mock_fetch_ohlcv.return_value = [{
        'symbol': 'AAPL',
        'date': date.today() - timedelta(days=1),
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000
    }]
    
    # Mock insert result
    mock_insert_ohlcv.return_value = {'inserted': 1, 'skipped': 0}
    
    # Call main
    result = module.main()
    
    # Verify results
    assert result['symbols'] == 2
    assert result['rows_inserted'] == 2  # 1 for each symbol
    assert result['rows_skipped'] == 0
    assert mock_insert_ohlcv.called

@patch('os.getenv')
@patch('scripts.init.backfill_ohlcv.get_ai_stocks')
@patch('scripts.init.backfill_ohlcv.load_env_settings')
@patch('scripts.init.backfill_ohlcv.get_db_session')
def test_main_no_symbols(mock_db_session, mock_load_env, mock_get_stocks, mock_getenv):
    """Test main function when no symbols are found."""
    # Setup mocks
    mock_getenv.return_value = 'test_api_key'
    mock_session = MagicMock()
    mock_db_session.return_value.__enter__.return_value = mock_session
    mock_load_env.return_value = 30
    mock_get_stocks.return_value = []  # No symbols
    
    # Call main
    result = module.main()
    
    # Verify results
    assert result == {
        'symbols': 0,
        'rows_inserted': 0,
        'rows_skipped': 0
    }
