import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print environment variables (for debugging)
print("=== Environment Variables ===")
for var in ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_PORT']:
    value = os.getenv(var)
    print(f"{var}: {'*' * len(value) if value and var == 'POSTGRES_PASSWORD' else value}")

# Check if required env vars are set
missing_vars = [var for var in ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD'] if not os.getenv(var)]
if missing_vars:
    print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
    print("Please check your .env file")
else:
    print("\n✅ All required environment variables are set")

# Test database connection
try:
    import psycopg2
    from urllib.parse import urlparse, quote_plus
    
    db_params = {
        'dbname': os.getenv('POSTGRES_DB'),
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432')
    }
    
    print("\n=== Testing Database Connection ===")
    print(f"Attempting to connect to: postgresql://{db_params['user']}:******@{db_params['host']}:{db_params['port']}/{db_params['dbname']}")
    
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    db_version = cur.fetchone()
    print(f"✅ Successfully connected to PostgreSQL {db_version[0]}")
    
    # Check if tables exist
    print("\n=== Checking Required Tables ===")
    for table in ['tickers', 'daily_bars']:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, (table,))
        exists = cur.fetchone()[0]
        print(f"Table '{table}': {'✅ Found' if exists else '❌ Not Found'}")
    
    # Count records if tables exist
    if exists:
        cur.execute("SELECT COUNT(*) FROM tickers")
        ticker_count = cur.fetchone()[0]
        print(f"\n📊 Tickers in database: {ticker_count:,}")
        
        cur.execute("SELECT COUNT(*) FROM daily_bars")
        bars_count = cur.fetchone()[0]
        print(f"📊 Daily bars in database: {bars_count:,}")
    
    cur.close()
    conn.close()
    
except ImportError as e:
    print(f"\n❌ Error: {e}")
    print("Please install required packages with: pip install psycopg2-binary python-dotenv")
except Exception as e:
    print(f"\n❌ Database connection failed: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check if PostgreSQL is running")
    print("2. Verify your .env file has the correct credentials")
    print("3. Ensure your database accepts connections from this host")
    print("4. Check if the database and user exist")
    print("5. Verify the password is correct")
