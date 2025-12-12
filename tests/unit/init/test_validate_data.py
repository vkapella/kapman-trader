import os
import sys
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, create_autospec
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

# Import the module we're testing
import scripts.init.validate_data as module

@pytest.fixture(autouse=True)
def mock_environment(monkeypatch):
    """Mock environment variables for all tests."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('ENV', 'dev')

@pytest.fixture
def mock_db_session():
    """Create a mock database session with execute method."""
    # Create a mock session with execute method
    session = MagicMock(spec=Session)
    # Create a mock for the execute method
    session.execute.return_value = MagicMock()
    return session

def test_universe_count_valid(mock_db_session):
    """Test validation of ticker universe count."""
    # Setup mock return values
    mock_count = MagicMock()
    mock_count.scalar.return_value = 3  # For COUNT query
    
    mock_required = MagicMock()
    mock_required.fetchall.return_value = []  # No missing required columns
    
    mock_db_session.execute.side_effect = [mock_count, mock_required]
    
    # Call the function with the mock session
    result = module.validate_universe(mock_db_session)
    assert result['universe_count'] == 3
    assert result['exit_code'] == 0
    assert result.get('missing_required_columns') == []

def test_universe_missing_required_columns(mock_db_session):
    """Test validation of missing required columns in ticker universe."""
    # Setup mock return values
    mock_count = MagicMock()
    mock_count.scalar.return_value = 3  # For COUNT query
    
    mock_missing = MagicMock()
    mock_missing.fetchall.return_value = [('AAPL',)]  # Missing required columns
    
    mock_db_session.execute.side_effect = [mock_count, mock_missing]
    
    # Call the function with the mock session
    result = module.validate_universe(mock_db_session)
    assert result['exit_code'] > 0
    assert 'missing_required_columns' in result
    assert len(result['missing_required_columns']) > 0

def test_watchlist_count_valid(mock_db_session):
    """Test validation of watchlist count."""
    # Setup mock return values
    mock_portfolio = MagicMock()
    mock_portfolio.fetchone.return_value = (1,)  # Portfolio exists
    
    mock_watchlist = MagicMock()
    mock_watchlist.fetchall.return_value = [('AAPL',), ('MSFT',), ('GOOGL',)]  # Watchlist symbols
    
    # Mock the symbol existence check
    def mock_execute(query, *args, **kwargs):
        if "SELECT DISTINCT t.symbol" in str(query):
            return mock_watchlist
        elif "SELECT id FROM portfolios" in str(query):
            return mock_portfolio
        elif "SELECT symbol FROM tickers" in str(query):
            mock_tickers = MagicMock()
            mock_tickers.fetchall.return_value = [('AAPL',), ('MSFT',), ('GOOGL',)]
            return mock_tickers
        return MagicMock()
    
    mock_db_session.execute.side_effect = mock_execute
    
    # Call the function with the mock session
    result = module.validate_watchlist(mock_db_session)
    assert result['exit_code'] == 0
    assert result['watchlist_count'] == 3
    assert result.get('missing_watchlist_symbols') == []

def test_watchlist_missing_symbol(mock_db_session):
    """Test validation of missing watchlist symbols."""
    # Setup mock return values
    mock_portfolio = MagicMock()
    mock_portfolio.fetchone.return_value = (1,)  # Portfolio exists
    
    mock_watchlist = MagicMock()
    mock_watchlist.fetchall.return_value = [('AAPL',), ('INVALID',)]  # Watchlist symbols
    
    # Mock the symbol existence check
    def mock_execute(query, *args, **kwargs):
        if "SELECT DISTINCT t.symbol" in str(query):
            return mock_watchlist
        elif "SELECT id FROM portfolios" in str(query):
            return mock_portfolio
        elif "SELECT symbol FROM tickers" in str(query):
            mock_tickers = MagicMock()
            mock_tickers.fetchall.return_value = [('AAPL',)]  # Only AAPL exists
            return mock_tickers
        return MagicMock()
    
    mock_db_session.execute.side_effect = mock_execute
    
    # Call the function with the mock session
    result = module.validate_watchlist(mock_db_session)
    assert result['exit_code'] > 0
    assert 'missing_watchlist_symbols' in result
    assert 'INVALID' in result['missing_watchlist_symbols']

def test_incomplete_ohlcv_history(mock_db_session):
    """Test validation of incomplete OHLCV history."""
    # Setup mock return values
    mock_symbols = MagicMock()
    mock_symbols.fetchall.return_value = [('AAPL',), ('MSFT',)]  # Watchlist symbols
    
    # Mock the OHLCV data query
    def mock_execute(query, *args, **kwargs):
        if "FROM portfolio_tickers pt" in str(query):
            return mock_symbols
        elif "COUNT" in str(query):
            mock_count = MagicMock()
            mock_count.fetchall.return_value = [{'symbol': 'AAPL', 'count': 15}]
            return mock_count
        return MagicMock()
    
    mock_db_session.execute.side_effect = mock_execute
    
    # Call the function with the mock session and expected days
    result = module.validate_ohlcv(mock_db_session, expected_days=30)
    assert result['exit_code'] > 0
    assert 'symbols_with_incomplete_ohlcv' in result
    assert 'AAPL' in result['symbols_with_incomplete_ohlcv']

def test_missing_dates(mock_db_session):
    """Test validation of missing dates in OHLCV data."""
    # Create test data with missing dates
    today = date.today()
    dates = [today - timedelta(days=x) for x in range(30) if x != 15]  # Missing one date
    
    # Setup mock return values
    mock_symbols = MagicMock()
    mock_symbols.fetchall.return_value = [('AAPL',)]  # Watchlist symbols
    
    mock_ohlcv = MagicMock()
    mock_ohlcv.fetchall.return_value = [(d, 100.0, 101.0, 99.0, 100.5, 1000) for d in dates]
    
    def mock_execute(query, *args, **kwargs):
        if "FROM portfolio_tickers pt" in str(query):
            return mock_symbols
        elif "SELECT date, open, high, low, close, volume" in str(query):
            return mock_ohlcv
        elif "COUNT" in str(query):
            mock_count = MagicMock()
            mock_count.fetchall.return_value = [{'symbol': 'AAPL', 'count': 29}]
            return mock_count
        return MagicMock()
    
    mock_db_session.execute.side_effect = mock_execute
    
    # Call the function with the mock session and expected days
    result = module.validate_ohlcv(mock_db_session, expected_days=30)
    assert result['exit_code'] > 0
    assert 'missing_dates' in result
    assert 'AAPL' in result['missing_dates']
    assert len(result['missing_dates']['AAPL']) == 1

def test_malformed_ohlcv_values(mock_db_session):
    """Test validation of malformed OHLCV values."""
    # Create test data with invalid OHLCV values
    today = date.today()
    ohlcv_data = [(today, 100.0, 99.0, 98.0, 99.5, 1000)]  # high < open
    
    # Setup mock return values
    mock_symbols = MagicMock()
    mock_symbols.fetchall.return_value = [('AAPL',)]  # Watchlist symbols
    
    mock_ohlcv = MagicMock()
    mock_ohlcv.fetchall.return_value = ohlcv_data
    
    def mock_execute(query, *args, **kwargs):
        if "FROM portfolio_tickers pt" in str(query):
            return mock_symbols
        elif "SELECT date, open, high, low, close, volume" in str(query):
            return mock_ohlcv
        elif "COUNT" in str(query):
            mock_count = MagicMock()
            mock_count.fetchall.return_value = [{'symbol': 'AAPL', 'count': 30}]
            return mock_count
        return MagicMock()
    
    mock_db_session.execute.side_effect = mock_execute
    
    # Call the function with the mock session and expected days
    result = module.validate_ohlcv(mock_db_session, expected_days=30)
    assert result['exit_code'] > 0
    assert 'symbols_with_bad_ohlcv_values' in result
    assert 'AAPL' in result['symbols_with_bad_ohlcv_values']

@patch('scripts.init.validate_data.validate_universe')
@patch('scripts.init.validate_data.validate_watchlist')
@patch('scripts.init.validate_data.validate_ohlcv')
@patch('scripts.init.validate_data.load_env_settings')
def test_valid_data_passes(mock_load_env, mock_validate_ohlcv, mock_validate_watchlist, 
                          mock_validate_universe, mock_db_session):
    """Test that valid data passes all validations."""
    # Setup mock return values
    mock_load_env.return_value = 30
    mock_validate_universe.return_value = {
        'universe_count': 3,
        'missing_required_columns': [],
        'exit_code': 0
    }
    mock_validate_watchlist.return_value = {
        'watchlist_count': 3,
        'missing_watchlist_symbols': [],
        'exit_code': 0
    }
    mock_validate_ohlcv.return_value = {
        'symbols_with_incomplete_ohlcv': [],
        'symbols_with_bad_ohlcv_values': [],
        'missing_dates': {},
        'exit_code': 0
    }
    
    # Mock the database session
    with patch('scripts.init.validate_data.get_db_session') as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_db_session
        
        # Call the validate_all function
        result = module.validate_all()
        
        # Verify the results
        assert result['exit_code'] == 0
        assert result['universe_count'] == 3
        assert result['watchlist_count'] == 3
        assert result.get('missing_watchlist_symbols') == []
        assert result.get('symbols_with_incomplete_ohlcv') == []
        assert result.get('symbols_with_bad_ohlcv_values') == []
        assert result.get('missing_dates') == {}
