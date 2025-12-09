#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import date, timedelta
from pprint import pprint
import traceback
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import the providers
from core.providers import (
    get_ai_provider,
    get_market_data_provider,
    AnalysisContext,
    Recommendation,
    OptionsChain,
    TechnicalData
)

# Load environment variables
load_dotenv(os.path.join(project_root, '.env'))

async def test_claude_provider():
    """Test the Claude AI provider."""
    print("\n=== Testing Claude AI Provider ===")
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n⚠️  ANTHROPIC_API_KEY not found in environment variables. Skipping Claude test.")
        return
    
    try:
        # Initialize the provider
        provider = get_ai_provider()
        print(f"\nUsing model: {provider.get_model_info().model}")
        
        # Create a test context
        context = AnalysisContext(
            symbol="AAPL",
            wyckoff_phase="Phase B",
            phase_confidence=0.75,
            events_detected=["Spring", "Test"],
            bc_score=75,
            spring_score=80,
            technical_indicators={
                "rsi": 65.5,
                "macd": {"histogram": 1.2, "signal": 0.8, "macd": 2.0},
                "sma_20": 150.0,
                "sma_50": 145.0,
                "volume": 12000000,
                "vwap": 148.5
            },
            dealer_metrics={
                "put_call_ratio": 1.5,
                "iv_rank": 65,
                "skew": 1.1
            },
            available_strikes=[140.0, 145.0, 150.0, 155.0, 160.0],
            available_expirations=["2024-12-20", "2025-01-17", "2025-03-21"]
        )
        
        print("\nGenerating recommendation...")
        recommendation = await provider.generate_recommendation(context)
        print("\n=== Recommendation ===")
        pprint(recommendation.dict())
        
        print("\nGenerating justification...")
        justification = await provider.generate_justification(recommendation, context)
        print("\n=== Justification ===\n" + justification)
        
        print("\n✅ Claude provider test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Claude provider test failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        raise

async def test_polygon_s3_provider():
    """Test the Polygon S3 provider."""
    print("\n=== Testing Polygon S3 Provider ===")
    
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n⚠️  Missing required environment variables: {', '.join(missing_vars)}")
        print("Skipping Polygon S3 test.")
        return
    
    try:
        # Initialize the provider
        provider = get_market_data_provider()
        provider_info = provider.get_provider_info()
        print(f"\nUsing provider: {provider_info.name}")
        
        # Test OHLCV data
        end_date = date.today()
        start_date = end_date - timedelta(days=5)  # Get data for the last 5 days
        
        print(f"\nFetching AAPL OHLCV data for {start_date} to {end_date}...")
        ohlcv_data = await provider.get_ohlcv("AAPL", start_date, end_date)
        
        if ohlcv_data is not None and not ohlcv_data.empty:
            print("\n=== OHLCV Data ===")
            print(f"Retrieved {len(ohlcv_data)} rows of data")
            print(f"Date range: {ohlcv_data['timestamp'].min()} to {ohlcv_data['timestamp'].max()}")
            print("\nSample data:")
            print(ohlcv_data.head())
        else:
            print("\nNo data returned. The date might be in the future or a weekend.")
        
        print("\n✅ Polygon S3 provider test completed!")
        
    except Exception as e:
        print(f"\n❌ Polygon S3 provider test failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        raise

async def main():
    """Run all provider tests."""
    print("=== Starting Provider Tests ===")
    
    # Test Claude provider
    await test_claude_provider()
    
    # Test Polygon S3 provider
    await test_polygon_s3_provider()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
