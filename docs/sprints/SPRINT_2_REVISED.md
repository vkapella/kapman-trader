# SPRINT 2: WYCKOFF ENGINE & DAILY PIPELINE
## Revised Implementation Guide (Post Schema Enhancement)

**Sprint Duration:** December 14-20, 2025  
**Total Points:** 28 (increased from 24)  
**Prerequisites:** Sprint 1 complete + Migration 004 applied

---

## Sprint 2 Overview

| Story | Points | Status | Dependencies |
|-------|--------|--------|--------------|
| 2.0 Apply Schema Migration | 2 | NEW | Sprint 1 complete |
| 2.1 S3 Universe Loader | 6 | REVISED | Migration 004 |
| 2.2 Options Chain Pipeline | 6 | REVISED | 2.1 |
| 2.3 Technical Indicators Integration | 4 | NEW | 2.1 |
| 2.4 Wyckoff Engine Migration | 6 | UNCHANGED | 2.1, 2.3 |
| 2.5 Daily Batch Orchestrator | 4 | REVISED | 2.1-2.4 |

---

## Story 2.0: Apply Schema Migration (2 pts)

### Tasks

```bash
# Task 2.0.1: Backup existing database
docker exec kapman-db pg_dump -U kapman kapman > backup_pre_migration.sql

# Task 2.0.2: Apply migration 004
docker exec -i kapman-db psql -U kapman kapman < db/migrations/004_enhanced_metrics_schema.sql

# Task 2.0.3: Verify migration
docker exec kapman-db psql -U kapman kapman -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name = 'daily_snapshots' 
  ORDER BY ordinal_position;
"

# Task 2.0.4: Verify hypertables
docker exec kapman-db psql -U kapman kapman -c "
  SELECT hypertable_name, num_chunks 
  FROM timescaledb_information.hypertables;
"
```

### Acceptance Criteria
- [ ] Migration 004 applied without errors
- [ ] `daily_snapshots` has 45+ columns
- [ ] `options_daily_summary` table exists
- [ ] `tickers` has universe_tier column
- [ ] Helper views created (v_latest_snapshots, v_watchlist_tickers, v_alerts)

---

## Story 2.1: S3 Universe Loader (6 pts)

### Overview
Load full Polygon universe OHLCV from S3 flat files daily.

### File: core/pipeline/s3_universe_loader.py

