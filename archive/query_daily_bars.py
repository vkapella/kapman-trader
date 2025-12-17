import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
db_params = {
    'dbname': os.getenv('POSTGRES_DB'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432')
}

def query_daily_bars(limit=500):
    """Query daily bars with a limit on number of records"""
    try:
        # Create connection string
        conn_str = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
        engine = create_engine(conn_str)
        
        # Query
        query = f"""
        SELECT 
            t.ticker,
            d.date,
            d.open,
            d.high,
            d.low,
            d.close,
            d.volume,
            d.transactions
        FROM 
            daily_bars d
        JOIN 
            tickers t ON d.ticker_id = t.ticker_id
        ORDER BY 
            t.ticker, d.date
        LIMIT {limit}
        """
        
        # Execute and return as DataFrame
        df = pd.read_sql(query, engine)
        print(f"Successfully retrieved {len(df)} records")
        return df
        
    except Exception as e:
        print(f"Error querying database: {e}")
        return None

if __name__ == "__main__":
    # Get first 500 records
    df = query_daily_bars(500)
    if df is not None:
        # Display first 20 rows
        print("\nFirst 20 records:")
        print(df.head(20))
        
        # Save to CSV
        output_file = "daily_bars_sample.csv"
        df.to_csv(output_file, index=False)
        print(f"\nSaved full results to {output_file}")
