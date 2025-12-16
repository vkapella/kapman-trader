"""
KapMan-Polygon.io-APIx-Wrapper (Single-file)

Features
- /api/polygon/{path} : Safe GET passthrough to Polygon.io with apiKey injection
- /api/aggs          : Helper to fetch OHLCV aggregates (minute/day)
- /api/indicators/{name} : Compute ANY pandas-ta indicator dynamically from Polygon OHLCV
- /api/indicators/batch  : Compute multiple indicators for 1-200 symbols in one call
- /api/indicators/list   : Enumerate available pandas-ta indicators discovered at runtime
- /api/metrics/price     : Calculate Wyckoff price & volume metrics (RVOL, VSI, HV, HV-IV diff)
- /api/health       : Basic health

Replit:
  Secrets:
    POLYGON_API_KEY (required)
    KAPMAN_AUTHENTICATION_TOKEN (optional; if set, all endpoints require Authorization: Bearer <token>)
Run:
  uvicorn app:app --host 0.0.0.0 --port 5000
"""

import os
from typing import Optional, Dict, Any, List

import httpx
import pandas as pd
import pandas_ta as ta
from fastapi import FastAPI, HTTPException, Header, Query, Path, Depends, Request
from fastapi.responses import JSONResponse, Response, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from lib.price_metrics import relative_volume, volume_surge_index, historical_volatility, hv_iv_diff
from lib.dealer_metrics import OptionContract as DealerOptionContract, calculate_dealer_metrics
from lib.volatility_metrics import OptionContractVol, calculate_volatility_metrics

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
KAPMAN_AUTHENTICATION_TOKEN = os.getenv("KAPMAN_AUTHENTICATION_TOKEN")
DEFAULT_TIMESPAN = os.getenv("DEFAULT_TIMESPAN", "day")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "500"))

if not POLYGON_API_KEY:
    print("WARNING: POLYGON_API_KEY is not set; Polygon passthrough/indicators will fail.")

app = FastAPI(
    title="KapMan Polygon APIx Wrapper",
    version="1.2.0",
    description="""
# Polygon.io API Wrapper with Technical Indicators

A comprehensive API wrapper that provides:
- **Full Polygon.io REST API passthrough** for stocks and options market data
- **160+ pandas_ta technical indicators** calculated dynamically from OHLCV data
- **Batch indicator processing** for multiple calculations in one request
- **Schwab-equivalent dealer metrics** (GEX, gamma flip, call/put walls)
- **Schwab-equivalent volatility metrics** (IV skew, term structure, OI ratio)

## Authentication
All endpoints require Bearer token authentication via the Authorization header:
```
Authorization: Bearer YOUR_TOKEN
```

## Available Data
- **Stocks**: Real-time and historical prices, trades, quotes, aggregates, snapshots
- **Options**: Contracts, chains, Greeks, implied volatility, option pricing
- **Indicators**: RSI, MACD, ADX, Bollinger Bands, EMA, SMA, and 150+ more
- **Dealer Flow**: GEX, Net GEX, Gamma Flip, Call/Put Walls, GEX Slope, DGPI
- **Volatility**: HV, IV Skew (25Δ), IV Term Structure, OI Ratio

## Common Use Cases
- Get stock prices: Use `/api/aggs` or `/api/polygon/v2/aggs/ticker/{symbol}/...`
- Calculate RSI: Use `/api/indicators/rsi?symbol=AAPL&length=14`
- Get option chain: Use `/api/polygon/v3/snapshot/options/{symbol}`
- Multiple indicators: Use POST `/api/indicators/batch`
- Dealer metrics: Use POST `/api/dealer-metrics`
- Volatility metrics: Use POST `/api/metrics/volatility`
    """
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_auth(authorization: Optional[str] = Header(None, include_in_schema=False)):
    """
    Validates Bearer token authentication.
    include_in_schema=False prevents duplicate authorization parameter in OpenAPI
    (already handled by bearerAuth security scheme).
    """
    if KAPMAN_AUTHENTICATION_TOKEN and authorization != f"Bearer {KAPMAN_AUTHENTICATION_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

# Pydantic models for request validation
class IndicatorSpec(BaseModel):
    name: str = Field(..., description="Indicator name (e.g., rsi, macd, adx)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Indicator parameters (e.g., {'length': 14})")

class BatchIndicatorRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="Single stock ticker symbol (deprecated, use 'symbols' instead)")
    symbols: Optional[List[str]] = Field(None, description="List of stock ticker symbols (1 to 200)", examples=[["AAPL"], ["AAPL", "MSFT", "GOOGL"]])
    timespan: str = Field(default="day", description="Time interval: 'minute' or 'day'")
    limit: int = Field(default=500, description="Number of data points", ge=5, le=5000)
    specs: List[IndicatorSpec] = Field(..., description="List of indicators to calculate for each symbol")
    
    def model_post_init(self, __context):
        """Convert single symbol to symbols array for backward compatibility"""
        if self.symbol and not self.symbols:
            self.symbols = [self.symbol]
        elif not self.symbol and not self.symbols:
            raise ValueError("Either 'symbol' or 'symbols' must be provided")
        
        # Ensure symbols is always a list
        if not isinstance(self.symbols, list):
            self.symbols = [self.symbols]

class PriceMetricsRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol", examples=["AAPL"])
    timespan: str = Field(default="day", description="Time interval: 'minute' or 'day'")
    limit: int = Field(default=100, description="Number of data points for calculation", ge=20, le=5000)
    period: int = Field(default=20, description="Lookback period for metrics calculation", ge=5, le=100)
    iv: Optional[float] = Field(None, description="Implied volatility (%) for HV-IV differential calculation")

class BatchPriceMetricsRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock ticker symbols (1 to 200)", examples=[["AAPL"], ["AAPL", "MSFT", "GOOGL"]])
    timespan: str = Field(default="day", description="Time interval: 'minute' or 'day'")
    limit: int = Field(default=100, description="Number of data points for calculation", ge=20, le=5000)
    period: int = Field(default=20, description="Lookback period for metrics calculation", ge=5, le=100)
    iv: Optional[float] = Field(None, description="Implied volatility (%) for HV-IV differential calculation")

class BatchChainsRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of underlying stock symbols (1 to 20)", examples=[["AAPL"], ["AAPL", "MSFT", "SPY"]])
    
class BatchDealerMetricsRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols (1 to 20)", examples=[["AAPL"], ["AAPL", "MSFT"]])
    dte_min: int = Field(default=0, description="Minimum days to expiration filter", ge=0)
    dte_max: int = Field(default=60, description="Maximum days to expiration filter", ge=1, le=365)
    min_oi: int = Field(default=100, description="Minimum open interest filter", ge=0)
    iv: Optional[float] = Field(None, description="Implied volatility (decimal, e.g., 0.25 for 25%) for expected move calculation")
    dte: Optional[int] = Field(None, description="Days to expiration for expected move calculation")
    iv_rank: Optional[float] = Field(None, description="IV Rank (0-100) for dealer gamma pressure index calculation")

class BatchVolatilityMetricsRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock symbols (1 to 20)", examples=[["AAPL"], ["AAPL", "MSFT"]])
    period: int = Field(default=20, description="Lookback period for HV calculation", ge=5, le=100)
    dte_min: int = Field(default=0, description="Minimum days to expiration filter", ge=0)
    dte_max: int = Field(default=60, description="Maximum days to expiration filter", ge=1, le=365)
    min_oi: int = Field(default=100, description="Minimum open interest filter", ge=0)

_POLY_BASE = "https://api.polygon.io"

async def polygon_get(path: str, query: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(query or {})
    params["apiKey"] = POLYGON_API_KEY
    url = f"{_POLY_BASE}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                return JSONResponse(r.json(), status_code=r.status_code)
            except Exception:
                raise e
        return r.json()

async def fetch_aggs(symbol: str, timespan: str = "day", limit: int = 500, **kwargs) -> pd.DataFrame:
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365*2)).strftime("%Y-%m-%d")
    path = f"v2/aggs/ticker/{symbol}/range/1/{timespan}/{start_date}/{end_date}"
    data = await polygon_get(path, {"limit": limit, "adjusted": "true", "sort": "desc", **kwargs})
    if isinstance(data, JSONResponse):
        raise HTTPException(status_code=data.status_code, detail=data.body.decode() if data.body else "Polygon error")
    rows = data.get("results") or []
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows).rename(
        columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]].sort_values("timestamp")

import inspect

def _discover_indicators() -> Dict[str, Any]:
    inds = {}
    for name in dir(ta):
        if name.startswith("_"):
            continue
        fn = getattr(ta, name, None)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        params = sig.parameters
        param_names = set(params.keys())
        if param_names & {"close", "high", "low", "open", "volume"}:
            inds[name.lower()] = fn
    return inds

INDICATORS = _discover_indicators()

def list_indicators() -> List[str]:
    return sorted(INDICATORS.keys())

def _df_to_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    d = df.set_index("timestamp").sort_index()
    return d[["open", "high", "low", "close", "volume"]]

def compute_indicator_dynamic(df: pd.DataFrame, name: str, user_params: Dict[str, Any]) -> pd.DataFrame:
    """
    Finds a pandas-ta indicator by name (case-insensitive), injects OHLCV Series based on the
    function signature, merges user params, and executes. Returns a DataFrame (columns prefixed).
    """
    if not name:
        raise ValueError("Indicator name required.")
    key = name.lower()
    fn = INDICATORS.get(key)
    if not fn:
        key2 = key.replace("-", "").replace("_", "")
        for k in INDICATORS.keys():
            if k.replace("-", "").replace("_", "") == key2:
                fn = INDICATORS[k]
                key = k
                break
    if not fn:
        raise ValueError(f"Unsupported indicator '{name}'. Use /api/indicators/list to see valid names.")

    d = _df_to_ohlcv(df)
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        raise ValueError(f"Cannot introspect indicator '{name}'.")

    kwargs = {}
    for p in sig.parameters.values():
        pname = p.name
        if pname in ("close", "high", "low", "open", "volume"):
            kwargs[pname] = d[pname]
    if user_params:
        kwargs.update(user_params)

    out = fn(**kwargs)
    if out is None:
        return pd.DataFrame()
    if isinstance(out, pd.Series):
        if out.empty:
            return pd.DataFrame()
        out = out.to_frame(name=key)
    if isinstance(out, pd.DataFrame) and out.empty:
        return pd.DataFrame()
    out = out.add_prefix(f"{key}_")
    out.index = d.index
    return out

