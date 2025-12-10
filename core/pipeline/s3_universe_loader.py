import os
import gzip
import io
import logging
import boto3
from datetime import datetime, timedelta
from botocore.config import Config
from botocore.exceptions import ClientError
import pandas as pd
from typing import Optional, List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class S3UniverseLoader:
    def __init__(self):
        """Initialize the S3UniverseLoader with AWS credentials and S3 configuration."""
        try:
            # Initialize S3 client with the working configuration
            self.s3 = boto3.client(
                's3',
                aws_access_key_id='e25caf9b-a4ec-4e41-98f0-73e13ed1564b',
                aws_secret_access_key='T1wfHMlp8DxyKJ0i8WqwfifydIPLyq4p',
                endpoint_url='https://files.massive.com',
                config=Config(signature_version='s3v4')
            )
            self.bucket_name = 'flatfiles'
            self.prefix = 'us_stocks_sip/day_aggs_v1'
            logger.info("S3UniverseLoader initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize S3UniverseLoader: {e}")
            raise

    def load_daily(self, date: Optional[datetime] = None) -> None:
        """
        Load daily universe data for the specified date.
        
        Args:
            date: The date to load data for. Defaults to yesterday.
        """
        if date is None:
            date = datetime.utcnow().date() - timedelta(days=1)
        
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"Starting daily load for {date_str}")
        
        # Construct the S3 key
        s3_key = f"{self.prefix}/{date.year:04d}/{date.month:02d}/{date_str}.csv.gz"
        
        try:
            # Download and process the file
            logger.info(f"Downloading {s3_key} from S3")
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            
            # Read and process the gzipped CSV
            with gzip.GzipFile(fileobj=response['Body']) as gz_file:
                df = pd.read_csv(io.BytesIO(gz_file.read()))
                logger.info(f"Successfully loaded {len(df)} records")
                
                # Process the data (add your processing logic here)
                self._process_data(df, date)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"File not found: {s3_key}")
            else:
                logger.error(f"Error downloading {s3_key}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def _process_data(self, df: pd.DataFrame, date: datetime) -> None:
        """
        Process the loaded data.
        
        Args:
            df: The DataFrame containing the loaded data.
            date: The date of the data.
        """
        # Add your data processing logic here
        logger.info(f"Processing data for {date.strftime('%Y-%m-%d')}")
        # Example: print the first few rows
        print(df.head())

    def list_available_dates(self, year: int, month: int) -> List[str]:
        """
        List all available dates for a given year and month.
        
        Args:
            year: The year to list dates for.
            month: The month to list dates for.
            
        Returns:
            A list of date strings in 'YYYY-MM-DD' format.
        """
        prefix = f"{self.prefix}/{year:04d}/{month:02d}/"
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=31  # Maximum number of days in a month
            )
            
            dates = []
            for obj in response.get('Contents', []):
                # Extract date from key (format: .../YYYY/MM/YYYY-MM-DD.csv.gz)
                date_str = obj['Key'].split('/')[-1].replace('.csv.gz', '')
                dates.append(date_str)
            
            return sorted(dates)
            
        except Exception as e:
            logger.error(f"Error listing dates: {e}")
            return []

def main():
    """Main function to run the S3UniverseLoader."""
    loader = S3UniverseLoader()
    
    # Example: Load yesterday's data
    loader.load_daily()
    
    # Example: List available dates for a specific month
    # dates = loader.list_available_dates(2025, 12)
    # print(f"Available dates: {dates}")

if __name__ == "__main__":
    main()
