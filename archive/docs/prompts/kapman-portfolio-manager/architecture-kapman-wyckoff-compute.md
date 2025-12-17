# KapMan Wyckoff Analysis Module v2.0.0 - Architecture & Design Document

**Project Status:** Production (v2.0.0)  
**Last Updated:** November 30, 2025  
**Framework:** FastAPI (Python 3.11)  
**Port:** 5000  
**Repository:** KapMan-Wyckoff-Analysis-Module-v2

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Current Architecture (v1 Implementation)](#current-architecture-v1-implementation)
3. [Data Models & API Contracts](#data-models--api-contracts)
4. [Integration Points](#integration-points)
5. [Module Structure](#module-structure)
6. [Core Algorithms](#core-algorithms)
7. [v2 Roadmap: Two-Level Wyckoff Analysis](#v2-roadmap-two-level-wyckoff-analysis)
8. [Configuration & Registry](#configuration--registry)
9. [External Dependencies](#external-dependencies)
10. [Implementation Notes for ChatGPT](#implementation-notes-for-chatgpt)

---

## System Overview

### Purpose

The Wyckoff Analysis Service is a **technical market analysis microservice** that identifies accumulation/distribution phases in stock price data using the Wyckoff methodology. It serves the KapMan investment ecosystem by providing:

- **Phase Classification:** Accumulation (A), Markup (B), Consolidation (C), Distribution (D), Markdown (E)
- **9-Step Diagnostic Checklist:** Quantitative validation of Wyckoff patterns
- **Volatility-Adaptive Analysis:** Dynamic threshold adjustments based on market conditions
- **Dealer Positioning Integration:** GEX, Gamma Flip, and Put/Call metrics for enhanced signals
- **Risk/Reward Analysis:** Entry point validation with dynamic support/resistance levels

### High-Level Data Flow

```
User Request (symbols)
    ↓
┌─────────────────────────────────────────────────┐
│ ORCHESTRATION LAYER (services/orchestrator.py)  │
│ - Coordinates multi-stage data fetching         │
│ - Manages rate limiting & batching              │
│ - Parallel execution strategy                   │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ DATA FETCHERS (services/data_fetch.py)          │
│ - Polygon API: OHLCV, RSI, MACD, ADX, SMA, EMA │
│ - Schwab API: GEX, Gamma Flip, IV metrics      │
│ - Batch processing with rate limiting           │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ ANALYTICS ENGINE (analytics/)                   │
│ - Phase classification (phase.py)               │
│ - 9-Step checklist validation (checklist.py)    │
│ - Scoring & normalization (scoring.py)          │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ API RESPONSE (WyckoffAnalysis model)            │
│ - Phase with confidence score                   │
│ - All 9 step results                            │
│ - Metrics & composite score                     │
└─────────────────────────────────────────────────┘
```

---

## Current Architecture (v1 Implementation)

### Directory Structure

```
KapMan-Wyckoff-Analysis-Module-v2/
├── main.py                           # FastAPI app entry point
├── requirements.txt                  # Python dependencies
├── replit.md                         # Project metadata & preferences
├── Kapman-Wyckoff-Analysis-Module-v2-Architecture.md  # THIS FILE
│
├── api/
│   ├── __init__.py
│   ├── routes.py                     # Endpoint handlers & HTML landing page
│   ├── auth.py                       # Bearer token verification
│   └── openapi.py                    # OpenAPI schema for ChatGPT Actions
│
├── analytics/
│   ├── __init__.py
│   ├── phase.py                      # Wyckoff phase classification (A-E)
│   ├── scoring.py                    # Metric normalization & composite scoring
│   ├── checklist.py                  # 9-step validation engine
│   ├── CHECKLIST_README.md           # 9-step scoring methodology docs
│   └── CHECKLIST_METRICS_TABLE.md    # Pass/fail criteria reference table
│
├── services/
│   ├── __init__.py
│   ├── orchestrator.py               # Multi-stage data fetching orchestration
│   └── data_fetch.py                 # HTTP batch requests to API wrappers
│
├── shared/
│   ├── __init__.py
│   ├── models.py                     # Pydantic AnalysisRequest, WyckoffAnalysis
│   ├── config.py                     # Configuration loader & ENV variables
│   └── validation.py                 # Input validation utilities
│
├── tests/
│   ├── __init__.py
│   ├── test_checklist.py             # 9-step checklist unit tests
│   └── test_integration.py           # End-to-end integration tests
│
├── archive/
│   └── old_docs/                     # Previous documentation versions
│
└── WYCKOFF_DATABASE_SCHEMA.md         # PostgreSQL schema for time-series storage
```

### API Endpoints (v1)

#### 1. `GET /` - Landing Page
- Returns HTML dashboard with API docs, service info, and quick test form
- Location: `api/routes.py::root()`
- No authentication required

#### 2. `POST /analyze` - Main Analysis Endpoint
- **Requires:** Bearer token authentication
- **Input:** `AnalysisRequest` - list of symbols
- **Output:** `list[WyckoffAnalysis]` - analysis results for each symbol
- **Location:** `api/routes.py::analyze()`
- **Flow:**
  1. Orchestrate multi-stage data fetching
  2. Normalize metrics
  3. Run 9-step checklist
  4. Classify phase & calculate scores
  5. Return comprehensive results

**Request Schema:**
```json
{
  "symbols": ["AAPL", "MSFT"],
  "include_historical": false
}
```

**Response Schema:**
```json
{
  "symbol": "AAPL",
  "wyckoff_phase": "A",
  "phase_description": "Accumulation - Potential bottom",
  "phase_score": 0.85,
  "phase_confidence": 0.78,
  "volatility_regime": "medium",
  "macd_signal": "bullish",
  "trend_strength": 0.62,
  "composite_score": 0.71,
  "metrics": {
    "rsi": 40.5,
    "adx": 22.3,
    "historical_volatility": 18.2,
    // ... 30+ additional metrics
  },
  "data_quality": "Live",
  "volatility_adjusted": true,
  "wyckoff_checklist": {
    "step_1_defined_support": {
      "passed": true,
      "score": 0.92,
      "support_level": 150.23
    },
    // ... steps 2-9
    "summary": {
      "total_passed": 7,
      "average_score": 0.68,
      "config_used": { /* parameters */ }
    }
  }
}
```

#### 3. `GET /health` - Health Check
- **Output:** Service status, timestamp, version
- **Location:** `api/routes.py::health()`
- No authentication required

#### 4. `GET /openapi.json` - OpenAPI Schema
- **Output:** OpenAPI 3.1.0 schema for ChatGPT Actions
- **Location:** `api/routes.py::get_openapi_schema()`
- No authentication required

---

## Data Models & API Contracts

### Core Pydantic Models (shared/models.py)

#### AnalysisRequest
```python
class AnalysisRequest(BaseModel):
    symbols: list[str]                    # Stock symbols: ["AAPL", "MSFT"]
    include_historical: bool = False      # Future: store in database
```

#### WyckoffAnalysis
```python
class WyckoffAnalysis(BaseModel):
    symbol: str                           # Stock symbol
    wyckoff_phase: str                    # A, B, C, D, E (or blank)
    phase_description: str                # Human-readable phase name
    phase_score: float                    # 0.0-1.0 phase quality
    phase_confidence: float               # 0.0-1.0 classification confidence
    volatility_regime: str                # low, medium, high, extreme
    macd_signal: str                      # bullish, bearish, n/a
    trend_strength: float                 # 0.0-1.0 trend magnitude
    composite_score: float                # Weighted combination score
    metrics: dict                         # Raw & normalized metrics
    data_quality: str                     # Live, Static, Cached
    volatility_adjusted: bool             # Thresholds adjusted?
    wyckoff_checklist: dict               # 9-step results (see below)
```

### Wyckoff Checklist Structure
```python
{
  "step_1_defined_support": {
    "passed": bool,
    "score": 0.0-1.0,
    "support_level": float,
    "description": str
  },
  "step_2_climax_volume": {
    "passed": bool,
    "score": 0.0-1.0,
    "avg_volume": float,
    "description": str
  },
  # ... steps 3-9 follow same pattern
  "summary": {
    "total_passed": 0-9,
    "average_score": 0.0-1.0,
    "config_used": {
      "lookback_short": 10,
      "lookback_medium": 20,
      "lookback_long": 50,
      "volume_spike_factor": 2.0,
      "support_threshold": 0.01,
      "base_volatility_threshold": 0.02,
      "min_risk_reward": 3.0
    }
  }
}
```

---

## Integration Points

### External Services

#### 1. **Polygon API Wrapper**
- **URL:** Environment variable `POLYGON_WRAPPER_URL`
- **Authentication:** Bearer token via `KAPMAN_AUTHENTICATION_TOKEN`
- **Endpoints Called:**
  - `POST /api/metrics/price` - Historical OHLCV data
  - `POST /api/indicators/batch` - Technical indicators (RSI, MACD, ADX, SMA, EMA)
  - `GET /api/aggs` - Aggregated bar data

#### 2. **Schwab API Wrapper**
- **URL:** Environment variable `SCHWAB_WRAPPER_URL`
- **Authentication:** Bearer token via `KAPMAN_AUTHENTICATION_TOKEN`
- **Endpoints Called:**
  - `GET /api/dealer-metrics` - GEX, Gamma Flip, Put/Call walls
  - `GET /api/metrics/volatility` - IV Skew, IV Term Structure, OI Ratio

#### 3. **KapMan Config Service (Registry)**
- **URL:** `https://kapman-registry.replit.app` (hardcoded)
- **Endpoint:** `GET /configs/v2/wyckoff_config.json`
- **Returns:** Centralized configuration including `checklist_thresholds`
- **Used in:** `shared/config.py::load_configs()`
- **Caching:** Config loaded once at service startup

#### 4. **KapMan Portfolio Manager**
- **Expected Integration:** Will consume analysis results
- **API:** `/analyze` endpoint via HTTP POST
- **Authentication:** Mutual Bearer token exchange
- **Frequency:** Called on portfolio rebalance or user demand

---

## Module Structure

### 1. API Layer (api/)

**auth.py**
- `verify_token()` - FastAPI dependency for Bearer token validation
- Validates `Authorization: Bearer {token}` header
- Compares against `KAPMAN_AUTHENTICATION_TOKEN` from env

**routes.py**
- `root()` - HTML landing page with docs & quick test
- `analyze(req: AnalysisRequest)` - Main analysis handler
- `health()` - Service status endpoint
- `get_openapi_schema()` - ChatGPT Actions schema
- `get_root_html()` - HTML content generator

**openapi.py**
- Generates OpenAPI 3.1.0 schema compatible with ChatGPT
- Custom schema with `servers`, `components`, `paths`

### 2. Analytics Layer (analytics/)

**phase.py - Phase Classification**

Functions:
- `classify_phase(metrics, volatility_regime, dealer_metrics)` → str
  - Returns phase letter (A, B, C, D, E) or blank
  - Uses RSI, ADX, volatility, and trend to classify
  - Integrates GEX metrics for confirmation

- `calculate_phase_confidence(metrics)` → float [0-1]
  - Measures how "textbook" the phase pattern is
  - Based on how well indicators align

- `classify_volatility(hist_vol, iv_skew, oi_ratio)` → str
  - Returns: "low", "medium", "high", "extreme"
  - Used for dynamic threshold adjustment

- `detect_macd_signal(df)` → str
  - Returns: "bullish", "bearish", "neutral", "n/a"
  - Analyzes MACD histogram crossover

- `adjust_thresholds_for_volatility(base_thresholds, vol_regime)` → dict
  - Scales RSI/ADX thresholds based on volatility
  - High volatility = looser thresholds (wider ranges)
  - Low volatility = tighter thresholds (narrower ranges)

**checklist.py - 9-Step Validation**

Functions (one per step):
1. `detect_defined_support(df, lookback, threshold)` - Support level test
2. `detect_climax_volume_spike(df, lookback, volume_spike_factor)` - Selling climax
3. `detect_rally_on_increasing_volume(df, lookback)` - Rally quality
4. `detect_pullback_low_volume(df, lookback)` - Secondary test
5. `detect_higher_swing_lows(df, lookback)` - Strength confirmation
6. `detect_downtrend_break(df, lookback)` - Resistance breakout
7. `detect_relative_strength(df, benchmark_df, lookback)` - Outperformance
8. `detect_horizontal_base(df, lookback, volatility_threshold)` - Consolidation
9. `detect_favorable_risk_reward(df, lookback, min_ratio)` - Entry validation

Main function:
- `run_wyckoff_checklist(df, benchmark_df, config)` → dict
  - Runs all 9 steps
  - Returns detailed results with scores & descriptions
  - Uses configurable parameters from registry

**scoring.py - Metrics Normalization**

Functions:
- `normalize_metrics(raw_metrics)` → dict
  - Converts raw values (RSI 0-100, ADX 0-100) to 0-1 scale
  - Uses min-max, sigmoid, or sign-preserving normalization
  - Handles negative values (e.g., MACD, dealer metrics)

- `composite_score(individual_scores)` → float
  - Weighted average of phase score, checklist average, confidence
  - Weights: phase_score=40%, checklist=35%, confidence=25%
  - Returns final 0-1 composite score

---

### 3. Services Layer (services/)

**orchestrator.py - Multi-Stage Fetching**

Main function:
- `orchestrate(symbols, orchestration_config)` → dict
  - Reads `wyckoff` workflow from registry config
  - Executes parallel groups of data fetching stages
  - Returns consolidated data for all stages

Key concepts:
- **Stages:** Individual API calls (e.g., "fetch_indicators", "fetch_dealer_metrics")
- **Parallel Groups:** Stages that can run simultaneously (no dependencies)
- **Rate Limiting:** Respects max requests per second per source

**data_fetch.py - HTTP Requests**

Functions:
- `fetch_batch(url, symbols, headers, params, method)` → list[dict]
  - Batch POST/GET request to external API
  - Handles rate limiting delays
  - Returns parsed JSON response
  - Catches and logs errors per symbol

---

### 4. Configuration Layer (shared/)

**config.py - Environment & Registry Loading**

Functions:
- `load_configs()` → dict
  - Fetches `wyckoff_config.json` from KapMan registry
  - Falls back to hardcoded defaults if registry unavailable
  - Caches config at service startup

Key variables:
```python
SERVICE_URL          # http://0.0.0.0:5000
PORT                 # 5000
KAPMAN_AUTHENTICATION_TOKEN  # Bearer token from env
POLYGON_WRAPPER_URL          # External API endpoint
SCHWAB_WRAPPER_URL           # External API endpoint
CONFIG_SERVICE_URL           # KapMan registry URL
```

**models.py - Pydantic Schemas**
- `AnalysisRequest` - Request contract
- `WyckoffAnalysis` - Response contract
- JSON schema validation with examples

**validation.py - Input Checks**
- Symbol format validation
- List length constraints
- Type checking utilities

---

## Core Algorithms

### Algorithm 1: Wyckoff Phase Classification

**Input:** Normalized metrics dict, volatility regime, dealer metrics

**Logic:**
```
Phase A (Accumulation):
  IF (rsi_normalized < 0.3 OR support_found) 
    AND adx_normalized < 0.5 
    AND volume_surge_detected
  THEN Phase = A
  
Phase B (Markup):
  IF (rsi_normalized > 0.6)
    AND (adx_normalized > 0.5)
    AND trend_strength > 0.6
    AND relative_strength > benchmark
  THEN Phase = B
  
Phase C (Consolidation):
  IF (consolidation_detected)
    AND (horizontal_price_base)
  THEN Phase = C
  
Phase D (Distribution):
  IF (rsi_normalized > 0.7)
    AND phase_not_B
    AND volume_elevated
    AND gex_negative (dealer short)
  THEN Phase = D
  
Phase E (Markdown):
  IF (downtrend_confirmed)
    AND (rsi_normalized < 0.3)
    AND (adx_normalized > 0.5)
  THEN Phase = E
```

**Output:** Phase letter + confidence score [0-1]

---

### Algorithm 2: 9-Step Checklist Scoring

**Each step returns:**
```python
{
  "signal": pd.Series([True/False, True/False, ...]),  # Per-bar results
  "score": 0.0-1.0,                                     # Current bar strength
  "metric_value": float                                 # Raw measurement
}
```

**Score Calculation (if step passes):**
- Step 1: `1 - (distance_from_support / threshold)`
- Step 2: `(volume_ratio - 1) / volume_spike_factor` (capped 0-1)
- Step 3: `abs(rally_pct) / 5.0` (capped 0-1)
- Step 4: `1 - volume_ratio` (low vol is better)
- Step 5: `consecutive_count / lookback`
- Step 6: `breakout_pct / 3.0` (capped 0-1)
- Step 7: `relative_return% / 10.0` (capped 0-1)
- Step 8: `1 - (volatility% / threshold%)`
- Step 9: `(ratio - 3.0) / 3.0` if ratio ≥ 3.0, else 0

**If step fails:** `score = 0.0`

**Summary:**
```python
total_passed = count(scores > 0)
average_score = sum(scores) / 9
```

---

### Algorithm 3: Volatility-Adaptive Thresholds

**Purpose:** Adjust RSI/ADX thresholds based on market conditions

**Historical Volatility Buckets:**
```
HV ≤ 10%  → "low"    → relax thresholds (RSI: 30-70 becomes 25-75)
HV 10-20% → "medium" → standard thresholds (RSI: 30-70)
HV 20-35% → "high"   → tighten thresholds (RSI: 30-70 becomes 35-65)
HV > 35%  → "extreme"→ very tight thresholds (RSI: 30-70 becomes 40-60)
```

**Effect on Phase Classification:**
- Extreme volatility = harder to trigger phase changes
- Low volatility = easier to trigger phase changes (more responsive)

---

## v2 Roadmap: Two-Level Wyckoff Analysis

### Overview

**Version 2.0** will extend the service with two distinct analysis levels:

1. **Level 1: Quick Scan** - Lightweight checklist for portfolio-wide screening
2. **Level 2: Deep Dive** - Comprehensive pattern analysis with bar-by-bar event detection

### Level 1: Quick Scan Analysis

**Purpose:** Rapid portfolio screening (fast, lightweight, for many symbols)

**What It Returns:**
- Phase classification (A-E)
- Quick checklist (pass/fail only, no detailed scores)
- Single composite score
- Risk/reward ratio only (no other metrics)
- Processing time: <200ms per symbol

**API Endpoint:** `POST /analyze/quick`

**Request:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "analysis_level": "quick"
}
```

**Response (abbreviated):**
```json
{
  "symbol": "AAPL",
  "wyckoff_phase": "A",
  "quick_checklist": {
    "steps_passed": 6,
    "total_steps": 9,
    "composite_score": 0.67,
    "risk_reward_ratio": 3.5
  },
  "processing_time_ms": 145
}
```

**Implementation Details:**
- Only calculate steps 1, 3, 5, 9 (skip others for speed)
- Use cached indicator data from Polygon
- No benchmark comparison (skip step 7)
- Single pass through checklist (no iterative refinement)

---

### Level 2: Deep Dive Analysis

**Purpose:** Institutional-grade pattern recognition with quantitative event detection

**What It Returns:**
- Complete 9-step checklist with all metrics
- **Wyckoff Events** table (see below)
- Accumulation/Distribution Pattern Strength [0-1]
- Multi-timeframe confirmation (daily + weekly if available)
- Event timeline with exact bar numbers
- Processing time: ~1-2 seconds per symbol

**API Endpoint:** `POST /analyze/deep`

**Request:**
```json
{
  "symbols": ["AAPL"],
  "analysis_level": "deep",
  "include_events": true,
  "lookback_bars": 60,
  "enable_multitimeframe": true
}
```

**Response (enhanced):**
```json
{
  "symbol": "AAPL",
  "wyckoff_phase": "A",
  "phase_description": "Accumulation - Strong bottom formation",
  "phase_confidence": 0.89,
  
  "wyckoff_checklist": { /* full 9-step results */ },
  
  "deep_analysis": {
    "accumulation_strength": 0.82,
    "distribution_strength": 0.15,
    "pattern_type": "textbook_accumulation",
    
    "events": [
      {
        "event_id": "EVT001",
        "type": "climax_volume",
        "bar_number": 42,
        "date": "2025-11-28",
        "price": 150.23,
        "volume": 25000000,
        "confirmation": 0.87,
        "description": "Selling climax with bullish reversal"
      },
      {
        "event_id": "EVT002",
        "type": "rally_initiation",
        "bar_number": 43,
        "date": "2025-11-29",
        "price": 152.45,
        "volume_ratio": 1.34,
        "confirmation": 0.75,
        "description": "Rally begins on above-average volume"
      },
      /* more events... */
    ],
    
    "event_count": 8,
    "event_sequence_validity": 0.91,
    
    "multitimeframe": {
      "daily": { /* phase, checklist */ },
      "weekly": { /* phase, checklist */ },
      "alignment": "strong"
    }
  },
  
  "processing_time_ms": 1245
}
```

---

### Wyckoff Events Quantitative Table

**Event Detection Engine:**

Each event captures a discrete market action and its confirmation score.

**Event Types:**

```python
"climax_volume"         # Selling climax with reversal
"rally_initiation"      # Price rises, volume increases
"pullback_test"         # Price dips, volume declines
"higher_low"            # Support bounce at new level
"accumulation_signal"   # Positive GEX + higher low combo
"resistance_break"      # Price breaks above previous high
"distribution_begins"   # Selling pressure initiates
"markup_acceleration"   # Trend accelerates with volume
"volatility_contraction"# Price consolidation tightening
"gex_regime_shift"      # Dealer positioning change
```

**Event Table Structure:**

```python
event = {
  "event_id": "EVT001",                    # Unique identifier per symbol
  "type": "climax_volume",                 # Event classification
  "bar_number": 42,                        # OHLCV bar index
  "date": "2025-11-28",                    # Calendar date
  "datetime": "2025-11-28T15:30:00Z",      # ISO timestamp
  "ohlc": {
    "open": 149.50,
    "high": 151.20,
    "low": 149.10,
    "close": 150.23,
    "volume": 25000000
  },
  "metrics_at_event": {
    "rsi": 28.5,
    "macd_histogram": -2.34,
    "gex": -150000000,
    "support_distance": 0.002,
  },
  "confirmation_score": 0.87,              # 0-1: How strong is this event?
  "related_checklist_steps": [2, 4, 5],    # Which steps validate this?
  "subsequent_bars": 5,                    # Bars until next event
  "description": "Selling climax with bullish reversal after support test",
  "action_suggested": "BUY",               # Implied trader action
  "risk_level": "medium"                   # Risk categorization
}
```

**Event Confirmation Score Calculation:**

```
For "climax_volume" event:
  - Volume ratio (2x avg) = 0.85
  - Reversal confirmation (close > prev) = 1.0
  - Support proximity (within 2%) = 0.95
  - MACD confirmation (MACD < signal) = 0.75
  
  confirmation_score = (0.85 + 1.0 + 0.95 + 0.75) / 4 = 0.89
```

---

### Pattern Strength Calculation

**Accumulation Strength [0-1]:**

```
Input: 9-step checklist results

Weighted formula:
  AS = (
    step1_score × 0.15   // Support is crucial
    + step2_score × 0.12 // Climax volume key
    + step3_score × 0.12 // Rally initiation
    + step4_score × 0.12 // Secondary test
    + step5_score × 0.15 // Higher lows = accumulation
    + step8_score × 0.12 // Base formation
    + step9_score × 0.12 // Entry quality
  )
  
  // Multiply by event_sequence_validity (0-1)
  final_AS = AS × sequence_validity
```

**Distribution Strength [0-1]:**

```
Similar but different weights:
  DS = (
    step6_score × 0.15   // Break above resistance
    + step7_score × 0.20 // Relative strength is key
    + step8_score × 0.15 // Top formation
    + step2_score × 0.12 // High volume at tops
    ...
  )
```

---

### Multi-Timeframe Confirmation

**Optional Feature (requires separate API call for weekly data):**

```json
"multitimeframe": {
  "daily": {
    "phase": "A",
    "checklist_passed": 7,
    "score": 0.82
  },
  "weekly": {
    "phase": "A",
    "checklist_passed": 6,
    "score": 0.76
  },
  "alignment": "strong|moderate|weak",
  "confirmation_level": 0.85
}
```

**Alignment Logic:**
- Same phase on both timeframes = **strong alignment**
- Adjacent phases (A→B or D→C) = **moderate alignment**
- Opposite phases = **weak alignment**

---

## Configuration & Registry

### Configuration Source: KapMan Registry

**URL:** `https://kapman-registry.replit.app/configs/v2/wyckoff_config.json`

**Structure:**
```json
{
  "service_name": "wyckoff-analysis",
  "version": "2.0.0",
  "analysis_workflows": {
    "wyckoff": {
      "execution_strategy": {
        "parallel_groups": [
          {
            "name": "group_1",
            "stages": [1, 2]
          },
          {
            "name": "group_2",
            "stages": [3, 4, 5]
          }
        ]
      },
      "stages": [
        {
          "name": "fetch_indicators",
          "source": "polygon",
          "endpoint": "indicators_batch",
          "batching": {
            "enabled": true,
            "max_batch_size": 10,
            "rate_limit": {
              "max_requests_per_second": 5
            }
          }
        },
        // ... more stages
      ]
    }
  },
  "checklist_thresholds": {
    "lookback_short": 10,
    "lookback_medium": 20,
    "lookback_long": 50,
    "volume_spike_factor": 2.0,
    "support_threshold": 0.01,
    "base_volatility_threshold": 0.02,
    "min_risk_reward": 3.0
  },
  "phase_classification": {
    "rsi_thresholds": {
      "oversold": 30,
      "overbought": 70
    },
    "adx_thresholds": {
      "no_trend": 25,
      "strong_trend": 50
    }
  }
}
```

### Environment Variables

```bash
# Service Configuration
KAPMAN_AUTHENTICATION_TOKEN=sk_live_xxxxx        # Bearer token for auth
POLYGON_WRAPPER_URL=https://polygon-wrapper.app  # Polygon API wrapper
SCHWAB_WRAPPER_URL=https://schwab-wrapper.app    # Schwab API wrapper
PORT=5000                                         # Server port
HOST=0.0.0.0                                      # Bind address

# Optional: Override registry URL (default: kapman-registry.replit.app)
CONFIG_SERVICE_URL=https://custom-registry.app
```

---

## External Dependencies

### Python Packages

**Core Framework:**
- `fastapi>=0.100.0` - Web framework
- `uvicorn>=0.23.0` - ASGI server
- `pydantic>=2.0.0` - Data validation & serialization
- `httpx>=0.24.0` - Async HTTP client

**Data Processing:**
- `pandas>=2.0.0` - OHLCV dataframe manipulation
- `numpy>=1.24.0` - Numerical computations

**Testing & Development:**
- `pytest>=7.4.0` - Unit testing
- `pytest-asyncio>=0.21.0` - Async test support

### External APIs

**1. Polygon API Wrapper**
- Supplies: OHLCV bars, RSI, MACD, ADX, SMA, EMA
- Batching: Up to 10 symbols per request
- Rate limit: 5 requests/second
- Response time: ~200-500ms

**2. Schwab API Wrapper**
- Supplies: GEX, Gamma Flip, Put/Call walls, IV metrics
- Batching: Per-symbol requests
- Rate limit: 2 requests/second
- Response time: ~300-1000ms

**3. KapMan Config Service (Registry)**
- Supplies: Orchestration config, thresholds
- Caching: Once per service startup
- Response time: ~50-200ms

---

## Implementation Notes for ChatGPT

### When Drafting Code for v2 Enhancements

**1. Keep v1 Intact**
- All current endpoints must continue working
- Add new endpoints (`/analyze/quick`, `/analyze/deep`) without breaking `/analyze`
- Maintain backward compatibility with existing `WyckoffAnalysis` schema

**2. Event Detection Engine**
- Create new module: `analytics/events.py`
- Function: `detect_wyckoff_events(df, checklist_results, dealer_metrics) → list[dict]`
- Each event is a discrete market action (climax, rally, pullback, etc.)
- Calculate `confirmation_score` for each event (0-1)
- Return events in chronological order with bar numbers

**3. OHLC Bar Calculations**
- New functions in `analytics/patterns.py`:
  - `identify_swing_lows(df, lookback)` - Find support bounce points
  - `identify_swing_highs(df, lookback)` - Find resistance points
  - `calculate_bar_patterns(df)` - Doji, engulfing, hammer detection
  - `measure_accumulation_bars(df)` - Quiet accumulation zones
  - `quantify_climax_bars(df)` - High-volume climax identification

**4. Multi-Timeframe Support**
- New module: `analytics/multitimeframe.py`
- Fetch weekly data from Polygon wrapper
- Run identical checklist on weekly timeframe
- Calculate `alignment` score between timeframes
- Store results in separate nested dict

**5. Pattern Strength Scoring**
- New function: `calculate_pattern_strength(checklist_results, event_list) → dict`
- Returns: `{"accumulation_strength": 0-1, "distribution_strength": 0-1}`
- Uses weighted scoring based on step importance
- Adjusts by event sequence validity

**6. API Layer Changes**
- Modify `api/routes.py`:
  - Add `analyze_quick(req)` endpoint
  - Add `analyze_deep(req)` endpoint
  - Keep existing `analyze(req)` for backward compatibility
  - Update OpenAPI schema with new endpoints

**7. Testing Requirements**
- Unit tests for each event type detection
- Integration tests for full event timeline
- Regression tests to ensure v1 endpoints unchanged
- Performance benchmarks (target: <2 seconds for deep analysis)

**8. Database Schema Integration**
- Events should be storable via `WYCKOFF_DATABASE_SCHEMA.md`
- Create PostgreSQL table: `wyckoff_events` with columns:
  - `event_id`, `symbol`, `event_type`, `bar_number`, `date`, `ohlc`, `metrics`, `confirmation_score`
- Allow time-series queries (e.g., "all climax events for AAPL in November 2025")

**9. Configuration for v2**
- Add to `wyckoff_config.json` registry:
  ```json
  {
    "event_detection": {
      "enabled": true,
      "event_types": ["climax_volume", "rally_initiation", "pullback_test", ...],
      "confirmation_threshold": 0.65
    },
    "multitimeframe": {
      "enabled": true,
      "timeframes": ["daily", "weekly"]
    },
    "pattern_strength": {
      "accumulation_weights": {...},
      "distribution_weights": {...}
    }
  }
  ```

**10. Performance Optimization**
- Use `@lru_cache` for frequently called functions
- Batch bar calculations (don't loop per-bar)
- Vectorize operations with pandas/numpy
- Cache intermediate results (e.g., support levels)
- Consider async processing for multiple symbols

**11. Error Handling**
- Return graceful errors if insufficient data (<20 bars)
- Log which stages fail in multi-stage orchestration
- Return partial results (e.g., v1 analysis works even if events fail)
- Include `data_quality` field to indicate completeness

**12. Code Organization**
- New files:
  - `analytics/events.py` - Event detection engine
  - `analytics/patterns.py` - OHLC bar pattern analysis
  - `analytics/multitimeframe.py` - Weekly timeframe analysis
  - `tests/test_events.py` - Event detection tests
  - `tests/test_patterns.py` - Pattern analysis tests
- Avoid modifying existing files unless necessary
- Keep functions focused and single-purpose

---

## Deployment & Publishing

### Current Deployment
- **Server:** Replit (NixOS environment)
- **Framework:** FastAPI on Uvicorn
- **Port:** 5000
- **Command:** `uvicorn main:app --host 0.0.0.0 --port 5000`
- **URL:** `https://kapman-wyckoff-analysis-module-v2.replit.app`

### Publishing Checklist (for v2 release)
1. ✅ All tests passing (`pytest tests/`)
2. ✅ v1 endpoints backward compatible
3. ✅ New endpoints documented in OpenAPI schema
4. ✅ Environment variables configured (`.env`)
5. ✅ Registry config updated with new parameters
6. ✅ Performance benchmarks met (<2s per symbol for deep analysis)
7. ✅ Integration tested with kapman-portfolio-manager
8. ✅ ChatGPT Actions schema updated (`/openapi.json`)
9. ⏳ Create deployment snapshot in Replit
10. ⏳ Update documentation on GitHub

### Changes to kapman-portfolio-manager
- Call new `/analyze/quick` endpoint for portfolio-wide screening (fast)
- Use `/analyze/deep` endpoint for selected holdings (detailed analysis)
- Store event timeline results in local database for pattern tracking
- Display multi-timeframe confirmation in UI
- Add "Event Timeline" visualization showing climax → rally → test sequence

### Changes to KapMan Registry
- Add new `event_detection` section to `wyckoff_config.json`
- Add new `multitimeframe` section with timeframe configuration
- Add new `pattern_strength` section with scoring weights
- Update `checklist_thresholds` as needed based on backtest results

---

## Documentation Files in Repo

- **This file:** `Kapman-Wyckoff-Analysis-Module-v2-Architecture.md` - Comprehensive architecture
- **Checklist Guide:** `analytics/CHECKLIST_README.md` - 9-step methodology explained
- **Metrics Table:** `analytics/CHECKLIST_METRICS_TABLE.md` - Pass/fail criteria reference
- **Database Schema:** `WYCKOFF_DATABASE_SCHEMA.md` - PostgreSQL DDL & queries
- **Project Info:** `replit.md` - Project metadata & preferences

---

## Quick Reference: Key Functions & Locations

| Function | File | Purpose |
|----------|------|---------|
| `analyze()` | `api/routes.py` | Main analysis endpoint handler |
| `orchestrate()` | `services/orchestrator.py` | Multi-stage data fetching coordinator |
| `classify_phase()` | `analytics/phase.py` | Phase A-E classification |
| `run_wyckoff_checklist()` | `analytics/checklist.py` | 9-step validation engine |
| `composite_score()` | `analytics/scoring.py` | Weighted scoring formula |
| `normalize_metrics()` | `analytics/scoring.py` | 0-1 metric normalization |
| `verify_token()` | `api/auth.py` | Bearer token validation |
| `load_configs()` | `shared/config.py` | Registry config loader |
| `detect_wyckoff_events()` | `analytics/events.py` | **[v2 NEW]** Event detection |
| `calculate_pattern_strength()` | `analytics/patterns.py` | **[v2 NEW]** Pattern scoring |

---

## Version History

- **v1.0.0** (Initial): 9-step checklist, phase classification, volatility-adaptive thresholds
- **v2.0.0** (Current): Added event detection, deep analysis, pattern strength scoring
- **v2.1.0** (Planned): Multi-timeframe support, database integration, ChatGPT persistence

---

**Document prepared for ChatGPT prompt engineering**  
**Last modified:** November 30, 2025  
**For questions:** See existing code + docstrings in repo
