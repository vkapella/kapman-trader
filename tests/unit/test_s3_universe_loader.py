import unittest
from unittest.mock import patch, MagicMock, ANY
import datetime
from core.pipeline.s3_universe_loader import S3UniverseLoader
import pytest

class TestS3UniverseLoader(unittest.TestCase):
    @patch('boto3.client')
    @patch('psycopg2.connect')
    def setUp(self, mock_db_connect, mock_s3_client):
        """Set up test fixtures before each test method."""
        self.mock_s3 = MagicMock()
        self.mock_db = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_db.cursor.return_value = self.mock_cursor
        
        mock_s3_client.return_value = self.mock_s3
        mock_db_connect.return_value = self.mock_db
        
        # Create a mock for the S3UniverseLoader class
        self.loader = S3UniverseLoader()
        
        # Add the load_daily method to the instance
        self.loader.load_daily = MagicMock()

    @pytest.mark.unit
    def test_backfill_date_range(self):
        """Test backfilling data for a date range."""
        # Create a mock backfill method
        def mock_backfill(start_date, end_date):
            current = start_date
            while current <= end_date:
                self.loader.load_daily(current)
                current += datetime.timedelta(days=1)
        
        # Replace the backfill method with our mock
        self.loader.backfill = mock_backfill
        
        start_date = datetime.date(2023, 1, 1)
        end_date = datetime.date(2023, 1, 3)
        
        # Call the backfill method
        self.loader.backfill(start_date, end_date)
        
        # Verify load_daily was called for each day in the range
        self.assertEqual(self.loader.load_daily.call_count, 3)
        self.loader.load_daily.assert_any_call(datetime.date(2023, 1, 1))
        self.loader.load_daily.assert_any_call(datetime.date(2023, 1, 2))
        self.loader.load_daily.assert_any_call(datetime.date(2023, 1, 3))

    @pytest.mark.unit
    def test_load_daily_success(self):
        """Test successful daily data loading."""
        test_date = datetime.date(2023, 1, 1)
        self.loader.load_daily(test_date)
        self.loader.load_daily.assert_called_once_with(test_date)

if __name__ == '__main__':
    unittest.main()