def compute_batch_dynamic(df: pd.DataFrame, specs: List) -> pd.DataFrame:
    frames = []
    for spec in specs:
        # Handle both dict and IndicatorSpec objects
        if hasattr(spec, 'name'):
            nm = spec.name.strip()
            params = spec.params or {}
        else:
            nm = str(spec.get("name", "")).strip()
            params = spec.get("params", {}) or {}
        frames.append(compute_indicator_dynamic(df, nm, params))
    out = pd.concat(frames, axis=1)
    out.index = _df_to_ohlcv(df).index
    return out

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>KapMan Polygon APIx Wrapper</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            }
            h1 { margin-top: 0; font-size: 2.5em; }
            .badge { 
                background: rgba(255, 255, 255, 0.2);
                padding: 5px 15px;
                border-radius: 20px;
                display: inline-block;
                margin: 5px;
                font-size: 0.9em;
            }
            .btn {
                display: inline-block;
                background: white;
                color: #667eea;
                padding: 15px 30px;
                margin: 10px 5px;
                border-radius: 10px;
                text-decoration: none;
                font-weight: bold;
                transition: transform 0.2s;
            }
            .btn:hover { transform: translateY(-2px); }
            .endpoint {
                background: rgba(255, 255, 255, 0.05);
                padding: 15px;
                margin: 10px 0;
                border-radius: 10px;
                border-left: 4px solid rgba(255, 255, 255, 0.5);
            }
            .endpoint code {
                background: rgba(0, 0, 0, 0.2);
                padding: 2px 8px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
            }
            .stats {
                display: flex;
                justify-content: space-around;
                margin: 30px 0;
            }
            .stat {
                text-align: center;
            }
            .stat-number {
                font-size: 3em;
                font-weight: bold;
                display: block;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 KapMan Polygon APIx Wrapper</h1>
            <p style="font-size: 1.2em; opacity: 0.9;">
                A lightweight FastAPI wrapper for Polygon.io with pandas_ta technical indicators
            </p>
            
            <div class="stats">
                <div class="stat">
                    <span class="stat-number">""" + str(len(INDICATORS)) + """</span>
                    <span>Indicators</span>
                </div>
                <div class="stat">
                    <span class="stat-number">∞</span>
                    <span>Stocks</span>
                </div>
                <div class="stat">
                    <span class="stat-number">∞</span>
                    <span>Options</span>
                </div>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="/docs" class="btn">📚 Interactive API Docs</a>
                <a href="/redoc" class="btn">📖 ReDoc</a>
                <a href="/api/health" class="btn">💚 Health Check</a>
            </div>

            <h2>Quick Start</h2>
            
            <div class="endpoint">
                <strong>List All Indicators</strong><br>
                <code>GET /api/indicators/list</code>
            </div>

            <div class="endpoint">
                <strong>Calculate RSI</strong><br>
                <code>GET /api/indicators/rsi?symbol=AAPL&length=14</code>
            </div>

            <div class="endpoint">
                <strong>Get OHLCV Data</strong><br>
                <code>GET /api/aggs?symbol=AAPL&timespan=day&limit=100</code>
            </div>

            <div class="endpoint">
                <strong>Batch Indicators</strong><br>
                <code>POST /api/indicators/batch</code>
            </div>

            <div class="endpoint">
                <strong>Polygon Passthrough (Stocks + Options)</strong><br>
                <code>GET /api/polygon/{any-polygon-endpoint}</code>
            </div>

            <h2>Options Endpoints</h2>
            
            <div class="endpoint">
                <strong>Option Contracts</strong><br>
                <code>GET /api/polygon/v3/reference/options/contracts?underlying_ticker=AAPL</code>
            </div>

            <div class="endpoint">
                <strong>Option Chain Snapshot</strong><br>
                <code>GET /api/polygon/v3/snapshot/options/AAPL</code>
            </div>

            <div class="endpoint">
                <strong>Option Contract Details</strong><br>
                <code>GET /api/polygon/v3/reference/options/contracts/O:AAPL250117C00200000</code>
            </div>

            <div class="endpoint">
                <strong>Option Aggregates (OHLCV)</strong><br>
                <code>GET /api/polygon/v2/aggs/ticker/O:AAPL250117C00200000/range/1/day/2024-01-01/2024-12-31</code>
            </div>

            <p style="margin-top: 40px; text-align: center; opacity: 0.7;">
                Version 1.1.0 | Built with FastAPI + pandas_ta
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get(
    "/api/health",
    tags=["System"],
    summary="Health check",
    description="Returns API status and number of available technical indicators. Public endpoint, no authentication required."
)
async def health():
    """
    Returns API health status including:
    - Service availability
    - Number of available pandas_ta indicators
    - Default configuration
    
    Note: Public endpoint - no authentication required for monitoring/health checks.
    """
    return {
        "ok": True,
        "service": "KapMan-Polygon.io-APIx-Wrapper",
        "pandas_ta_indicators": len(INDICATORS),
        "default_timespan": DEFAULT_TIMESPAN
    }

# Override FastAPI's built-in OpenAPI schema generator
def custom_openapi_schema():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes
    )
    
    # CRITICAL: Set servers field for Custom GPT Actions
    # This will be set to the production URL when deployed
    openapi_schema["servers"] = [
        {"url": "https://kapman-polygon-apix-wrapper.replit.app"}
    ]
    
    # Add bearer auth security scheme
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http", "scheme": "bearer", "bearerFormat": "JWT"
    }
    
    # Apply security to all operations except health endpoint
    for path, path_data in openapi_schema.get("paths", {}).items():
        for operation in path_data.values():
            if isinstance(operation, dict):
                # Health endpoint is public, no auth required
                if path != "/api/health":
                    operation.setdefault("security", [{"bearerAuth": []}])
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi_schema

@app.get(
    "/api/polygon/{path:path}",
    tags=["Polygon.io Passthrough"],
    summary="Polygon.io API passthrough",
    description="Access any Polygon.io endpoint. Examples: v2/last/trade/AAPL, v3/snapshot/options/TSLA, v2/aggs/ticker/NVDA/range/1/day/2024-01-01/2024-12-31"
)
async def polygon_passthrough(path: str, request: Request, _=Depends(require_auth)):
    """
    Universal passthrough to Polygon.io REST API.
    Automatically injects your API key and forwards all query parameters.
    
    The path should be the Polygon.io endpoint without the base URL.
    Example: To call https://api.polygon.io/v2/last/trade/AAPL, use path: v2/last/trade/AAPL
    """
    query = dict(request.query_params)
    data = await polygon_get(path, query)
    if isinstance(data, JSONResponse):
        return data
    return JSONResponse(data)

