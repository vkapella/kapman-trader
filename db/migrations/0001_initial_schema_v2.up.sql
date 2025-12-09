-- 0001_initial_schema_v2.up.sql
-- Consolidated schema for Kapman Trader

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Create enum types
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_type') THEN
        CREATE TYPE asset_type AS ENUM ('STOCK', 'OPTION', 'CRYPTO', 'FUTURE');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_type') THEN
        CREATE TYPE order_type AS ENUM ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT', 'TRAILING_STOP');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_side') THEN
        CREATE TYPE order_side AS ENUM ('BUY', 'SELL');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
        CREATE TYPE order_status AS ENUM ('OPEN', 'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'REJECTED');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'position_side') THEN
        CREATE TYPE position_side AS ENUM ('LONG', 'SHORT');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'strategy_type') THEN
        CREATE TYPE strategy_type AS ENUM ('MOMENTUM', 'MEAN_REVERSION', 'ARBITRAGE', 'MARKET_MAKING', 'HEDGING');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signal_type') THEN
        CREATE TYPE signal_type AS ENUM ('ENTRY', 'EXIT', 'STOP_LOSS', 'TAKE_PROFIT');
    END IF;
END $$;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Exchanges table
CREATE TABLE IF NOT EXISTS exchanges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    country TEXT,
    timezone TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Assets table
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    name TEXT,
    exchange_id UUID REFERENCES exchanges(id),
    type asset_type NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    min_price_increment NUMERIC(12, 6),
    min_order_size NUMERIC(12, 6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, exchange_id)
);

-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    broker_name TEXT NOT NULL,
    api_key TEXT,
    api_secret TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Portfolios table
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    initial_balance NUMERIC(20, 8) NOT NULL DEFAULT 0,
    current_balance NUMERIC(20, 8) NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    client_order_id TEXT,
    exchange_order_id TEXT,
    type order_type NOT NULL,
    side order_side NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8),
    stop_price NUMERIC(20, 8),
    time_in_force TEXT DEFAULT 'GTC',
    status order_status NOT NULL,
    filled_quantity NUMERIC(20, 8) DEFAULT 0,
    average_fill_price NUMERIC(20, 8),
    commission NUMERIC(20, 8) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    notes TEXT
);

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    quantity NUMERIC(20, 8) NOT NULL,
    side position_side NOT NULL,
    average_entry_price NUMERIC(20, 8) NOT NULL,
    current_price NUMERIC(20, 8),
    unrealized_pnl NUMERIC(20, 8) DEFAULT 0,
    realized_pnl NUMERIC(20, 8) DEFAULT 0,
    is_open BOOLEAN DEFAULT TRUE,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    side order_side NOT NULL,
    fee NUMERIC(20, 8) DEFAULT 0,
    fee_asset TEXT,
    realized_pnl NUMERIC(20, 8) DEFAULT 0,
    strategy_id TEXT,
    signal_id TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Strategies table
CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type strategy_type NOT NULL,
    description TEXT,
    parameters JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    type signal_type NOT NULL,
    strength NUMERIC(5, 2) CHECK (strength >= 0 AND strength <= 100),
    price_target NUMERIC(20, 8),
    stop_loss NUMERIC(20, 8),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Market data hypertable
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    vwap NUMERIC(20, 8),
    trade_count INTEGER,
    PRIMARY KEY (time, asset_id)
);

-- Order book snapshots hypertable
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    bid_price_1 NUMERIC(20, 8),
    bid_size_1 NUMERIC(20, 8),
    ask_price_1 NUMERIC(20, 8),
    ask_size_1 NUMERIC(20, 8),
    -- Add more levels as needed
    PRIMARY KEY (time, asset_id)
);

