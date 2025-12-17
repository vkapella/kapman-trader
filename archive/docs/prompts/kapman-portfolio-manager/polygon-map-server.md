# Polygon MCP Server

A Model Context Protocol (MCP) server that provides access to Polygon.io financial market data. This server enables AI assistants and other MCP clients to retrieve real-time and historical stock market information.

## Features

- **Stock Prices**: Get latest stock prices with OHLCV data
- **Stock News**: Retrieve recent news articles for any ticker
- **Market Status**: Check if markets are open/closed
- **Ticker Details**: Get comprehensive company information
- **Historical Data**: Fetch aggregate bars for any time range
- **Ticker Search**: Search for stocks by name or symbol
- **Technical Analysis**: 43 indicators with 84 output values including:
  - Momentum: RSI, MACD, Stochastic, Williams %R, TSI, ROC, and more
  - Volatility: Bollinger Bands, ATR, Keltner Channel, Donchian Channel
  - Trend: SMA, EMA, ADX, Ichimoku, PSAR, Aroon, CCI, TRIX, Vortex
  - Volume: OBV, MFI, CMF, VWAP, Force Index, ADI
- **Batch Processing**: Analyze up to 10 symbols simultaneously
- **Advanced Metrics** (requires paid Polygon Options tier):
  - Dealer Metrics: GEX, Net GEX, Gamma Flip, Call/Put Walls, DGPI
  - Price Metrics: RVOL, VSI, Historical Volatility, HV-IV Differential
  - Volatility Metrics: IV Skew, Term Structure, Put/Call Ratio

## Quick Start: Connect to Claude

### OAuth Setup (Authentication)

1. **Get your OAuth credentials:**
   - **Client ID**: `polygon-mcp-client` (fixed)
   - **Client Secret**: Stored in Replit Secrets as `OAUTH_CLIENT_SECRET`

2. **Connect in Claude Web:**
   - Go to **Settings → Connectors → Add custom connector**
   - Fill in the following:
     - **Name**: Polygon MCP
     - **Remote MCP server URL**: `https://your-replit-url/mcp`
     - **OAuth Client ID**: `polygon-mcp-client`
     - **OAuth Client Secret**: Copy from Replit Secrets
   - Click **Add** - Claude will automatically handle OAuth authentication

3. **Start using it:**
   - Ask Claude to get stock prices, analyze market data, compute technical indicators, and more
   - Example: "Get the latest price for AAPL and calculate RSI"

### OAuth Flow Details

The server implements OAuth 2.0 with PKCE for secure Claude integration:
- **Authorization Endpoint**: `/authorize` - initiates authorization code flow
- **Token Endpoint**: `/token` - exchanges authorization codes for Bearer tokens
- **MCP Endpoint**: `/mcp` - WebSocket + Streamable HTTP transport
- **Credentials**: Stored securely as Replit Secrets

## Prerequisites