@app.get(
    "/api/aggs",
    tags=["Stock Data"],
    summary="Get OHLCV aggregates (price bars)",
    description="Fetch OHLCV price data for stocks. Supports minute and day timeframes. Returns up to 2 years of historical data with timestamp, open, high, low, close, volume."
)
async def aggs(
    symbol: str = Query(..., description="Stock ticker symbol (e.g., AAPL, TSLA, NVDA)", examples=["AAPL"]),
    timespan: str = Query(DEFAULT_TIMESPAN, description="Time interval: 'minute' or 'day'", pattern="^(minute|day)$"),
    limit: int = Query(DEFAULT_LIMIT, description="Number of bars to return (1-5000)", ge=1, le=5000),
    adjusted: bool = Query(True, description="Adjust for stock splits"),
    _=Depends(require_auth)
):
    """
    Returns OHLCV price data as JSON array with fields:
    - timestamp: ISO datetime
    - open: Opening price
    - high: Highest price
    - low: Lowest price  
    - close: Closing price
    - volume: Trading volume
    """
    df = await fetch_aggs(symbol.upper(), timespan=timespan, limit=limit, adjusted=str(adjusted).lower())
    df["timestamp"] = df["timestamp"].astype(str)
    return JSONResponse(df.to_dict(orient="records"))

@app.get(
    "/api/indicators/list",
    tags=["Technical Indicators"],
    summary="List all available indicators",
    description="Returns 160+ available technical indicators including RSI, MACD, ADX, Bollinger Bands, SMA, EMA, ATR, Stochastic, and more. Use names with /api/indicators/{name}."
)
async def indicators_list(_=Depends(require_auth)):
    """
    Returns comprehensive list of all available pandas_ta technical indicators.
    Each indicator can be calculated on any stock by calling /api/indicators/{indicator_name}
    """
    return {"count": len(INDICATORS), "indicators": list_indicators()}

@app.get(
    "/api/indicators/{name}",
    tags=["Technical Indicators"],
    summary="Calculate technical indicator",
    description="Calculate any indicator for a stock. Examples: rsi?symbol=AAPL&length=14, macd?symbol=TSLA&fast=12&slow=26, bbands?symbol=NVDA&length=20. Supports 160+ indicators."
)
async def indicator(
    name: str = Path(..., description="Indicator name (e.g., rsi, macd, adx, bbands, sma, ema)"),
    symbol: str = Query(..., description="Stock ticker symbol"),
    timespan: str = Query(DEFAULT_TIMESPAN, description="Time interval: 'minute' or 'day'", pattern="^(minute|day)$"),
    limit: int = Query(500, description="Number of data points (5-5000)", ge=5, le=5000),
    request: Request = None,
    _=Depends(require_auth)
):
    user_params = {k: v for k, v in request.query_params.items()
                   if k not in {"symbol", "timespan", "limit"}}
    for k, v in list(user_params.items()):
        if isinstance(v, str) and v.isdigit():
            user_params[k] = int(v)
        else:
            try:
                user_params[k] = float(v) if "." in v else int(v)
            except Exception:
                pass
    df = await fetch_aggs(symbol.upper(), timespan=timespan, limit=limit)
    try:
        out = compute_indicator_dynamic(df, name, user_params).reset_index(names="timestamp")
        out["timestamp"] = out["timestamp"].astype(str)
        json_data = out.to_json(orient="records", date_format="iso")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(content=json_data, media_type="application/json")

@app.post(
    "/api/indicators/batch",
    tags=["Technical Indicators"],
    summary="Calculate indicators for 1-N symbols in one request",
    description="Universal batch endpoint: calculate multiple indicators for one or many symbols. Single symbol returns time-series data, multiple symbols return latest values per symbol."
)
async def indicators_batch(payload: BatchIndicatorRequest, _=Depends(require_auth)):
    """
    Unified batch endpoint that handles both single and multiple symbols.
    
    Single symbol example (returns time-series):
    {
        "symbols": ["AAPL"],
        "timespan": "day",
        "limit": 500,
        "specs": [
            {"name": "rsi", "params": {"length": 14}},
            {"name": "macd", "params": {}}
        ]
    }
    
    Multiple symbols example (returns latest values per symbol):
    {
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "timespan": "day",
        "limit": 500,
        "specs": [
            {"name": "rsi", "params": {"length": 14}},
            {"name": "sma", "params": {"length": 20}}
        ]
    }
    """
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(400, "At least one symbol required")
    
    if len(symbols) > 200:
        raise HTTPException(400, "Maximum 200 symbols per request")
    
    specs = payload.specs or []
    if not isinstance(specs, list) or not specs:
        raise HTTPException(400, "specs must be a non-empty list")
    
    timespan = payload.timespan
    limit = payload.limit
    
    # Single symbol: return time-series data
    if len(symbols) == 1:
        symbol = symbols[0]
        df = await fetch_aggs(symbol, timespan=timespan, limit=limit)
        try:
            out = compute_batch_dynamic(df, specs).reset_index(names="timestamp")
            out["timestamp"] = out["timestamp"].astype(str)
            json_data = out.to_json(orient="records", date_format="iso")
        except ValueError as e:
            raise HTTPException(400, str(e))
        return Response(content=json_data, media_type="application/json")
    
    # Multiple symbols: return latest values per symbol
    async def process_symbol(symbol: str):
        """Process one symbol with all indicators"""
        try:
            df = await fetch_aggs(symbol, timespan=timespan, limit=limit)
            if df.empty:
                return {
                    "symbol": symbol,
                    "error": "No data available",
                    "indicators": None
                }
            
            # Compute all indicators for this symbol
            result_df = compute_batch_dynamic(df, specs)
            
            # Get the most recent values
            latest = result_df.iloc[-1].to_dict()
            
            return {
                "symbol": symbol,
                "error": None,
                "indicators": {k: (float(v) if pd.notna(v) else None) for k, v in latest.items()}
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "indicators": None
            }
    
    # Process all symbols concurrently
    import asyncio
    results = await asyncio.gather(*[process_symbol(sym) for sym in symbols])
    
    return {
        "timespan": timespan,
        "limit": limit,
        "total_symbols": len(symbols),
        "successful": sum(1 for r in results if r["error"] is None),
        "results": results
    }

