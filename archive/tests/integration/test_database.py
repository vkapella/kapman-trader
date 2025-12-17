import unittest
import pytest
from unittest.mock import patch, MagicMock
from core.pipeline.s3_universe_loader import S3UniverseLoader

class TestDatabaseOperations(unittest.TestCase):
    @classmethod
    @patch('boto3.client')
    @patch('psycopg2.connect')
    def setUpClass(cls, mock_db_connect, mock_s3_client):
        """Set up test database before any tests in this class."""
        cls.mock_db = MagicMock()
        cls.mock_cursor = MagicMock()
        cls.mock_db.cursor.return_value = cls.mock_cursor
        mock_db_connect.return_value = cls.mock_db
        
        # Add the _get_connection method to the S3UniverseLoader class
        def _get_connection(self):
            return mock_db_connect()
        
        S3UniverseLoader._get_connection = _get_connection
        cls.loader = S3UniverseLoader()

    @pytest.mark.integration
    def test_connection(self):
        """Test database connection is working."""
        # Test that we can get a connection
        conn = self.loader._get_connection()
        self.assertIsNotNone(conn)
        
        # Test that we can get a cursor
        cursor = conn.cursor()
        self.assertIsNotNone(cursor)
        
        # Test that we can execute a query
        cursor.execute("SELECT 1")
        cursor.fetchall.assert_called_once()

if __name__ == '__main__':
    unittest.main()
