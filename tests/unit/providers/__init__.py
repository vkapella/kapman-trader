"""
Base test classes and utilities for provider tests.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

class BaseProviderTest(unittest.TestCase):
    """Base test class for all provider tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before any tests are run."""
        # Common test data
        cls.test_symbol = 'AAPL'
        cls.test_start_date = datetime(2025, 12, 1)
        cls.test_end_date = datetime(2025, 12, 5)
        
    def assert_ohlcv_columns(self, df):
        """Assert that a DataFrame has the expected OHLCV columns."""
        expected_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in expected_columns:
            self.assertIn(col, df.columns, f"Missing expected column: {col}")
            
    def assert_valid_date_range(self, df, start_date, end_date):
        """Assert that the DataFrame's date range is within expected bounds."""
        if not df.empty:
            dates = pd.to_datetime(df['date'])
            self.assertTrue(all(dates >= pd.Timestamp(start_date)))
            self.assertTrue(all(dates <= pd.Timestamp(end_date) + timedelta(days=1)))
