import os
import sys
import asyncio
from datetime import date, datetime, timezone, timedelta

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

from core.providers import get_market_data_provider

async def test_provider():
    print("=== Testing Stocks Data Provider ===")
    
    try:
        # Initialize the provider
        print("Initializing provider...")
        provider = get_market_data_provider()
        provider_info = provider.get_provider_info()
        
        print(f"\nProvider: {provider_info.name}")
        print(f"Version: {getattr(provider_info, 'version', 'N/A')}")
        print(f"Tier: {getattr(provider_info, 'tier', 'N/A')}")
        print(f"Capabilities: {', '.join(getattr(provider_info, 'capabilities', []))}")
        
        # List available symbols
        print("\n=== Listing Available Symbols ===")
        symbols = await provider.list_available_symbols()
        if symbols:
            print(f"Found {len(symbols)} symbols. First 10:")
            for i, symbol in enumerate(symbols[:10], 1):
                print(f"  {i}. {symbol}")
            if len(symbols) > 10:
                print(f"  ... and {len(symbols) - 10} more")
            
            # Test with the first available symbol
            test_symbol = symbols[0]
            print(f"\n=== Testing with symbol: {test_symbol} ===")
            
            # Test OHLCV data
            print("\n=== Testing OHLCV Data ===")
            end_date = date.today()
            start_date = end_date - timedelta(days=7)  # Last 7 days
            ohlcv_data = await provider.get_ohlcv(test_symbol, start_date, end_date)
            print(f"OHLCV data shape: {ohlcv_data.shape if ohlcv_data is not None else 'None'}")
            
        else:
            print("No symbols found. Checking bucket contents...")
            # If no symbols found, try to list the bucket contents
            try:
                contents = await provider._list_bucket_contents()
                print("\nBucket contents:")
                for item in contents[:10]:  # Show first 10 items
                    key = item.get('Key', item.get('Prefix', 'Unknown'))
                    size = f" ({item.get('Size', 0)} bytes)" if 'Size' in item else ""
                    print(f"- {key}{size}")
            except Exception as e:
                print(f"Error listing bucket contents: {str(e)}")
    
    except Exception as e:
        print(f"\n❌ Error in test_provider: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_provider())