@app.get(
    "/api/metrics/price",
    tags=["Price Metrics"],
    summary="Calculate Wyckoff price & volume metrics",
    description="Calculates relative volume, volume surge index, historical volatility, and HV-IV differential for technical analysis. Supports minute and day timeframes."
)
async def get_price_metrics(
    symbol: str = Query(..., description="Stock ticker symbol", examples=["AAPL"]),
    timespan: str = Query(DEFAULT_TIMESPAN, description="Time interval: 'minute' or 'day'", pattern="^(minute|day)$"),
    limit: int = Query(100, description="Number of data points for calculation (20-5000)", ge=20, le=5000),
    period: int = Query(20, description="Lookback period for metrics calculation", ge=5, le=100),
    iv: Optional[float] = Query(None, description="Implied volatility (%) for HV-IV differential calculation"),
    _=Depends(require_auth)
):
    """
    Computes price and volume-derived metrics for Wyckoff analysis:
    - Relative Volume (RVOL): Current volume vs average volume over period
    - Volume Surge Index (VSI): Z-score of current volume vs trailing mean
    - Historical Volatility (HV): Annualized volatility percentage
    - HV-IV Differential: Difference between historical and implied volatility (if IV provided)
    
    Returns:
    - symbol: Stock ticker
    - Relative_Volume: RVOL ratio
    - Volume_Surge_Index: VSI z-score
    - Historical_Volatility: Annualized HV percentage
    - HV_IV_Diff: HV - IV differential (null if IV not provided)
    """
    df = await fetch_aggs(symbol.upper(), timespan=timespan, limit=limit)
    
    # Return null values if insufficient data instead of throwing error
    if len(df) < period:
        return {
            "symbol": symbol.upper(),
            "timespan": timespan,
            "period": period,
            "bars_available": len(df),
            "warning": f"Insufficient data: need at least {period} bars, got {len(df)}",
            "Relative_Volume": None,
            "Volume_Surge_Index": None,
            "Historical_Volatility": None,
            "HV_IV_Diff": None
        }
    
    try:
        rv = relative_volume(df, period=period)
        vsi = volume_surge_index(df, period=period)
        hv = historical_volatility(df, period=period)
        diff = hv_iv_diff(hv, iv) if iv is not None else None
        
        return {
            "symbol": symbol.upper(),
            "timespan": timespan,
            "period": period,
            "bars_available": len(df),
            "Relative_Volume": float(rv) if not pd.isna(rv) else None,
            "Volume_Surge_Index": float(vsi) if not pd.isna(vsi) else None,
            "Historical_Volatility": float(hv) if not pd.isna(hv) else None,
            "HV_IV_Diff": float(diff) if diff is not None and not pd.isna(diff) else None
        }
    except ValueError as e:
        return {
            "symbol": symbol.upper(),
            "timespan": timespan,
            "period": period,
            "bars_available": len(df),
            "error": str(e),
            "Relative_Volume": None,
            "Volume_Surge_Index": None,
            "Historical_Volatility": None,
            "HV_IV_Diff": None
        }

@app.post(
    "/api/metrics/price",
    tags=["Price Metrics"],
    summary="Calculate Wyckoff price & volume metrics (POST)",
    description="Calculates relative volume, volume surge index, historical volatility, and HV-IV differential for technical analysis. POST version accepts JSON body."
)
async def post_price_metrics(payload: PriceMetricsRequest, _=Depends(require_auth)):
    """
    Computes price and volume-derived metrics for Wyckoff analysis using JSON request body.
    Same functionality as GET endpoint but accepts parameters as JSON.
    """
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(400, "symbol required")
    
    df = await fetch_aggs(symbol, timespan=payload.timespan, limit=payload.limit)
    
    # Return null values if insufficient data instead of throwing error
    if len(df) < payload.period:
        return {
            "symbol": symbol,
            "timespan": payload.timespan,
            "period": payload.period,
            "bars_available": len(df),
            "warning": f"Insufficient data: need at least {payload.period} bars, got {len(df)}",
            "Relative_Volume": None,
            "Volume_Surge_Index": None,
            "Historical_Volatility": None,
            "HV_IV_Diff": None
        }
    
    try:
        rv = relative_volume(df, period=payload.period)
        vsi = volume_surge_index(df, period=payload.period)
        hv = historical_volatility(df, period=payload.period)
        diff = hv_iv_diff(hv, payload.iv) if payload.iv is not None else None
        
        return {
            "symbol": symbol,
            "timespan": payload.timespan,
            "period": payload.period,
            "bars_available": len(df),
            "Relative_Volume": float(rv) if not pd.isna(rv) else None,
            "Volume_Surge_Index": float(vsi) if not pd.isna(vsi) else None,
            "Historical_Volatility": float(hv) if not pd.isna(hv) else None,
            "HV_IV_Diff": float(diff) if diff is not None and not pd.isna(diff) else None
        }
    except ValueError as e:
        return {
            "symbol": symbol,
            "timespan": payload.timespan,
            "period": payload.period,
            "bars_available": len(df),
            "error": str(e),
            "Relative_Volume": None,
            "Volume_Surge_Index": None,
            "Historical_Volatility": None,
            "HV_IV_Diff": None
        }