```python
"""
S3 Universe OHLCV Loader

Loads full Polygon universe (~15K tickers) from S3 flat files.
Single daily file contains all tickers - download once, bulk insert.
"""

import asyncio
import gzip
import io
from datetime import date, timedelta
from typing import Optional

import boto3
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.db.client import get_async_session

class S3UniverseLoader:
    """Load full OHLCV universe from Polygon S3 flat files."""
    
    S3_BUCKET = "flatfiles"
    OHLCV_PREFIX = "us_stocks_sip/day_aggs_v1"
    
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    
    async def load_daily(
        self, 
        target_date: Optional[date] = None,
        batch_size: int = 5000
    ) -> dict:
        """
        Load all OHLCV data for a single day.
        
        Args:
            target_date: Date to load (default: yesterday)
            batch_size: Rows per INSERT batch
            
        Returns:
            dict with loaded count, errors, duration
        """
        import time
        start_time = time.time()
        
        target_date = target_date or (date.today() - timedelta(days=1))
        
        # Download and parse S3 file
        df = await self._download_daily_file(target_date)
        
        if df.empty:
            return {
                "status": "no_data",
                "date": str(target_date),
                "loaded": 0,
                "duration_seconds": time.time() - start_time
            }
        
        # Bulk insert
        loaded = await self._bulk_insert(df, batch_size)
        
        # Update ticker last_ohlcv_date
        await self._update_ticker_dates(df['symbol'].unique().tolist(), target_date)
        
        return {
            "status": "success",
            "date": str(target_date),
            "loaded": loaded,
            "tickers": len(df['symbol'].unique()),
            "duration_seconds": round(time.time() - start_time, 2)
        }
    
    async def backfill(
        self,
        start_date: date,
        end_date: date,
        symbols: Optional[list[str]] = None
    ) -> dict:
        """
        Backfill historical OHLCV data.
        
        Args:
            start_date: Start of backfill range
            end_date: End of backfill range  
            symbols: Optional filter to specific symbols
            
        Returns:
            dict with total loaded, errors, duration
        """
        import time
        start_time = time.time()
        
        results = {
            "status": "success",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "days_processed": 0,
            "total_loaded": 0,
            "errors": []
        }
        
        current = start_date
        while current <= end_date:
            try:
                daily_result = await self.load_daily(current)
                results["days_processed"] += 1
                results["total_loaded"] += daily_result.get("loaded", 0)
                
                # Rate limit: don't hammer S3
                await asyncio.sleep(0.1)
                
            except Exception as e:
                results["errors"].append({
                    "date": str(current),
                    "error": str(e)
                })
            
            current += timedelta(days=1)
        
        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results
    
    async def _download_daily_file(self, target_date: date) -> pd.DataFrame:
        """Download and parse a single day's OHLCV file from S3."""
        
        key = f"{self.OHLCV_PREFIX}/{target_date.year}/{target_date.month:02d}/{target_date.strftime('%Y-%m-%d')}.csv.gz"
        
        try:
            response = self.s3.get_object(Bucket=self.S3_BUCKET, Key=key)
            
            # Decompress and read
            with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as gz:
                df = pd.read_csv(gz)
            
            # Rename columns to match our schema
            df = df.rename(columns={
                'ticker': 'symbol',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'vw': 'vwap',
                't': 'timestamp_ms'
            })
            
            # Convert timestamp (Polygon uses milliseconds)
            df['time'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
            
            # Filter to stocks only (exclude weird tickers)
            df = df[
                df['symbol'].str.match(r'^[A-Z]{1,5}$') &  # 1-5 uppercase letters
                (df['volume'] > 0)  # Has trading activity
            ]
            
            return df[['time', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'vwap']]
            
        except self.s3.exceptions.NoSuchKey:
            # No data for this date (weekend/holiday)
            return pd.DataFrame()
    
    async def _bulk_insert(self, df: pd.DataFrame, batch_size: int) -> int:
        """Bulk insert OHLCV data using batched INSERTs."""
        
        async with get_async_session() as session:
            loaded = 0
            
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i + batch_size]
                
                # Build VALUES clause
                values = []
                for _, row in batch.iterrows():
                    values.append(
                        f"('{row['time']}'::timestamptz, '{row['symbol']}', "
                        f"{row['open']}, {row['high']}, {row['low']}, {row['close']}, "
                        f"{row['volume']}, {row['vwap'] if pd.notna(row['vwap']) else 'NULL'}, "
                        f"'polygon_s3')"
                    )
                
                # Bulk insert with ON CONFLICT
                await session.execute(text(f"""
                    INSERT INTO ohlcv_daily 
                        (time, symbol, open, high, low, close, volume, vwap, source)
                    VALUES {', '.join(values)}
                    ON CONFLICT (time, symbol) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        vwap = EXCLUDED.vwap
                """))
                
                loaded += len(batch)
            
            await session.commit()
            return loaded
    
    async def _update_ticker_dates(self, symbols: list[str], target_date: date):
        """Update last_ohlcv_date for loaded tickers."""
        
        async with get_async_session() as session:
            # Upsert tickers that don't exist yet
            for symbol in symbols:
                await session.execute(text("""
                    INSERT INTO tickers (symbol, universe_tier, is_active, last_ohlcv_date)
                    VALUES (:symbol, 'polygon_full', true, :date)
                    ON CONFLICT (symbol) DO UPDATE SET
                        last_ohlcv_date = GREATEST(tickers.last_ohlcv_date, :date)
                """), {"symbol": symbol, "date": target_date})
            
            await session.commit()
```

### Tasks

