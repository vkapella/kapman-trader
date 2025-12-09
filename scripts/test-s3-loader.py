import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment FIRST
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# NOW import core (after env is loaded)
import asyncio
from datetime import date, timedelta
from core.pipeline.s3_loader import S3OHLCVLoader

async def test_loader():
    loader = S3OHLCVLoader()
    
    # Use last Friday (Dec 6, 2024) - markets closed on weekends
    target_date = date(2024, 12, 6)
    
    print(f"Loading AAPL data for {target_date}...")
    result = await loader.load_daily(["AAPL"], target_date)
    
    print(f"\n✅ Loaded: {result['loaded']}")
    if result['errors']:
        print(f"❌ Errors: {result['errors']}")

if __name__ == "__main__":
    asyncio.run(test_loader())
