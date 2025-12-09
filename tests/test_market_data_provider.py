"""
Tests for market data providers.
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
import os

class TestPolygonS3Provider(unittest.TestCase):
    """Test cases for PolygonS3Provider."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.test_symbol = 'AAPL'
        cls.test_start_date = datetime(2025, 12, 1)
        cls.test_end_date = datetime(2025, 12, 5)
        
        # Set up test environment
        os.environ['AWS_ACCESS_KEY_ID'] = 'test-key'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret'
        os.environ['S3_ENDPOINT_URL'] = 'https://test-endpoint.com'
        os.environ['S3_BUCKET'] = 'flatfiles'
    
    @patch('boto3.client')
    def test_get_ohlcv(self, mock_boto):
        """Test fetching OHLCV data."""
        # Import here to avoid loading boto3 during test discovery
        from core.providers.market_data.polygon_s3 import PolygonS3Provider
        
        # Mock S3 response
        test_data = """ticker,volume,open,close,high,low,window_start,transactions
AAPL,1000000,150.0,152.0,153.0,149.5,1733558400000000000,5000"""
        
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=test_data.encode('utf-8'))),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        # Initialize provider with correct parameters
        provider = PolygonS3Provider()
        
        # Test the method
        result = provider.get_ohlcv(
            symbol=self.test_symbol,
            start_date=self.test_start_date,
            end_date=self.test_end_date
        )
        
        # Verify the results
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)
        self.assertEqual(result['close'].iloc[0], 152.0)

if __name__ == '__main__':
    unittest.main()