| Task | Description | Est. Hours |
|------|-------------|------------|
| 2.1.1 | Create S3UniverseLoader class | 2 |
| 2.1.2 | Implement download_daily_file with gzip | 1 |
| 2.1.3 | Implement bulk_insert with batching | 2 |
| 2.1.4 | Implement backfill with rate limiting | 1 |
| 2.1.5 | Add ticker upsert logic | 1 |
| 2.1.6 | Unit tests | 1 |

### Acceptance Criteria
- [ ] Single day loads ~15K tickers in < 60 seconds
- [ ] Backfill 2 years completes in < 4 hours
- [ ] Tickers auto-created with universe_tier='polygon_full'
- [ ] last_ohlcv_date updated correctly

---

## Story 2.2: Options Chain Pipeline (6 pts)

### Overview
Fetch options data via API for watchlist tickers only, aggregate to summary table.

### File: core/pipeline/options_loader.py

```python
"""
Options Chain Loader

Fetches options data from Polygon API for watchlist tickers.
Aggregates to options_daily_summary for dealer calculations.
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.db.client import get_async_session

class OptionsChainLoader:
    """Load options chains from Polygon API for watchlist tickers."""
    
    BASE_URL = "https://api.polygon.io"
    MAX_RPS = 100  # Stay under 100 requests/second
    
    def __init__(self):
        self.api_key = settings.POLYGON_API_KEY
        self.semaphore = asyncio.Semaphore(50)  # Concurrent request limit
    
    async def load_watchlist_options(
        self,
        symbols: Optional[list[str]] = None,
        target_date: Optional[date] = None
    ) -> dict:
        """
        Load options chains for watchlist tickers.
        
        Args:
            symbols: List of symbols (default: all watchlist tickers)
            target_date: Date for snapshot
            
        Returns:
            dict with loaded counts and errors
        """
        import time
        start_time = time.time()
        
        target_date = target_date or date.today()
        
        # Get watchlist symbols if not provided
        if symbols is None:
            symbols = await self._get_watchlist_symbols()
        
        results = {
            "status": "success",
            "date": str(target_date),
            "symbols_processed": 0,
            "contracts_loaded": 0,
            "summaries_created": 0,
            "errors": []
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [
                self._process_symbol(client, symbol, target_date, results)
                for symbol in symbols
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results
    
    async def _process_symbol(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        target_date: date,
        results: dict
    ):
        """Process a single symbol: fetch chain, store, aggregate."""
        
        async with self.semaphore:
            try:
                # Fetch options chain
                chain_data = await self._fetch_options_chain(client, symbol)
                
                if not chain_data:
                    return
                
                # Store individual contracts
                contracts_stored = await self._store_contracts(
                    symbol, target_date, chain_data
                )
                
                # Create daily summary
                await self._create_daily_summary(symbol, target_date, chain_data)
                
                results["symbols_processed"] += 1
                results["contracts_loaded"] += contracts_stored
                results["summaries_created"] += 1
                
                # Rate limiting
                await asyncio.sleep(0.01)  # ~100 RPS max
                
            except Exception as e:
                results["errors"].append({
                    "symbol": symbol,
                    "error": str(e)
                })
    
    async def _fetch_options_chain(
        self,
        client: httpx.AsyncClient,
        symbol: str
    ) -> list[dict]:
        """Fetch options chain from Polygon API."""
        
        url = f"{self.BASE_URL}/v3/snapshot/options/{symbol}"
        params = {
            "apiKey": self.api_key,
            "limit": 250  # Max per request
        }
        
        all_contracts = []
        
        while url:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            all_contracts.extend(data.get("results", []))
            
            # Handle pagination
            url = data.get("next_url")
            params = {"apiKey": self.api_key} if url else None
        
        return all_contracts
    
    async def _store_contracts(
        self,
        symbol: str,
        target_date: date,
        contracts: list[dict]
    ) -> int:
        """Store individual option contracts."""
        
        async with get_async_session() as session:
            stored = 0
            
            for contract in contracts:
                details = contract.get("details", {})
                greeks = contract.get("greeks", {})
                day = contract.get("day", {})
                
                await session.execute(text("""
                    INSERT INTO options_chains (
                        time, symbol, expiration, strike, option_type,
                        bid, ask, last, volume, open_interest,
                        implied_volatility, delta, gamma, theta, vega,
                        source
                    ) VALUES (
                        :time, :symbol, :expiration, :strike, :option_type,
                        :bid, :ask, :last, :volume, :open_interest,
                        :iv, :delta, :gamma, :theta, :vega,
                        'polygon_api'
                    )
                    ON CONFLICT (time, symbol, expiration, strike, option_type) 
                    DO UPDATE SET
                        bid = EXCLUDED.bid,
                        ask = EXCLUDED.ask,
                        volume = EXCLUDED.volume,
                        open_interest = EXCLUDED.open_interest,
                        implied_volatility = EXCLUDED.implied_volatility,
                        delta = EXCLUDED.delta,
                        gamma = EXCLUDED.gamma
                """), {
                    "time": target_date,
                    "symbol": symbol,
                    "expiration": details.get("expiration_date"),
                    "strike": details.get("strike_price"),
                    "option_type": details.get("contract_type", "")[0].upper(),
                    "bid": day.get("bid"),
                    "ask": day.get("ask"),
                    "last": day.get("close"),
                    "volume": day.get("volume", 0),
                    "open_interest": contract.get("open_interest", 0),
                    "iv": greeks.get("implied_volatility"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                })
                stored += 1
            
            await session.commit()
            return stored
    
    async def _create_daily_summary(
        self,
        symbol: str,
        target_date: date,
        contracts: list[dict]
    ):
        """Aggregate contracts into daily summary."""
        
        # Convert to DataFrame for easier aggregation
        df = pd.DataFrame([
            {
                "type": c.get("details", {}).get("contract_type", "")[0].upper(),
                "strike": c.get("details", {}).get("strike_price"),
                "expiration": c.get("details", {}).get("expiration_date"),
                "oi": c.get("open_interest", 0),
                "volume": c.get("day", {}).get("volume", 0),
                "iv": c.get("greeks", {}).get("implied_volatility"),
                "gamma": c.get("greeks", {}).get("gamma"),
                "delta": c.get("greeks", {}).get("delta"),
            }
            for c in contracts
        ])
        
        if df.empty:
            return
        
        # Separate calls and puts
        calls = df[df['type'] == 'C']
        puts = df[df['type'] == 'P']
        
        # Aggregate metrics
        summary = {
            "total_call_oi": int(calls['oi'].sum()) if not calls.empty else 0,
            "total_put_oi": int(puts['oi'].sum()) if not puts.empty else 0,
            "total_call_volume": int(calls['volume'].sum()) if not calls.empty else 0,
            "total_put_volume": int(puts['volume'].sum()) if not puts.empty else 0,
            "weighted_avg_iv": self._weighted_avg(df, 'iv', 'oi'),
            "total_call_gamma": calls['gamma'].sum() if not calls.empty else 0,
            "total_put_gamma": puts['gamma'].sum() if not puts.empty else 0,
            "total_call_delta": calls['delta'].sum() if not calls.empty else 0,
            "total_put_delta": puts['delta'].sum() if not puts.empty else 0,
            "contracts_analyzed": len(df),
            "expirations_count": df['expiration'].nunique(),
        }
        
        # Top strikes by OI
        call_top = calls.nlargest(3, 'oi')[['strike', 'oi']].values.tolist()
        put_top = puts.nlargest(3, 'oi')[['strike', 'oi']].values.tolist()
        
        for i, (strike, oi) in enumerate(call_top, 1):
            summary[f"top_call_strike_{i}"] = strike
            summary[f"top_call_oi_{i}"] = int(oi)
        
        for i, (strike, oi) in enumerate(put_top, 1):
            summary[f"top_put_strike_{i}"] = strike
            summary[f"top_put_oi_{i}"] = int(oi)
        
        # Nearest expiry
        if not df['expiration'].isna().all():
            summary["nearest_expiry"] = df['expiration'].min()
        
        # Store summary
        async with get_async_session() as session:
            await session.execute(text("""
                INSERT INTO options_daily_summary (
                    time, symbol,
                    total_call_oi, total_put_oi,
                    total_call_volume, total_put_volume,
                    weighted_avg_iv,
                    top_call_strike_1, top_call_oi_1,
                    top_call_strike_2, top_call_oi_2,
                    top_call_strike_3, top_call_oi_3,
                    top_put_strike_1, top_put_oi_1,
                    top_put_strike_2, top_put_oi_2,
                    top_put_strike_3, top_put_oi_3,
                    total_call_gamma, total_put_gamma,
                    total_call_delta, total_put_delta,
                    nearest_expiry, expirations_count, contracts_analyzed
                ) VALUES (
                    :time, :symbol,
                    :total_call_oi, :total_put_oi,
                    :total_call_volume, :total_put_volume,
                    :weighted_avg_iv,
                    :top_call_strike_1, :top_call_oi_1,
                    :top_call_strike_2, :top_call_oi_2,
                    :top_call_strike_3, :top_call_oi_3,
                    :top_put_strike_1, :top_put_oi_1,
                    :top_put_strike_2, :top_put_oi_2,
                    :top_put_strike_3, :top_put_oi_3,
                    :total_call_gamma, :total_put_gamma,
                    :total_call_delta, :total_put_delta,
                    :nearest_expiry, :expirations_count, :contracts_analyzed
                )
                ON CONFLICT (time, symbol) DO UPDATE SET
                    total_call_oi = EXCLUDED.total_call_oi,
                    total_put_oi = EXCLUDED.total_put_oi,
                    weighted_avg_iv = EXCLUDED.weighted_avg_iv
            """), {"time": target_date, "symbol": symbol, **summary})
            
            await session.commit()
    
    def _weighted_avg(self, df: pd.DataFrame, value_col: str, weight_col: str) -> float:
        """Calculate weighted average, handling nulls."""
        valid = df[[value_col, weight_col]].dropna()
        if valid.empty or valid[weight_col].sum() == 0:
            return None
        return (valid[value_col] * valid[weight_col]).sum() / valid[weight_col].sum()
    
    async def _get_watchlist_symbols(self) -> list[str]:
        """Get symbols from watchlist that have options enabled."""
        async with get_async_session() as session:
            result = await session.execute(text("""
                SELECT DISTINCT t.symbol
                FROM tickers t
                JOIN portfolio_tickers pt ON t.id = pt.ticker_id
                WHERE t.is_active = true
                  AND t.options_enabled = true
            """))
            return [row[0] for row in result.fetchall()]
```