@app.post(
    "/api/metrics/batch",
    tags=["Price Metrics"],
    summary="Calculate Wyckoff metrics for multiple symbols",
    description="Batch endpoint to calculate Wyckoff price & volume metrics for 1-200 symbols in one request. Returns latest metrics for each symbol."
)
async def batch_price_metrics(payload: BatchPriceMetricsRequest, _=Depends(require_auth)):
    """
    Batch calculate Wyckoff metrics for multiple symbols concurrently.
    
    Request body:
    {
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "timespan": "day",
        "limit": 100,
        "period": 20,
        "iv": 35.5
    }
    
    Returns array of results with metrics for each symbol.
    """
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(400, "At least one symbol required")
    
    if len(symbols) > 200:
        raise HTTPException(400, "Maximum 200 symbols per request")
    
    async def process_symbol(symbol: str):
        """Process single symbol and return metrics or error"""
        try:
            df = await fetch_aggs(symbol, timespan=payload.timespan, limit=payload.limit)
            
            # Return null values if insufficient data
            if len(df) < payload.period:
                return {
                    "symbol": symbol,
                    "error": None,
                    "warning": f"Insufficient data: need at least {payload.period} bars, got {len(df)}",
                    "bars_available": len(df),
                    "Relative_Volume": None,
                    "Volume_Surge_Index": None,
                    "Historical_Volatility": None,
                    "HV_IV_Diff": None
                }
            
            rv = relative_volume(df, period=payload.period)
            vsi = volume_surge_index(df, period=payload.period)
            hv = historical_volatility(df, period=payload.period)
            diff = hv_iv_diff(hv, payload.iv) if payload.iv is not None else None
            
            return {
                "symbol": symbol,
                "error": None,
                "bars_available": len(df),
                "Relative_Volume": float(rv) if not pd.isna(rv) else None,
                "Volume_Surge_Index": float(vsi) if not pd.isna(vsi) else None,
                "Historical_Volatility": float(hv) if not pd.isna(hv) else None,
                "HV_IV_Diff": float(diff) if diff is not None and not pd.isna(diff) else None
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "bars_available": 0,
                "Relative_Volume": None,
                "Volume_Surge_Index": None,
                "Historical_Volatility": None,
                "HV_IV_Diff": None
            }
    
    # Process all symbols concurrently
    import asyncio
    results = await asyncio.gather(*[process_symbol(sym) for sym in symbols])
    
    return {
        "timespan": payload.timespan,
        "limit": payload.limit,
        "period": payload.period,
        "total_symbols": len(symbols),
        "successful": sum(1 for r in results if r["error"] is None and r.get("warning") is None),
        "results": results
    }

# ============================================================================
# OPTIONS DATA ENDPOINTS (Batch up to 20 symbols)
# ============================================================================