- Python 3.10 or higher
- A Polygon.io API key (get one at [polygon.io](https://polygon.io))
- **For advanced metrics (dealer, volatility)**: Polygon.io Options tier subscription

## Installation

1. Clone this repository or deploy to Replit
2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Set your Polygon.io API key:
   - On Replit: Add `POLYGON_API_KEY` to Secrets
   - Locally: Set environment variable:
     ```bash
     export POLYGON_API_KEY=your_api_key_here
     ```

## Running the Server

```bash
python main.py
```

The server will start on port 5000 (or the port specified in the `PORT` environment variable).

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Service information |
| `/health` | Health check endpoint |
| `/authorize` | OAuth authorization endpoint |
| `/token` | OAuth token endpoint |
| `/mcp` | MCP endpoint (WebSocket + Streamable HTTP) |

## Available Tools (16 Total)

### Market Data Tools

#### get_stock_price
Get the latest stock price for a given symbol.

**Parameters:**
- `symbol` (string): Stock ticker symbol (e.g., AAPL, GOOGL, MSFT)

**Returns:** Close, high, low, open prices, volume, and VWAP

#### get_stock_news
Get recent news articles for a stock symbol.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `limit` (int, optional): Max articles to return (default: 5, max: 50)

**Returns:** List of articles with title, publisher, date, and URL

#### get_market_status
Get current market status including exchange states.

**Returns:** Market status, server time, and exchange states (NASDAQ, NYSE, OTC)

#### get_ticker_details
Get detailed information about a stock ticker.

**Parameters:**
- `symbol` (string): Stock ticker symbol

**Returns:** Company name, description, market cap, sector, homepage, and more

#### get_stock_aggregates
Get historical aggregate bars (OHLCV) for a stock.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `multiplier` (int, optional): Timespan multiplier (default: 1)
- `timespan` (string, optional): Time window - minute, hour, day, week, month, quarter, year (default: day)
- `from_date` (string, optional): Start date YYYY-MM-DD (default: 30 days ago)
- `to_date` (string, optional): End date YYYY-MM-DD (default: today)
- `limit` (int, optional): Max results (default: 30, max: 50000)

**Returns:** List of OHLCV bars with timestamps

#### search_tickers
Search for stock tickers by name or symbol.

**Parameters:**
- `query` (string): Search query (company name or symbol)
- `market` (string, optional): Market type - stocks, crypto, fx, options (default: stocks)
- `limit` (int, optional): Max results (default: 10, max: 100)

**Returns:** List of matching tickers with symbol, name, and metadata

### Technical Analysis Tools

#### list_available_indicators
List all 43 available technical indicators with 84 output values.

**Parameters:**
- `category` (string, optional): Filter by category - momentum, volatility, trend, volume, others

**Returns:** Complete indicator catalog with descriptions, outputs, required data, and default parameters

#### get_all_ta_indicators
Compute ALL technical indicators at once for a stock.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `days` (int, optional): Historical data period (default: 100)

**Returns:** All 84 indicator values organized by category

#### get_indicator_by_category
Get all indicators for a specific category.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `category` (string): Category name - momentum, volatility, trend, volume, others
- `days` (int, optional): Historical data period (default: 100)

**Returns:** All indicator values for the specified category

#### get_single_indicator
Get a specific indicator with custom parameters.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `indicator` (string): Indicator name (e.g., rsi, macd, bbands, ichimoku, vwap)
- `params` (dict, optional): Custom parameters to override defaults
- `days` (int, optional): Historical data period (default: 100)

**Returns:** Indicator values with description and parameters used

#### get_technical_indicators
Quick access to common technical indicators.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `indicators` (list, optional): Specific indicators to calculate

**Returns:** Selected indicator values

#### get_batch_quotes
Get quotes for multiple symbols at once.

**Parameters:**
- `symbols` (list): List of stock symbols (max 10)

**Returns:** Previous close data for all symbols

#### get_batch_technical_analysis
Technical analysis for multiple symbols.

**Parameters:**
- `symbols` (list): List of stock symbols (max 10)
- `indicators` (list, optional): Indicators to calculate
- `days` (int, optional): Historical data period

**Returns:** Technical analysis for all symbols

### Advanced Metrics Tools (Requires Paid Options Tier)

#### get_dealer_metrics
Get dealer positioning metrics from options chain data.

**Parameters:**
- `symbol` (string): Stock ticker symbol

**Returns:**
- `gamma_exposure`: Total gamma exposure across strikes
- `net_gex`: Directional gamma exposure
- `gamma_flip`: Price where dealers switch positioning
- `call_walls`: Top 3 call strikes by open interest (resistance)
- `put_walls`: Top 3 put strikes by open interest (support)
- `gex_slope`: Rate of change of gamma with price
- `dealer_gamma_pressure_index`: Composite pressure indicator (-100 to +100)
- `position`: Dealer positioning (long_gamma, short_gamma, neutral)
- `confidence`: Data quality confidence (high, medium, low)

**Note:** Requires Polygon.io Options tier subscription

#### get_price_metrics
Get Wyckoff-style price and volume metrics.

**Parameters:**
- `symbol` (string): Stock ticker symbol
- `period` (int, optional): Lookback period (default: 20 days)
- `days` (int, optional): Historical data to fetch (default: 100)

**Returns:**
- `relative_volume`: Current vs average volume (>1 = above average)
- `volume_surge_index`: Z-score of volume (>2 = significant surge)
- `historical_volatility`: Annualized price volatility
- `implied_volatility`: Average IV from options (if available)
- `hv_iv_diff`: HV minus IV in percentage points

**Note:** RVOL, VSI, HV work on free tier. IV/HV-IV diff require Options tier.

#### get_volatility_metrics
Get volatility metrics from options chain data.

**Parameters:**
- `symbol` (string): Stock ticker symbol

**Returns:**
- `iv_skew_25delta`: Put minus call IV at 25 delta (positive = hedging demand)
- `iv_term_structure`: Long minus short-dated IV (negative = backwardation)
- `oi_ratio`: Volume to open interest ratio
- `put_call_ratio`: Put to call open interest ratio
- `average_iv`: OI-weighted average implied volatility
- `contracts_analyzed`: Number of option contracts used

**Note:** Requires Polygon.io Options tier subscription

## Connecting MCP Clients

### Claude Desktop Configuration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "polygon": {
      "url": "https://your-replit-url/mcp"
    }
  }
}
```

### Generic MCP Client

Connect to the MCP endpoint at `/mcp` using any MCP-compatible client. The endpoint supports both WebSocket and Streamable HTTP transport.

## Error Handling

All tools return structured error responses when issues occur:

```json
{
  "error": "Description of what went wrong",
  "hint": "Suggestion for fixing the issue (when applicable)"
}
```

Common errors:
- API key not configured
- Invalid ticker symbol
- Options data requires paid subscription
- Network/API failures
- Rate limiting

## Development

### Project Structure

```
polygon-mcp-server/
├── main.py           # Main server with all tools
├── indicators.py     # Technical indicator registry
├── lib/
│   ├── dealer_metrics.py    # GEX, gamma flip, DGPI calculations
│   ├── price_metrics.py     # RVOL, VSI, HV calculations
│   └── volatility_metrics.py # IV skew, term structure calculations
├── pyproject.toml    # Python project configuration
├── README.md         # This file
└── replit.md         # Replit-specific documentation
```

### Adding New Tools

1. Define a new function with the `@mcp.tool()` decorator
2. Add comprehensive docstring with Args and Returns
3. Implement error handling
4. Update this README

## License

MIT License

## Support

For Polygon.io API issues, see [Polygon.io Documentation](https://polygon.io/docs)

For MCP protocol issues, see [MCP Documentation](https://modelcontextprotocol.io)