### Tasks

| Task | Description | Est. Hours |
|------|-------------|------------|
| 2.2.1 | Create OptionsChainLoader class | 1 |
| 2.2.2 | Implement Polygon API client with pagination | 2 |
| 2.2.3 | Implement contract storage | 1 |
| 2.2.4 | Implement summary aggregation | 2 |
| 2.2.5 | Add rate limiting and concurrency control | 1 |
| 2.2.6 | Unit tests | 1 |

### Acceptance Criteria
- [ ] 100 symbols processed in < 5 minutes
- [ ] Individual contracts stored in options_chains
- [ ] Summary aggregated to options_daily_summary
- [ ] Top 3 call/put walls identified correctly

---

## Story 2.3: Technical Indicators Integration (4 pts) - NEW

### Overview
Integrate Polygon MCP tools for technical indicators, dealer metrics, volatility metrics, and price metrics.

### File: core/pipeline/metrics_calculator.py

```python
"""
Metrics Calculator

Calls Polygon MCP server tools to calculate all metrics for watchlist tickers.
Maps MCP responses to daily_snapshots columns.
"""

import httpx
from typing import Optional
from datetime import date

from core.config import settings

class MetricsCalculator:
    """Calculate metrics using Polygon MCP server."""
    
    def __init__(self, mcp_base_url: str = "http://localhost:5001"):
        self.mcp_url = mcp_base_url
    
    async def calculate_all_metrics(self, symbol: str) -> dict:
        """
        Calculate all metrics for a symbol using MCP tools.
        
        Returns dict ready for daily_snapshots INSERT.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Parallel fetch all metrics
            ta_task = self._call_mcp(client, "get_all_ta_indicators", {"symbol": symbol})
            dealer_task = self._call_mcp(client, "get_dealer_metrics", {"symbol": symbol})
            vol_task = self._call_mcp(client, "get_volatility_metrics", {"symbol": symbol})
            price_task = self._call_mcp(client, "get_price_metrics", {"symbol": symbol})
            
            ta_result, dealer_result, vol_result, price_result = await asyncio.gather(
                ta_task, dealer_task, vol_task, price_task,
                return_exceptions=True
            )
        
        # Map to daily_snapshots columns
        return self._map_to_snapshot(
            ta_result if not isinstance(ta_result, Exception) else {},
            dealer_result if not isinstance(dealer_result, Exception) else {},
            vol_result if not isinstance(vol_result, Exception) else {},
            price_result if not isinstance(price_result, Exception) else {},
        )
    
    async def _call_mcp(self, client: httpx.AsyncClient, tool: str, params: dict) -> dict:
        """Call an MCP tool and return result."""
        # MCP uses JSON-RPC style
        response = await client.post(
            f"{self.mcp_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool, "arguments": params},
                "id": 1
            }
        )
        response.raise_for_status()
        return response.json().get("result", {})
    
    def _map_to_snapshot(
        self,
        ta: dict,
        dealer: dict,
        volatility: dict,
        price: dict
    ) -> dict:
        """Map MCP results to daily_snapshots columns."""
        
        momentum = ta.get("momentum", {})
        trend = ta.get("trend", {})
        vol_ta = ta.get("volatility", {})
        volume = ta.get("volume", {})
        
        return {
            # Technical - Momentum
            "rsi_14": momentum.get("rsi"),
            "macd_line": momentum.get("macd", {}).get("macd"),
            "macd_signal": momentum.get("macd", {}).get("macd_signal"),
            "macd_histogram": momentum.get("macd", {}).get("macd_histogram"),
            "stoch_k": momentum.get("stochastic", {}).get("stoch_k"),
            "stoch_d": momentum.get("stochastic", {}).get("stoch_d"),
            "mfi_14": momentum.get("mfi"),
            
            # Technical - Trend
            "sma_20": trend.get("sma_20"),
            "sma_50": trend.get("sma_50"),
            "sma_200": trend.get("sma_200"),
            "ema_12": trend.get("ema_12"),
            "ema_26": trend.get("ema_26"),
            "adx_14": trend.get("adx"),
            
            # Technical - Volatility
            "atr_14": vol_ta.get("atr"),
            "bbands_upper": vol_ta.get("bollinger", {}).get("upper"),
            "bbands_middle": vol_ta.get("bollinger", {}).get("middle"),
            "bbands_lower": vol_ta.get("bollinger", {}).get("lower"),
            
            # Technical - Volume
            "obv": volume.get("obv"),
            "vwap": volume.get("vwap"),
            
            # Dealer Metrics
            "gex_total": dealer.get("gamma_exposure"),
            "gex_net": dealer.get("net_gex"),
            "gamma_flip_level": dealer.get("gamma_flip"),
            "call_wall_primary": dealer.get("call_walls", [{}])[0].get("strike"),
            "call_wall_primary_oi": dealer.get("call_walls", [{}])[0].get("oi"),
            "put_wall_primary": dealer.get("put_walls", [{}])[0].get("strike"),
            "put_wall_primary_oi": dealer.get("put_walls", [{}])[0].get("oi"),
            "dgpi": dealer.get("dealer_gamma_pressure_index"),
            "dealer_position": dealer.get("position"),
            
            # Volatility Metrics
            "iv_skew_25d": volatility.get("iv_skew_25delta"),
            "iv_term_structure": volatility.get("iv_term_structure"),
            "put_call_ratio_oi": volatility.get("put_call_ratio"),
            "average_iv": volatility.get("average_iv"),
            
            # Price Metrics
            "rvol": price.get("relative_volume"),
            "vsi": price.get("volume_surge_index"),
            "hv_20": price.get("historical_volatility"),
            "iv_hv_diff": price.get("hv_iv_differential"),
            
            # Full JSONB for complete data
            "technical_indicators_json": ta,
            "dealer_metrics_json": dealer,
            "volatility_metrics_json": volatility,
            "price_metrics_json": price,
        }
```