-- Trade history hypertable
CREATE TABLE IF NOT EXISTS trade_history (
    time TIMESTAMPTZ NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    side order_side,
    is_buyer_maker BOOLEAN,
    trade_id BIGINT,
    PRIMARY KEY (time, asset_id, trade_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_portfolio_id ON orders(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_orders_asset_id ON orders(asset_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_positions_portfolio_id ON positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_positions_asset_id ON positions(asset_id);
CREATE INDEX IF NOT EXISTS idx_trades_portfolio_id ON trades(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_trades_asset_id ON trades(asset_id);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_strategy_id ON signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_signals_asset_id ON signals(asset_id);

-- Create or replace the update_modified_column function
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
DO $$ 
BEGIN
    -- Drop existing triggers if they exist
    DROP TRIGGER IF EXISTS update_users_modtime ON users;
    DROP TRIGGER IF EXISTS update_exchanges_modtime ON exchanges;
    DROP TRIGGER IF EXISTS update_assets_modtime ON assets;
    DROP TRIGGER IF EXISTS update_accounts_modtime ON accounts;
    DROP TRIGGER IF EXISTS update_portfolios_modtime ON portfolios;
    DROP TRIGGER IF EXISTS update_orders_modtime ON orders;
    DROP TRIGGER IF EXISTS update_positions_modtime ON positions;
    DROP TRIGGER IF EXISTS update_strategies_modtime ON strategies;
    DROP TRIGGER IF EXISTS update_signals_modtime ON signals;
    
    -- Recreate triggers
    CREATE TRIGGER update_users_modtime
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_exchanges_modtime
        BEFORE UPDATE ON exchanges
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_assets_modtime
        BEFORE UPDATE ON assets
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_accounts_modtime
        BEFORE UPDATE ON accounts
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_portfolios_modtime
        BEFORE UPDATE ON portfolios
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_orders_modtime
        BEFORE UPDATE ON orders
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_positions_modtime
        BEFORE UPDATE ON positions
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_strategies_modtime
        BEFORE UPDATE ON strategies
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
        
    CREATE TRIGGER update_signals_modtime
        BEFORE UPDATE ON signals
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
END $$;

-- Convert tables to hypertables
DO $$
BEGIN
    -- Only create hypertables if they don't exist
    IF NOT EXISTS (
        SELECT 1 
        FROM _timescaledb_catalog.hypertable 
        WHERE table_name = 'market_data'
    ) THEN
        PERFORM create_hypertable('market_data', 'time', if_not_exists => TRUE);
    END IF;

    IF NOT EXISTS (
        SELECT 1 
        FROM _timescaledb_catalog.hypertable 
        WHERE table_name = 'order_book_snapshots'
    ) THEN
        PERFORM create_hypertable('order_book_snapshots', 'time', if_not_exists => TRUE);
    END IF;

    IF NOT EXISTS (
        SELECT 1 
        FROM _timescaledb_catalog.hypertable 
        WHERE table_name = 'trade_history'
    ) THEN
        PERFORM create_hypertable('trade_history', 'time', if_not_exists => TRUE);
    END IF;
    
    -- Add compression policies
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_compression' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'market_data'
    ) THEN
        ALTER TABLE market_data SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'asset_id'
        );
        PERFORM add_compression_policy('market_data', INTERVAL '7 days');
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_compression' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'order_book_snapshots'
    ) THEN
        ALTER TABLE order_book_snapshots SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'asset_id'
        );
        PERFORM add_compression_policy('order_book_snapshots', INTERVAL '1 day');
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_compression' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'trade_history'
    ) THEN
        ALTER TABLE trade_history SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'asset_id'
        );
        PERFORM add_compression_policy('trade_history', INTERVAL '1 day');
    END IF;
    
    -- Add retention policies
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_retention' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'market_data'
    ) THEN
        PERFORM add_retention_policy('market_data', INTERVAL '1 year');
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_retention' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'order_book_snapshots'
    ) THEN
        PERFORM add_retention_policy('order_book_snapshots', INTERVAL '30 days');
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_retention' 
        AND hypertable_schema = 'public' 
        AND hypertable_name = 'trade_history'
    ) THEN
        PERFORM add_retention_policy('trade_history', INTERVAL '90 days');
    END IF;
END $$;
