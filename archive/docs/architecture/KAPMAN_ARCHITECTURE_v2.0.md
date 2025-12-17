# KAPMAN TRADING SYSTEM - ARCHITECTURE & IMPLEMENTATION PROMPT
**Version:** 2.0  
**Date:** December 9, 2025  
**Status:** Ready for Sprint 2 Implementation  
**Target MVP:** December 31, 2025

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Business Context](#2-business-context)
3. [System Requirements](#3-system-requirements)
4. [Architecture Decisions](#4-architecture-decisions)
5. [Data Model](#5-data-model)
6. [Service Architecture](#6-service-architecture)
7. [API Specification](#7-api-specification)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [Pre-Sprint 2 Setup: Applying Schema Enhancements](#9-pre-sprint-2-setup-applying-schema-enhancements)
10. [Sprint 1: Infrastructure (COMPLETED)](#10-sprint-1-infrastructure-completed)
11. [Sprint 2: Wyckoff Engine & Pipeline](#11-sprint-2-wyckoff-engine--pipeline)
12. [Sprint 3: Recommendations & Dashboard](#12-sprint-3-recommendations--dashboard)
13. [Sprint 4: Deployment & Hardening](#13-sprint-4-deployment--hardening)
14. [Configuration Reference](#14-configuration-reference)
15. [Appendices](#15-appendices)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Vision Statement

Build an automated trading decision-support system that:
- Gathers daily OHLCV for full market universe (~15K tickers) from Polygon S3
- Enriches watchlist tickers (~100) with options data, technical indicators, dealer metrics
- Performs Wyckoff phase classification and event detection
- Generates actionable trade recommendations with justification
- Tracks forecast accuracy using directional Brier scoring
- Provides a minimal dashboard for daily decision-making

### 1.2 Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database** | PostgreSQL 15 + TimescaleDB 2.x | Time-series hypertables, compression, retention policies |
| **OHLCV Universe** | Full Polygon (~15K tickers) | Enables screening, sector analysis, no backfill needed |
| **Analysis Scope** | Watchlist only (~100 tickers) | Cost-effective options API usage |
| **Deployment** | Docker Compose → Fly.io | Portable, ~$20/month |
| **Frontend** | Next.js 14 + Shadcn/ui | AI-friendly, minimal MVP |
| **Backend** | Python (FastAPI) + TypeScript (Express) | Python for quant, TS for API |
| **AI Provider** | Claude (swappable) | Provider abstraction layer |
| **Market Data** | Polygon S3 (OHLCV) + Polygon API (Options) | 100 RPS, no rate limiting |
| **Metrics** | Polygon MCP Server | 84 TA indicators, dealer/vol metrics |

### 1.3 MVP Scope (December 31, 2025)

**Included:**
- Daily batch pipeline (S3 universe → watchlist enrichment → Wyckoff → Recommendations)
- Full OHLCV universe storage (3-year retention)
- Options chain storage for watchlist (90-day retention)
- 45+ metrics per snapshot (technical, dealer, volatility, price)
- 8 critical Wyckoff events (BC, SC, AR, ST, SPRING, TEST, SOS, SOW)
- 4 option strategies (Long Call, Long Put, CSP, Vertical Spread)
- Minimal dashboard with recommendations and alerts
- Directional accuracy scoring (Brier)

**Deferred to Post-MVP:**
- Full 17 Wyckoff events
- Calendar Spread, Covered Call strategies
- Chatbot interface
- Email scraping
- Advanced UI/charts

### 1.4 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-07 | Initial architecture |
| 2.0 | 2025-12-09 | Enhanced schema (45+ columns), full universe OHLCV, options summary table, revised Sprint 2 |

---

## 2. BUSINESS CONTEXT

### 2.1 Business Information

| Field | Value |
|-------|-------|
| **Business Name** | Kapman Investments |
| **Team Members** | Victor Kapella (Partner), Ron Nyman (Partner) |
| **Target Users** | Internal use only (Victor) |
| **Primary Market Focus** | AI stocks, Technology sector, sector rotation |

### 2.2 Trading Strategy

| Strategy Element | Description |
|------------------|-------------|
| **Timeframe** | Swing trades (30-90 days) |
| **Instruments** | Options: Long Calls/Puts, CSPs, Vertical Spreads |
| **Analysis Method** | Wyckoff methodology + dealer positioning |
| **Risk Management** | Market/sector hedging, BC score alerts |

### 2.3 Current State (Being Replaced)

| Component | Technology | Status | Issue |
|-----------|------------|--------|-------|
| ChatGPT Custom GPT | OpenAI Actions + Schwab/Polygon | Working | Non-deterministic results |
| Claude Project | MCP + Polygon | Working | No recommendation capture |
| kapman-portfolio-manager | React + Express + Neon | Proof of concept | Architecture debt |
| kapman-wyckoff-module-v2 | FastAPI (Python) | Production | Keep & migrate |

---

## 3. SYSTEM REQUIREMENTS

### 3.1 Functional Requirements

#### P1 - Must Have (MVP)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-001 | Daily batch job loads OHLCV for full universe | ~15K tickers loaded from S3 by 5 AM ET |
| FR-002 | Daily batch job fetches options chains for watchlist | All watchlist tickers have current options data |
| FR-003 | Technical indicators calculated via Polygon MCP | 84 indicators stored per watchlist ticker |
| FR-004 | Dealer metrics calculated for watchlist | GEX, DGPI, gamma flip, walls stored |
| FR-005 | Volatility metrics calculated for watchlist | IV skew, term structure, P/C ratio stored |
| FR-006 | Price metrics calculated for watchlist | RVOL, VSI, HV stored |
| FR-007 | Wyckoff phase classification for watchlist | Phase (A-E) + confidence score stored daily |
| FR-008 | Wyckoff event detection (8 critical events) | Events detected with >70% accuracy |
| FR-009 | Trade recommendations generated with justification | Claude generates strategy + rationale |
| FR-010 | Recommendations use ONLY real strike/expiration data | Zero hallucinated strikes |
| FR-011 | Portfolio CRUD operations | Create, read, update, delete portfolios and tickers |
| FR-012 | Dashboard displays daily recommendations | Accessible via web browser |
| FR-013 | Directional accuracy tracking | Brier score calculated weekly |
| FR-014 | Alert on BC Score ≥ 24 | EXIT signal displayed prominently in dashboard |
| FR-015 | Alert on SPRING + SOS events | ENTRY signal displayed prominently in dashboard |
| FR-016 | Display all 8 Wyckoff events status | Each event shown with detection status, confidence, date |
| FR-017 | Event timeline per ticker | Visual timeline of event sequence progression |

#### P2 - Should Have

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-018 | Email daily summary | Sent by 6 AM ET |
| FR-019 | Email alert on BC Score ≥ 24 | Immediate notification |
| FR-020 | Filter recommendations by strategy/direction | UI filtering works |
| FR-021 | Screen universe by technical indicators | Query OHLCV for RSI < 30, etc. |

#### P3 - Nice to Have (Post-MVP)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-022 | Full 17 Wyckoff events | All events detected |
| FR-023 | 3-component success score | Profitability + timing added |
| FR-024 | Historical backfill (2 years) | Backtesting capability |

### 3.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Daily pipeline completion time | < 15 minutes for 100 watchlist tickers |
| NFR-002 | S3 OHLCV load time | < 60 seconds for full universe |
| NFR-003 | Dashboard response time | < 2 seconds page load |
| NFR-004 | System availability | 99% uptime (excluding maintenance) |
| NFR-005 | Data retention (OHLCV) | 3 years, compressed after 1 year |
| NFR-006 | Data retention (options chains) | 90 days |
| NFR-007 | Data retention (snapshots) | 2 years, compressed after 1 year |
| NFR-008 | Cost (infrastructure) | < $100/month |
| NFR-009 | Provider swappability | AI and market data providers swappable via config |

### 3.3 Constraints

| Constraint | Description |
|------------|-------------|
| **Budget** | < $100/month for hosting/tools |
| **Timeline** | MVP by December 31, 2025 |
| **Data Source** | Polygon.io Options Starter+ (100 RPS, unlimited requests) |
| **Portability** | Must run on any Docker-compatible host |
| **Real Data Only** | NO estimated/hallucinated data in recommendations |

---

## 4. ARCHITECTURE DECISIONS

### 4.1 Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY STACK                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FRONTEND          Next.js 14 + Shadcn/ui + Tailwind CSS               │
│                    TanStack Query for state                            │
│                                                                         │
│  API GATEWAY       TypeScript + Express.js                             │
│                    Drizzle ORM                                         │
│                                                                         │
│  CORE SERVICES     Python 3.11 + FastAPI                               │
│                    SQLAlchemy + asyncpg                                │
│                    APScheduler for batch jobs                          │
│                                                                         │
│  DATABASE          PostgreSQL 15 + TimescaleDB 2.x                     │
│                    Hypertables for time-series                         │
│                                                                         │
│  CACHE             Redis 7                                             │
│                                                                         │
│  EXTERNAL          Polygon S3 (OHLCV flat files)                       │
│                    Polygon API (Options chains)                        │
│                    Polygon MCP Server (Technical analysis)             │
│                    Claude API (Recommendations)                        │
│                                                                         │
│  INFRASTRUCTURE    Docker Compose (local)                              │
│                    Fly.io (production)                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Provider Abstraction Layer

```python
# AI Provider Interface
class AIProvider(Protocol):
    async def generate_recommendation(self, context: AnalysisContext) -> Recommendation: ...
    async def generate_justification(self, rec: Recommendation) -> str: ...
    def get_model_info(self) -> ModelInfo: ...

# Implementations
class ClaudeProvider(AIProvider):      # Default
class OpenAIProvider(AIProvider):      # Alternative

# Market Data Provider Interface  
class MarketDataProvider(Protocol):
    async def get_ohlcv(self, symbol: str, start: date, end: date) -> DataFrame: ...
    async def get_options_chain(self, symbol: str) -> OptionsChain: ...

# Implementations
class PolygonS3Provider(MarketDataProvider):   # OHLCV from S3 flat files
class PolygonAPIProvider(MarketDataProvider):  # Options, real-time quotes

# Metrics Provider (Polygon MCP)
class MetricsProvider(Protocol):
    async def get_technical_indicators(self, symbol: str) -> dict: ...
    async def get_dealer_metrics(self, symbol: str) -> dict: ...
    async def get_volatility_metrics(self, symbol: str) -> dict: ...
    async def get_price_metrics(self, symbol: str) -> dict: ...
```

### 4.3 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DAILY PIPELINE FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  04:00 ET ─► PHASE 1: S3 OHLCV LOAD (~30 sec)                          │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ Download: us_stocks_sip/day_aggs_v1/YYYY-MM-DD.csv.gz│    │
│             │ Parse: ~15K tickers in single file                  │    │
│             │ Insert: Bulk COPY to ohlcv_daily hypertable         │    │
│             │ Update: tickers.last_ohlcv_date                     │    │
│             └─────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  04:01 ET ─► PHASE 2: OPTIONS ENRICHMENT (~5 min, watchlist only)      │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ For each watchlist ticker (~100):                   │    │
│             │   • Polygon API: /v3/snapshot/options/{symbol}      │    │
│             │   • Store: options_chains (individual contracts)    │    │
│             │   • Aggregate: options_daily_summary                │    │
│             │ Rate: ~100 RPS, ~50 concurrent                      │    │
│             └─────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  04:06 ET ─► PHASE 3: METRICS CALCULATION (~3 min, watchlist only)     │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ For each watchlist ticker:                          │    │
│             │   • Polygon MCP: get_all_ta_indicators (84 values)  │    │
│             │   • Polygon MCP: get_dealer_metrics                 │    │
│             │   • Polygon MCP: get_volatility_metrics             │    │
│             │   • Polygon MCP: get_price_metrics                  │    │
│             └─────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  04:09 ET ─► PHASE 4: WYCKOFF ANALYSIS (~3 min, watchlist only)        │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ For each watchlist ticker:                          │    │
│             │   • Phase classification (A-E)                      │    │
│             │   • Event detection (8 MVP events)                  │    │
│             │   • BC/Spring scoring                               │    │
│             │   • Store: daily_snapshots (45+ columns)            │    │
│             └─────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  04:12 ET ─► PHASE 5: RECOMMENDATIONS (~5 min, P1 tickers only)        │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ For P1 tickers with actionable signals:             │    │
│             │   • Claude API: Generate recommendation             │    │
│             │   • Validate: Real strikes from options_chains      │    │
│             │   • Store: recommendations table                    │    │
│             └─────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│  04:17 ET ─► PHASE 6: NOTIFICATIONS                                    │
│             ┌─────────────────────────────────────────────────────┐    │
│             │ • Generate daily summary                            │    │
│             │ • Check BC >= 24 alerts                             │    │
│             │ • Email if enabled (P2)                             │    │
│             └─────────────────────────────────────────────────────┘    │
│                                                                         │
│  ~04:20 ET  PIPELINE COMPLETE                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DATA MODEL

### 5.1 Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KAPMAN DATA MODEL v2.0                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  UNIVERSE LAYER (Full Polygon ~15K Tickers)                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ohlcv_daily (TimescaleDB Hypertable)                               │   │
│  │  • Full market universe stored daily                                │   │
│  │  • 3-year retention, compressed after 1 year                        │   │
│  │  • ~15K tickers × 252 days = 3.8M rows/year                         │   │
│  │  • Enables screening: WHERE rsi_14 < 30 across all tickers          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  WATCHLIST LAYER (Portfolio Tickers ~50-100)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  options_chains          → Raw contract-level data (90-day)         │   │
│  │  options_daily_summary   → Aggregated OI, Greeks, walls per symbol  │   │
│  │  daily_snapshots         → 45+ columns: Wyckoff + all metrics       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  RECOMMENDATION LAYER                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  recommendations         → Trade suggestions with justification     │   │
│  │  recommendation_outcomes → Accuracy tracking (Brier scores)         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  REFERENCE LAYER                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  tickers                 → Universe with tier classification        │   │
│  │  portfolios              → Watchlist groupings                      │   │
│  │  portfolio_tickers       → Many-to-many with priority (P1/P2)       │   │
│  │  model_parameters        → Algorithm version control                │   │
│  │  job_runs                → Pipeline audit trail                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│   portfolios    │       │    tickers      │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ name            │       │ symbol (unique) │
│ description     │       │ name            │
│ created_at      │       │ sector          │
│ updated_at      │       │ universe_tier   │  ← NEW: sp500/russell3000/polygon_full/custom
└────────┬────────┘       │ is_active       │
         │                │ options_enabled │  ← NEW: fetch options for this ticker?
         │                │ last_ohlcv_date │  ← NEW: data freshness tracking
         │                │ last_analysis_date│← NEW: analysis freshness
         │                └────────┬────────┘
         │                         │
         │    ┌────────────────────┘
         ▼    ▼
┌─────────────────────┐
│ portfolio_tickers   │
├─────────────────────┤
│ portfolio_id (FK)   │
│ ticker_id (FK)      │
│ priority (P1/P2)    │
│ added_at            │
└─────────────────────┘

                    HYPERTABLES (Time-Series)
┌─────────────────────────────────────────────────────────────────────────────┐
│ ohlcv_daily                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ time (PK), symbol (PK), open, high, low, close, volume, vwap, source       │
│ Retention: 3 years │ Compression: after 1 year │ Universe: ~15K tickers    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ options_chains                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ time (PK), symbol, expiration, strike, option_type (PK)                    │
│ bid, ask, last, volume, open_interest                                      │
│ implied_volatility, delta, gamma, theta, vega                              │
│ Retention: 90 days │ Scope: watchlist only                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ options_daily_summary (NEW)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ time (PK), symbol (PK)                                                     │
│ total_call_oi, total_put_oi, total_call_volume, total_put_volume          │
│ put_call_oi_ratio (generated), put_call_volume_ratio (generated)          │
│ weighted_avg_iv                                                            │
│ top_call_strike_1/2/3, top_call_oi_1/2/3 (resistance walls)               │
│ top_put_strike_1/2/3, top_put_oi_1/2/3 (support walls)                    │
│ total_call_gamma, total_put_gamma, total_call_delta, total_put_delta      │
│ calculated_gex, calculated_net_gex                                         │
│ Retention: 90 days │ Purpose: dealer calculations source                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ daily_snapshots (ENHANCED - 45+ columns)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ IDENTITY:          time (PK), symbol (PK)                                  │
│                                                                             │
│ WYCKOFF PHASE:     wyckoff_phase (A-E), phase_score, phase_confidence      │
│                    phase_sub_stage                                          │
│                                                                             │
│ WYCKOFF EVENTS:    events_detected[], primary_event, primary_event_confidence│
│                    events_json (JSONB)                                      │
│                                                                             │
│ WYCKOFF SCORES:    bc_score (0-28), spring_score (0-12), composite_score   │
│                                                                             │
│ TECHNICAL-MOMENTUM: rsi_14, macd_line, macd_signal, macd_histogram         │
│                    stoch_k, stoch_d, mfi_14                                 │
│                                                                             │
│ TECHNICAL-TREND:   sma_20, sma_50, sma_200, ema_12, ema_26, adx_14        │
│                                                                             │
│ TECHNICAL-VOL:     atr_14, bbands_upper, bbands_middle, bbands_lower       │
│                    bbands_width                                             │
│                                                                             │
│ TECHNICAL-VOLUME:  obv, vwap                                               │
│                                                                             │
│ DEALER METRICS:    gex_total, gex_net, gamma_flip_level                    │
│                    call_wall_primary, call_wall_primary_oi                 │
│                    put_wall_primary, put_wall_primary_oi                   │
│                    dgpi (-100 to +100), dealer_position                     │
│                                                                             │
│ VOLATILITY:        iv_skew_25d, iv_term_structure                          │
│                    put_call_ratio_oi, put_call_ratio_volume                │
│                    average_iv, iv_rank, iv_percentile                      │
│                                                                             │
│ PRICE METRICS:     rvol, vsi, hv_20, hv_60, iv_hv_diff                    │
│                    price_vs_sma20, price_vs_sma50, price_vs_sma200        │
│                                                                             │
│ JSONB STORAGE:     technical_indicators_json (all 84 indicators)           │
│                    dealer_metrics_json, volatility_metrics_json            │
│                    price_metrics_json, checklist_json                      │
│                                                                             │
│ METADATA:          volatility_regime, model_version, data_quality          │
│                                                                             │
│ Retention: 2 years │ Compression: after 1 year │ Scope: watchlist only     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ recommendations                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ id (PK), snapshot_time (FK), snapshot_symbol (FK)                          │
│ symbol, recommendation_date, direction, action, confidence                  │
│ justification (text), entry_price_target, stop_loss, profit_target         │
│ option_strike, option_expiration, option_type, option_strategy             │
│ status (active/closed/expired), model_version                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ recommendation_outcomes                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ id (PK), recommendation_id (FK), evaluation_date                           │
│ entry_price_actual, exit_price_actual, direction_correct                   │
│ predicted_confidence, directional_brier, success_score_v1                  │
│ outcome_status (WIN/LOSS/NEUTRAL)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 daily_snapshots Column Reference

| Category | Column | Type | Source | Description |
|----------|--------|------|--------|-------------|
| **Identity** | time | TIMESTAMPTZ | System | Snapshot timestamp |
| | symbol | VARCHAR(20) | System | Ticker symbol |
| **Wyckoff Phase** | wyckoff_phase | CHAR(1) | Wyckoff Engine | Phase A-E |
| | phase_score | NUMERIC(4,3) | Wyckoff Engine | Phase confidence |
| | phase_confidence | NUMERIC(4,3) | Wyckoff Engine | Overall confidence |
| | phase_sub_stage | VARCHAR(20) | Wyckoff Engine | Sub-stage detail |
| **Wyckoff Events** | events_detected | VARCHAR(20)[] | Wyckoff Engine | Array of events |
| | primary_event | VARCHAR(20) | Wyckoff Engine | Most significant |
| | primary_event_confidence | NUMERIC(4,3) | Wyckoff Engine | Event confidence |
| | events_json | JSONB | Wyckoff Engine | Full event details |
| **Wyckoff Scores** | bc_score | INTEGER | Wyckoff Engine | Buying Climax 0-28 |
| | spring_score | INTEGER | Wyckoff Engine | Spring 0-12 |
| | composite_score | NUMERIC(4,3) | Wyckoff Engine | Combined score |
| **Tech-Momentum** | rsi_14 | NUMERIC(6,2) | Polygon MCP | RSI 14-period |
| | macd_line | NUMERIC(12,4) | Polygon MCP | MACD line |
| | macd_signal | NUMERIC(12,4) | Polygon MCP | MACD signal |
| | macd_histogram | NUMERIC(12,4) | Polygon MCP | MACD histogram |
| | stoch_k | NUMERIC(6,2) | Polygon MCP | Stochastic %K |
| | stoch_d | NUMERIC(6,2) | Polygon MCP | Stochastic %D |
| | mfi_14 | NUMERIC(6,2) | Polygon MCP | Money Flow Index |
| **Tech-Trend** | sma_20 | NUMERIC(12,4) | Polygon MCP | 20-day SMA |
| | sma_50 | NUMERIC(12,4) | Polygon MCP | 50-day SMA |
| | sma_200 | NUMERIC(12,4) | Polygon MCP | 200-day SMA |
| | ema_12 | NUMERIC(12,4) | Polygon MCP | 12-day EMA |
| | ema_26 | NUMERIC(12,4) | Polygon MCP | 26-day EMA |
| | adx_14 | NUMERIC(6,2) | Polygon MCP | ADX trend strength |
| **Tech-Volatility** | atr_14 | NUMERIC(12,4) | Polygon MCP | 14-day ATR |
| | bbands_upper | NUMERIC(12,4) | Polygon MCP | Bollinger upper |
| | bbands_middle | NUMERIC(12,4) | Polygon MCP | Bollinger middle |
| | bbands_lower | NUMERIC(12,4) | Polygon MCP | Bollinger lower |
| | bbands_width | NUMERIC(8,4) | Calculated | Band width % |
| **Tech-Volume** | obv | BIGINT | Polygon MCP | On-Balance Volume |
| | vwap | NUMERIC(12,4) | OHLCV | VWAP |
| **Dealer Metrics** | gex_total | NUMERIC(18,2) | Polygon MCP | Total Gamma Exposure |
| | gex_net | NUMERIC(18,2) | Polygon MCP | Net directional GEX |
| | gamma_flip_level | NUMERIC(12,4) | Polygon MCP | Gamma flip price |
| | call_wall_primary | NUMERIC(12,2) | Polygon MCP | Top call OI strike |
| | call_wall_primary_oi | INTEGER | Polygon MCP | OI at call wall |
| | put_wall_primary | NUMERIC(12,2) | Polygon MCP | Top put OI strike |
| | put_wall_primary_oi | INTEGER | Polygon MCP | OI at put wall |
| | dgpi | NUMERIC(5,2) | Polygon MCP | Dealer Gamma Pressure -100 to +100 |
| | dealer_position | VARCHAR(15) | Polygon MCP | long_gamma/short_gamma/neutral |
| **Volatility** | iv_skew_25d | NUMERIC(6,4) | Polygon MCP | 25-delta IV skew |
| | iv_term_structure | NUMERIC(6,4) | Polygon MCP | IV term structure |
| | put_call_ratio_oi | NUMERIC(6,4) | Polygon MCP | P/C ratio (OI) |
| | put_call_ratio_volume | NUMERIC(6,4) | Polygon MCP | P/C ratio (volume) |
| | average_iv | NUMERIC(6,4) | Polygon MCP | Weighted avg IV |
| | iv_rank | NUMERIC(5,2) | Calculated | IV rank 0-100 |
| | iv_percentile | NUMERIC(5,2) | Calculated | IV percentile 0-100 |
| **Price Metrics** | rvol | NUMERIC(8,4) | Polygon MCP | Relative Volume |
| | vsi | NUMERIC(8,4) | Polygon MCP | Volume Surge Index |
| | hv_20 | NUMERIC(6,4) | Polygon MCP | 20-day HV |
| | hv_60 | NUMERIC(6,4) | Polygon MCP | 60-day HV |
| | iv_hv_diff | NUMERIC(6,4) | Calculated | IV minus HV |
| | price_vs_sma20 | NUMERIC(6,4) | Calculated | Price % from SMA20 |
| | price_vs_sma50 | NUMERIC(6,4) | Calculated | Price % from SMA50 |
| | price_vs_sma200 | NUMERIC(6,4) | Calculated | Price % from SMA200 |
| **JSONB** | technical_indicators_json | JSONB | Polygon MCP | All 84 indicators |
| | dealer_metrics_json | JSONB | Polygon MCP | Full dealer data |
| | volatility_metrics_json | JSONB | Polygon MCP | Full vol data |
| | price_metrics_json | JSONB | Polygon MCP | Full price data |
| | checklist_json | JSONB | Wyckoff Engine | 9-step checklist |
| **Metadata** | volatility_regime | VARCHAR(20) | Calculated | low/normal/high/extreme |
| | model_version | VARCHAR(50) | System | Algorithm version |
| | data_quality | VARCHAR(20) | System | complete/partial/stale |

### 5.4 Wyckoff Events Reference (MVP: 8 Events)

| Event | Code | Phase | Description | Detection Signals |
|-------|------|-------|-------------|-------------------|
| Selling Climax | SC | A | Panic selling, high volume | Volume >2x avg, wide range, close near low |
| Automatic Rally | AR | A | Quick bounce after SC | Rally on declining volume |
| Secondary Test | ST | A | Retest of SC area | Lower volume than SC, higher low |
| Spring | SPRING | A | False breakdown | Break support, quick recovery, low volume |
| Test of Spring | TEST | A | Validate spring | Low volume retest of spring area |
| Sign of Strength | SOS | A→B | Breakout signal | High volume rally, break resistance |
| Buying Climax | BC | D | Euphoric buying | Volume >2x avg, wide range at highs |
| Sign of Weakness | SOW | D | Breakdown signal | High volume drop, break support |

### 5.5 Wyckoff Event Dashboard Specification

The dashboard displays the status of all 8 MVP Wyckoff events per ticker, with clear ENTRY and EXIT signals.

#### Signal Classification

| Signal Type | Events | Visual Indicator | Action |
|-------------|--------|------------------|--------|
| **🟢 ENTRY** | SPRING, SOS, TEST | Green badge | Consider opening position |
| **🔴 EXIT** | BC (score ≥ 24) | Red badge, prominent | Close position immediately |
| **🟡 CAUTION** | BC (score ≥ 20), SOW | Yellow badge | Prepare exit, monitor closely |
| **🔵 ACCUMULATION** | SC, AR, ST | Blue badge | Building phase, watch for entry |
| **⚪ NEUTRAL** | No events | Gray | No actionable signal |

#### Event Status Display per Ticker

| Column | Description | Example |
|--------|-------------|---------|
| Symbol | Ticker | NVDA |
| Phase | Current Wyckoff phase | A (Accumulation) |
| Primary Event | Most recent/significant event | SPRING |
| Event Confidence | Detection confidence | 85% |
| Days Since Event | How long ago detected | 2 days |
| BC Score | Buying Climax score 0-28 | 8 |
| Spring Score | Spring score 0-12 | 10 |
| Signal | Actionable signal | 🟢 ENTRY |

#### Event Timeline per Ticker

```
NVDA - Accumulation Phase (65% confidence)
┌──────────────────────────────────────────────────────────────────┐
│  SC      AR      ST      SPRING    TEST     SOS                 │
│  ✅      ✅      ✅       ✅        🔄       ⬜                  │
│ Nov 15  Nov 18  Nov 25   Dec 2    Dec 8    Pending              │
│                                                                  │
│  Current: TEST in progress (72% confidence)                     │
│  Next Expected: SOS (Sign of Strength)                          │
│  Signal: 🟢 ENTRY - Spring confirmed, awaiting SOS breakout     │
└──────────────────────────────────────────────────────────────────┘

Legend: ✅ Detected  🔄 In Progress  ⬜ Pending  ❌ Failed
```

#### Alert Priority Levels

| Priority | Condition | Dashboard Treatment |
|----------|-----------|---------------------|
| **CRITICAL** | BC Score ≥ 24 | Red banner, top of page, audio alert option |
| **HIGH** | SPRING + SOS detected | Green highlight, notification badge |
| **MEDIUM** | BC Score ≥ 20, SOW detected | Yellow highlight |
| **LOW** | Other events (SC, AR, ST, TEST) | Normal display |
| **INFO** | Phase transition | Log entry |

#### Events JSON Structure (stored in daily_snapshots.events_json)

```json
{
  "events": [
    {
      "type": "SPRING",
      "detected_at": "2025-12-02",
      "confidence": 0.85,
      "price_level": 142.30,
      "volume_ratio": 0.6,
      "description": "False breakdown with quick recovery",
      "is_active": true
    },
    {
      "type": "TEST",
      "detected_at": "2025-12-08",
      "confidence": 0.72,
      "price_level": 143.50,
      "volume_ratio": 0.4,
      "description": "Low volume retest of spring area",
      "is_active": true
    }
  ],
  "sequence_position": 5,
  "expected_next": ["SOS"],
  "pattern_completion_pct": 0.65,
  "entry_signal": true,
  "exit_signal": false,
  "signal_strength": "STRONG",
  "signal_message": "SPRING confirmed, TEST in progress - favorable entry setup"
}
```

### 5.6 Helper Views

```sql
-- v_latest_snapshots: Most recent snapshot per symbol
SELECT DISTINCT ON (symbol) symbol, time, wyckoff_phase, bc_score, ...
FROM daily_snapshots ORDER BY symbol, time DESC;

-- v_watchlist_tickers: Tickers in portfolios needing analysis
SELECT t.symbol, pt.priority, p.name as portfolio_name
FROM tickers t JOIN portfolio_tickers pt ... WHERE t.is_active = true;

-- v_alerts: Active alert conditions with signal classification
CREATE OR REPLACE VIEW v_alerts AS
-- CRITICAL: BC Exit Signal
SELECT 
    symbol, time, 'EXIT_CRITICAL' as signal_type,
    'BC_CRITICAL' as alert_type, bc_score as alert_value,
    '🔴 EXIT IMMEDIATELY - BC Score ≥ 24' as alert_message,
    1 as priority
FROM daily_snapshots
WHERE bc_score >= 24 AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- HIGH: Entry Signal (SPRING + SOS)
SELECT 
    symbol, time, 'ENTRY_SIGNAL' as signal_type,
    'SPRING_SOS' as alert_type, spring_score as alert_value,
    '🟢 ENTRY SIGNAL - Spring confirmed with SOS' as alert_message,
    2 as priority
FROM daily_snapshots
WHERE 'SPRING' = ANY(events_detected) 
  AND 'SOS' = ANY(events_detected)
  AND bc_score < 12
  AND time > NOW() - INTERVAL '14 days'

UNION ALL

-- HIGH: Strong Entry Setup (SPRING confirmed)
SELECT 
    symbol, time, 'ENTRY_SETUP' as signal_type,
    'SPRING_CONFIRMED' as alert_type, spring_score as alert_value,
    '🟢 ENTRY SETUP - Spring Score ≥ 9' as alert_message,
    3 as priority
FROM daily_snapshots
WHERE spring_score >= 9
  AND bc_score < 12
  AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: Caution Exit Warning
SELECT 
    symbol, time, 'EXIT_WARNING' as signal_type,
    'BC_WARNING' as alert_type, bc_score as alert_value,
    '🟡 CAUTION - BC Score ≥ 20, prepare exit' as alert_message,
    4 as priority
FROM daily_snapshots
WHERE bc_score >= 20 AND bc_score < 24
  AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- MEDIUM: Distribution Warning
SELECT 
    symbol, time, 'EXIT_WARNING' as signal_type,
    'SOW_DETECTED' as alert_type, 
    primary_event_confidence as alert_value,
    '🟡 CAUTION - Sign of Weakness detected' as alert_message,
    5 as priority
FROM daily_snapshots
WHERE primary_event = 'SOW'
  AND time > NOW() - INTERVAL '7 days'

UNION ALL

-- LOW: Volume Surge (potential event confirmation)
SELECT 
    symbol, time, 'INFO' as signal_type,
    'VOLUME_SURGE' as alert_type, vsi as alert_value,
    '🔵 INFO - Volume Surge Index > 2' as alert_message,
    6 as priority
FROM daily_snapshots
WHERE vsi > 2
  AND time > NOW() - INTERVAL '7 days'

ORDER BY priority, time DESC;

-- v_wyckoff_events: Current event status for all watchlist tickers
CREATE OR REPLACE VIEW v_wyckoff_events AS
SELECT 
    s.symbol,
    s.time,
    s.wyckoff_phase,
    s.phase_confidence,
    s.events_detected,
    s.primary_event,
    s.primary_event_confidence,
    s.bc_score,
    s.spring_score,
    -- Signal classification
    CASE 
        WHEN s.bc_score >= 24 THEN 'EXIT_CRITICAL'
        WHEN s.bc_score >= 20 THEN 'EXIT_WARNING'
        WHEN s.spring_score >= 9 AND s.bc_score < 12 THEN 'ENTRY_SIGNAL'
        WHEN 'SPRING' = ANY(s.events_detected) THEN 'ENTRY_SETUP'
        WHEN 'SOS' = ANY(s.events_detected) THEN 'ENTRY_SIGNAL'
        WHEN 'SOW' = ANY(s.events_detected) THEN 'EXIT_WARNING'
        ELSE 'NEUTRAL'
    END as signal_type,
    -- Individual event status
    'SC' = ANY(s.events_detected) as has_sc,
    'AR' = ANY(s.events_detected) as has_ar,
    'ST' = ANY(s.events_detected) as has_st,
    'SPRING' = ANY(s.events_detected) as has_spring,
    'TEST' = ANY(s.events_detected) as has_test,
    'SOS' = ANY(s.events_detected) as has_sos,
    'BC' = ANY(s.events_detected) as has_bc,
    'SOW' = ANY(s.events_detected) as has_sow,
    -- Event count for sequence tracking
    array_length(s.events_detected, 1) as events_count,
    s.events_json
FROM daily_snapshots s
WHERE s.time = (
    SELECT MAX(time) FROM daily_snapshots WHERE symbol = s.symbol
);
```

### 5.6 Storage Estimates

| Table | Rows/Day | Rows/Year | Size/Year | Retention |
|-------|----------|-----------|-----------|-----------|
| ohlcv_daily | 15,000 | 3.8M | ~2GB | 3 years |
| options_chains | 50,000 | 12.6M | ~5GB | 90 days |
| options_daily_summary | 100 | 25K | ~50MB | 90 days |
| daily_snapshots | 100 | 25K | ~100MB | 2 years |
| recommendations | 10 | 2.5K | ~10MB | Indefinite |
| **Total/Year** | | | **~7-8GB** | |
| **After Compression** | | | **~3GB** | |

---

## 6. SERVICE ARCHITECTURE

### 6.1 Service Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KAPMAN TRADING SYSTEM v2.0                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐                                                  │
│  │     FRONTEND      │  Next.js 14 + Shadcn/ui                         │
│  │    Port: 3000     │  • Portfolio management                         │
│  │                   │  • Recommendations dashboard                    │
│  │                   │  • Alerts display                               │
│  └─────────┬─────────┘                                                  │
│            │                                                            │
│            ▼                                                            │
│  ┌───────────────────┐         ┌───────────────────┐                   │
│  │   API GATEWAY     │         │   PYTHON CORE     │                   │
│  │   (Express/TS)    │◄───────►│   (FastAPI)       │                   │
│  │   Port: 4000      │         │   Port: 5000      │                   │
│  │                   │         │                   │                   │
│  │ • REST routes     │         │ • S3 OHLCV loader │                   │
│  │ • Validation      │         │ • Options loader  │                   │
│  │ • Portfolio CRUD  │         │ • Metrics calc    │                   │
│  │                   │         │ • Wyckoff engine  │                   │
│  │                   │         │ • Recommendations │                   │
│  │                   │         │ • Scheduler       │                   │
│  └─────────┬─────────┘         └─────────┬─────────┘                   │
│            │                             │                              │
│            ▼                             ▼                              │
│  ┌───────────────────────────────────────────────────────┐             │
│  │                    DATA LAYER                          │             │
│  │  ┌─────────────────┐    ┌─────────────────┐           │             │
│  │  │  TimescaleDB    │    │     Redis       │           │             │
│  │  │  Port: 5432     │    │   Port: 6379    │           │             │
│  │  └─────────────────┘    └─────────────────┘           │             │
│  └───────────────────────────────────────────────────────┘             │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ EXTERNAL SERVICES                                                       │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│ │ Polygon S3   │ │ Polygon API  │ │ Polygon MCP  │ │ Claude API   │    │
│ │ (OHLCV)      │ │ (Options)    │ │ (Metrics)    │ │ (Recommend)  │    │
│ │ ~15K tickers │ │ 100 RPS      │ │ 84 indicators│ │ Swappable    │    │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Directory Structure

```
kapman-trader/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
├── KAPMAN_ARCHITECTURE_v2.0.md      ← This document
│
├── frontend/                         # Next.js application
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── app/                      # App Router
│   │   ├── components/
│   │   └── lib/
│
├── api/                              # TypeScript API Gateway
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── routes/
│   │   ├── middleware/
│   │   ├── services/
│   │   └── db/
│
├── core/                             # Python Core Services
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py
│   ├── config.py
│   │
│   ├── providers/                    # Abstraction layers
│   │   ├── ai/
│   │   │   ├── base.py
│   │   │   ├── claude.py
│   │   │   └── openai.py
│   │   └── market_data/
│   │       ├── base.py
│   │       ├── polygon_s3.py
│   │       └── polygon_api.py
│   │
│   ├── pipeline/                     # Data pipeline
│   │   ├── s3_universe_loader.py     # Full OHLCV load
│   │   ├── options_loader.py         # Watchlist options
│   │   ├── metrics_calculator.py     # MCP integration
│   │   ├── daily_job.py              # Orchestrator
│   │   └── scheduler.py
│   │
│   ├── wyckoff/                      # Wyckoff engine
│   │   ├── phase.py
│   │   ├── events.py
│   │   ├── scoring.py
│   │   └── models.py
│   │
│   ├── recommendations/              # Claude integration
│   │   ├── generator.py
│   │   ├── strike_selector.py
│   │   └── prompts.py
│   │
│   ├── scoring/                      # Accuracy tracking
│   │   ├── brier.py
│   │   └── evaluator.py
│   │
│   └── api/                          # FastAPI routes
│       └── routes.py
│
├── db/                               # Database
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_create_hypertables.sql
│   │   ├── 003_retention_policies.sql
│   │   └── 004_enhanced_metrics_schema.sql  ← NEW
│   └── seed/
│
├── docs/                             # Documentation
│   ├── DATA_MODEL_v1.1.md
│   └── SPRINT_2_REVISED.md
│
└── scripts/
    ├── setup-dev.sh
    ├── deploy-fly.sh
    └── backfill-historical.py
```

---

## 7. API SPECIFICATION

### 7.1 API Gateway Endpoints (Port 4000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Portfolio** | | |
| GET | `/api/portfolios` | List all portfolios |
| POST | `/api/portfolios` | Create portfolio |
| GET | `/api/portfolios/:id` | Get portfolio detail |
| PATCH | `/api/portfolios/:id` | Update portfolio |
| DELETE | `/api/portfolios/:id` | Delete portfolio |
| POST | `/api/portfolios/:id/tickers` | Add tickers |
| DELETE | `/api/portfolios/:id/tickers/:tid` | Remove ticker |
| **Tickers** | | |
| GET | `/api/tickers` | List tracked tickers |
| GET | `/api/tickers/:symbol` | Get ticker with latest snapshot |
| GET | `/api/tickers/:symbol/snapshots` | Historical snapshots |
| GET | `/api/tickers/:symbol/options` | Current options chain |
| **Analysis** | | |
| POST | `/api/analyze` | Batch analyze symbols |
| GET | `/api/events/recent` | Recent Wyckoff events |
| **Recommendations** | | |
| GET | `/api/recommendations` | List recommendations |
| GET | `/api/recommendations/:id` | Get detail |
| POST | `/api/recommendations/generate` | Generate new |
| **Jobs** | | |
| POST | `/api/jobs/daily` | Trigger daily job |
| GET | `/api/jobs/daily/status` | Job status |
| GET | `/api/jobs/history` | Recent runs |
| **Dashboard** | | |
| GET | `/api/dashboard/alerts` | Active alerts |
| GET | `/api/dashboard/summary` | Portfolio summary |

### 7.2 Python Core Endpoints (Port 5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/pipeline/daily` | Run full daily pipeline |
| POST | `/pipeline/ohlcv` | Load OHLCV from S3 |
| POST | `/pipeline/options` | Load options for watchlist |
| POST | `/analyze/{symbol}` | Single symbol analysis |
| POST | `/recommend` | Generate recommendation |
| GET | `/health` | Health check |

---

## 8. IMPLEMENTATION ROADMAP

### 8.1 Timeline Overview

```
Week 1: Dec 7-13   │ Sprint 1: Infrastructure ✅ COMPLETED
Week 2: Dec 14-20  │ Sprint 2: Wyckoff Engine & Pipeline (REVISED)
Week 3: Dec 21-27  │ Sprint 3: Recommendations & Dashboard
Week 4: Dec 28-31  │ Sprint 4: Deployment & Hardening
```

### 8.2 Sprint Summary

| Sprint | Week | Points | Status |
|--------|------|--------|--------|
| Sprint 1: Infrastructure | Dec 7-13 | 21 | ✅ COMPLETED |
| Sprint 2: Wyckoff & Pipeline | Dec 14-20 | 28 | 🔄 REVISED |
| Sprint 3: Recommendations & UI | Dec 21-27 | 18 | Planned |
| Sprint 4: Deployment | Dec 28-31 | 10 | Planned |
| **TOTAL** | | **77** | |

---

## 9. PRE-SPRINT 2 SETUP: APPLYING SCHEMA ENHANCEMENTS

Before starting Sprint 2, you must apply Migration 004 to add the enhanced metrics schema. This section provides step-by-step instructions.

### 9.1 Prerequisites Checklist

| Item | Check | Notes |
|------|-------|-------|
| Sprint 1 completed | ☐ | Migrations 001-003 applied |
| Docker running | ☐ | `docker-compose up -d` |
| Database accessible | ☐ | Can connect to TimescaleDB |
| Migration 004 file ready | ☐ | `db/migrations/004_enhanced_metrics_schema.sql` |

### 9.2 Step-by-Step Migration Process

#### Step 1: Verify Current Database State

```bash
# Connect to database and check existing tables
docker exec kapman-db psql -U kapman kapman -c "\dt"

# Verify hypertables exist
docker exec kapman-db psql -U kapman kapman -c "
SELECT hypertable_name FROM timescaledb_information.hypertables;
"

# Expected output should include:
# - ohlcv_daily
# - options_chains
# - daily_snapshots
```

#### Step 2: Backup Current Database

```bash
# Create backup before migration
docker exec kapman-db pg_dump -U kapman kapman > backup_pre_migration_004_$(date +%Y%m%d_%H%M%S).sql

# Verify backup was created
ls -la backup_pre_migration_004_*.sql
```

#### Step 3: Review Migration 004

The migration adds:

| Category | Changes |
|----------|---------|
| **tickers table** | +4 columns: universe_tier, last_ohlcv_date, last_analysis_date, options_enabled |
| **daily_snapshots** | +30 columns for technical, dealer, volatility, price metrics |
| **New table** | options_daily_summary (aggregated options data) |
| **New views** | v_alerts, v_wyckoff_events, v_entry_signals, v_exit_signals |
| **New functions** | fn_symbols_needing_ohlcv, fn_watchlist_needing_analysis |
| **Seed data** | Common ETFs (SPY, QQQ, IWM, etc.) |

#### Step 4: Apply Migration 004

```bash
# Apply the migration
docker exec -i kapman-db psql -U kapman kapman < db/migrations/004_enhanced_metrics_schema.sql

# Expected: Multiple "ALTER TABLE", "CREATE INDEX", "CREATE VIEW" messages
# Should complete without errors
```

#### Step 5: Verify Migration Success

```bash
# Check daily_snapshots has new columns
docker exec kapman-db psql -U kapman kapman -c "
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'daily_snapshots' 
  AND column_name IN ('rsi_14', 'gex_total', 'iv_skew_25d', 'rvol')
ORDER BY column_name;
"

# Expected output:
#  column_name  |     data_type
# --------------+-------------------
#  gex_total    | numeric
#  iv_skew_25d  | numeric
#  rvol         | numeric
#  rsi_14       | numeric

# Check new table exists
docker exec kapman-db psql -U kapman kapman -c "\d options_daily_summary"

# Check views exist
docker exec kapman-db psql -U kapman kapman -c "
SELECT viewname FROM pg_views 
WHERE schemaname = 'public' 
  AND viewname LIKE 'v_%'
ORDER BY viewname;
"

# Expected output:
#       viewname
# --------------------
#  v_alerts
#  v_entry_signals
#  v_exit_signals
#  v_latest_snapshots
#  v_watchlist_tickers
#  v_wyckoff_events

# Check tickers have new columns
docker exec kapman-db psql -U kapman kapman -c "
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'tickers' 
  AND column_name IN ('universe_tier', 'last_ohlcv_date', 'options_enabled');
"

# Check seed data loaded
docker exec kapman-db psql -U kapman kapman -c "
SELECT symbol, universe_tier, options_enabled FROM tickers WHERE universe_tier = 'etf';
"
```

#### Step 6: Test Helper Views

```bash
# Test v_alerts (will be empty until data is loaded)
docker exec kapman-db psql -U kapman kapman -c "SELECT * FROM v_alerts LIMIT 5;"

# Test v_wyckoff_events (will be empty until data is loaded)
docker exec kapman-db psql -U kapman kapman -c "SELECT * FROM v_wyckoff_events LIMIT 5;"
```

### 9.3 Troubleshooting Migration Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `relation "daily_snapshots" does not exist` | Migrations 001-003 not applied | Apply migrations in order |
| `column "X" already exists` | Migration partially applied | Drop column manually or restore from backup |
| `permission denied` | Wrong user | Use `-U kapman` flag |
| `extension "uuid-ossp" not found` | Extension not installed | Run `CREATE EXTENSION "uuid-ossp";` |
| `hypertable not found` | TimescaleDB not enabled | Run `CREATE EXTENSION timescaledb;` |

### 9.4 Rollback Procedure (If Needed)

```bash
# Only if migration fails and you need to restore
docker exec -i kapman-db psql -U kapman kapman < backup_pre_migration_004_YYYYMMDD_HHMMSS.sql
```

### 9.5 Post-Migration: Ready for Sprint 2

After successful migration, verify you're ready for Sprint 2:

```bash
# Final verification script
docker exec kapman-db psql -U kapman kapman -c "
SELECT 
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'daily_snapshots') as snapshot_columns,
  (SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'options_daily_summary') as summary_table,
  (SELECT COUNT(*) FROM pg_views WHERE viewname LIKE 'v_%') as views_count,
  (SELECT COUNT(*) FROM tickers WHERE universe_tier IS NOT NULL) as seeded_tickers;
"

# Expected output:
#  snapshot_columns | summary_table | views_count | seeded_tickers
# ------------------+---------------+-------------+----------------
#                55 |             1 |           6 |             12
```

✅ **Migration 004 complete - proceed to Sprint 2!**

---

## 10. SPRINT 1: INFRASTRUCTURE (COMPLETED)

### 12.1 Completed Stories

| Story | Points | Status |
|-------|--------|--------|
| 1.1 Dev Environment Setup | 5 | ✅ |
| 1.2 Database Setup (Migrations 001-003) | 5 | ✅ |
| 1.3 Provider Abstraction Layer | 5 | ✅ |
| 1.4 S3 OHLCV Pipeline (Basic) | 6 | ✅ |

---

## 11. SPRINT 2: WYCKOFF ENGINE & PIPELINE

**Duration:** December 14-20, 2025  
**Total Points:** 28
**Prerequisite:** Migration 004 applied (see Section 9)

### 12.1 Story Overview

| Story | Points | Description |
|-------|--------|-------------|
| 2.1 S3 Universe Loader | 6 | Full ~15K ticker OHLCV load |
| 2.2 Options Chain Pipeline | 6 | Watchlist options + summary aggregation |
| 2.3 Metrics Integration | 4 | Polygon MCP for TA, dealer, vol, price |
| 2.4 Wyckoff Engine Migration | 6 | Port existing logic, 8 events |
| 2.5 Daily Batch Orchestrator | 6 | Full pipeline coordination |

### 12.2 Story 2.1: S3 Universe Loader (6 pts)

**File:** `core/pipeline/s3_universe_loader.py`

**Key Implementation:**
```python
class S3UniverseLoader:
    async def load_daily(self, target_date: date) -> dict:
        # Download single daily file (~10MB gzipped)
        # Contains ALL ~15K tickers
        df = await self._download_daily_file(target_date)
        
        # Bulk insert via COPY
        loaded = await self._bulk_insert(df)
        
        # Update tickers.last_ohlcv_date
        await self._update_ticker_dates(df['symbol'].unique(), target_date)
        
        return {"loaded": loaded, "tickers": len(df['symbol'].unique())}
```

**Acceptance Criteria:**
- [ ] Single day loads ~15K tickers in < 60 seconds
- [ ] Tickers auto-created with universe_tier='polygon_full'
- [ ] last_ohlcv_date updated correctly

### 12.3 Story 2.2: Options Chain Pipeline (6 pts)

**File:** `core/pipeline/options_loader.py`

**Key Implementation:**
```python
class OptionsChainLoader:
    async def load_watchlist_options(self, target_date: date) -> dict:
        symbols = await self._get_watchlist_symbols()  # ~100
        
        for symbol in symbols:
            # Fetch from Polygon API
            chain = await self._fetch_options_chain(symbol)
            
            # Store individual contracts
            await self._store_contracts(symbol, target_date, chain)
            
            # Aggregate to summary
            await self._create_daily_summary(symbol, target_date, chain)
```

**Acceptance Criteria:**
- [ ] 100 symbols processed in < 5 minutes
- [ ] options_chains populated
- [ ] options_daily_summary aggregated with walls

### 12.4 Story 2.3: Metrics Integration (4 pts)

**File:** `core/pipeline/metrics_calculator.py`

**Key Implementation:**
```python
class MetricsCalculator:
    async def calculate_all_metrics(self, symbol: str) -> dict:
        # Parallel calls to Polygon MCP
        ta = await self._call_mcp("get_all_ta_indicators", {"symbol": symbol})
        dealer = await self._call_mcp("get_dealer_metrics", {"symbol": symbol})
        vol = await self._call_mcp("get_volatility_metrics", {"symbol": symbol})
        price = await self._call_mcp("get_price_metrics", {"symbol": symbol})
        
        # Map to daily_snapshots columns
        return self._map_to_snapshot(ta, dealer, vol, price)
```

**Acceptance Criteria:**
- [ ] All 84 TA indicators fetched
- [ ] Dealer metrics (GEX, DGPI, walls) extracted
- [ ] Volatility metrics (IV skew, term structure) populated
- [ ] Price metrics (RVOL, VSI, HV) populated

### 12.5 Story 2.4: Wyckoff Engine Migration (6 pts)

**Files:** `core/wyckoff/phase.py`, `events.py`, `scoring.py`

**8 MVP Events:**
- SC (Selling Climax)
- AR (Automatic Rally)
- ST (Secondary Test)
- SPRING
- TEST (Test of Spring)
- SOS (Sign of Strength)
- BC (Buying Climax)
- SOW (Sign of Weakness)

**Acceptance Criteria:**
- [ ] Phase classification A-E working
- [ ] 8 events detected with confidence scores
- [ ] BC score (0-28) calculated
- [ ] Spring score (0-12) calculated

### 12.6 Story 2.5: Daily Batch Orchestrator (6 pts)

**File:** `core/pipeline/daily_job.py`

**Key Implementation:**
```python
class DailyBatchJob:
    async def run(self, target_date: date) -> dict:
        # Phase 1: S3 OHLCV (full universe)
        await self.s3_loader.load_daily(target_date)
        
        # Phase 2: Options (watchlist only)
        await self.options_loader.load_watchlist_options(target_date)
        
        # Phase 3: Metrics (watchlist only)
        # Phase 4: Wyckoff (watchlist only)
        for symbol in watchlist:
            metrics = await self.metrics_calc.calculate_all_metrics(symbol)
            wyckoff = await self.wyckoff.analyze(symbol)
            await self._store_snapshot(symbol, target_date, {**metrics, **wyckoff})
```

**Acceptance Criteria:**
- [ ] Full pipeline < 15 minutes
- [ ] job_runs audit trail
- [ ] All 45+ snapshot columns populated

---

## 12. SPRINT 3: RECOMMENDATIONS & DASHBOARD

**Duration:** December 21-27, 2025  
**Total Points:** 18

### 12.1 Story Overview

| Story | Points | Description |
|-------|--------|-------------|
| 3.1 Recommendation Engine | 6 | Claude integration with prompts |
| 3.2 Strike Selection | 4 | Real strikes from options_chains |
| 3.3 Portfolio UI | 4 | Next.js CRUD pages |
| 3.4 Recommendations Dashboard | 4 | List, detail, alerts |

### 12.2 Story 3.1: Recommendation Engine (6 pts)

**Prompt Template:**
```
You are a trading assistant analyzing {symbol}.

Current Wyckoff Analysis:
- Phase: {phase} (confidence: {confidence})
- Events: {events}
- BC Score: {bc_score}/28
- Spring Score: {spring_score}/12

Technical Indicators:
- RSI: {rsi_14}
- MACD: {macd_histogram}
- ADX: {adx_14}

Dealer Positioning:
- DGPI: {dgpi}
- Gamma Flip: {gamma_flip_level}
- Call Wall: {call_wall_primary}
- Put Wall: {put_wall_primary}

Available Option Strikes: {strikes}
Available Expirations: {expirations}

Generate a trading recommendation with:
1. Direction (LONG/SHORT/NEUTRAL)
2. Strategy (LONG_CALL/LONG_PUT/CSP/VERTICAL_SPREAD)
3. Specific strike and expiration from available options
4. Entry, stop loss, and profit target
5. Detailed justification
```

### 12.3 Story 3.2: Strike Selection (4 pts)

**Rule: ONLY use strikes from options_chains table**

```python
def select_strike(symbol: str, direction: str, strategy: str) -> dict:
    # Query available strikes
    strikes = await db.query("""
        SELECT DISTINCT strike, expiration, open_interest
        FROM options_chains
        WHERE symbol = :symbol
          AND expiration > CURRENT_DATE + INTERVAL '30 days'
          AND expiration < CURRENT_DATE + INTERVAL '90 days'
        ORDER BY open_interest DESC
    """)
    
    # Select based on strategy
    if strategy == "LONG_CALL":
        return select_otm_call(strikes, direction)
    elif strategy == "CSP":
        return select_otm_put(strikes)
    ...
```

---

## 13. SPRINT 4: DEPLOYMENT & HARDENING

**Duration:** December 28-31, 2025  
**Total Points:** 10

| Story | Points | Description |
|-------|--------|-------------|
| 4.1 Fly.io Deployment | 5 | Apps, secrets, networking |
| 4.2 Production Hardening | 5 | Logging, health checks, monitoring |

---

## 14. CONFIGURATION REFERENCE

### 15.1 Environment Variables

```bash
# ===========================================
# DATABASE
# ===========================================
DATABASE_URL=postgresql://kapman:${DB_PASSWORD}@db:5432/kapman
DB_PASSWORD=your_secure_password

# ===========================================
# CACHE
# ===========================================
REDIS_URL=redis://redis:6379

# ===========================================
# AI PROVIDERS
# ===========================================
AI_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# ===========================================
# MARKET DATA
# ===========================================
MARKET_DATA_PROVIDER=polygon
POLYGON_API_KEY=your_polygon_key

# ===========================================
# AWS / S3 (Polygon Flat Files)
# ===========================================
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET=flatfiles

# ===========================================
# POLYGON MCP SERVER
# ===========================================
POLYGON_MCP_URL=http://localhost:5001

# ===========================================
# EMAIL (P2)
# ===========================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=alerts@yourdomain.com

# ===========================================
# SCHEDULER
# ===========================================
DAILY_JOB_HOUR=4
DAILY_JOB_MINUTE=0
TIMEZONE=America/New_York
```

### 15.2 Docker Compose

```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:4000
    depends_on: [api]

  api:
    build: ./api
    ports: ["4000:4000"]
    environment:
      - DATABASE_URL=postgresql://kapman:${DB_PASSWORD}@db:5432/kapman
      - REDIS_URL=redis://redis:6379
      - CORE_SERVICE_URL=http://core:5000
    depends_on: [db, redis, core]

  core:
    build: ./core
    ports: ["5000:5000"]
    environment:
      - DATABASE_URL=postgresql://kapman:${DB_PASSWORD}@db:5432/kapman
      - REDIS_URL=redis://redis:6379
      - AI_PROVIDER=claude
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - POLYGON_API_KEY=${POLYGON_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - POLYGON_MCP_URL=http://polygon-mcp:5001
    depends_on: [db, redis]

  db:
    image: timescale/timescaledb:latest-pg15
    ports: ["5432:5432"]
    environment:
      - POSTGRES_USER=kapman
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=kapman
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

---

## 15. APPENDICES

### 15.1 Wyckoff Phase Definitions

| Phase | Code | Description | Typical Events |
|-------|------|-------------|----------------|
| Accumulation | A | Smart money buying | PS, SC, AR, ST, SPRING, TEST, SOS |
| Markup | B | Uptrend | BU, continuation |
| Consolidation | C | Sideways | Range-bound |
| Distribution | D | Smart money selling | PSY, BC, AR, SOW, LPSY, UTAD |
| Markdown | E | Downtrend | Continuation lower |

### 15.2 BC Score Signals (0-28)

| Signal | Max Points | Description |
|--------|------------|-------------|
| Parabolic Price | 4 | >5% gain in 1 day or >3% consecutive days |
| Volume Explosion | 4 | Volume >2x 20-day average |
| Wide Range Bars | 4 | Daily range >4% of price, close in bottom 30% |
| Overbought Indicators | 4 | RSI >70 AND Stochastic >80 |
| Volume Divergence | 4 | Price new high, OBV flat/declining |
| Behavior at Highs | 4 | New high but can't hold, closes 2%+ below |
| Sentiment Extreme | 4 | Media/social euphoria |

### 15.3 Spring Score Signals (0-12)

| Signal | Max Points | Description |
|--------|------------|-------------|
| Support Break | 3 | Price breaks below established support |
| Quick Recovery | 3 | Price recovers above support within 1-3 bars |
| Low Volume | 3 | Volume below average during break |
| Bullish Close | 3 | Closes in upper half of range |

### 15.4 Decision Rules Summary

```
ENTRY SIGNALS (🟢):
─────────────────────────────────────────────────────
IF SPRING detected AND SOS confirmed:
    → STRONG ENTRY - Primary accumulation complete
    → Consider 2-3x normal position size

IF Spring Score ≥ 9 AND BC Score < 12:
    → ENTRY SETUP - Favorable risk/reward
    → Position size normal

IF SOS detected (without prior SPRING):
    → BREAKOUT ENTRY - Momentum confirmation
    → Tighter stops required

EXIT SIGNALS (🔴):
─────────────────────────────────────────────────────
IF BC Score ≥ 24:
    → EXIT IMMEDIATELY (no exceptions)
    → Close all positions in this ticker

IF BC Score ≥ 20:
    → PREPARE EXIT - Set tight stops
    → No new positions

IF SOW detected:
    → DISTRIBUTION WARNING
    → Reduce position size, tighten stops
```

### 15.5 Glossary

| Term | Definition |
|------|------------|
| **BC** | Buying Climax - euphoric buying at market tops |
| **SC** | Selling Climax - panic selling at market bottoms |
| **AR** | Automatic Rally - bounce after selling climax |
| **ST** | Secondary Test - retest of climax area |
| **SPRING** | False breakdown below support, entry signal |
| **TEST** | Test of Spring - validates the spring |
| **SOS** | Sign of Strength - high volume breakout rally |
| **SOW** | Sign of Weakness - high volume breakdown |
| **CSP** | Cash-Secured Put - selling puts with cash collateral |
| **DTE** | Days to Expiration |
| **GEX** | Gamma Exposure - dealer hedging pressure |
| **DGPI** | Dealer Gamma Pressure Index |
| **RVOL** | Relative Volume - current vs average volume |
| **VSI** | Volume Surge Index - z-score of volume |
| **HV** | Historical Volatility |
| **IV** | Implied Volatility |
| **Brier Score** | Probabilistic accuracy metric (lower = better) |

---

## DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-07 | Victor Kapella / Claude | Initial release |
| 2.0 | 2025-12-09 | Victor Kapella / Claude | Enhanced schema (45+ columns), full universe OHLCV, options summary table, Wyckoff event dashboard with ENTRY/EXIT signals, revised sprints |

---

**END OF ARCHITECTURE DOCUMENT**

*This document is the single source of truth for the Kapman Trading System. Load this file at the start of each Windsurf development session for full context.*