# KapMan Portfolio Manager - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Data Model & Schema](#data-model--schema)
6. [External Dependencies](#external-dependencies)
7. [Current Wyckoff Analysis Implementation](#current-wyckoff-analysis-implementation)
8. [API Endpoints](#api-endpoints)
9. [Data Flow](#data-flow)
10. [Future: Two-Level Wyckoff Analysis](#future-two-level-wyckoff-analysis)

---

## System Overview

**Purpose**: Full-stack web application for tracking stock portfolios using Wyckoff analysis methodology combined with options trading strategies.

**Core Capabilities**:
- Create and manage multiple portfolios
- Track tickers across portfolios with real-time analysis
- Display comprehensive Wyckoff analysis dashboards
- Show technical indicators, dealer positioning, volatility metrics
- Generate AI-powered trade recommendations
- Run daily analysis jobs on all tracked securities

**Deployment**: Live production app at `kapman-portfolio-manager.replit.app`

---

## Technology Stack

### Frontend
- **Framework**: React 18 with TypeScript (ES modules)
- **Build Tool**: Vite with dev HMR support
- **UI Framework**: Shadcn/ui (New York style) + Radix UI primitives + Tailwind CSS v3
- **Routing**: Wouter (lightweight client-side routing)
- **State Management**: 
  - TanStack Query (React Query) for server state
  - React hooks for component-level state
  - No global state library
- **Charting**: React Plotly.js, Recharts (optional)
- **Forms**: React Hook Form + Zod validation

### Backend
- **Runtime**: Node.js with TypeScript (ES modules)
- **Server**: Express.js REST API
- **Database**: PostgreSQL via Neon (serverless)
- **ORM**: Drizzle ORM (type-safe)
- **Validation**: Zod + Drizzle schemas
- **Authentication**: Session-based (express-session, connect-pg-simple)

### Database
- **Provider**: Neon PostgreSQL (serverless)
- **Connection**: Via @neondatabase/serverless driver
- **Schema Management**: Drizzle with SQL migrations
- **Tables**: portfolios, tickers, portfolio_tickers, daily_snapshots, forecast_evaluations

---

## Frontend Architecture

### Directory Structure
```
client/
├── src/
│   ├── pages/                    # Route pages
│   │   ├── Home.tsx              # Dashboard - portfolio list
│   │   ├── PortfolioDetail.tsx   # Portfolio with tickers
│   │   ├── TickerDetail.tsx      # Main analysis page (6 tabs)
│   │   └── AllTickers.tsx        # All tracked tickers
│   ├── components/               # UI components
│   │   ├── Layout.tsx            # Main layout wrapper
│   │   ├── TickerTable.tsx       # Portfolio ticker table
│   │   ├── TradesSuggestionsPanel.tsx  # AI trade suggestions (default tab)
│   │   ├── WyckoffChecklistPanel.tsx   # 9-step checklist
│   │   ├── TechnicalMetricsPanel.tsx   # RSI, MACD, Bollinger, ATR, Stochastic, EMA, SMA
│   │   ├── DealerMetricsPanel.tsx      # GEX, Gamma Flip, Put/Call walls
│   │   ├── TradingViewHoverChart.tsx   # Chart component
│   │   └── ui/                   # Shadcn UI primitives
│   ├── lib/
│   │   ├── api.ts                # Type-safe API client
│   │   └── mockData.ts           # TypeScript interfaces
│   ├── hooks/
│   │   └── use-toast.ts          # Toast notifications
│   ├── App.tsx                   # Route definitions
│   ├── index.css                 # Tailwind + global styles
│   └── main.tsx                  # Entry point
└── index.html                    # HTML with meta tags (OG, Twitter)
```

### Key Components

#### TickerDetail.tsx (Main Analysis Page)
- **6 Tabs**:
  1. **Trades** (DEFAULT) - KapMan AI trade suggestions with categorization
  2. **Checklist** - Wyckoff 9-step progression
  3. **Technical** - RSI, MACD, Bollinger Bands, ATR, Stochastic, EMA, SMA
  4. **Dealer** - GEX, Gamma Flip, Put/Call wall strikes
  5. **AI** - On-demand (gpt-4.1) + Nightly batch (gpt-4.1-mini) analysis
  6. **History** - 30-day Wyckoff phase progression

- **Data Sources**:
  - `latestSnapshot` from ticker data + embedded snapshot
  - Real-time dealer metrics from Schwab API
  - Technical indicators from Polygon API
  - Wyckoff analysis from external module

#### TradesSuggestionsPanel.tsx
- Displays KapMan AI trade recommendations
- **Categories**:
  - Primary trade (best risk/reward)
  - Swing opportunities (30-90 DTE)
  - LEAPS opportunities (10-14 months)
- Shows Wyckoff phase context + current price

#### DealerMetricsPanel.tsx
- **Prominent Gamma Flip Display** (top of card)
  - Status: DETECTED (amber) or STABLE (blue)
  - Shows strike price when detected
  - Visual indication of reversal risk
- Metrics grid: Total GEX, Net GEX, Put/Call walls, IV Skew, Term Structure, OI Ratio

#### WyckoffChecklistPanel.tsx
- Displays all 9 Wyckoff steps with real data from API
- Each step shows: pass/fail status, confidence score, description
- Progress tracking: `total_passed / 9`

#### TechnicalMetricsPanel.tsx
- All 7 technical indicators from Polygon API:
  - RSI(14) with color-coded zones
  - MACD with histogram
  - Bollinger Bands with bandwidth & %B
  - Stochastic with %K, %D, %H
  - ATR(14) absolute and % of price
  - EMA(20) and SMA(50)
- Real-time updates with data timestamps

### Routing (Wouter)
```typescript
// App.tsx route definitions
/                          → Home (portfolios dashboard)
/portfolio/:id             → PortfolioDetail (tickers in portfolio)
/ticker/:symbol            → TickerDetail (main analysis)
/tickers                   → AllTickers (all tracked)
```

### API Layer (`lib/api.ts`)
Type-safe fetch wrapper with error handling:
- `getPortfolios()` - Fetch all user portfolios
- `getTicker(symbol)` - Fetch ticker with latest snapshot + forecast
- `getSnapshots(symbol)` - Fetch 30-day history
- `generateAiForecast(symbol)` - On-demand analysis (gpt-4.1)
- `runDailyJob()` - Trigger analysis job

**Error Handling**: 
- 60-second timeout on AI forecast requests
- AbortController for request cancellation
- Defensive rendering for unexpected response formats
- Error messages displayed instead of blank screens

---

## Backend Architecture

### Directory Structure
```
server/
├── index-dev.ts              # Dev entry (with Vite middleware HMR)
├── index-prod.ts             # Prod entry (static file serving)
├── routes.ts                 # Express route handlers
├── storage.ts                # Database abstraction layer (IStorage interface)
├── services/
│   ├── wyckoff.ts            # Wyckoff API integration
│   ├── kapmanAiService.ts    # KapMan AI + OpenAI integration
│   ├── polygon.ts            # Polygon.io API wrapper
│   ├── schwab.ts             # Schwab options API wrapper
│   ├── openai.ts             # OpenAI API client (deprecated)
│   ├── registry.ts           # Registry config loader
│   └── dailyJob.ts           # Scheduled analysis job
└── middleware/
    └── logging.ts            # Request/response logging
```

### IStorage Interface (Repository Pattern)
**Location**: `server/storage.ts`

Abstracts all data access operations:
- Portfolio CRUD: `createPortfolio()`, `getPortfolio()`, `updatePortfolio()`, `deletePortfolio()`, `getAllPortfolios()`
- Ticker CRUD: `createTicker()`, `getTickerBySymbol()`, `getAllTickers()`, `addTickerToPortfolio()`, `removeTickerFromPortfolio()`
- Snapshots: `createSnapshot()`, `getLatestSnapshotByTicker()`, `getSnapshotsByTicker()`, `getSnapshotsByDate()`

**Implementation**: Uses Drizzle ORM queries directly against PostgreSQL

### Express Routes (`server/routes.ts`)

**Portfolio Endpoints**:
```
GET    /api/portfolios                      → List all portfolios
GET    /api/portfolios/:id                  → Get portfolio detail
POST   /api/portfolios                      → Create portfolio
PATCH  /api/portfolios/:id                  → Update portfolio
DELETE /api/portfolios/:id                  → Delete portfolio
```

**Ticker Endpoints**:
```
GET    /api/tickers                         → Get all tickers (with latest snapshot)
GET    /api/tickers/:symbol                 → Get ticker detail
GET    /api/tickers/:symbol/snapshots       → Get 30-day history
POST   /api/portfolios/:id/tickers          → Add tickers to portfolio
DELETE /api/portfolios/:id/tickers/:tickerId → Remove from portfolio
```

**Analysis Endpoints**:
```
POST   /api/ai/forecast/:symbol             → On-demand AI forecast (gpt-4.1)
POST   /api/jobs/daily                      → Trigger daily job
GET    /api/jobs/daily/status               → Get job status/progress
POST   /api/registry                        → Load registry config
```

### Service Layer

#### WyckoffService (`wyckoff.ts`)
- **External API**: `https://kapman-wyckoff-analysis-module-v2.replit.app`
- **Auth**: Bearer token via `KAPMAN_AUTHENTICATION_TOKEN`
- **Methods**:
  - `analyzeSymbol(symbol)` - Single symbol analysis
  - `analyzeBatch(symbols)` - Batch analysis (all tickers)
  - `parseAnalysis()` - Parse raw API response to unified format
- **Timeout**: 60 seconds for complex analysis
- **Returns**: `ParsedAnalysis` with phase, subState, confidence, details (including wyckoff_checklist)

**Response Structure**:
```typescript
{
  phase: "Accumulation" | "Markup" | "Distribution" | "Markdown" | "Re-Accumulation"
  subState: string                           // Phase A - Spr, Phase B - Build, etc.
  confidence: number                         // 0-1
  details: {
    phaseScore, compositeScore, volatilityRegime, macdSignal, trendStrength,
    dataQuality, volatilityAdjusted, metrics, checklist, checklistPassed, checklistAvgScore
  }
}
```

#### PolygonService (`polygon.ts`)
- **External API**: Via KapMan wrapper at `https://kapman-polygon-apix-wrapper.replit.app`
- **Auth**: Via `KAPMAN_POLYGON_TOKEN`
- **Methods**:
  - `getQuote(symbol)` - Current price, volume, change%
  - `getTechnicalIndicators(symbol)` - All 7 indicators (RSI, MACD, EMA, SMA, Bollinger Bands, Stochastic, ATR)
  - `getOHLCV(symbol)` - OHLCV data
- **Timeout**: 30 seconds
- **Returns**: Real market data with timestamps

**Technical Indicators** (7 total):
```typescript
{
  rsi: { value: number, timestamp: string }
  macd: { value, signal, histogram, timestamp }
  ema_20: { value, timestamp }
  sma_50: { value, timestamp }
  bollinger_bands: { upper, middle, lower, bandwidth, percent_b, timestamp }
  stochastic: { k, d, h, timestamp }
  atr_14: { value, pct_of_price, timestamp }
}
```

#### SchwabService (`schwab.ts`)
- **External API**: Via KapMan wrapper at `https://kapman-schwab-api-wrapper.replit.app`
- **Auth**: Via `KAPMAN_SCHWAB_TOKEN`
- **Methods**:
  - `getOptionsChain(symbol)` - Call/put expirations + strikes
  - `getDealerMetrics(symbol)` - GEX, Gamma Flip, Put/Call walls
  - `getVolatilityMetrics(symbol)` - IV Skew, Term Structure, OI Ratio
- **Timeout**: 30 seconds
- **Non-blocking**: Failures don't block main job

**Dealer Metrics** (normalized by backend):
```typescript
{
  gex_total: number              // Gamma exposure (billions)
  gex_net: number                // Net gamma
  gamma_flip: number | null      // Strike price where dealers flip from long to short gamma
  put_wall: number               // Put wall open interest
  call_wall: number              // Call wall open interest
  put_wall_strikes?: number[]    // Real strike prices
  call_wall_strikes?: number[]   // Real strike prices
  put_call_ratio: number
}
```

**Volatility Metrics** (normalized):
```typescript
{
  IV_Skew: number                // Put vs call IV difference
  IV_Term_Structure: number      // Curve slope
  OI_Ratio: number               // Put/call open interest
}
```

#### KapManAiService (`kapmanAiService.ts`)
- **Models**: 
  - `gpt-4.1` for on-demand analysis (highest quality)
  - `gpt-4.1-mini` for daily batch jobs (cost-optimized)
- **Methods**:
  - `generateOnDemandForecast()` - Real-time analysis with gpt-4.1
  - `generateDailyBatchForecast()` - Nightly batch with gpt-4.1-mini
- **Policy**:
  - KapMan Wyckoff methodology
  - Options-first approach (but flexible)
  - Risk/reward assessment
  - Strike price validation (real data only, no hallucination)
  - Expiry date validation (uses real option expirations)

**Forecast Output**:
```typescript
{
  engineVersion: "KapMan AI v1.0"
  asOfDate: string               // ISO date
  symbol: string
  wyckoffPhase: string
  wyckoffSubState?: string
  primaryIntent: "enter"|"add"|"hold"|"trim"|"exit"|"hedge"
  riskLevel: "Low"|"Medium"|"High"
  confidence: number             // 0-1
  thesis: string                 // Market analysis summary
  keyFactors: string[]           // Key reasoning
  trades: [                      // Up to 3 trade recommendations
    {
      type: string
      direction: "bullish"|"bearish"|"neutral"
      strategy: "long_call"|"call_spread"|"cash_secured_put"|"put_spread"|"stock"|"covered_call"
      strike?: number            // REAL strike from options chain
      expiry?: string            // REAL expiration date
      size?: number
      notes?: string[]
    }
  ]
}
```

#### DailyJobService (`dailyJob.ts`)
- **Trigger**: Manual via `/api/jobs/daily` or scheduled
- **Timeout**: 30 seconds per ticker (with fallbacks)
- **Process**:
  1. Load registry configs (thresholds, rules)
  2. For each ticker:
     - Fetch Wyckoff analysis (30s timeout)
     - Fetch Polygon technical indicators (non-blocking, 30s timeout)
     - Fetch Schwab dealer metrics (non-blocking, 30s timeout)
     - Generate KapMan AI forecast (gpt-4.1-mini batch model)
     - Store comprehensive snapshot
  3. Return: Success count + error details

**Key Features**:
- Non-blocking optional data: Polygon + Schwab failures don't block main analysis
- Graceful degradation: Falls back to Wyckoff-based recommendations if AI unavailable
- Real data enforcement: All strikes/expirations validated against live market data
- Progress tracking: Real-time job status available via `/api/jobs/daily/status`

---

## Data Model & Schema

### Portfolios Table
```sql
portfolios (
  id: SERIAL PRIMARY KEY,
  name: TEXT NOT NULL,
  description: TEXT,
  created_at: TIMESTAMP DEFAULT NOW(),
  updated_at: TIMESTAMP DEFAULT NOW()
)
```

### Tickers Table
```sql
tickers (
  id: SERIAL PRIMARY KEY,
  symbol: VARCHAR(10) NOT NULL UNIQUE,
  name: TEXT,
  notes: TEXT,
  created_at: TIMESTAMP DEFAULT NOW(),
  INDEX symbol_idx ON (symbol)
)
```

### Portfolio-Ticker Relationship
```sql
portfolio_tickers (
  id: SERIAL PRIMARY KEY,
  portfolio_id: INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  ticker_id: INTEGER NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
  active: BOOLEAN DEFAULT true NOT NULL,
  added_at: TIMESTAMP DEFAULT NOW(),
  UNIQUE(portfolio_id, ticker_id),
  INDEX portfolio_idx ON (portfolio_id),
  INDEX ticker_idx ON (ticker_id)
)
```

### Daily Snapshots Table (Core Analysis Data)
```sql
daily_snapshots (
  id: SERIAL PRIMARY KEY,
  date: DATE NOT NULL,
  ticker_id: INTEGER NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
  
  -- Wyckoff Phase (Level 1)
  wyckoff_phase: VARCHAR(50),
  wyckoff_sub_state: TEXT,
  
  -- Market Data
  price: DECIMAL(10,2),
  change_percent: DECIMAL(6,2),
  volume: INTEGER,
  
  -- JSON Storage (Complex Data)
  key_metrics_json: JSONB,              -- RSI, HV, IV, etc.
  options_summary_json: JSONB,          -- IV rank, skew, etc.
  openai_forecast_json: JSONB,          -- AI recommendations (legacy)
  ohlcv_json: JSONB,                    -- OHLCV from Polygon
  technical_indicators_json: JSONB,     -- All 7 indicators: RSI, MACD, Bollinger, etc.
  wyckoff_metrics_json: JSONB,          -- Relative Volume, Volume Surge, HV-IV Diff
  dealer_metrics_json: JSONB,           -- GEX, Gamma Flip, Put/Call walls (from Schwab)
  volatility_metrics_json: JSONB,       -- IV Skew, Term Structure, OI Ratio
  quotes_json: JSONB,                   -- Real-time quotes
  
  created_at: TIMESTAMP DEFAULT NOW(),
  refreshed_at: TIMESTAMP,              -- When last updated with real data
  
  INDEX date_ticker_idx ON (date, ticker_id),
  INDEX ticker_date_idx ON (ticker_id, date)
)
```

### Forecast Evaluations Table (Future Capability)
```sql
forecast_evaluations (
  id: SERIAL PRIMARY KEY,
  snapshot_id: INTEGER NOT NULL REFERENCES daily_snapshots(id) ON DELETE CASCADE,
  realized_pnl: DECIMAL(10,2),
  realized_outcome_label: VARCHAR(50),
  notes: TEXT,
  created_at: TIMESTAMP DEFAULT NOW()
)
```

### Zod Schema Integration
All tables have corresponding Zod schemas:
- `insertPortfolioSchema` / `PortfolioSelectSchema`
- `insertTickerSchema` / `TickerSelectSchema`
- `insertDailySnapshotSchema` / `DailySnapshotSelectSchema`

Runtime validation on all API requests + responses.

---

## External Dependencies

### 1. Wyckoff Analysis Module
- **URL**: `https://kapman-wyckoff-analysis-module-v2.replit.app`
- **Authentication**: Bearer token (`KAPMAN_AUTHENTICATION_TOKEN`)
- **Endpoint**: `POST /analyze`
- **Input**: `{ symbols: string[] }`
- **Output**: Complete Wyckoff analysis with 9-step checklist
- **Timeout**: 60 seconds
- **Status**: ✅ Operational

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "wyckoff_phase": "B",              // A=Accumulation, B=Markup, C=Distribution, etc.
  "phase_description": "Phase B - Build",
  "phase_score": 0.85,
  "phase_confidence": 0.78,
  "volatility_regime": "elevated",
  "macd_signal": "bullish",
  "trend_strength": 0.72,
  "composite_score": 0.80,
  "data_quality": "high",
  "volatility_adjusted": true,
  "metrics": {...},
  "wyckoff_checklist": {
    "step_1_defined_support": { "passed": true, "score": 0.9, "description": "..." },
    ...
    "step_9_risk_reward": { "passed": true, "score": 0.85, "description": "..." },
    "summary": { "total_passed": 8, "average_score": 0.82 }
  }
}
```

### 2. Polygon.io API
- **URL**: Via KapMan wrapper at `https://kapman-polygon-apix-wrapper.replit.app`
- **Authentication**: Token (`KAPMAN_POLYGON_TOKEN`)
- **Endpoints Used**:
  - Quote data (price, volume, change%)
  - 7 Technical indicators (RSI, MACD, EMA, SMA, Bollinger Bands, Stochastic, ATR)
  - OHLCV data
- **Timeout**: 30 seconds
- **Batch Limit**: `limit=100` for batch requests (1-2 second response time)
- **Status**: ✅ Operational - All 7 indicators actively collected

### 3. Schwab Options API
- **URL**: Via KapMan wrapper at `https://kapman-schwab-api-wrapper.replit.app`
- **Authentication**: Token (`KAPMAN_SCHWAB_TOKEN`)
- **Data Provided**:
  - Options chain (calls/puts by expiration)
  - Dealer positioning (GEX, Gamma Flip)
  - Put/Call walls with strike prices
  - Volatility metrics (IV Skew, Term Structure, OI Ratio)
- **Timeout**: 30 seconds
- **Non-blocking**: Failures don't halt job
- **Status**: ✅ Operational - Real GEX, Gamma Flip, Put/Call walls with strike prices

### 4. KapMan AI (KapMan Registry)
- **Internal Integration**: Managed via registry configs
- **Models**:
  - Batch (daily jobs): `gpt-4.1-mini`
  - On-demand: `gpt-4.1`
- **Fallback**: Wyckoff-based recommendations if AI unavailable
- **Policy**: KapMan Wyckoff methodology + options-first + risk management
- **Status**: ✅ Operational

### 5. OpenAI API (Deprecated)
- **Status**: ❌ Deprecated in favor of KapMan AI
- **Usage**: Backup only (not called in current flow)

---

## Current Wyckoff Analysis Implementation

### Single-Level Implementation
The current system uses a **single level** of Wyckoff analysis:

```
Level 1: Main Phase Classification
├── Phase (5 main categories)
│   ├── Accumulation (Phase A)
│   ├── Markup (Phase B)
│   ├── Distribution (Phase C)
│   ├── Markdown (Phase D)
│   └── Re-Accumulation (Phase E)
├── Sub-State (detailed progression)
│   ├── Phase A - Spr (Spring)
│   ├── Phase B - Build
│   ├── Phase C - Spring
│   ├── Phase D - LPS (Last Point of Supply)
│   └── Phase E - Climax
├── 9-Step Checklist (confirmation steps)
│   ├── Step 1: Defined Support
│   ├── Step 2: Climax Volume
│   ├── Step 3: Rally Volume
│   ├── Step 4: Pullback (low volume)
│   ├── Step 5: Higher Lows
│   ├── Step 6: Downtrend Break
│   ├── Step 7: Relative Strength
│   ├── Step 8: Horizontal Base
│   └── Step 9: Risk/Reward Setup
├── Confidence Score (0-1)
└── Supporting Metrics
    ├── Phase Score (0-1)
    ├── Trend Strength (0-1)
    ├── MACD Signal
    ├── Volatility Regime
    └── Data Quality Flag
```

### Data Storage
All Wyckoff data stored in `daily_snapshots.key_metrics_json`:
```typescript
{
  confidence: 0.78,              // Phase confidence
  checklist: {
    step_1_defined_support: { passed: true, score: 0.9, description: "..." },
    step_2_climax_volume: { passed: true, score: 0.85, ... },
    // ... all 9 steps
    summary: { total_passed: 8, average_score: 0.82 }
  },
  phaseScore: 0.85,
  compositeScore: 0.80,
  volatilityRegime: "elevated",
  macdSignal: "bullish",
  trendStrength: 0.72,
  dataQuality: "high",
  volatilityAdjusted: true,
  metrics: {...}
}
```

### Display
- **TickerDetail Tabs**:
  - Checklist tab: Shows all 9 steps with passed/failed + scores
  - Technical tab: Shows supporting metrics (RSI, MACD, Bollinger Bands, etc.)
  - Dealer tab: Shows dealer positioning (GEX, Gamma Flip, Put/Call walls)

---

## API Endpoints

### Portfolio Management
```
GET    /api/portfolios
       Response: Portfolio[]

GET    /api/portfolios/:id
       Response: Portfolio (with portfolioTickers array)

POST   /api/portfolios
       Body: { name: string, description: string }
       Response: Portfolio

PATCH  /api/portfolios/:id
       Body: Partial<Portfolio>
       Response: Portfolio

DELETE /api/portfolios/:id
       Response: { success: boolean }
```

### Ticker Management
```
GET    /api/tickers
       Response: Ticker[] (with latest snapshot + forecast embedded)
       Each ticker includes: { ...ticker, snapshot: { ...data }, forecast: {...} }

GET    /api/tickers/:symbol
       Response: Ticker (with latest snapshot + forecast)

GET    /api/tickers/:symbol/snapshots?limit=30
       Response: DailySnapshot[]

POST   /api/portfolios/:id/tickers
       Body: { symbols: string[] }
       Response: { success: boolean, added: number }

DELETE /api/portfolios/:id/tickers/:tickerId
       Response: { success: boolean }
```

### Analysis & Jobs
```
POST   /api/ai/forecast/:symbol
       Description: On-demand KapMan AI forecast (gpt-4.1)
       Response: {
         symbol: string,
         wyckoff: ParsedAnalysis,
         market: { price, volume, changePercent },
         optionsChain?: {...},
         forecast: KapmanForecast
       }
       Timeout: 60 seconds

POST   /api/jobs/daily
       Description: Trigger daily job on all tickers
       Response: { success: boolean, tickersProcessed: number, ... }

GET    /api/jobs/daily/status
       Description: Get real-time job progress
       Response: { running: boolean, progress: number, ... }

GET    /api/registry
       Description: Get KapMan registry configs
       Response: RegistryConfig
```

### Expected Response Codes
- **200**: Success
- **304**: Not Modified (caching)
- **400**: Bad Request
- **404**: Not Found
- **500**: Server Error

### Error Responses
```json
{
  "error": "Human-readable error message"
}
```

---

## Data Flow

### Daily Analysis Job Flow
```
1. Scheduler triggers /api/jobs/daily
2. For each ticker (parallel processing):
   a. Fetch Wyckoff analysis
      → wyckoffService.analyzeBatch([symbol])
      → Returns: phase, subState, confidence, checklist, composite_score
   
   b. Fetch Polygon technical indicators (non-blocking)
      → polygonService.getTechnicalIndicators(symbol)
      → Returns: RSI, MACD, Bollinger, Stochastic, ATR, EMA, SMA
   
   c. Fetch Schwab dealer metrics (non-blocking)
      → schwabService.getDealerMetrics(symbol)
      → Returns: GEX, Gamma Flip, Put/Call walls with strikes
   
   d. Generate KapMan AI forecast (gpt-4.1-mini)
      → kapmanAiService.generateDailyBatchForecast({symbol, wyckoff, price, optionsChain})
      → Returns: KapmanForecast with trades, thesis, confidence
   
   e. Create snapshot with all data
      → storage.createSnapshot({
          date, ticker_id, price, volume,
          key_metrics_json: {wyckoff data},
          technical_indicators_json: {7 indicators},
          dealer_metrics_json: {GEX, walls},
          openai_forecast_json: {forecast mapped to legacy format}
        })

3. Store comprehensive daily_snapshot with all metrics
4. Return results: { success: true, tickersProcessed: 32, ... }
```

### On-Demand AI Forecast Flow
```
1. User clicks "Generate Forecast" on AI tab
2. Frontend calls POST /api/ai/forecast/:symbol

3. Backend:
   a. Fetch real market data
      → polygonService.getQuote(symbol)
   
   b. Fetch current Wyckoff analysis
      → wyckoffService.analyzeSymbol(symbol)
   
   c. Fetch options chain (non-blocking)
      → schwabService.getOptionsChain(symbol)
   
   d. Generate on-demand forecast (gpt-4.1)
      → kapmanAiService.generateOnDemandForecast({symbol, wyckoff, price, optionsChain})
   
   e. Return complete analysis with market context
      → {symbol, wyckoff, market, optionsChain, forecast}

4. Frontend displays analysis with:
   - Trade recommendations
   - Key factors
   - Wyckoff phase context
   - Price + change%
```

### Frontend Data Display Flow
```
TickerDetail page loads
├── Fetch: getTicker(symbol)
│   ├── Backend queries: tickers + latest daily_snapshots + forecast
│   ├── Returns: Ticker with embedded snapshot + forecast
│   └── Frontend state: setTicker()
│
├── Extract data from snapshot:
│   ├── Wyckoff: latestSnapshot.keyMetricsJson.checklist
│   ├── Technical: latestSnapshot.technicalIndicatorsJson
│   ├── Dealer: latestSnapshot.dealerMetricsJson (normalized)
│   ├── Volatility: latestSnapshot.volatilityMetricsJson
│   └── Forecast: latestSnapshot.forecast
│
└── Render 6 tabs with real data:
    ├── Trades tab: From forecast._kapmanOriginal.trades
    ├── Checklist: From keyMetricsJson.checklist
    ├── Technical: From technicalIndicatorsJson
    ├── Dealer: From dealerMetricsJson + volatilityMetricsJson
    ├── AI: On-demand + batch forecast display
    └── History: Query /api/tickers/:symbol/snapshots for 30 days
```

---

## Future: Two-Level Wyckoff Analysis

### Architecture Vision

The refactoring will introduce **two complementary levels** of Wyckoff analysis:

#### Level 1: Primary Phase Classification (Current)
```
Main Wyckoff Phase
├── Accumulation | Markup | Distribution | Markdown | Re-Accumulation
├── 9-Step Checklist
├── Composite Score (0-1)
└── Trader Decision: "Is this asset in a favorable phase for entry?"
```

**Use Case**: Quick phase identification, portfolio screening

#### Level 2: Sub-Phase Granularity (New)
```
Deep Wyckoff Sub-State Analysis
├── Within each phase (A, B, C, D, E):
│   ├── Micro-patterns (springs, stops, climaxes)
│   ├── Volume structure progression
│   ├── Pattern success probability (0-1)
│   └── Next-step prediction
│
├── Detailed Stage Breakdown:
│   ├── Cause Formation (accumulation base quality)
│   ├── Effect Trajectory (breakout likelihood)
│   ├── Volatility Zones (resistance/support precision)
│   ├── Volume Profile (smart money absorption)
│   └── Time Progression (phase maturity)
│
└── Trader Decision: "Where exactly are we in this phase? What's next?"
```

**Use Case**: Entry/exit timing, risk optimization, trade structure refinement

### Implementation Changes Required

#### 1. External Module Updates (`KapMan-Wyckoff-Analysis-Module-v2`)
**New API endpoint** (Level 2 endpoint):
```
POST /analyze-detailed
Input: { symbols: string[], includeSubPhaseAnalysis: boolean = true }

Output: Enhanced analysis with Level 2 data:
{
  wyckoff_phase: "B",                    // Level 1: Main phase
  wyckoff_sub_state: "Phase B - Build",  // Level 1: Sub-state label
  
  // Level 2: New detailed breakdown
  phase_detailed: {
    phase_level: "B",
    micro_patterns: [
      { type: "spring", strength: 0.7, timestamp: "2025-11-28" },
      { type: "stop", strength: 0.85, timestamp: "2025-11-29" }
    ],
    volume_structure: {
      absorption_phase: "active",
      climax_proximity: 0.6,      // 0-1, how close to distribution climax
      next_signal: "expect_momentum_test"
    },
    pattern_success_probability: 0.82,    // This pattern succeeds X% of time
    estimated_phase_completion: 0.65,     // % through this phase (0-1)
    time_to_next_phase: { min: 5, max: 15, unit: "days" },
    volatility_zones: [
      { level: 145.50, type: "resistance", strength: 0.8 },
      { level: 142.75, type: "support", strength: 0.75 }
    ]
  },
  
  // Level 1: Keep existing data
  phase_score: 0.85,
  phase_confidence: 0.78,
  composite_score: 0.80,
  wyckoff_checklist: {...}
}
```

#### 2. Registry Configuration Updates (`KapMan-Registry`)
**New config sections**:
```yaml
wyckoff_analysis:
  level_1_enabled: true              # Always on
  level_2_enabled: true              # New feature toggle
  
  level_2_thresholds:
    phase_completion_warning: 0.70   # Alert when phase 70% complete
    pattern_success_threshold: 0.65  # Only signal patterns with >65% success rate
    volatility_zone_precision: 0.02  # Within 2% of predicted level
    
  display_preferences:
    show_micro_patterns: true
    show_volume_absorption: true
    show_phase_timing: true
    highlight_critical_zones: true
```

#### 3. Database Schema Updates
**Extend daily_snapshots**:
```sql
ALTER TABLE daily_snapshots ADD COLUMN wyckoff_level_2_json JSONB;
-- Stores: {
--   micro_patterns: [...],
--   volume_structure: {...},
--   pattern_success_probability: number,
--   estimated_phase_completion: number,
--   time_to_next_phase: {...},
--   volatility_zones: [...]
-- }
```

#### 4. Frontend New Components

**New Component: `WyckoffLevel2Panel.tsx`**
```typescript
// Display Level 2 sub-phase analysis
// Sections:
// - Micro-patterns (springs, stops, climaxes)
// - Volume absorption progress
// - Phase completion gauge (0-100%)
// - Time-to-next-phase estimate
// - Critical volatility zones
// - Pattern success probability score
```

**Updated: `TickerDetail.tsx` Tabs**
```
Existing 6 tabs → 7 tabs:
1. Trades (default)
2. Checklist (Level 1: 9-step)
3. Technical (indicators)
4. Dealer (GEX, walls)
5. AI (forecasts)
6. History (30-day)
7. [NEW] Advanced Wyckoff (Level 2 sub-phase detail)
```

**Updated: `WyckoffChecklistPanel.tsx`**
```
Add toggle: "Show Advanced Level 2"
├── Show: Micro-patterns timeline
├── Show: Volume absorption meter
├── Show: Phase completion progress
├── Show: Next phase prediction
└── Show: Critical zones (overlay on chart)
```

#### 5. Backend Service Updates

**Update `WyckoffService.ts`**:
```typescript
// Add new method for Level 2 analysis
async analyzeSymbolDetailed(symbol: string): Promise<ParsedAnalysisWithLevel2> {
  // Calls POST /analyze-detailed endpoint
  // Returns both Level 1 + Level 2 data
}

// Update batch analysis to support Level 2
async analyzeBatchDetailed(symbols: string[]): Promise<Map<string, ParsedAnalysisWithLevel2>>
```

**Update `DailyJobService.ts`**:
```typescript
// Enhance snapshot creation to include Level 2
async function createSnapshotWithLevel2(
  ticker: Ticker,
  analysisLevel1: ParsedAnalysis,
  analysisLevel2?: Level2Analysis
) {
  // Store both levels in daily_snapshot
  // level 1 → key_metrics_json
  // level 2 → wyckoff_level_2_json (new column)
}
```

#### 6. API Endpoint Updates
```
GET    /api/tickers/:symbol
       Response: Ticker with both Level 1 + Level 2 analysis

GET    /api/tickers/:symbol/snapshots
       Response: DailySnapshot[] with both levels

POST   /api/ai/forecast/:symbol
       Request can include: { includeLevel2: boolean = true }
       Response: Analysis context includes Level 2 for better AI reasoning
```

### Data Structure: Level 2 Complete Example
```typescript
interface WyckoffLevel2 {
  // Micro-patterns detected in current phase
  micro_patterns: {
    type: "spring" | "stop" | "climax" | "volume_spike" | "reversal";
    strength: number;           // 0-1: confidence in pattern
    timestamp: string;          // When detected
    description: string;        // Human-readable
  }[];
  
  // Volume absorption and structure
  volume_structure: {
    absorption_phase: "early" | "active" | "ending";
    climax_proximity: number;   // 0-1: proximity to distribution climax
    next_signal: string;        // e.g., "expect_momentum_test"
  };
  
  // Pattern success rates
  pattern_success_probability: number;  // 0-1: How often this pattern succeeds
  
  // Phase progression
  estimated_phase_completion: number;   // 0-1: % through current phase
  time_to_next_phase: {
    min: number;               // Earliest days until next phase
    max: number;               // Latest days until next phase
    unit: "days";
  };
  
  // Critical price levels
  volatility_zones: {
    level: number;             // Price level
    type: "support" | "resistance";
    strength: number;          // 0-1: How strong this level is
    description?: string;
  }[];
  
  // Trader context
  trader_action: string;       // e.g., "Enter near support, hold for breakout"
}
```

### UI/UX Changes
1. **TickerDetail page**: Add 7th tab "Advanced Wyckoff" for Level 2
2. **WyckoffChecklistPanel**: Add toggle for "Advanced Sub-Phase Analysis"
3. **TradingViewChart**: Overlay volatility zones + micro-pattern markers
4. **Dashboard card**: Show phase completion gauge
5. **Color coding**: Level 2 patterns use distinct visual hierarchy

### Testing & Validation
1. **Backward compatibility**: Level 1 always returns same data
2. **Frontend graceful degradation**: If Level 2 unavailable, use Level 1
3. **Registry toggle**: Can disable Level 2 via config if needed
4. **Performance**: Level 2 calls parallel with Level 1, non-blocking

---

## Extending for Specific Use Cases

### Adding Custom Indicators
1. Update `Polygon Service` to fetch new indicator
2. Store in `daily_snapshots.technical_indicators_json`
3. Create new panel component to display
4. Add to TickerDetail tabs

### Adding New Registry Thresholds
1. Add to `KapMan-Registry`
2. Update `DailyJobService` to apply thresholds
3. Store results in `daily_snapshots.key_metrics_json`
4. Display in relevant panel

### Adding New External Data Source
1. Create new service class (e.g., `MyDataService`)
2. Integrate in `DailyJobService` (parallel + non-blocking)
3. Store results in new JSONB field or reuse existing
4. Update API response types
5. Display in new frontend component

---

## Deployment & Configuration

### Environment Variables Required
```
DATABASE_URL=postgresql://...                    # Neon connection
PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE # DB credentials

KAPMAN_AUTHENTICATION_TOKEN=...                  # Wyckoff module auth
KAPMAN_POLYGON_TOKEN=...                         # Polygon API key
KAPMAN_SCHWAB_TOKEN=...                          # Schwab API key

OPENAI_API_KEY=...                               # OpenAI (deprecated)
```

### Build & Deployment
```bash
# Development
npm run dev          # Starts Vite + Express dev server

# Production
npm run build        # Builds React + TypeScript
npm run start        # Runs production server

# Database
npm run db:push      # Syncs schema with Neon
npm run db:studio    # Local Drizzle Studio
```

### Performance Considerations
- Daily job: ~5-10 seconds per ticker (with 4 parallel data fetches)
- Caching: Use ETag headers for 304 responses
- Database indexes: date_ticker_idx, ticker_date_idx on snapshots
- Connection pooling: Neon serverless handles pooling

---

## References & Documentation

- **Wyckoff Module**: https://replit.com/@kapmaninvestmen/KapMan-Wyckoff-Analysis-Module-v2
- **Polygon.io Docs**: https://polygon.io/docs
- **Schwab API**: Via KapMan wrapper
- **KapMan Registry**: Internal configuration system
- **Frontend Frameworks**: React 18, Tailwind CSS v3, Radix UI
- **Backend Framework**: Express.js, Drizzle ORM
- **Database**: PostgreSQL (Neon serverless)

---

## Notes for ChatGPT Prompts

When drafting prompts for ChatGPT regarding refactoring:

1. **Reference this architecture doc** to provide full system context
2. **Specify**: Which files to modify (e.g., `server/services/wyckoff.ts`, `client/src/components/TickerDetail.tsx`)
3. **Provide examples** of current data structures and expected new structures
4. **Highlight constraints**:
   - Backward compatibility required (Level 1 must remain unchanged)
   - Real data only (no hallucinated strikes/expirations)
   - Non-blocking optional data collection
   - 60-second timeouts on external API calls
5. **Test prompt**: Include sample ticker symbols (AAPL, NVDA, SPY, etc.)
6. **Validation**: Ensure Level 2 integrates without breaking Level 1 or frontend

---

**Document Version**: 1.0  
**Last Updated**: November 30, 2025  
**System Status**: Fully Operational  
**Frontend**: React 18, Tailwind CSS v3, 6 tabs on TickerDetail  
**Backend**: Node.js + Express, real data from 4 external APIs  
**Database**: PostgreSQL with comprehensive daily snapshots
