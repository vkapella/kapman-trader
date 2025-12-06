# Polygon.io API Wrapper

## Overview
A lightweight FastAPI-based wrapper for Polygon.io that provides complete endpoint passthrough and dynamic technical indicator calculations using pandas_ta. Designed specifically for use with Custom GPT Actions.

## Purpose
- Expose all Polygon.io REST API endpoints with automatic API key injection
- Provide computed technical indicators from OHLCV time series data
- Enable secure, authenticated access for Custom GPT integration

## Current State
**Status:** Active Development (October 18, 2025)

### Features Implemented
✅ GET passthrough to all Polygon.io endpoints via `/api/polygon/{path}`
✅ OHLCV aggregates endpoint (`/api/aggs`)
✅ Dynamic pandas_ta indicator computation (`/api/indicators/{name}`)
✅ Batch indicator processing (`/api/indicators/batch`)
✅ Indicator discovery endpoint (`/api/indicators/list`)
✅ Wyckoff price & volume metrics (`/api/metrics/price`)
✅ Health check endpoint (`/api/health`)
✅ Optional bearer token authentication
✅ OpenAPI schema with bearer auth for Custom GPT Actions

## Project Architecture

### Technology Stack
- **Framework:** FastAPI 0.119.0
- **Server:** Uvicorn (ASGI)
- **HTTP Client:** httpx (async)
- **Data Processing:** pandas 2.3.3
- **Technical Analysis:** pandas_ta 0.4.71b0
- **Python Version:** 3.12+

### Project Structure
```
/
├── app.py              # Main application file with all endpoints
├── lib/
│   ├── __init__.py     # Package initialization
│   ├── price_metrics.py # Wyckoff price & volume metrics library
│   ├── dealer_metrics.py # GEX/gamma flip calculations (Schwab-equivalent)
│   └── volatility_metrics.py # IV skew, term structure, OI ratio
├── polygon_metrics.json # Registry file for KapMan metrics service
├── pyproject.toml      # Python project configuration
├── uv.lock            # Dependency lock file
├── replit.md          # This file
└── .gitignore         # Git ignore patterns
```

### Registry Service Integration
The `polygon_metrics.json` file defines all available metrics for the KapMan registry service:
- **Indicators**: RSI, ADX, ATR, MACD, EMA, SMA (160+ via pandas_ta)
- **Volatility**: HV, IV_SKEW, IV_TERM, OI_RATIO, EXPECTED_MOVE
- **Dealer Flow**: GEX, NET_GEX, GAMMA_FLIP, CALL_WALL, PUT_WALL, GEX_SLOPE, DGPI
- **Schwab-Compatible Parameters**: dte_min, dte_max, min_oi, iv, dte, iv_rank

### Environment Variables
- `POLYGON_API_KEY` (required) - Your Polygon.io API key
- `KAPMAN_AUTHENTICATION_TOKEN` (optional) - Bearer token for API authentication (shared across KapMan microservices)
- `DEFAULT_TIMESPAN` (optional) - Default timespan for aggregates (default: "day")
- `DEFAULT_LIMIT` (optional) - Default limit for data points (default: 500)

## API Endpoints

### Health Check
**GET** `/api/health`
- Returns service status and available indicator count

### Polygon Passthrough
**GET** `/api/polygon/{path}`
- Safe passthrough to any Polygon.io GET endpoint
- Automatically injects API key
- Example: `/api/polygon/v2/aggs/ticker/AAPL/range/1/day/2023-01-09/2023-02-10`

### Aggregates Helper
**GET** `/api/aggs`
- Query params: `symbol`, `timespan` (minute/day), `limit`, `adjusted`
- Returns OHLCV data as JSON array

### List Indicators
**GET** `/api/indicators/list`
- Returns all available pandas_ta indicators discovered at runtime

### Single Indicator
**GET** `/api/indicators/{name}`
- Compute any pandas_ta indicator dynamically
- Query params: `symbol`, `timespan`, `limit`, plus indicator-specific params
- Example: `/api/indicators/rsi?symbol=AAPL&length=14`