@app.post(
    "/api/chains",
    tags=["Options Data"],
    summary="Get option chains with Greeks for multiple symbols",
    description="Batch retrieve option chains with Greeks data for 1-20 underlying symbols"
)
async def batch_option_chains(payload: BatchChainsRequest, _=Depends(require_auth)):
    """
    Get option chains with Greeks for multiple symbols concurrently.
    
    Request body:
    {
        "symbols": ["AAPL", "SPY", "MSFT"]
    }
    
    Returns options snapshot data with Greeks for each symbol.
    """
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(400, "At least one symbol required")
    
    if len(symbols) > 20:
        raise HTTPException(400, "Maximum 20 symbols per request")
    
    async def process_symbol(symbol: str):
        """Fetch options snapshot for single symbol"""
        try:
            path = f"v3/snapshot/options/{symbol}"
            data = await polygon_get(path, {"limit": 250})
            
            if isinstance(data, JSONResponse):
                return {
                    "symbol": symbol,
                    "error": f"Polygon error: {data.status_code}",
                    "contracts": [],
                    "count": 0
                }
            
            results = data.get("results", [])
            if not results:
                return {
                    "symbol": symbol,
                    "error": None,
                    "contracts": [],
                    "count": 0
                }
            
            contracts = []
            for contract in results:
                details = contract.get("details", {})
                greeks = contract.get("greeks", {})
                last_quote = contract.get("last_quote", {})
                contracts.append({
                    "ticker": contract.get("ticker", ""),
                    "strike": details.get("strike_price"),
                    "type": details.get("contract_type"),
                    "expiration": details.get("expiration_date"),
                    "last_price": last_quote.get("last_updated"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                    "rho": greeks.get("rho"),
                    "iv": greeks.get("implied_volatility")
                })
            
            return {
                "symbol": symbol,
                "error": None,
                "contracts": contracts,
                "count": len(contracts)
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "contracts": [],
                "count": 0
            }
    
    import asyncio
    results = await asyncio.gather(*[process_symbol(sym) for sym in symbols])
    
    return {
        "total_symbols": len(symbols),
        "successful": sum(1 for r in results if r["error"] is None),
        "results": results
    }

@app.post(
    "/api/dealer-metrics",
    tags=["Options Data"],
    summary="Get dealer positioning metrics for multiple symbols",
    description="""Batch retrieve dealer flow and positioning metrics for 1-20 symbols.

Returns Schwab-equivalent dealer metrics including:
- **gamma_exposure**: Total absolute GEX (gamma exposure) across all strikes
- **net_gex**: Signed GEX (positive for calls, negative for puts)
- **gamma_flip**: Price level where dealers switch from long to short gamma
- **call_walls**: Top 3 strikes with highest call open interest (resistance levels)
- **put_walls**: Top 3 strikes with highest put open interest (support levels)
- **gex_slope**: Rate of change of GEX with price movement
- **dealer_gamma_pressure_index**: Composite stress measure (0-1)
- **position**: Current position relative to gamma flip (above_flip/below_flip/at_flip)
- **confidence**: Data quality confidence (high/medium/low/invalid)
- **expected_move**: Expected price move based on IV and DTE"""
)
async def batch_dealer_metrics(payload: BatchDealerMetricsRequest, _=Depends(require_auth)):
    """
    Get dealer positioning and flow metrics for multiple symbols.
    
    Request body:
    {
        "symbols": ["AAPL", "SPY"]
    }
    
    Returns comprehensive dealer flow metrics based on options gamma exposure.
    """
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(400, "At least one symbol required")
    
    if len(symbols) > 20:
        raise HTTPException(400, "Maximum 20 symbols per request")
    
    async def get_underlying_price(symbol: str) -> Optional[float]:
        """Get current underlying price from Polygon"""
        try:
            path = f"v2/aggs/ticker/{symbol}/prev"
            data = await polygon_get(path, {})
            if isinstance(data, dict) and "results" in data:
                results = data.get("results", [])
                if results:
                    return results[0].get("c")  # Close price
        except:
            pass
        return None
    
    async def process_symbol(symbol: str):
        """Calculate dealer metrics for single symbol"""
        try:
            underlying_price = await get_underlying_price(symbol)
            if underlying_price is None:
                return {
                    "symbol": symbol,
                    "error": None,
                    "warning": "Could not fetch underlying price",
                    "underlying_price": None,
                    "expected_move": None,
                    "gamma_exposure": None,
                    "net_gex": None,
                    "gamma_flip": None,
                    "call_walls": [],
                    "put_walls": [],
                    "gex_slope": None,
                    "dealer_gamma_pressure_index": None,
                    "position": "unknown",
                    "confidence": "invalid",
                    "metadata": None
                }
            
            path = f"v3/snapshot/options/{symbol}"
            data = await polygon_get(path, {"limit": 250})
            
            if isinstance(data, JSONResponse):
                return {
                    "symbol": symbol,
                    "error": None,
                    "warning": f"Polygon error: {data.status_code}",
                    "underlying_price": underlying_price,
                    "expected_move": None,
                    "gamma_exposure": None,
                    "net_gex": None,
                    "gamma_flip": None,
                    "call_walls": [],
                    "put_walls": [],
                    "gex_slope": None,
                    "dealer_gamma_pressure_index": None,
                    "position": "unknown",
                    "confidence": "invalid",
                    "metadata": None
                }
            
            results = data.get("results", [])
            if not results:
                return {
                    "symbol": symbol,
                    "error": None,
                    "warning": "No options data available",
                    "underlying_price": underlying_price,
                    "expected_move": None,
                    "gamma_exposure": None,
                    "net_gex": None,
                    "gamma_flip": None,
                    "call_walls": [],
                    "put_walls": [],
                    "gex_slope": None,
                    "dealer_gamma_pressure_index": None,
                    "position": "unknown",
                    "confidence": "invalid",
                    "metadata": None
                }
            
            contracts = []
            iv_values = []
            min_dte = float('inf')
            from datetime import datetime
            
            for contract in results:
                details = contract.get("details", {})
                greeks = contract.get("greeks", {})
                day_data = contract.get("day", {})
                
                gamma = greeks.get("gamma")
                if gamma is None:
                    continue
                
                oi = contract.get("open_interest", 0) or 0
                iv = contract.get("implied_volatility")
                
                exp = details.get("expiration_date")
                contract_dte = 30
                if exp:
                    try:
                        exp_date = datetime.strptime(exp, "%Y-%m-%d")
                        contract_dte = max(0, (exp_date - datetime.now()).days)
                    except:
                        pass
                
                if contract_dte < payload.dte_min or contract_dte > payload.dte_max:
                    continue
                
                if oi < payload.min_oi:
                    continue
                
                contracts.append(DealerOptionContract(
                    strike=details.get("strike_price", 0),
                    contract_type=details.get("contract_type", "call"),
                    gamma=gamma,
                    open_interest=oi,
                    delta=greeks.get("delta"),
                    implied_volatility=iv,
                    bid=contract.get("last_quote", {}).get("bid"),
                    ask=contract.get("last_quote", {}).get("ask"),
                    expiration=exp,
                    dte=contract_dte
                ))
                
                if iv is not None:
                    iv_values.append(iv)
                
                if contract_dte > 0 and contract_dte < min_dte:
                    min_dte = contract_dte
            
            if not contracts:
                return {
                    "symbol": symbol,
                    "error": None,
                    "warning": "No valid contracts with gamma data",
                    "underlying_price": underlying_price,
                    "expected_move": None,
                    "gamma_exposure": None,
                    "net_gex": None,
                    "gamma_flip": None,
                    "call_walls": [],
                    "put_walls": [],
                    "gex_slope": None,
                    "dealer_gamma_pressure_index": None,
                    "position": "unknown",
                    "confidence": "invalid",
                    "metadata": None
                }
            
            avg_iv = sum(iv_values) / len(iv_values) if iv_values else None
            calc_dte = min_dte if min_dte != float('inf') else None
            
            final_iv = payload.iv if payload.iv is not None else avg_iv
            final_dte = payload.dte if payload.dte is not None else calc_dte
            final_iv_rank = payload.iv_rank
            
            metrics = calculate_dealer_metrics(
                underlying_price=underlying_price,
                contracts=contracts,
                iv=final_iv,
                dte=final_dte,
                iv_rank=final_iv_rank
            )
            
            return {
                "symbol": symbol,
                "error": None,
                "underlying_price": metrics.underlying_price,
                "expected_move": metrics.expected_move,
                "gamma_exposure": metrics.gamma_exposure,
                "net_gex": metrics.net_gex,
                "gamma_flip": metrics.gamma_flip,
                "call_walls": metrics.call_walls,
                "put_walls": metrics.put_walls,
                "gex_slope": metrics.gex_slope,
                "dealer_gamma_pressure_index": metrics.dealer_gamma_pressure_index,
                "position": metrics.position,
                "confidence": metrics.confidence,
                "metadata": metrics.metadata
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": None,
                "warning": str(e),
                "underlying_price": None,
                "expected_move": None,
                "gamma_exposure": None,
                "net_gex": None,
                "gamma_flip": None,
                "call_walls": [],
                "put_walls": [],
                "gex_slope": None,
                "dealer_gamma_pressure_index": None,
                "position": "unknown",
                "confidence": "invalid",
                "metadata": None
            }
    
    import asyncio
    results = await asyncio.gather(*[process_symbol(sym) for sym in symbols])
    
    return {
        "total_symbols": len(symbols),
        "successful": sum(1 for r in results if r.get("confidence") not in [None, "invalid"]),
        "results": results
    }

@app.post(
    "/api/metrics/volatility",
    tags=["Options Data"],
    summary="Get volatility metrics for multiple symbols",
    description="""Batch retrieve volatility metrics for 1-20 symbols.

Returns Schwab-equivalent volatility metrics including:
- **historical_volatility**: Annualized HV from price data
- **implied_volatility**: Average IV from options chain
- **iv_skew**: IV(25Δ put) - IV(25Δ call) in percentage points. Positive = higher put demand
- **iv_term_structure**: IV(90D) - IV(30D) in percentage points. Positive = backwardation
- **oi_ratio**: Volume / Open Interest ratio. Higher = more speculative activity"""
)
async def batch_volatility_metrics(payload: BatchVolatilityMetricsRequest, _=Depends(require_auth)):
    """
    Get volatility metrics for multiple symbols.
    
    Request body:
    {
        "symbols": ["AAPL", "SPY"],
        "period": 20
    }
    
    Returns comprehensive volatility metrics including skew and term structure.
    """
    symbols = [s.strip().upper() for s in payload.symbols if s.strip()]
    if not symbols:
        raise HTTPException(400, "At least one symbol required")
    
    if len(symbols) > 20:
        raise HTTPException(400, "Maximum 20 symbols per request")
    
    async def get_underlying_price(symbol: str) -> Optional[float]:
        """Get the current/last price of the underlying"""
        try:
            path = f"v2/aggs/ticker/{symbol}/prev"
            data = await polygon_get(path, {})
            if isinstance(data, dict) and "results" in data:
                results = data.get("results", [])
                if results:
                    return results[0].get("c")  # Close price
        except:
            pass
        return None

    async def process_symbol(symbol: str):
        """Calculate volatility metrics for single symbol"""
        try:
            underlying_price = await get_underlying_price(symbol)
            df = await fetch_aggs(symbol, timespan="day", limit=100)
            
            hv = None
            if len(df) >= payload.period:
                hv = historical_volatility(df, period=payload.period)
                if pd.isna(hv):
                    hv = None
            
            path = f"v3/snapshot/options/{symbol}"
            opt_data = await polygon_get(path, {"limit": 250})
            
            if isinstance(opt_data, JSONResponse):
                return {
                    "symbol": symbol,
                    "error": None,
                    "bars_available": len(df),
                    "historical_volatility": float(hv) if hv else None,
                    "implied_volatility": None,
                    "iv_skew": None,
                    "iv_term_structure": None,
                    "oi_ratio": None
                }
            
            results = opt_data.get("results", [])
            if not results:
                return {
                    "symbol": symbol,
                    "error": None,
                    "bars_available": len(df),
                    "historical_volatility": float(hv) if hv else None,
                    "implied_volatility": None,
                    "iv_skew": None,
                    "iv_term_structure": None,
                    "oi_ratio": None
                }
            
            contracts = []
            iv_values = []
            from datetime import datetime
            
            for contract in results:
                details = contract.get("details", {})
                greeks = contract.get("greeks", {})
                day_data = contract.get("day", {})
                
                iv = contract.get("implied_volatility")
                oi = contract.get("open_interest", 0) or 0
                
                exp = details.get("expiration_date")
                contract_dte = 30
                if exp:
                    try:
                        exp_date = datetime.strptime(exp, "%Y-%m-%d")
                        contract_dte = max(0, (exp_date - datetime.now()).days)
                    except:
                        pass
                
                if contract_dte < payload.dte_min or contract_dte > payload.dte_max:
                    continue
                
                if oi < payload.min_oi:
                    continue
                
                if iv is not None:
                    iv_values.append(iv)
                
                contracts.append(OptionContractVol(
                    strike=details.get("strike_price", 0),
                    contract_type=details.get("contract_type", "call"),
                    delta=greeks.get("delta"),
                    iv=iv,
                    dte=contract_dte,
                    volume=day_data.get("volume", 0) or 0,
                    open_interest=oi
                ))
            
            avg_iv = sum(iv_values) / len(iv_values) if iv_values else None
            
            vol_metrics = calculate_volatility_metrics(contracts, spot=underlying_price)
            
            return {
                "symbol": symbol,
                "error": None,
                "bars_available": len(df),
                "underlying_price": underlying_price,
                "historical_volatility": float(hv) if hv else None,
                "implied_volatility": avg_iv,
                "iv_skew": vol_metrics['iv_skew'],
                "iv_term_structure": vol_metrics['iv_term_structure'],
                "oi_ratio": vol_metrics['oi_ratio']
            }
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "bars_available": 0,
                "historical_volatility": None,
                "implied_volatility": None,
                "iv_skew": None,
                "iv_term_structure": None,
                "oi_ratio": None
            }
    
    import asyncio
    results = await asyncio.gather(*[process_symbol(sym) for sym in symbols])
    
    return {
        "total_symbols": len(symbols),
        "period": payload.period,
        "successful": sum(1 for r in results if r["error"] is None),
        "results": results
    }