### Tasks

| Task | Description | Est. Hours |
|------|-------------|------------|
| 2.3.1 | Create MetricsCalculator class | 1 |
| 2.3.2 | Implement MCP tool calling | 2 |
| 2.3.3 | Map MCP responses to snapshot columns | 2 |
| 2.3.4 | Unit tests with mocked MCP | 1 |

### Acceptance Criteria
- [ ] All 84 technical indicators fetched via MCP
- [ ] Dealer metrics mapped to extracted columns
- [ ] Volatility metrics mapped correctly
- [ ] Price metrics (RVOL, VSI, HV) populated

---

## Story 2.4: Wyckoff Engine Migration (6 pts) - UNCHANGED

Migrate existing kapman-wyckoff-module-v2 logic.

*[Keep existing spec from architecture doc]*

---

## Story 2.5: Daily Batch Orchestrator (4 pts) - REVISED

### File: core/pipeline/daily_job.py

```python
"""
Daily Batch Job Orchestrator

Runs the complete daily pipeline:
1. S3 OHLCV Load (full universe)
2. Options Enrichment (watchlist only)
3. Metrics Calculation (watchlist only)
4. Wyckoff Analysis (watchlist only)
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text

from core.db.client import get_async_session
from core.pipeline.s3_universe_loader import S3UniverseLoader
from core.pipeline.options_loader import OptionsChainLoader
from core.pipeline.metrics_calculator import MetricsCalculator
from core.wyckoff.analyzer import WyckoffAnalyzer

class DailyBatchJob:
    """Orchestrates the complete daily analysis pipeline."""
    
    def __init__(self):
        self.s3_loader = S3UniverseLoader()
        self.options_loader = OptionsChainLoader()
        self.metrics_calc = MetricsCalculator()
        self.wyckoff = WyckoffAnalyzer()
    
    async def run(self, target_date: Optional[date] = None) -> dict:
        """
        Execute complete daily pipeline.
        
        Args:
            target_date: Date to process (default: yesterday)
            
        Returns:
            dict with results from each phase
        """
        import time
        start_time = time.time()
        
        target_date = target_date or (date.today() - timedelta(days=1))
        job_id = await self._create_job_run(target_date)
        
        results = {
            "job_id": str(job_id),
            "date": str(target_date),
            "phases": {}
        }
        
        try:
            # Phase 1: S3 OHLCV (full universe)
            results["phases"]["ohlcv"] = await self.s3_loader.load_daily(target_date)
            
            # Phase 2: Options (watchlist only)
            results["phases"]["options"] = await self.options_loader.load_watchlist_options(
                target_date=target_date
            )
            
            # Phase 3 & 4: Metrics + Wyckoff (watchlist only)
            watchlist = await self._get_watchlist_symbols()
            results["phases"]["analysis"] = await self._analyze_watchlist(
                watchlist, target_date
            )
            
            # Update job status
            await self._complete_job_run(job_id, "SUCCESS", results)
            
        except Exception as e:
            await self._complete_job_run(job_id, "FAILED", {"error": str(e)})
            raise
        
        results["duration_seconds"] = round(time.time() - start_time, 2)
        return results
    
    async def _analyze_watchlist(
        self,
        symbols: list[str],
        target_date: date
    ) -> dict:
        """Run metrics + Wyckoff analysis for watchlist symbols."""
        
        results = {
            "symbols_processed": 0,
            "snapshots_created": 0,
            "errors": []
        }
        
        for symbol in symbols:
            try:
                # Get metrics from MCP
                metrics = await self.metrics_calc.calculate_all_metrics(symbol)
                
                # Run Wyckoff analysis
                wyckoff_result = await self.wyckoff.analyze(symbol)
                
                # Merge and store snapshot
                snapshot = {**metrics, **wyckoff_result}
                await self._store_snapshot(symbol, target_date, snapshot)
                
                results["symbols_processed"] += 1
                results["snapshots_created"] += 1
                
            except Exception as e:
                results["errors"].append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return results
    
    async def _store_snapshot(
        self,
        symbol: str,
        target_date: date,
        data: dict
    ):
        """Store complete snapshot to daily_snapshots."""
        
        # Build column list dynamically from data keys
        columns = [k for k in data.keys() if data[k] is not None]
        placeholders = [f":{k}" for k in columns]
        
        async with get_async_session() as session:
            await session.execute(text(f"""
                INSERT INTO daily_snapshots (time, symbol, {', '.join(columns)})
                VALUES (:time, :symbol, {', '.join(placeholders)})
                ON CONFLICT (time, symbol) DO UPDATE SET
                    {', '.join(f'{c} = EXCLUDED.{c}' for c in columns)}
            """), {"time": target_date, "symbol": symbol, **data})
            
            # Update ticker last_analysis_date
            await session.execute(text("""
                UPDATE tickers SET last_analysis_date = :date
                WHERE symbol = :symbol
            """), {"date": target_date, "symbol": symbol})
            
            await session.commit()
    
    async def _get_watchlist_symbols(self) -> list[str]:
        """Get all symbols in portfolios."""
        async with get_async_session() as session:
            result = await session.execute(text("""
                SELECT DISTINCT t.symbol
                FROM tickers t
                JOIN portfolio_tickers pt ON t.id = pt.ticker_id
                WHERE t.is_active = true
                ORDER BY t.symbol
            """))
            return [row[0] for row in result.fetchall()]
    
    async def _create_job_run(self, target_date: date) -> str:
        """Create job_runs record."""
        async with get_async_session() as session:
            result = await session.execute(text("""
                INSERT INTO job_runs (job_name, started_at)
                VALUES (:name, NOW())
                RETURNING id
            """), {"name": f"daily_batch_{target_date}"})
            await session.commit()
            return result.scalar()
    
    async def _complete_job_run(self, job_id: str, status: str, results: dict):
        """Update job_runs with completion status."""
        async with get_async_session() as session:
            await session.execute(text("""
                UPDATE job_runs SET
                    completed_at = NOW(),
                    status = :status,
                    tickers_processed = :tickers,
                    errors_json = :errors,
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))
                WHERE id = :id
            """), {
                "id": job_id,
                "status": status,
                "tickers": results.get("phases", {}).get("analysis", {}).get("symbols_processed", 0),
                "errors": results.get("phases", {}).get("analysis", {}).get("errors", [])
            })
            await session.commit()
```

### Acceptance Criteria
- [ ] Full pipeline completes in < 15 minutes for 100 tickers
- [ ] Job audit trail in job_runs table
- [ ] OHLCV loaded for full universe
- [ ] Analysis only for watchlist tickers
- [ ] All snapshot columns populated

---

## Sprint 2 Summary

| Metric | Target |
|--------|--------|
| **Total Story Points** | 28 |
| **Duration** | Dec 14-20 (7 days) |
| **Daily Velocity** | 4 pts/day |
| **Key Deliverables** | Full OHLCV pipeline, Options enrichment, Metrics integration, Wyckoff analysis |

### Dependencies for Sprint 3

Sprint 2 completion enables:
- Recommendation generation (has all metrics available)
- Strike selection (has real options data)
- Dashboard display (has daily_snapshots populated)