### Batch Indicators (Universal)
**POST** `/api/indicators/batch`
- Compute multiple indicators for 1 to 200 symbols in one request
- Single symbol returns time-series data
- Multiple symbols return latest values per symbol

### Options Data (Batch up to 20)

**POST** `/api/chains`
- Get option chains with Greeks for multiple symbols
- Request: `{"symbols": ["AAPL", "SPY", "MSFT"]}`
- Returns: Contracts with delta, gamma, theta, vega, rho, IV per symbol

**POST** `/api/dealer-metrics`
- Get Schwab-equivalent dealer positioning metrics for multiple symbols
- Request: `{"symbols": ["AAPL", "SPY"]}`
- Returns:
  - `gamma_exposure`: Total absolute GEX across all strikes
  - `net_gex`: Signed GEX (calls positive, puts negative)
  - `gamma_flip`: Price where dealers switch from long to short gamma
  - `call_walls`: Top 3 strikes with highest call open interest (resistance)
  - `put_walls`: Top 3 strikes with highest put open interest (support)
  - `gex_slope`: Rate of change of GEX with price movement
  - `dealer_gamma_pressure_index`: Composite stress measure (0-1)
  - `position`: Current position relative to gamma flip (above_flip/below_flip/at_flip)
  - `confidence`: Data quality confidence (high/medium/low/invalid)
  - `expected_move`: Expected price move based on IV and DTE

**POST** `/api/metrics/volatility`
- Get Schwab-equivalent volatility metrics for symbols
- Request: `{"symbols": ["AAPL", "SPY"], "period": 20}`
- Returns:
  - `historical_volatility`: Annualized HV from price data
  - `implied_volatility`: Average IV from options chain
  - `iv_skew`: IV(25Δ put) - IV(25Δ call) in percentage points. Positive = higher put demand
  - `iv_term_structure`: IV(90D) - IV(30D) in percentage points. Positive = backwardation
  - `oi_ratio`: Volume / Open Interest ratio. Higher = more speculative activity
- Request body (single symbol):
```json
{
  "symbols": ["AAPL"],
  "timespan": "day",
  "limit": 500,
  "specs": [
    {"name": "rsi", "params": {"length": 14}},
    {"name": "macd", "params": {}}
  ]
}
```
- Request body (multiple symbols):
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "timespan": "day",
  "limit": 100,
  "specs": [
    {"name": "rsi", "params": {"length": 14}},
    {"name": "sma", "params": {"length": 20}}
  ]
}
```

### Price Metrics (Wyckoff Analysis)
**GET/POST** `/api/metrics/price`
- Calculate price and volume metrics for Wyckoff analysis (single symbol)
- GET query params: `symbol`, `timespan`, `limit`, `period`, `iv` (optional)
- POST request body:
```json
{
  "symbol": "AAPL",
  "timespan": "day",
  "limit": 100,
  "period": 20,
  "iv": 50.0
}
```
- Returns: Relative Volume, Volume Surge Index, Historical Volatility, HV-IV Differential
- Example GET: `/api/metrics/price?symbol=AAPL&period=20&limit=100&iv=35.5`

**POST** `/api/metrics/batch`
- Batch calculate Wyckoff metrics for 1-200 symbols in one request
- Returns latest metrics for each symbol
- Request body:
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "timespan": "day",
  "limit": 100,
  "period": 20,
  "iv": 35.5
}
```
- Performance: 10 symbols in ~0.4 seconds
- Returns null values with warning for symbols with insufficient data

## Recent Changes
- **2025-12-03:** Upgraded dealer and volatility metrics to Schwab-equivalent
  - Created `lib/dealer_metrics.py` with GEX, gamma flip, call/put walls calculations
  - Created `lib/volatility_metrics.py` with IV skew, term structure, OI ratio
  - Updated `/api/dealer-metrics` to return full dealer positioning analysis
  - Updated `/api/metrics/volatility` to include skew and term structure metrics
  - Matches Schwab microservice output format for unified KapMan ecosystem
