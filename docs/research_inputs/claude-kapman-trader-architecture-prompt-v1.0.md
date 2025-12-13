# KAPMAN TRADING SYSTEM - ARCHITECTURE & IMPLEMENTATION PROMPT
**Version:** 1.0  
**Date:** December 7, 2025  
**Status:** Ready for Implementation  
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
9. [Sprint 1 Detailed Tasks](#9-sprint-1-detailed-tasks)
10. [Configuration Reference](#10-configuration-reference)
11. [Appendices](#11-appendices)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Vision Statement

Build an automated trading decision-support system that:
- Gathers daily OHLCV and options data from Polygon.io
- Performs Wyckoff phase classification and event detection
- Generates actionable trade recommendations with justification
- Tracks forecast accuracy using directional Brier scoring
- Provides a minimal dashboard for daily decision-making

### 1.2 Key Decisions Summary

| Decision | Choice |
|----------|--------|
| **Database** | PostgreSQL + TimescaleDB |
| **Deployment** | Docker Compose → Fly.io |
| **Frontend** | Next.js + Shadcn/ui (minimal MVP) |
| **Backend** | Python (FastAPI) + TypeScript (Express) |
| **AI Provider** | Claude (swappable to OpenAI) |
| **Market Data** | Polygon S3 (OHLCV) + Polygon API (Options) |
| **Notifications** | Email (SMTP) + Dashboard |

### 1.3 MVP Scope (December 31, 2025)

**Included:**
- Daily batch pipeline (S3 → Wyckoff → Recommendations)
- Portfolio management (tickers, lists, priorities)
- 8 critical Wyckoff events (BC, SC, AR, ST, SPRING, TEST, SOS, SOW)
- 4 option strategies (Long Call, Long Put, CSP, Vertical Spread)
- Minimal dashboard with recommendations
- Directional accuracy scoring (Brier)

**Deferred to Post-MVP:**
- Full 17 Wyckoff events
- Calendar Spread, Covered Call strategies
- Chatbot interface
- Email scraping
- Advanced UI/charts

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
| **Risk Management** | Market/sector hedging |

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
| FR-001 | Daily batch job loads OHLCV from S3 | Pipeline completes by 5 AM ET |
| FR-002 | Daily batch job fetches options chains via API | All P1 tickers have current options data |
| FR-003 | Wyckoff phase classification for all portfolio tickers | Phase (A-E) + confidence score stored daily |
| FR-004 | Wyckoff event detection (8 critical events) | Events detected with >70% accuracy |
| FR-005 | Trade recommendations generated with justification | Claude generates strategy + rationale |
| FR-006 | Recommendations use ONLY real strike/expiration data | Zero hallucinated strikes |
| FR-007 | Portfolio CRUD operations | Create, read, update, delete portfolios and tickers |
| FR-008 | Dashboard displays daily recommendations | Accessible via web browser |
| FR-009 | Directional accuracy tracking | Brier score calculated weekly |

#### P2 - Should Have

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-010 | Email daily summary | Sent by 6 AM ET |
| FR-011 | Alert on BC Score ≥ 24 | Immediate email notification |
| FR-012 | Filter recommendations by strategy/direction | UI filtering works |

#### P3 - Nice to Have (Post-MVP)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-013 | Full 17 Wyckoff events | All events detected |
| FR-014 | 3-component success score | Profitability + timing added |
| FR-015 | Historical backfill (2 years) | Backtesting capability |

### 3.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Daily job completion time | < 30 minutes for 100 tickers |
| NFR-002 | Dashboard response time | < 2 seconds page load |
| NFR-003 | System availability | 99% uptime (excluding maintenance) |
| NFR-004 | Data retention (OHLCV) | 3 years, compressed after 1 year |
| NFR-005 | Data retention (options chains) | 90 days |
| NFR-006 | Cost (infrastructure) | < $100/month |
| NFR-007 | Provider swappability | AI and market data providers swappable via config |

### 3.3 Constraints

| Constraint | Description |
|------------|-------------|
| **Budget** | < $100/month for hosting/tools |
| **Timeline** | MVP by December 31, 2025 |
| **Data Source** | Polygon.io (existing subscription) |
| **Portability** | Must run on any Docker-compatible host |
| **Real Data Only** | NO estimated/hallucinated data in recommendations |

### 3.4 Decision Boundaries

| Decision Type | System SHOULD | System SHOULD NOT |
|---------------|---------------|-------------------|
| Entry Timing | Recommend based on Wyckoff signals | Execute automatically |
| Strike Selection | Select from REAL option chain data | Generate/hallucinate strikes |
| Position Sizing | Suggest based on risk parameters | Override user risk limits |
| Exit Timing | Alert on BC Score ≥ 24 | Force liquidation |
| Parameter Tuning | Suggest adjustments | Auto-modify without approval |

---

## 4. ARCHITECTURE DECISIONS

### 4.1 Technology Stack

#### Database
```
PostgreSQL 15 + TimescaleDB 2.x
├── Why: Time-series hypertables, automatic partitioning, compression
├── Alternative considered: ClickHouse (rejected: less familiar)
└── Hosting: Fly.io Postgres or Timescale Cloud
```

#### Backend - Python Services
```
Python 3.11 + FastAPI
├── Services: Wyckoff Engine, Recommendation Service, Data Pipeline, Scoring
├── Why: Existing Wyckoff module, pandas/numpy for data processing
├── Scheduler: APScheduler
└── HTTP Client: httpx (async)
```

#### Backend - API Gateway
```
TypeScript + Express.js
├── Services: API Gateway, Portfolio Service
├── Why: Type safety, existing experience
└── ORM: Drizzle (existing) or Prisma
```

#### Frontend
```
Next.js 14 + Shadcn/ui + Tailwind CSS
├── Why: AI-friendly (v0.dev), React experience, SSR
├── State: TanStack Query
└── Scope: Minimal MVP UI
```

#### Infrastructure
```
Docker Compose (local) → Fly.io (production)
├── Services: 3 containers (frontend, api, core)
├── Database: TimescaleDB container (local) / Fly Postgres (prod)
├── Cache: Redis container
└── Why: Portable, cost-effective (~$10-20/month)
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
class LocalProvider(AIProvider):       # Future (Ollama)

# Market Data Provider Interface  
class MarketDataProvider(Protocol):
    async def get_ohlcv(self, symbol: str, start: date, end: date) -> DataFrame: ...
    async def get_options_chain(self, symbol: str) -> OptionsChain: ...
    async def get_technical_indicators(self, symbol: str) -> TechnicalData: ...

# Implementations
class PolygonS3Provider(MarketDataProvider):   # OHLCV from S3
class PolygonAPIProvider(MarketDataProvider):  # Options, real-time
class SchwabProvider(MarketDataProvider):      # Backup
```

### 4.3 Configuration

```bash
# Provider Selection (environment variables)
AI_PROVIDER=claude              # claude | openai | local
MARKET_DATA_PROVIDER=polygon    # polygon | schwab | alpaca
OHLCV_SOURCE=s3                 # s3 | api
```

---

## 5. DATA MODEL

### 5.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│   portfolios    │       │    tickers      │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ name            │       │ symbol (unique) │
│ description     │       │ name            │
│ created_at      │       │ sector          │
│ updated_at      │       │ is_active       │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │    ┌────────────────────┘
         │    │
         ▼    ▼
┌─────────────────────┐
│ portfolio_tickers   │
├─────────────────────┤
│ portfolio_id (FK)   │
│ ticker_id (FK)      │
│ priority (P1/P2)    │
│ added_at            │
└─────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ohlcv_daily (TimescaleDB hypertable)                        │
├─────────────────────────────────────────────────────────────┤
│ time (PK, timestamptz)                                      │
│ symbol (PK, varchar, indexed)                               │
│ open, high, low, close, volume, vwap                        │
│ source                                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ options_chains (TimescaleDB hypertable)                     │
├─────────────────────────────────────────────────────────────┤
│ time (PK), symbol, expiration, strike, option_type          │
│ bid, ask, last, volume, open_interest                       │
│ implied_volatility, delta, gamma, theta, vega               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ daily_snapshots (TimescaleDB hypertable)                    │
├─────────────────────────────────────────────────────────────┤
│ time (PK), symbol (PK)                                      │
│ wyckoff_phase, phase_score, phase_confidence                │
│ phase_sub_stage                                             │
│ events_detected (varchar[])  ← Queryable array              │
│ primary_event, primary_event_confidence                     │
│ events_json (jsonb)          ← Detailed event data          │
│ bc_score (0-28), spring_score (0-12)                        │
│ composite_score, volatility_regime                          │
│ checklist_json, technical_indicators_json                   │
│ dealer_metrics_json, price_metrics_json                     │
│ model_version, data_quality                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ recommendations                                              │
├─────────────────────────────────────────────────────────────┤
│ id (PK), snapshot_id (FK), symbol, recommendation_date      │
│ direction (LONG/SHORT/NEUTRAL)                              │
│ action (BUY/SELL/HOLD/HEDGE)                                │
│ confidence (0-1)                                            │
│ justification (text)         ← Claude narrative             │
│ entry_price_target, stop_loss, profit_target                │
│ risk_reward_ratio                                           │
│ option_strike, option_expiration, option_type               │
│ option_strategy (LONG_CALL/LONG_PUT/CSP/VERTICAL_SPREAD)    │
│ status (active/closed/expired)                              │
│ model_version, created_at                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ recommendation_outcomes                                      │
├─────────────────────────────────────────────────────────────┤
│ id (PK), recommendation_id (FK)                             │
│ evaluation_date, evaluation_window_days                     │
│ entry_price_actual, exit_price_actual                       │
│ high_price_during_window, low_price_during_window           │
│ days_to_target, days_to_stop                                │
│ max_favorable_excursion, max_adverse_excursion              │
│ direction_correct (boolean)                                 │
│ predicted_confidence, directional_brier                     │
│ actual_return_pct, hit_profit_target, hit_stop_loss         │
│ days_held, outcome_status (WIN/LOSS/NEUTRAL)                │
│ success_score_v1 (directional only for MVP)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ model_parameters                                             │
├─────────────────────────────────────────────────────────────┤
│ id (PK), model_name, version                                │
│ parameters_json                                             │
│ effective_from, effective_to                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ job_runs                                                     │
├─────────────────────────────────────────────────────────────┤
│ id (PK), job_name, started_at, completed_at                 │
│ status, tickers_processed, errors_json, duration_seconds    │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Wyckoff Events Reference (MVP: 8 Events)

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

### 5.3 Events JSON Structure

```json
{
  "events": [
    {
      "type": "SOS",
      "confidence": 0.85,
      "price_level": 152.30,
      "volume_ratio": 2.3,
      "description": "Sign of Strength on high volume"
    }
  ],
  "sequence_position": 5,
  "expected_next": ["LPS", "BU"],
  "pattern_completion_pct": 0.65
}
```

### 5.4 Option Strategy Mapping

| Strategy | Direction | Wyckoff Phase Fit | DTE Range |
|----------|-----------|-------------------|-----------|
| Long Call | Bullish | Accumulation (Spring, SOS), early Markup | 30-90 days |
| Long Put | Bearish | Distribution (BC, SOW), early Markdown | 30-90 days |
| Cash-Secured Put | Neutral-Bullish | Accumulation (ST, TEST), support levels | 30-45 days |
| Vertical Spread | Directional | Any phase with clear direction | 30-60 days |

### 5.5 Evaluation Schedule

| Strategy | Evaluation Frequency | Success Threshold |
|----------|---------------------|-------------------|
| All strategies | Weekly until expiration | 50% profit target |
| Long Call/Put | Check assignment: N/A | |
| CSP | Check assignment: Weekly | |
| Vertical Spread | Check max profit: Weekly | |

### 5.6 Data Retention Policy

| Data Type | Retention | Compression |
|-----------|-----------|-------------|
| OHLCV daily | 3 years | After 1 year |
| Options chains | 90 days | None |
| Daily snapshots | 2 years | After 1 year |
| Recommendations | Indefinite | None |
| Recommendation outcomes | Indefinite | None |
| Job run logs | 90 days | None |

---

## 6. SERVICE ARCHITECTURE

### 6.1 MVP Service Topology (Consolidated)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KAPMAN TRADING SYSTEM (MVP)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐                                                  │
│  │     FRONTEND      │                                                  │
│  │    (Next.js)      │                                                  │
│  │    Port: 3000     │                                                  │
│  │                   │                                                  │
│  │ • Portfolio mgmt  │                                                  │
│  │ • Recommendations │                                                  │
│  │ • Alerts display  │                                                  │
│  └─────────┬─────────┘                                                  │
│            │                                                            │
│            ▼                                                            │
│  ┌───────────────────┐         ┌───────────────────┐                   │
│  │   API GATEWAY     │         │   PYTHON CORE     │                   │
│  │   (Express/TS)    │────────▶│   (FastAPI)       │                   │
│  │   Port: 4000      │         │   Port: 5000      │                   │
│  │                   │         │                   │                   │
│  │ • REST routes     │         │ • Wyckoff engine  │                   │
│  │ • Validation      │         │ • Recommendations │                   │
│  │ • Portfolio CRUD  │         │ • Data pipeline   │                   │
│  │                   │         │ • Scoring         │                   │
│  └─────────┬─────────┘         │ • Scheduler       │                   │
│            │                   └─────────┬─────────┘                   │
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
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│ │ Polygon S3   │  │ Polygon API  │  │ Claude API   │  │ SMTP Server  │ │
│ │ (OHLCV)      │  │ (Options)    │  │ (Recommend)  │  │ (Email)      │ │
│ └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Directory Structure

```
kapman-trader-v2/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
│
├── frontend/                      # Next.js application
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app/                   # Next.js App Router
│   │   │   ├── page.tsx           # Dashboard
│   │   │   ├── portfolios/
│   │   │   ├── recommendations/
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/                # Shadcn components
│   │   │   ├── PortfolioList.tsx
│   │   │   ├── RecommendationCard.tsx
│   │   │   └── AlertBadge.tsx
│   │   └── lib/
│   │       ├── api.ts             # API client
│   │       └── types.ts
│   └── public/
│
├── api/                           # TypeScript API Gateway
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts               # Express server
│   │   ├── routes/
│   │   │   ├── portfolios.ts
│   │   │   ├── tickers.ts
│   │   │   ├── recommendations.ts
│   │   │   ├── jobs.ts
│   │   │   └── dashboard.ts
│   │   ├── middleware/
│   │   │   ├── auth.ts
│   │   │   ├── validation.ts
│   │   │   └── errorHandler.ts
│   │   ├── services/
│   │   │   ├── coreClient.ts      # Calls Python core
│   │   │   └── portfolioService.ts
│   │   └── db/
│   │       ├── schema.ts          # Drizzle schema
│   │       └── client.ts
│   └── drizzle/
│       └── migrations/
│
├── core/                          # Python Core Services
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment config
│   │
│   ├── providers/                 # Abstraction layer
│   │   ├── __init__.py
│   │   ├── ai/
│   │   │   ├── base.py            # AIProvider protocol
│   │   │   ├── claude.py
│   │   │   └── openai.py
│   │   └── market_data/
│   │       ├── base.py            # MarketDataProvider protocol
│   │       ├── polygon_s3.py
│   │       ├── polygon_api.py
│   │       └── schwab.py
│   │
│   ├── wyckoff/                   # Wyckoff analysis engine
│   │   ├── __init__.py
│   │   ├── phase.py               # Phase classification (A-E)
│   │   ├── events.py              # Event detection (8 MVP events)
│   │   ├── checklist.py           # 9-step checklist
│   │   ├── scoring.py             # BC score, Spring score
│   │   └── models.py              # Pydantic models
│   │
│   ├── recommendations/           # Recommendation engine
│   │   ├── __init__.py
│   │   ├── generator.py           # Claude integration
│   │   ├── strike_selector.py     # Real strike selection
│   │   ├── strategy.py            # Strategy selection logic
│   │   └── prompts.py             # Prompt templates
│   │
│   ├── pipeline/                  # Data pipeline
│   │   ├── __init__.py
│   │   ├── s3_loader.py           # S3 OHLCV ingestion
│   │   ├── options_loader.py      # Options API ingestion
│   │   ├── daily_job.py           # Main batch orchestrator
│   │   └── scheduler.py           # APScheduler config
│   │
│   ├── scoring/                   # Accuracy tracking
│   │   ├── __init__.py
│   │   ├── brier.py               # Brier score calculation
│   │   └── evaluator.py           # Weekly evaluation
│   │
│   ├── notifications/             # Email notifications
│   │   ├── __init__.py
│   │   ├── email.py               # SMTP client
│   │   └── templates/
│   │       ├── daily_summary.html
│   │       └── critical_alert.html
│   │
│   ├── api/                       # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── models.py
│   │
│   └── db/
│       ├── __init__.py
│       ├── models.py              # SQLAlchemy models
│       └── client.py              # Database connection
│
├── db/                            # Database migrations
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_create_hypertables.sql
│   │   └── 003_create_indexes.sql
│   └── seed/
│       └── sample_portfolios.sql
│
└── scripts/
    ├── setup-dev.sh               # Local dev setup
    ├── deploy-fly.sh              # Fly.io deployment
    └── backfill-historical.py     # Historical data loader
```

### 6.3 Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:4000
    depends_on:
      - api

  api:
    build: ./api
    ports:
      - "4000:4000"
    environment:
      - DATABASE_URL=postgresql://kapman:${DB_PASSWORD}@db:5432/kapman
      - REDIS_URL=redis://redis:6379
      - CORE_SERVICE_URL=http://core:5000
      - NODE_ENV=development
    depends_on:
      - db
      - redis
      - core

  core:
    build: ./core
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://kapman:${DB_PASSWORD}@db:5432/kapman
      - REDIS_URL=redis://redis:6379
      - AI_PROVIDER=claude
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - MARKET_DATA_PROVIDER=polygon
      - POLYGON_API_KEY=${POLYGON_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - S3_BUCKET=${S3_BUCKET}
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - NOTIFICATION_EMAIL=${NOTIFICATION_EMAIL}
    depends_on:
      - db
      - redis

  db:
    image: timescale/timescaledb:latest-pg15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=kapman
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=kapman
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

---

## 7. API SPECIFICATION

### 7.1 API Gateway Endpoints (Port 4000)

#### Portfolio Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolios` | List all portfolios |
| POST | `/api/portfolios` | Create portfolio |
| GET | `/api/portfolios/:id` | Get portfolio detail |
| PATCH | `/api/portfolios/:id` | Update portfolio |
| DELETE | `/api/portfolios/:id` | Delete portfolio |
| POST | `/api/portfolios/:id/tickers` | Add tickers |
| DELETE | `/api/portfolios/:id/tickers/:tid` | Remove ticker |
| PATCH | `/api/portfolios/:id/tickers/:tid` | Update priority |

#### Ticker Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tickers` | List all tracked tickers |
| GET | `/api/tickers/:symbol` | Get ticker with latest snapshot |
| GET | `/api/tickers/:symbol/snapshots` | Get historical snapshots |
| GET | `/api/tickers/:symbol/events` | Get Wyckoff events timeline |
| GET | `/api/tickers/:symbol/options` | Get current options chain |

#### Wyckoff Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Batch analyze symbols |
| POST | `/api/analyze/:symbol` | Single symbol deep analysis |
| GET | `/api/events/recent` | Recent events across tickers |

#### Recommendations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recommendations` | List recommendations |
| GET | `/api/recommendations/:id` | Get recommendation detail |
| POST | `/api/recommendations/generate` | Generate new recommendation |
| GET | `/api/recommendations/:id/outcome` | Get evaluation results |

#### Batch Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jobs/daily` | Trigger daily batch job |
| GET | `/api/jobs/daily/status` | Get job status |
| POST | `/api/jobs/backfill` | Trigger historical backfill |
| GET | `/api/jobs/history` | List recent job runs |

#### Scoring & Accuracy

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/accuracy/summary` | Overall accuracy metrics |
| GET | `/api/accuracy/by-phase` | Accuracy by Wyckoff phase |
| GET | `/api/accuracy/by-strategy` | Accuracy by option strategy |
| POST | `/api/scoring/evaluate` | Trigger weekly evaluation |

#### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/alerts` | Active alerts (BC≥20, etc.) |
| GET | `/api/dashboard/summary` | Portfolio summary stats |
| GET | `/api/dashboard/events-today` | Today's Wyckoff events |

### 7.2 Python Core Endpoints (Port 5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Wyckoff analysis (batch) |
| POST | `/analyze/{symbol}` | Single symbol analysis |
| POST | `/recommend` | Generate recommendation |
| POST | `/pipeline/daily` | Run daily pipeline |
| POST | `/pipeline/load-ohlcv` | Load OHLCV from S3 |
| POST | `/pipeline/load-options` | Load options chains |
| POST | `/evaluate` | Run scoring evaluation |
| GET | `/health` | Health check |

---

## 8. IMPLEMENTATION ROADMAP

### 8.1 Timeline Overview

```
Week 1: Dec 7-13   │ Foundation (Infrastructure, DB, Providers)
Week 2: Dec 14-20  │ Core Engine (Wyckoff, Pipeline, Events)
Week 3: Dec 21-27  │ Recommendations + Minimal Dashboard
Week 4: Dec 28-31  │ Deployment + Hardening
```

### 8.2 Epic Summary

| Epic | Week | Points | Priority |
|------|------|--------|----------|
| EPIC 1: Infrastructure | 1 | 21 | P0 |
| EPIC 2: Wyckoff Engine | 2 | 24 | P0 |
| EPIC 3: Recommendations | 3 | 18 | P0 |
| EPIC 4: Dashboard & Notifications | 3 | 16 | P1 |
| EPIC 5: Deployment | 4 | 10 | P0 |
| **TOTAL** | | **89** | |

### 8.3 Sprint Breakdown

#### Sprint 1: Infrastructure (Dec 7-13)

| Story | Points | Tasks |
|-------|--------|-------|
| 1.1 Dev Environment | 5 | Windsurf, Docker, GitHub repo, pre-commit |
| 1.2 Database Setup | 5 | TimescaleDB, migrations, hypertables, indexes |
| 1.3 Provider Abstraction | 5 | AI interface, Market Data interface, env config |
| 1.4 S3 OHLCV Pipeline | 6 | boto3, download, parse, bulk insert |

#### Sprint 2: Wyckoff Engine (Dec 14-20)

| Story | Points | Tasks |
|-------|--------|-------|
| 2.1 Wyckoff Migration | 8 | Copy logic, refactor DB layer, provider abstraction |
| 2.2 Event Detection | 6 | 8 events, confidence scoring, sequence tracking |
| 2.3 Options Integration | 4 | Polygon API, parse Greeks, store |
| 2.4 Daily Batch Job | 6 | APScheduler, orchestration, error handling |

#### Sprint 3: Recommendations + UI (Dec 21-27)

| Story | Points | Tasks |
|-------|--------|-------|
| 3.1 Recommendation Engine | 8 | Claude integration, prompts, justification |
| 3.2 Strike Selection | 6 | Real strikes only, phase-aware DTE |
| 3.3 Recommendation Storage | 4 | Save, link to snapshot, status tracking |
| 4.1 Portfolio UI | 5 | Next.js setup, CRUD pages |
| 4.2 Recommendations Dashboard | 6 | List view, detail, filters, alerts |
| 4.3 Email Notifications | 5 | SMTP, templates, daily summary |

#### Sprint 4: Deployment (Dec 28-31)

| Story | Points | Tasks |
|-------|--------|-------|
| 5.1 Fly.io Deployment | 5 | Apps, config, secrets |
| 5.2 Production Hardening | 5 | Health checks, logging, monitoring |

---

## 9. SPRINT 1 DETAILED TASKS

### 9.1 Story 1.1: Development Environment Setup (5 pts)

**Day 1-2**

```bash
# Task 1.1.1: Create GitHub repository
gh repo create kapman-trader-v2 --private --clone
cd kapman-trader-v2
git checkout -b main

# Task 1.1.2: Initialize directory structure
mkdir -p frontend api core db/migrations db/seed scripts

# Task 1.1.3: Create root files
touch docker-compose.yml .env.example .gitignore README.md

# Task 1.1.4: Setup pre-commit hooks
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.11
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
EOF

pre-commit install
```

**Task 1.1.5: Create .env.example**
```bash
# Database
DB_PASSWORD=your_secure_password

# AI Provider
AI_PROVIDER=claude
CLAUDE_API_KEY=your_claude_key
OPENAI_API_KEY=your_openai_key

# Market Data
MARKET_DATA_PROVIDER=polygon
POLYGON_API_KEY=your_polygon_key

# S3 (Polygon Flat Files)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET=polygon-flat-files

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=your_notification_email

# Redis
REDIS_URL=redis://localhost:6379
```

**Task 1.1.6: Create .gitignore**
```
# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp

# Build
.next/
dist/
build/

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db

# Database
pgdata/
redisdata/
```

### 9.2 Story 1.2: Database Setup (5 pts)

**Day 3-4**

**Task 1.2.1: Create initial migration**

```sql
-- db/migrations/001_initial_schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Portfolios
CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tickers
CREATE TABLE tickers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tickers_symbol ON tickers(symbol);

-- Portfolio-Ticker junction
CREATE TABLE portfolio_tickers (
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker_id UUID REFERENCES tickers(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 2 CHECK (priority IN (1, 2)),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, ticker_id)
);

-- Model parameters (version control for algorithms)
CREATE TABLE model_parameters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    parameters_json JSONB NOT NULL,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_to TIMESTAMPTZ,
    notes TEXT
);

-- Job runs (audit trail)
CREATE TABLE job_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    tickers_processed INTEGER DEFAULT 0,
    errors_json JSONB,
    duration_seconds INTEGER
);

CREATE INDEX idx_job_runs_started ON job_runs(started_at DESC);
```

**Task 1.2.2: Create hypertables migration**

```sql
-- db/migrations/002_create_hypertables.sql

-- OHLCV Daily (TimescaleDB hypertable)
CREATE TABLE ohlcv_daily (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4),
    volume BIGINT,
    vwap NUMERIC(12, 4),
    source VARCHAR(50) DEFAULT 'polygon_s3',
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('ohlcv_daily', 'time');
CREATE INDEX idx_ohlcv_symbol ON ohlcv_daily(symbol, time DESC);

-- Options Chains (TimescaleDB hypertable)
CREATE TABLE options_chains (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    expiration DATE NOT NULL,
    strike NUMERIC(12, 2) NOT NULL,
    option_type CHAR(1) NOT NULL CHECK (option_type IN ('C', 'P')),
    bid NUMERIC(12, 4),
    ask NUMERIC(12, 4),
    last NUMERIC(12, 4),
    volume INTEGER,
    open_interest INTEGER,
    implied_volatility NUMERIC(8, 4),
    delta NUMERIC(8, 4),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 4),
    vega NUMERIC(8, 4),
    source VARCHAR(50) DEFAULT 'polygon_api',
    PRIMARY KEY (time, symbol, expiration, strike, option_type)
);

SELECT create_hypertable('options_chains', 'time');
CREATE INDEX idx_options_symbol ON options_chains(symbol, time DESC);

-- Daily Snapshots (TimescaleDB hypertable)
CREATE TABLE daily_snapshots (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Wyckoff Phase
    wyckoff_phase CHAR(1) CHECK (wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')),
    phase_score NUMERIC(4, 3),
    phase_confidence NUMERIC(4, 3),
    phase_sub_stage VARCHAR(20),
    
    -- Wyckoff Events
    events_detected VARCHAR(20)[],
    primary_event VARCHAR(20),
    primary_event_confidence NUMERIC(4, 3),
    events_json JSONB,
    
    -- Scores
    bc_score INTEGER CHECK (bc_score >= 0 AND bc_score <= 28),
    spring_score INTEGER CHECK (spring_score >= 0 AND spring_score <= 12),
    composite_score NUMERIC(4, 3),
    volatility_regime VARCHAR(20),
    
    -- Detailed metrics (JSONB)
    checklist_json JSONB,
    technical_indicators_json JSONB,
    dealer_metrics_json JSONB,
    price_metrics_json JSONB,
    
    -- Metadata
    model_version VARCHAR(50),
    data_quality VARCHAR(20) DEFAULT 'complete',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('daily_snapshots', 'time');
CREATE INDEX idx_snapshots_symbol ON daily_snapshots(symbol, time DESC);
CREATE INDEX idx_snapshots_events ON daily_snapshots USING GIN(events_detected);
CREATE INDEX idx_snapshots_phase ON daily_snapshots(wyckoff_phase, time DESC);

-- Recommendations
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ,
    snapshot_symbol VARCHAR(20),
    symbol VARCHAR(20) NOT NULL,
    recommendation_date DATE NOT NULL,
    
    -- Direction & Action
    direction VARCHAR(10) CHECK (direction IN ('LONG', 'SHORT', 'NEUTRAL')),
    action VARCHAR(10) CHECK (action IN ('BUY', 'SELL', 'HOLD', 'HEDGE')),
    confidence NUMERIC(4, 3),
    
    -- Justification
    justification TEXT,
    
    -- Price targets
    entry_price_target NUMERIC(12, 4),
    stop_loss NUMERIC(12, 4),
    profit_target NUMERIC(12, 4),
    risk_reward_ratio NUMERIC(6, 2),
    
    -- Option details
    option_strike NUMERIC(12, 2),
    option_expiration DATE,
    option_type CHAR(1) CHECK (option_type IN ('C', 'P')),
    option_strategy VARCHAR(30) CHECK (option_strategy IN (
        'LONG_CALL', 'LONG_PUT', 'CSP', 'VERTICAL_SPREAD'
    )),
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'closed', 'expired')),
    
    -- Metadata
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (snapshot_time, snapshot_symbol) 
        REFERENCES daily_snapshots(time, symbol)
);

CREATE INDEX idx_recommendations_symbol ON recommendations(symbol, recommendation_date DESC);
CREATE INDEX idx_recommendations_status ON recommendations(status, recommendation_date DESC);

-- Recommendation Outcomes
CREATE TABLE recommendation_outcomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id UUID REFERENCES recommendations(id) ON DELETE CASCADE,
    evaluation_date DATE NOT NULL,
    evaluation_window_days INTEGER,
    
    -- Actual prices
    entry_price_actual NUMERIC(12, 4),
    exit_price_actual NUMERIC(12, 4),
    high_price_during_window NUMERIC(12, 4),
    low_price_during_window NUMERIC(12, 4),
    
    -- Timing
    days_to_target INTEGER,
    days_to_stop INTEGER,
    days_held INTEGER,
    
    -- Excursions
    max_favorable_excursion NUMERIC(8, 4),
    max_adverse_excursion NUMERIC(8, 4),
    
    -- Directional accuracy (MVP)
    direction_correct BOOLEAN,
    predicted_confidence NUMERIC(4, 3),
    directional_brier NUMERIC(6, 4),
    
    -- Profitability (Phase 2)
    actual_return_pct NUMERIC(8, 4),
    hit_profit_target BOOLEAN,
    hit_stop_loss BOOLEAN,
    
    -- Scores
    success_score_v1 NUMERIC(4, 3),
    outcome_status VARCHAR(10) CHECK (outcome_status IN ('WIN', 'LOSS', 'NEUTRAL')),
    
    -- Metadata
    notes TEXT,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outcomes_recommendation ON recommendation_outcomes(recommendation_id);
CREATE INDEX idx_outcomes_date ON recommendation_outcomes(evaluation_date DESC);
```

**Task 1.2.3: Create compression and retention policies**

```sql
-- db/migrations/003_retention_policies.sql

-- Enable compression on old data
ALTER TABLE ohlcv_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

ALTER TABLE options_chains SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

ALTER TABLE daily_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

-- Add compression policies (compress after 1 year)
SELECT add_compression_policy('ohlcv_daily', INTERVAL '1 year');
SELECT add_compression_policy('daily_snapshots', INTERVAL '1 year');

-- Add retention policies
SELECT add_retention_policy('ohlcv_daily', INTERVAL '3 years');
SELECT add_retention_policy('options_chains', INTERVAL '90 days');
SELECT add_retention_policy('daily_snapshots', INTERVAL '2 years');
```

### 9.3 Story 1.3: Provider Abstraction Layer (5 pts)

**Day 5-6**

**Task 1.3.1: Create AI Provider interface**

```python
# core/providers/ai/base.py
from abc import ABC, abstractmethod
from typing import Protocol
from pydantic import BaseModel

class AnalysisContext(BaseModel):
    symbol: str
    wyckoff_phase: str
    phase_confidence: float
    events_detected: list[str]
    bc_score: int
    spring_score: int
    technical_indicators: dict
    dealer_metrics: dict
    available_strikes: list[float]
    available_expirations: list[str]

class Recommendation(BaseModel):
    symbol: str
    direction: str  # LONG, SHORT, NEUTRAL
    action: str  # BUY, SELL, HOLD, HEDGE
    confidence: float
    strategy: str  # LONG_CALL, LONG_PUT, CSP, VERTICAL_SPREAD
    strike: float | None
    expiration: str | None
    entry_target: float
    stop_loss: float
    profit_target: float
    justification: str

class ModelInfo(BaseModel):
    provider: str
    model: str
    version: str

class AIProvider(Protocol):
    async def generate_recommendation(
        self, context: AnalysisContext
    ) -> Recommendation:
        ...
    
    async def generate_justification(
        self, recommendation: Recommendation, context: AnalysisContext
    ) -> str:
        ...
    
    def get_model_info(self) -> ModelInfo:
        ...
```

**Task 1.3.2: Create Claude Provider implementation**

```python
# core/providers/ai/claude.py
import anthropic
from .base import AIProvider, AnalysisContext, Recommendation, ModelInfo
from core.recommendations.prompts import RECOMMENDATION_PROMPT

class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
    
    async def generate_recommendation(
        self, context: AnalysisContext
    ) -> Recommendation:
        prompt = RECOMMENDATION_PROMPT.format(
            symbol=context.symbol,
            phase=context.wyckoff_phase,
            phase_confidence=context.phase_confidence,
            events=", ".join(context.events_detected),
            bc_score=context.bc_score,
            spring_score=context.spring_score,
            strikes=context.available_strikes,
            expirations=context.available_expirations,
            technical=context.technical_indicators,
            dealer=context.dealer_metrics
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response into Recommendation
        return self._parse_response(response.content[0].text, context)
    
    async def generate_justification(
        self, recommendation: Recommendation, context: AnalysisContext
    ) -> str:
        # Justification is included in recommendation
        return recommendation.justification
    
    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="anthropic",
            model=self.model,
            version="2025-01"
        )
    
    def _parse_response(self, text: str, context: AnalysisContext) -> Recommendation:
        # Parse structured response from Claude
        # Implementation details...
        pass
```

**Task 1.3.3: Create Market Data Provider interface**

```python
# core/providers/market_data/base.py
from abc import ABC, abstractmethod
from typing import Protocol
from datetime import date
import pandas as pd
from pydantic import BaseModel

class OptionsChain(BaseModel):
    symbol: str
    timestamp: str
    expirations: list[str]
    strikes: list[float]
    calls: list[dict]
    puts: list[dict]

class TechnicalData(BaseModel):
    symbol: str
    timestamp: str
    rsi: float | None
    macd: dict | None
    sma_20: float | None
    sma_50: float | None
    ema_12: float | None
    ema_26: float | None
    bbands: dict | None
    atr: float | None

class ProviderInfo(BaseModel):
    name: str
    tier: str
    capabilities: list[str]

class MarketDataProvider(Protocol):
    async def get_ohlcv(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        ...
    
    async def get_options_chain(self, symbol: str) -> OptionsChain:
        ...
    
    async def get_technical_indicators(self, symbol: str) -> TechnicalData:
        ...
    
    def get_provider_info(self) -> ProviderInfo:
        ...
```

**Task 1.3.4: Create Polygon S3 Provider**

```python
# core/providers/market_data/polygon_s3.py
import boto3
import pandas as pd
from datetime import date
from io import BytesIO
from .base import MarketDataProvider, ProviderInfo

class PolygonS3Provider:
    def __init__(
        self,
        aws_access_key: str,
        aws_secret_key: str,
        bucket: str = "flatfiles"
    ):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        self.bucket = bucket
    
    async def get_ohlcv(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        """Load OHLCV data from Polygon S3 flat files"""
        frames = []
        current = start
        
        while current <= end:
            key = f"us_stocks_sip/day_aggs_v1/{current.year}/{current.month:02d}/{current.strftime('%Y-%m-%d')}.csv.gz"
            try:
                obj = self.s3.get_object(Bucket=self.bucket, Key=key)
                df = pd.read_csv(BytesIO(obj['Body'].read()), compression='gzip')
                df = df[df['ticker'] == symbol]
                frames.append(df)
            except self.s3.exceptions.NoSuchKey:
                pass  # Skip missing dates
            current += pd.Timedelta(days=1)
        
        if not frames:
            return pd.DataFrame()
        
        result = pd.concat(frames, ignore_index=True)
        result = result.rename(columns={
            'ticker': 'symbol',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume',
            'vw': 'vwap',
            't': 'time'
        })
        
        return result
    
    async def get_options_chain(self, symbol: str):
        raise NotImplementedError("Use PolygonAPIProvider for options")
    
    async def get_technical_indicators(self, symbol: str):
        raise NotImplementedError("Use PolygonAPIProvider for indicators")
    
    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="polygon_s3",
            tier="flat_files",
            capabilities=["ohlcv_historical", "bulk_load"]
        )
```

**Task 1.3.5: Create provider factory**

```python
# core/providers/__init__.py
import os
from .ai.base import AIProvider
from .ai.claude import ClaudeProvider
from .ai.openai import OpenAIProvider
from .market_data.base import MarketDataProvider
from .market_data.polygon_s3 import PolygonS3Provider
from .market_data.polygon_api import PolygonAPIProvider

def get_ai_provider() -> AIProvider:
    provider = os.getenv("AI_PROVIDER", "claude")
    
    if provider == "claude":
        return ClaudeProvider(
            api_key=os.getenv("CLAUDE_API_KEY")
        )
    elif provider == "openai":
        return OpenAIProvider(
            api_key=os.getenv("OPENAI_API_KEY")
        )
    else:
        raise ValueError(f"Unknown AI provider: {provider}")

def get_market_data_provider(source: str = None) -> MarketDataProvider:
    source = source or os.getenv("OHLCV_SOURCE", "s3")
    
    if source == "s3":
        return PolygonS3Provider(
            aws_access_key=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            bucket=os.getenv("S3_BUCKET", "flatfiles")
        )
    elif source == "api":
        return PolygonAPIProvider(
            api_key=os.getenv("POLYGON_API_KEY")
        )
    else:
        raise ValueError(f"Unknown market data source: {source}")
```

### 9.4 Story 1.4: S3 OHLCV Pipeline (6 pts)

**Day 7**

**Task 1.4.1: Create S3 loader service**

```python
# core/pipeline/s3_loader.py
import asyncio
from datetime import date, timedelta
import pandas as pd
from sqlalchemy import text
from core.providers import get_market_data_provider
from core.db.client import get_db_session

class S3OHLCVLoader:
    def __init__(self):
        self.provider = get_market_data_provider(source="s3")
    
    async def load_daily(
        self, 
        symbols: list[str], 
        target_date: date = None
    ) -> dict:
        """Load daily OHLCV for specified symbols"""
        target_date = target_date or date.today() - timedelta(days=1)
        
        results = {"loaded": 0, "errors": []}
        
        for symbol in symbols:
            try:
                df = await self.provider.get_ohlcv(
                    symbol=symbol,
                    start=target_date,
                    end=target_date
                )
                
                if not df.empty:
                    await self._insert_ohlcv(df, symbol)
                    results["loaded"] += 1
            except Exception as e:
                results["errors"].append({"symbol": symbol, "error": str(e)})
        
        return results
    
    async def backfill(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date
    ) -> dict:
        """Backfill historical OHLCV data"""
        results = {"loaded": 0, "errors": []}
        
        for symbol in symbols:
            try:
                df = await self.provider.get_ohlcv(
                    symbol=symbol,
                    start=start_date,
                    end=end_date
                )
                
                if not df.empty:
                    await self._insert_ohlcv(df, symbol)
                    results["loaded"] += len(df)
            except Exception as e:
                results["errors"].append({"symbol": symbol, "error": str(e)})
        
        return results
    
    async def _insert_ohlcv(self, df: pd.DataFrame, symbol: str):
        """Bulk insert OHLCV data using COPY"""
        async with get_db_session() as session:
            # Use PostgreSQL COPY for bulk insert
            records = df.to_dict('records')
            
            for record in records:
                await session.execute(
                    text("""
                        INSERT INTO ohlcv_daily (time, symbol, open, high, low, close, volume, vwap, source)
                        VALUES (:time, :symbol, :open, :high, :low, :close, :volume, :vwap, 'polygon_s3')
                        ON CONFLICT (time, symbol) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            vwap = EXCLUDED.vwap
                    """),
                    record
                )
            
            await session.commit()
```

---

## 10. CONFIGURATION REFERENCE

### 10.1 Environment Variables

```bash
# ===========================================
# DATABASE
# ===========================================
DATABASE_URL=postgresql://kapman:password@localhost:5432/kapman
DB_PASSWORD=your_secure_password

# ===========================================
# CACHE
# ===========================================
REDIS_URL=redis://localhost:6379

# ===========================================
# AI PROVIDERS
# ===========================================
AI_PROVIDER=claude                    # claude | openai
CLAUDE_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# ===========================================
# MARKET DATA
# ===========================================
MARKET_DATA_PROVIDER=polygon          # polygon | schwab
OHLCV_SOURCE=s3                       # s3 | api
POLYGON_API_KEY=your_polygon_key

# ===========================================
# AWS / S3 (Polygon Flat Files)
# ===========================================
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET=flatfiles
S3_REGION=us-east-1

# ===========================================
# EMAIL NOTIFICATIONS
# ===========================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=alerts@yourdomain.com

# ===========================================
# APPLICATION
# ===========================================
NODE_ENV=development                  # development | production
LOG_LEVEL=INFO                        # DEBUG | INFO | WARNING | ERROR
DAILY_JOB_HOUR=4                      # Hour to run daily job (ET)
DAILY_JOB_MINUTE=0
```

### 10.2 Model Parameters (Stored in DB)

```json
{
  "model_name": "wyckoff_v2",
  "version": "2.0.0",
  "parameters_json": {
    "phase_thresholds": {
      "accumulation_min_score": 0.60,
      "distribution_min_score": 0.60
    },
    "event_detection": {
      "bc_volume_multiplier": 2.0,
      "spring_recovery_threshold": 0.02,
      "sos_volume_multiplier": 1.5
    },
    "scoring": {
      "bc_signal_weights": [4, 4, 4, 4, 4, 4, 4],
      "spring_signal_weights": [3, 3, 3, 3]
    }
  }
}
```

---

## 11. APPENDICES

### 11.1 Wyckoff Phase Definitions

| Phase | Code | Description | Typical Events |
|-------|------|-------------|----------------|
| Accumulation | A | Smart money buying, bottoming process | PS, SC, AR, ST, SPRING, TEST, SOS |
| Markup | B | Uptrend, price appreciation | BU (backup), continuation |
| Consolidation | C | Sideways movement, re-accumulation | Range-bound, low volume |
| Distribution | D | Smart money selling, topping process | PSY, BC, AR, SOW, LPSY, UTAD |
| Markdown | E | Downtrend, price depreciation | Continuation lower |

### 11.2 BC Score Signals (0-28 scale)

| Signal | Max Points | Description |
|--------|------------|-------------|
| Parabolic Price | 4 | >5% gain in 1 day or >3% consecutive days |
| Volume Explosion | 4 | Volume >2x 20-day average |
| Wide Range Bars | 4 | Daily range >4% of price, close in bottom 30% |
| Overbought Indicators | 4 | RSI >70 AND Stochastic >80 |
| Volume Divergence | 4 | Price new high, OBV flat/declining |
| Behavior at Highs | 4 | New high but can't hold, closes 2%+ below |
| Sentiment Extreme | 4 | Media/social euphoria |

### 11.3 Spring Score Signals (0-12 scale)

| Signal | Max Points | Description |
|--------|------------|-------------|
| Support Break | 3 | Price breaks below established support |
| Quick Recovery | 3 | Price recovers above support within 1-3 bars |
| Low Volume | 3 | Volume below average during break |
| Bullish Close | 3 | Closes in upper half of range |

### 11.4 Decision Rules Summary

```
IF BC Score ≥ 24:
    → EXIT IMMEDIATELY (no exceptions)
    → Email critical alert

IF BC Score ≥ 20:
    → Prepare exit orders
    → Monitor closely

IF BC Score < 12 AND Spring Score ≥ 9:
    → CONSIDER ENTRY
    → Risk/reward favorable

IF Spring Score ≥ 9 AND Accumulation Phase:
    → Strong entry setup
    → Position size 2-3x normal (low risk entry)
```

### 11.5 Glossary

| Term | Definition |
|------|------------|
| **BC** | Buying Climax - euphoric buying at market tops |
| **SC** | Selling Climax - panic selling at market bottoms |
| **SOS** | Sign of Strength - high volume breakout rally |
| **SOW** | Sign of Weakness - high volume breakdown |
| **SPRING** | False breakdown below support, entry signal |
| **CSP** | Cash-Secured Put - selling puts with cash collateral |
| **DTE** | Days to Expiration |
| **GEX** | Gamma Exposure - dealer hedging pressure |
| **Brier Score** | Probabilistic accuracy metric (lower = better) |

---

## DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-07 | Victor Kapella / Claude | Initial release |

---

**END OF DOCUMENT**

*This prompt file is designed to be used with AI coding assistants (Claude, Windsurf, Cursor) to implement the Kapman Trading System. Load this file at the start of each development session for full context.*
