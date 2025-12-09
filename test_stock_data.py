import asyncio
from datetime import datetime, timedelta
import os
import sys
import boto3
from botocore.client import Config
import pandas as pd
import gzip
from io import BytesIO, StringIO
from typing import List, Optional

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

class StockDataFetcher:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id="5c4b2c4b-3ef5-46bf-a415-e916576fd837",
            aws_secret_access_key="UuUXOYAWS7WTTVdPjQtVHM7EFqTquRwX",
            endpoint_url="https://files.massive.com",
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name="us-east-1"
        )
        self.bucket = "flatfiles"
        self.base_prefix = "us_stocks_sip/day_aggs_v1"

    def get_s3_key(self, date_obj: datetime) -> str:
        """Generate S3 key for daily data."""
        return f"{self.base_prefix}/{date_obj.year}/{date_obj.month:02d}/{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}.csv.gz"

    def process_dataframe(self, df: pd.DataFrame, date_obj: datetime) -> pd.DataFrame:
        """Process the raw dataframe to match the expected format."""
        if df.empty:
            return df
            
        # Rename columns to match our expected format
        df = df.rename(columns={
            'ticker': 'symbol',
            'window_start': 'timestamp'
        })
        
        # Convert timestamp from nanoseconds to datetime
        if 'timestamp' in df.columns:
            df['date'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('US/Eastern')
        
        # Add date column if not present
        if 'date' not in df.columns:
            df['date'] = date_obj.date()
            
        return df

    async def fetch_daily_data(self, symbol: str, date_obj: datetime) -> pd.DataFrame:
        """Fetch and process data for a specific date and symbol."""
        try:
            key = self.get_s3_key(date_obj)
            print(f"Fetching data from s3://{self.bucket}/{key}")
            
            # Get and decompress the file
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            
            # Read and decompress the gzipped content
            with gzip.GzipFile(fileobj=BytesIO(response['Body'].read())) as gz_file:
                content = gz_file.read().decode('utf-8')
            
            # Read the CSV data
            df = pd.read_csv(StringIO(content))
            
            if not df.empty:
                # Filter by symbol
                df = df[df['ticker'] == symbol.upper()].copy()
                if not df.empty:
                    df = self.process_dataframe(df, date_obj)
                    print(f"✅ Found {len(df)} records for {symbol.upper()} on {date_obj.date()}")
                return df
            return pd.DataFrame()
            
        except self.s3.exceptions.NoSuchKey:
            print(f"⚠️ No data file found for {date_obj.date()}")
            return pd.DataFrame()
        except Exception as e:
            print(f"⚠️ Error processing data for {date_obj.date()}: {str(e)}")
            return pd.DataFrame()

    async def analyze_stock(self, symbol: str, days_back: int = 30):
        """Analyze stock data for the specified symbol."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"\n=== Analyzing {symbol.upper()} data from {start_date.date()} to {end_date.date()} ===")
        
        # Fetch data for each day in the date range
        all_data = []
        current_date = start_date
        
        while current_date <= end_date:
            df = await self.fetch_daily_data(symbol, current_date)
            if not df.empty:
                all_data.append(df)
            current_date += timedelta(days=1)
        
        if not all_data:
            print(f"\n❌ No data found for {symbol.upper()} in the specified date range")
            return
        
        # Combine all data
        df = pd.concat(all_data, ignore_index=True)
        
        # Ensure we have the required columns
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                print(f"⚠️ Missing column in data: {col}")
                return
        
        # Sort by date
        df = df.sort_values('date')
        
        # Display the data
        print("\n=== Daily OHLCV Data ===")
        print(df[['date', 'open', 'high', 'low', 'close', 'volume']].to_string(index=False))
        
        # Calculate and display summary statistics
        print("\n=== Summary Statistics ===")
        print(f"Time Period: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
        print(f"Starting Price: ${df['open'].iloc[0]:.2f}")
        print(f"Ending Price: ${df['close'].iloc[-1]:.2f}")
        price_change = (df['close'].iloc[-1] / df['open'].iloc[0] - 1) * 100
        print(f"Price Change: {price_change:+.2f}%")
        print(f"Average Daily Volume: {df['volume'].mean():,.0f} shares")
        print(f"Highest Price: ${df['high'].max():.2f}")
        print(f"Lowest Price: ${df['low'].min():.2f}")

async def main():
    # Initialize the fetcher
    fetcher = StockDataFetcher()
    
    # Test with AAPL for the last 30 days
    await fetcher.analyze_stock("AAPL", days_back=7)  # Reduced to 7 days for testing

if __name__ == "__main__":
    asyncio.run(main())