- **2025-11-09:** Added batch Wyckoff metrics endpoint
  - Created `/api/metrics/batch` to handle 1-200 symbols concurrently
  - Mirrors `/api/indicators/batch` design for consistency
  - Returns latest Wyckoff metrics (RVOL, VSI, HV, HV-IV) for each symbol
  - Performance: 10 symbols in 0.4 seconds with concurrent processing
  - Gracefully handles symbols with insufficient data (returns null with warning)
- **2025-11-09:** Improved error handling for insufficient data
  - `/api/metrics/price` now returns null values instead of throwing HTTP 400 errors
  - Added `bars_available` and `warning` fields to responses
  - Allows ChatGPT to continue processing when some symbols lack data
  - Both GET and POST methods updated
- **2025-10-27:** Unified batch indicator endpoint
  - Updated `/api/indicators/batch` to handle 1-200 symbols (was single symbol only)
  - Single symbol returns time-series data with all timestamps
  - Multiple symbols return latest indicator values per symbol
  - Handles bulk processing: tested 100 symbols × 5 indicators in 3.7 seconds
  - Example: scan entire watchlist with RSI, MACD, SMA, EMA, ADX in one request
- **2025-10-19:** Added POST support for price metrics endpoint
  - Created PriceMetricsRequest Pydantic model for JSON request body
  - Added POST version of `/api/metrics/price` endpoint
  - Custom GPT Actions can now use either GET or POST method
  - Both methods return identical response format
- **2025-10-19:** Changed authentication token to KAPMAN_AUTHENTICATION_TOKEN
  - Renamed WRAPPER_AUTH_TOKEN to KAPMAN_AUTHENTICATION_TOKEN
  - Unified authentication across all KapMan microservices
  - Updated all documentation and code references
- **2025-10-19:** Added Wyckoff price & volume metrics
  - Created lib/price_metrics.py with 4 metric functions
  - Added `/api/metrics/price` endpoint for Wyckoff analysis
  - Metrics: Relative Volume (RVOL), Volume Surge Index (VSI), Historical Volatility (HV), HV-IV Differential
  - Supports customizable lookback period and optional implied volatility input
  - Integrated with existing OHLCV data fetching infrastructure
- **2025-10-18:** Production-ready deployment
  - Enhanced OpenAPI schema with comprehensive descriptions for Custom GPT Actions
  - Added detailed endpoint documentation with examples
  - Configured bearer token authentication (WRAPPER_AUTH_TOKEN)
  - Organized endpoints with tags (System, Stock Data, Technical Indicators, Polygon.io Passthrough)
  - Added support for options data (contracts, chains, Greeks, pricing)
  - Created DEPLOYMENT_GUIDE.md for production setup
  - API fully documented for GPT natural language query conversion
- **2025-10-18:** Initial project setup
  - Created app.py with all endpoint implementations
  - Configured Python 3.12 environment
  - Installed dependencies: fastapi, uvicorn, httpx, pandas, pandas_ta
  - Set up POLYGON_API_KEY and WRAPPER_AUTH_TOKEN secrets
  - Configured workflow to run on port 5000

## User Preferences
- Using ChatGPT-provided code as reference implementation
- Focus on lightweight, single-file design
- Optimized for Custom GPT Actions integration

## Next Phase Features (Not Yet Implemented)
- Caching layer for frequently requested data
- Rate limiting and throttling
- POST/DELETE endpoint support for Polygon
- Custom indicator presets
- Data export formats (CSV, Excel)

## Usage with Custom GPT

1. Deploy this wrapper to a public URL
2. In Custom GPT Actions, import the OpenAPI schema from `/openapi.json`
3. Set Authentication to "Bearer" with your `WRAPPER_AUTH_TOKEN`
4. The GPT can now call all endpoints to fetch market data and compute indicators

## Development Notes
- Server runs on port 5000 (required for Replit)
- All Polygon.io requests are async for performance
- Dynamic indicator discovery scans pandas_ta at runtime
- OpenAPI schema includes bearer auth configuration
