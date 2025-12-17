-- Insert default portfolio
INSERT INTO portfolios (id, name, description)
VALUES ('00000000-0000-0000-0000-000000000001', 'Kapman Core', 'Primary trading portfolio')
ON CONFLICT DO NOTHING;

-- Insert common AI/tech stocks
INSERT INTO tickers (id, symbol, name, sector, is_active)
VALUES 
    (uuid_generate_v5(uuid_nil(), 'AAPL'), 'AAPL', 'Apple Inc.', 'Technology', true),
    (uuid_generate_v5(uuid_nil(), 'MSFT'), 'MSFT', 'Microsoft Corporation', 'Technology', true),
    (uuid_generate_v5(uuid_nil(), 'GOOGL'), 'GOOGL', 'Alphabet Inc.', 'Communication Services', true),
    (uuid_generate_v5(uuid_nil(), 'AMZN'), 'AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', true),
    (uuid_generate_v5(uuid_nil(), 'META'), 'META', 'Meta Platforms Inc.', 'Communication Services', true),
    (uuid_generate_v5(uuid_nil(), 'TSLA'), 'TSLA', 'Tesla Inc.', 'Consumer Cyclical', true),
    (uuid_generate_v5(uuid_nil(), 'NVDA'), 'NVDA', 'NVIDIA Corporation', 'Technology', true)
ON CONFLICT (symbol) DO UPDATE 
SET name = EXCLUDED.name, 
    sector = EXCLUDED.sector, 
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Add tickers to portfolio
INSERT INTO portfolio_tickers (portfolio_id, ticker_id, priority)
SELECT 
    '00000000-0000-0000-0000-000000000001',
    id,
    CASE 
        WHEN symbol IN ('AAPL', 'MSFT') THEN 'P0'
        ELSE 'P1'
    END
FROM tickers
WHERE symbol IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA')
ON CONFLICT DO NOTHING;
