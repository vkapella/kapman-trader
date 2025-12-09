import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Union
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import pandas as pd
import gzip
from io import StringIO, BytesIO
import pytz
from ..market_data.base import MarketDataProvider, OptionsChain, TechnicalData, ProviderInfo

class PolygonS3Provider(MarketDataProvider):
    def __init__(
        self,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        region_name: str = "us-east-1",
        bucket: str = "flatfiles",
        data_type: str = "us_stocks_sip",
        endpoint_url: Optional[str] = None
    ):
        self.bucket = bucket
        self.data_type = data_type
        self.timezone = pytz.timezone('US/Eastern')
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name=region_name
        )

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="Massive Stocks Data",
            capabilities=["ohlcv", "trades", "quotes"],
            version="1.0.0",
            tier="enterprise"
        )

    def _get_s3_key(self, symbol: str, date_obj: date, data_type: str = "day_aggs") -> str:
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%m")
        day = date_obj.strftime("%d")
        return f"{self.data_type}/{data_type}_v1/{year}/{month}/{year}-{month}-{day}.csv.gz"

    def _process_daily_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and clean the daily data DataFrame."""
        try:
            # Rename columns to match our schema
            df = df.rename(columns={'ticker': 'symbol'})
            
            # Convert window_start to datetime and create time column
            if 'window_start' in df.columns:
                df['time'] = pd.to_datetime(df['window_start'], unit='ns')
                df['time'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(self.timezone)
            
            # Calculate VWAP as (high + low + close) / 3 if not present
            if 'vwap' not in df.columns and all(col in df.columns for col in ['high', 'low', 'close']):
                df['vwap'] = (df['high'] + df['low'] + df['close']) / 3
            
            # Select and order columns
            columns = ['symbol', 'time', 'open', 'high', 'low', 'close', 'volume', 'vwap']
            df = df[[col for col in columns if col in df.columns]]
            
            return df
            
        except Exception as e:
            print(f"⚠️ Error processing data: {str(e)}")
            return pd.DataFrame()

    async def _get_daily_data(self, date_obj: date) -> pd.DataFrame:
        try:
            key = self._get_s3_key("", date_obj, "day_aggs")
            print(f"Fetching data from s3://{self.bucket}/{key}")
            
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            
            with gzip.GzipFile(fileobj=BytesIO(response['Body'].read())) as gz_file:
                content = gz_file.read().decode('utf-8')
            
            df = pd.read_csv(StringIO(content))
            print(f"Raw columns: {df.columns.tolist()}")
            
            return self._process_daily_data(df)
            
        except self.s3.exceptions.NoSuchKey:
            print(f"⚠️ No data found for {date_obj}")
            return pd.DataFrame()
        except Exception as e:
            print(f"⚠️ Error fetching data for {date_obj}: {str(e)}")
            return pd.DataFrame()

    async def get_ohlcv(
        self, 
        symbol: str, 
        start: date, 
        end: date, 
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        try:
            if timeframe != "1d":
                print("⚠️ Warning: Only daily ('1d') timeframe is supported")
                return pd.DataFrame()
            
            date_range = pd.date_range(start=start, end=end)
            all_data = []
            
            for single_date in date_range:
                current_date = single_date.date()
                print(f"\nProcessing date: {current_date}")
                
                df = await self._get_daily_data(current_date)
                
                if not df.empty:
                    # Filter for the requested symbol
                    df = df[df['symbol'].str.upper() == symbol.upper()]
                    
                    if not df.empty:
                        print(f"Found {len(df)} records for {symbol.upper()} on {current_date}")
                        all_data.append(df)
                    else:
                        print(f"No data found for {symbol.upper()} on {current_date}")
                else:
                    print(f"No data available for any symbol on {current_date}")
            
            if not all_data:
                print("\n❌ No OHLCV data found for the specified date range")
                return pd.DataFrame()
            
            # Combine all data and sort by time
            result = pd.concat(all_data, ignore_index=True)
            result = result.sort_values('time')
            
            print(f"\n✅ Successfully retrieved {len(result)} days of OHLCV data")
            print(f"Final columns: {result.columns.tolist()}")
            print(f"Sample data: {result.head(1).to_dict('records')}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Error in get_ohlcv: {str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    async def list_available_dates(self) -> List[date]:
        print("Listing available dates...")
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            prefix = f"{self.data_type}/day_aggs_v1/"
            result = paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter='/')
            
            dates = set()
            for page in result:
                if 'CommonPrefixes' in page:
                    for obj in page['CommonPrefixes']:
                        try:
                            date_str = obj['Prefix'].split('/')[-2]
                            dates.add(date_str)
                        except:
                            continue
            
            sorted_dates = sorted([datetime.strptime(d, '%Y-%m-%d').date() for d in dates])
            return sorted_dates
            
        except Exception as e:
            print(f"Error listing available dates: {str(e)}")
            return []

    async def get_options_chain(self, symbol: str, expiration: Optional[str] = None) -> OptionsChain:
        raise NotImplementedError("Options chain not implemented in this provider")

    async def get_technical_indicators(
        self, symbol: str, timeframe: str = "1d", lookback: int = 100
    ) -> TechnicalData:
        raise NotImplementedError("Technical indicators not implemented in this provider")
