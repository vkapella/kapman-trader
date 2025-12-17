from datetime import date, timedelta
import uuid
import pandas as pd
from sqlalchemy import text
from core.db.client import get_db_session
from core.providers import get_market_data_provider

class S3OHLCVLoader:
    def __init__(self):
        self.provider = get_market_data_provider()

    async def _get_or_create_ticker(self, session, symbol: str) -> uuid.UUID:
        """Get or create a ticker in the database and return its UUID."""
        result = await session.execute(
            text("SELECT id FROM tickers WHERE symbol = :symbol"),
            {"symbol": symbol}
        )
        ticker = result.scalar_one_or_none()
        
        if ticker:
            return ticker
            
        new_ticker_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO tickers (id, symbol, created_at)
                VALUES (:id, :symbol, NOW())
            """),
            {"id": new_ticker_id, "symbol": symbol}
        )
        return new_ticker_id

    async def _insert_ohlcv(self, records: list) -> int:
        """Insert OHLCV records using raw SQL with symbol_id."""
        if not records:
            return 0

        async with get_db_session() as session:
            try:
                symbol_to_id = {}
                for record in records:
                    symbol = record.get('symbol')
                    if symbol and symbol not in symbol_to_id:
                        symbol_to_id[symbol] = await self._get_or_create_ticker(session, symbol)
                
                mapped_records = []
                for record in records:
                    symbol = record.get('symbol')
                    if not symbol:
                        continue
                        
                    new_record = {
                        'symbol_id': symbol_to_id[symbol],
                        'time': record.get('time'),
                        'open': record.get('open'),
                        'high': record.get('high'),
                        'low': record.get('low'),
                        'close': record.get('close'),
                        'volume': record.get('volume'),
                        'vwap': record.get('vwap'),
                        'source': 'polygon_s3'
                    }
                    mapped_records.append(new_record)

                sql = """
                INSERT INTO ohlcv_daily 
                    (time, symbol_id, open, high, low, close, volume, vwap, source)
                VALUES 
                    (:time, :symbol_id, :open, :high, :low, :close, :volume, :vwap, :source)
                ON CONFLICT (time, symbol_id) 
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    vwap = EXCLUDED.vwap,
                    source = EXCLUDED.source
                """
                
                result = await session.execute(text(sql), mapped_records)
                await session.commit()
                return len(mapped_records)

            except Exception as e:
                await session.rollback()
                print(f"Error inserting OHLCV data: {str(e)}")
                raise

    async def load_daily(self, symbols: list, target_date: date) -> dict:
        """Load OHLCV data for multiple symbols for a specific date."""
        results = {
            'loaded': 0,
            'errors': []
        }
        
        try:
            all_records = []
            
            for symbol in symbols:
                try:
                    print(f"\nLoading {symbol} data for {target_date}...")
                    df = await self.provider.get_ohlcv(
                        symbol=symbol,
                        start=target_date,
                        end=target_date
                    )
                    
                    if not df.empty:
                        # Convert time to datetime and ensure it's in UTC
                        df['time'] = pd.to_datetime(df['time'])
                        if df['time'].dt.tz is not None:
                            df['time'] = df['time'].dt.tz_convert('UTC')
                        else:
                            df['time'] = df['time'].dt.tz_localize('UTC')
                        
                        records = df.to_dict('records')
                        all_records.extend(records)
                        print(f"✅ Successfully retrieved {len(records)} records for {symbol}")
                    else:
                        print(f"⚠️ No data found for {symbol} on {target_date}")
                        
                except Exception as e:
                    error_msg = f"Error processing {symbol} on {target_date}: {str(e)}"
                    print(f"❌ {error_msg}")
                    results['errors'].append(error_msg)
                    continue
            
            if not all_records:
                print("⚠️ No data found for any symbol")
                return results
            
            try:
                inserted = await self._insert_ohlcv(all_records)
                results['loaded'] = inserted
                print(f"\n✅ Successfully loaded {inserted} records")
            except Exception as e:
                error_msg = f"Database error for date {target_date}: {str(e)}"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error in load_daily for date {target_date}: {str(e)}"
            print(f"❌ {error_msg}")
            results['errors'].append(error_msg)
            
        return results

    async def backfill(self, symbols: list, start: date, end: date) -> dict:
        """Backfill OHLCV data for multiple symbols over a date range."""
        results = {
            'total_loaded': 0,
            'errors': []
        }
        
        current_date = start
        while current_date <= end:
            if current_date.weekday() < 5:  # Skip weekends
                print(f"\n📅 Processing date: {current_date}")
                daily_result = await self.load_daily(symbols, current_date)
                results['total_loaded'] += daily_result.get('loaded', 0)
                results['errors'].extend(daily_result.get('errors', []))
            
            current_date += timedelta(days=1)
        
        return results
