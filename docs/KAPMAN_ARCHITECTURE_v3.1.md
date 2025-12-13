# KAPMAN TRADING SYSTEM - ARCHITECTURE & IMPLEMENTATION PROMPT
**Version:** 3.2  
**Date:** December 12, 2025  
**Status:** Ready for Sprint 2.2 Implementation  
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
8. [Testing Strategy](#8-testing-strategy) ← **NEW in v3.1**
9. [Environment Strategy](#9-environment-strategy) ← **NEW in v3.1**
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Sprint 0.5: Initial Data Seeding](#11-sprint-05-initial-data-seeding) ← **NEW in v3.1**
12. [Sprint 1: Infrastructure (COMPLETED)](#12-sprint-1-infrastructure-completed)
13. [Sprint 2: Wyckoff Engine & Pipeline](#13-sprint-2-wyckoff-engine--pipeline)
14. [Sprint 3: Recommendations & Dashboard](#14-sprint-3-recommendations--dashboard)
15. [Sprint 4: Hardening & Environment Setup](#15-sprint-4-hardening--environment-setup) ← **REVISED in v3.1**
16. [Configuration Reference](#16-configuration-reference)
17. [Appendices](#17-appendices)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Vision Statement

Build an automated trading decision-support system that:
- Gathers daily OHLCV for full market universe (~15K tickers) from Polygon S3
- Enriches watchlist tickers (~140) with options data, technical indicators, dealer metrics
- Performs Wyckoff phase classification and event detection
- Generates actionable trade recommendations with justification
- Tracks forecast accuracy using directional Brier scoring
- Provides a minimal dashboard for daily decision-making

### 1.2 Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database** | PostgreSQL 15 + TimescaleDB 2.x | Time-series hypertables, compression, retention policies |
| **OHLCV Universe** | Full Polygon (~15K tickers) | Enables screening, sector analysis, no backfill needed |
| **Analysis Scope** | Watchlist only (~140 tickers) | Cost-effective options API usage |
| **Deployment** | Docker on Mac (dev/test/prod) | MVP simplicity, ~$0/month |
| **Frontend** | Next.js 14 + Shadcn/ui | AI-friendly, minimal MVP |
| **Backend** | Python (FastAPI) + TypeScript (Express) | Python for quant, TS for API |
| **AI Provider** | Claude (swappable) | Provider abstraction layer |
| **Market Data** | Polygon S3 (OHLCV) + Polygon API (Options) | 100 RPS, no rate limiting |
| **Data Model** | Two-layer: Base OHLCV + Analytical watchlists | Centralizes ingestion + deterministic analytics |
| **Metrics** | Polygon MCP Server | 84 TA indicators, dealer/vol metrics |
| **Testing** | pytest + 80% coverage requirement | TDD for all new stories |
| **Environments** | Sequential Docker (dev→test→prod) | Single Mac deployment |

### 1.3 MVP Scope (December 31, 2025)

**Included:**
- Daily batch pipeline (S3 universe → base loader → watchlist enrichment → Wyckoff → Recommendations)
- Full OHLCV universe storage (rolling 730 trading days)
- Options chain storage for watchlist (90-day retention)
- 45+ metrics per snapshot (technical, dealer, volatility, price)
- 8 critical Wyckoff events (BC, SC, AR, ST, SPRING, TEST, SOS, SOW)
- 4 option strategies (Long Call, Long Put, CSP, Vertical Spread)
- Minimal dashboard with recommendations and alerts
- Directional accuracy scoring (Brier)
- Test coverage ≥ 80% for all new code
- Three environments (dev/test/prod) on local Mac

**Deferred to Post-MVP:**
- Full 17 Wyckoff events
- Calendar Spread, Covered Call strategies
- Chatbot interface
- Email scraping
- Advanced UI/charts
- Cloud deployment (AWS/Fly.io)
- Automatic daily job scheduling (manual trigger for MVP)

### 1.4 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-07 | Initial architecture |
| 2.0 | 2025-12-09 | Enhanced schema (45+ columns), full universe OHLCV, options summary table, revised Sprint 2 |
| 3.0 | 2025-12-11 | **TDD testing strategy**, **Mac-only deployment**, **environment promotion**, **initial data seeding**, **140-ticker watchlist**, removed cloud deployment from MVP |
| 3.2 | 2025-12 | Wyckoff benchmark results incorporated; Sprint 2 sequencing clarified; Metrics enrichment formally positioned; Wyckoff logic marked as research-validated, not final |

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

### 2.3 AI Stocks Watchlist (140 Tickers)

The primary watchlist for daily analysis:

```
AAPL, ADBE, ADI, AEHR, AEVA, AI, AMBA, AMD, AMZN, ANET,
APPN, ASML, AVGO, BB, BBWI, BIDU, BILL, BKE, BOLT, BPMC,
BRO, BWXT, CCJ, CEG, CHKP, CMG, COCO, CORZ, CRM, CRWD,
CXM, DDOG, DELL, DKS, DOCU, DOMO, DUOL, ESTC, ETSY, FIVN,
FLNC, FRPT, FRSH, FTNT, GE, GEL, GEV, GLD, GOOG, GST,
GTLB, HD, HON, HOOK, HUBS, IBM, IFNNY, ILMN, INTC, INTU,
INVZ, IONQ, JBL, JNJ, JNPR, JNUG, KGC, LDSF, LLY, LMT,
LULU, MANH, MCD, META, MNPR, MOD, MRVL, MSFT, MTTR, MVIS,
NEM, NET, NEWR, NFLX, NKE, NOVT, NOW, NTRA, NVDA, NVST,
OKTA, ON, ORCL, PATH, PFE, PG, PLTR, PSNY, PTON, PYPL,
QCOM, QQQ, RBLX, REGN, RKLB, ROKU, RTX, SBUX, SHOP, SMCI,
SNAP, SOFI, SONO, SPOT, SPY, STM, STRL, SWAV, TEAM, TECH,
TER, TLRY, TSLA, TSM, TTD, TTWO, TXN, UBER, UPST, UTHR,
UVXY, VRTX, VRT, VZ, WBA, WDC, WMT, WORK, WW, WWD,
XOM, ZM, ZS
```

**Count:** 140 tickers

---

## 3. SYSTEM REQUIREMENTS

### 3.1 Functional Requirements - P1 (Must Have)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-001 | Daily batch job loads OHLCV for full universe | ~15K tickers loaded from S3 |
| FR-002 | Daily batch job fetches options chains for watchlist | All 140 watchlist tickers have current options data |
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
| FR-014 | Alert on BC Score ≥ 24 | EXIT signal displayed prominently |
| FR-015 | Alert on SPRING + SOS events | ENTRY signal displayed prominently |
| FR-016 | Test coverage ≥ 80% for new code | All stories include test specifications |
| FR-017 | Three environments (dev/test/prod) | Isolated databases, promotion workflow |

### 3.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Daily pipeline completion time | < 20 minutes for 140 watchlist tickers |
| NFR-002 | S3 OHLCV load time | < 60 seconds for full universe |
| NFR-003 | Dashboard response time | < 2 seconds page load |
| NFR-004 | Data retention (OHLCV) | Rolling 730 trading days, compress after 365 |
| NFR-005 | Data retention (options chains) | 90 days |
| NFR-006 | Cost (infrastructure) | $0/month for MVP (local Mac) |
| NFR-007 | Test coverage | ≥ 80% for all new code |

---

## 4. ARCHITECTURE DECISIONS

### 4.1 Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY STACK v3.1                           │
├─────────────────────────────────────────────────────────────────────────┤
│  FRONTEND          Next.js 14 + Shadcn/ui + Tailwind CSS               │
│  API GATEWAY       TypeScript + Express.js + Drizzle ORM               │
│  CORE SERVICES     Python 3.11 + FastAPI + SQLAlchemy                  │
│  DATABASE          PostgreSQL 15 + TimescaleDB 2.x                     │
│  CACHE             Redis 7                                             │
│  TESTING           pytest + pytest-asyncio + pytest-cov (80% min)      │
│  EXTERNAL          Polygon S3, Polygon API, Polygon MCP, Claude API    │
│  INFRASTRUCTURE    Docker Compose on Mac (dev/test/prod sequential)    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE FLOW (140 tickers)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  MANUAL TRIGGER ─► PHASE 1: S3 OHLCV LOAD (~30 sec)                    │
│                    • Download daily file (~15K tickers)                 │
│                    • Bulk COPY to ohlcv_daily                          │
│                              │                                          │
│                              ▼                                          │
│                ─► PHASE 2: OPTIONS ENRICHMENT (~7 min)                 │
│                    • Polygon API for 140 watchlist tickers             │
│                    • Store contracts + aggregate summary               │
│                              │                                          │
│                              ▼                                          │
│                ─► PHASE 3: METRICS CALCULATION (~5 min)                │
│                    • Polygon MCP: 84 TA indicators                     │
│                    • Dealer, volatility, price metrics                 │
│                              │                                          │
│                              ▼                                          │
│                ─► PHASE 4: WYCKOFF ANALYSIS (~5 min)                   │
│                    • Phase classification (A-E)                        │
│                    • 8 event detection + BC/Spring scoring             │
│                    • Store to daily_snapshots (45+ columns)            │
│                              │                                          │
│                              ▼                                          │
│                ─► PHASE 5: RECOMMENDATIONS (~5 min)                    │
│                    • Claude API for actionable signals                 │
│                    • Validate real strikes only                        │
│                                                                         │
│  TOTAL: ~20 minutes for 140 tickers                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DATA MODEL

### 5.1 Two-Layer Data Model (NEW in v3.1)

- **Base Market Data Layer**  
  - Scope: *All* listed tickers with raw OHLCV only.  
  - Source: Massive (Polygon) S3 daily aggregates, hydrated through the Base OHLCV Loader.  
  - Storage: `ohlcv` table keyed by `(ticker_id, date)` optimized for bulk ingest, retention, and range scans.  
- **Analytical Layer**  
  - Scope: Portfolio/watchlist tickers only (AI_STOCKS today).  
  - Inputs: Always read from the Base layer—never directly from S3.  
  - Outputs: Wyckoff metrics, options/vol/dealer analytics, indicators, and recommendations.

### 5.2 Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BASE MARKET DATA LAYER (All tickers)                                   │
│  └─ ohlcv (TimescaleDB Hypertable) - Rolling 730 trading days          │
│                                                                         │
│  ANALYTICAL LAYER (Portfolios / Watchlists)                             │
│  ├─ options_chains (90-day retention)                                   │
│  ├─ options_daily_summary (aggregated walls, Greeks)                    │
│  └─ daily_snapshots (45+ columns: Wyckoff + all metrics)               │
│                                                                         │
│  RECOMMENDATION LAYER                                                   │
│  ├─ recommendations (trade suggestions)                                 │
│  └─ recommendation_outcomes (Brier scores)                              │
│                                                                         │
│  REFERENCE LAYER                                                        │
│  ├─ tickers (universe with tier classification)                         │
│  ├─ portfolios (watchlist groupings)                                    │
│  ├─ portfolio_tickers (many-to-many with P1/P2 priority)               │
│  └─ job_runs (pipeline audit trail)                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Base OHLCV Policy (Rolling 730 Trading Days)

- **Coverage:** All tickers in `tickers` (Polygon universe).  
- **Depth:** Rolling window of the most recent 730 trading days (≈2 calendar years).  
- **S3 Source:** `us_stocks_sip/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz` via Massive flat files.  
- **Daily Update Model:**  
  1. Base loader ingests the *entire* trading-day file (one S3 read).  
  2. Bulk insert rows into `ohlcv` with `ON CONFLICT (ticker_id, date) DO NOTHING`.  
  3. Commit per-day to maintain transactional integrity.  
- **Retention & Compression:**  
  - Delete/mark data older than 730 trading days immediately after each run.  
  - If TimescaleDB compression is enabled, compress partitions older than 365 days.  
- **Isolation:** Watchlist/analytical jobs are forbidden from pulling data directly from S3—Base layer is the only ingress.

### 5.4 Analytical Layer Responsibilities

- Consume only persisted data (`ohlcv`, options tables, `daily_snapshots`).  
- Execute Wyckoff phase/event detection, volatility/dealer computations, and technical indicators via pandas.  
- Produce watchlist analytics deterministically so reruns on the same `ohlcv` slice yield identical outputs.  
- React to portfolio composition changes without touching S3—new tickers already exist in the Base layer.  
- Export enriched metrics for downstream APIs and dashboards.

### 5.5 daily_snapshots Key Columns (45+)

| Category | Columns |
|----------|---------|
| **Identity** | time, symbol |
| **Wyckoff Phase** | wyckoff_phase, phase_score, phase_confidence |
| **Wyckoff Events** | events_detected[], primary_event, events_json |
| **Wyckoff Scores** | bc_score (0-28), spring_score (0-12), composite_score |
| **Tech-Momentum** | rsi_14, macd_line, macd_signal, macd_histogram, stoch_k, stoch_d, mfi_14 |
| **Tech-Trend** | sma_20, sma_50, sma_200, ema_12, ema_26, adx_14 |
| **Tech-Volatility** | atr_14, bbands_upper, bbands_middle, bbands_lower, bbands_width |
| **Tech-Volume** | obv, vwap |
| **Dealer Metrics** | gex_total, gex_net, gamma_flip_level, call_wall_primary, put_wall_primary, dgpi, dealer_position |
| **Volatility** | iv_skew_25d, iv_term_structure, put_call_ratio_oi, average_iv |
| **Price Metrics** | rvol, vsi, hv_20, hv_60, iv_hv_diff |
| **JSONB Storage** | technical_indicators_json, dealer_metrics_json, volatility_metrics_json, price_metrics_json |

---

## 6. SERVICE ARCHITECTURE

### 6.1 Directory Structure

```
kapman-trader/
├── KAPMAN_ARCHITECTURE_v3.1.md       ← This document
├── pytest.ini
├── environments/                     # NEW in v3.1
│   ├── dev/
│   ├── test/
│   └── prod/
├── scripts/
│   ├── init/                         # Data seeding (Sprint 0.5) + Base Loader
│   │   ├── load_ohlcv_base.py        # Base Massive loader (2-year rolling)
│   │   ├── 01_load_ticker_universe.py
│   │   ├── 02_create_watchlists.py
│   │   ├── 03_backfill_ohlcv.py
│   │   └── 04_validate_data.py
│   ├── env/                          # Environment management
│   │   ├── start-env.sh
│   │   ├── stop-env.sh
│   │   ├── promote-to-test.sh
│   │   ├── promote-to-prod.sh
│   │   └── backup-prod.sh
│   └── run-daily-job.sh              # Manual trigger
├── frontend/                         # Next.js
├── api/                              # TypeScript API Gateway
├── core/                             # Python Core Services
│   ├── providers/
│   ├── pipeline/
│   ├── wyckoff/
│   └── recommendations/
├── db/migrations/
├── tests/                            # ENHANCED in v3.1
│   ├── conftest.py                   # Shared fixtures
│   ├── fixtures/                     # Sample data
│   ├── unit/
│   │   ├── wyckoff/                  # NEW - Wyckoff tests
│   │   └── pipeline/                 # NEW - Pipeline tests
│   └── integration/
└── docs/
```

---

## 7. API SPECIFICATION

### 7.1 Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jobs/daily` | Trigger daily job (manual) |
| GET | `/api/portfolios` | List portfolios |
| GET | `/api/tickers/:symbol` | Get ticker with latest snapshot |
| GET | `/api/recommendations` | List recommendations |
| GET | `/api/dashboard/alerts` | Active alerts (BC ≥ 24, SPRING+SOS) |
| POST | `/pipeline/daily` | Run full daily pipeline (Core) |
| GET | `/health` | Health check |

---

## 8. TESTING STRATEGY

### 8.1 Testing Philosophy

**Test-Driven Development (TDD):** For all new stories starting with Sprint 2.2:
1. Write test specification BEFORE implementation
2. Create failing tests
3. Implement code to pass tests
4. Refactor while maintaining green tests

### 8.2 Coverage Requirements

| Metric | Requirement |
|--------|-------------|
| **New Code Coverage** | ≥ 80% |
| **Critical Paths** | 100% (Wyckoff scoring, signal generation) |
| **Branch Coverage** | ≥ 70% |

### 8.3 Story Test Specification Template

Every story MUST include this section before implementation:

```markdown
## Story X.Y: [Name]

### Test Specification

#### Unit Tests (tests/unit/test_<module>.py)
| Test Case | Input | Expected Output | Mocks Required |
|-----------|-------|-----------------|----------------|
| test_<function>_happy_path | ... | ... | ... |
| test_<function>_edge_case | ... | ... | ... |
| test_<function>_error_handling | ... | ... | ... |

#### Integration Tests (tests/integration/test_<feature>.py)
| Test Case | Setup | Action | Assertion |
|-----------|-------|--------|-----------|
| test_<workflow>_e2e | ... | ... | ... |

#### Acceptance Criteria
- [ ] All unit tests pass
- [ ] All integration tests pass  
- [ ] Coverage ≥ 80% for new code
- [ ] `pytest tests/ -v` shows all green
```

### 8.4 Test Fixtures (tests/conftest.py)

```python
import pytest

@pytest.fixture
def ai_stocks_watchlist():
    """Return the full AI stocks watchlist (140 tickers)."""
    return [
        "AAPL", "ADBE", "ADI", "AEHR", "AEVA", "AI", "AMBA", "AMD", "AMZN", "ANET",
        "APPN", "ASML", "AVGO", "BB", "BBWI", "BIDU", "BILL", "BKE", "BOLT", "BPMC",
        "BRO", "BWXT", "CCJ", "CEG", "CHKP", "CMG", "COCO", "CORZ", "CRM", "CRWD",
        "CXM", "DDOG", "DELL", "DKS", "DOCU", "DOMO", "DUOL", "ESTC", "ETSY", "FIVN",
        "FLNC", "FRPT", "FRSH", "FTNT", "GE", "GEL", "GEV", "GLD", "GOOG", "GST",
        "GTLB", "HD", "HON", "HOOK", "HUBS", "IBM", "IFNNY", "ILMN", "INTC", "INTU",
        "INVZ", "IONQ", "JBL", "JNJ", "JNPR", "JNUG", "KGC", "LDSF", "LLY", "LMT",
        "LULU", "MANH", "MCD", "META", "MNPR", "MOD", "MRVL", "MSFT", "MTTR", "MVIS",
        "NEM", "NET", "NEWR", "NFLX", "NKE", "NOVT", "NOW", "NTRA", "NVDA", "NVST",
        "OKTA", "ON", "ORCL", "PATH", "PFE", "PG", "PLTR", "PSNY", "PTON", "PYPL",
        "QCOM", "QQQ", "RBLX", "REGN", "RKLB", "ROKU", "RTX", "SBUX", "SHOP", "SMCI",
        "SNAP", "SOFI", "SONO", "SPOT", "SPY", "STM", "STRL", "SWAV", "TEAM", "TECH",
        "TER", "TLRY", "TSLA", "TSM", "TTD", "TTWO", "TXN", "UBER", "UPST", "UTHR",
        "UVXY", "VRTX", "VRT", "VZ", "WBA", "WDC", "WMT", "WORK", "WW", "WWD",
        "XOM", "ZM", "ZS"
    ]

@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data for testing."""
    return {
        "NVDA": [
            {"date": "2025-12-10", "open": 140.0, "high": 145.0, "low": 139.0, "close": 144.0, "volume": 50000000},
            {"date": "2025-12-09", "open": 138.0, "high": 141.0, "low": 137.0, "close": 140.0, "volume": 45000000}
        ]
    }

@pytest.fixture
def mock_polygon_mcp():
    """Mock Polygon MCP server responses."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.get_all_ta_indicators.return_value = {"rsi_14": 45.5, "macd_line": 1.23, "sma_20": 142.50}
    mock.get_dealer_metrics.return_value = {"gex_total": 1500000000, "dgpi": 25.5, "gamma_flip_level": 145.0}
    return mock
```

### 8.5 Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit -v

# Integration tests (requires test DB)
USE_TEST_DB=true pytest tests/integration -v

# With coverage report
pytest --cov=core --cov-report=html tests/

# Specific module
pytest tests/unit/wyckoff/test_events.py -v
```

---

## 9. ENVIRONMENT STRATEGY

### 9.1 Three-Environment Architecture

| Environment | Purpose | Data Scope |
|-------------|---------|------------|
| **dev** | Active development | 30 days OHLCV, 10 tickers |
| **test** | Pre-production validation | 90 days OHLCV, 50 tickers |
| **prod** | Live trading decisions | 730 days OHLCV, 140 tickers |

**Note:** Environments run sequentially (one at a time) to conserve Mac resources. All use port 5432.

### 9.2 Environment Management Scripts

```bash
# Start environment
./scripts/env/start-env.sh dev|test|prod

# Stop environment
./scripts/env/stop-env.sh dev|test|prod

# Promote code to test (applies migrations, loads fresh data)
./scripts/env/promote-to-test.sh

# Promote code to prod (backs up first, applies migrations)
./scripts/env/promote-to-prod.sh

# Backup prod database
./scripts/env/backup-prod.sh

# Run daily job manually
./scripts/run-daily-job.sh [prod]
```

### 9.3 Promotion Workflow

```
DEV → develop feature, run unit tests, commit to main
  │
  ▼
TEST → ./scripts/env/promote-to-test.sh
       • Pull latest main
       • Apply migrations
       • Load fresh data from Polygon (90 days)
       • Run integration tests
       • Manual validation
  │
  ▼
PROD → ./scripts/env/promote-to-prod.sh
       • Backup current prod
       • Pull latest main
       • Apply migrations (data stays)
       • Verify daily job runs
```

**Key Principle:** Code is promoted. Data is NOT promoted (each environment loads its own from Polygon).

---

## 10. IMPLEMENTATION ROADMAP

### 10.1 Timeline Overview

```
Sprint 0.5: Dec 11-12   │ Initial Data Seeding (NEW)
Sprint 1: Dec 7-13      │ Infrastructure ✅ COMPLETED
Sprint 2.0: Dec 14-16   │ Base OHLCV Loader (NEW)
Sprint 2.1+: Dec 17-20  │ Wyckoff Engine & Pipeline (analytics consume base data)
Sprint 3: Dec 21-27     │ Recommendations & Dashboard
Sprint 4: Dec 28-31     │ Hardening & Environment Setup
```

### 10.2 Sprint Summary

| Sprint | Points | Status |
|--------|--------|--------|
| Sprint 0.5: Data Seeding | 8 | 🆕 NEW |
| Sprint 1: Infrastructure | 21 | ✅ DONE |
| Sprint 2.0: Base OHLCV Loader | 8 | ✅ COMPLETED |
| Sprint 2.1+: Wyckoff & Pipeline | 20 | 🔄 IN PROGRESS |
| Sprint 3: Recommendations & UI | 18 | Planned |
| Sprint 4: Hardening & Environments | 12 | REVISED |
| **TOTAL** | **87** | |

---

## 11. SPRINT 0.5: INITIAL DATA SEEDING

**Duration:** December 11-12, 2025 | **Points:** 8

### Stories

| Story | Points | Description |
|-------|--------|-------------|
| 0.5.1 | 2 | Load ticker universe from Polygon (~15K) |
| 0.5.2 | 2 | Create AI_STOCKS watchlist (140 tickers) |
| 0.5.3 | 3 | Backfill OHLCV history (env-specific) |
| 0.5.4 | 1 | Validate data integrity |

### Data Depths by Environment

| Environment | Days | Time Estimate |
|-------------|------|---------------|
| dev | 30 | ~5 minutes |
| test | 90 | ~15 minutes |
| prod | 730 | ~2-3 hours |

### Running Data Seeding

```bash
./scripts/env/start-env.sh dev
python scripts/init/01_load_ticker_universe.py
python scripts/init/02_create_watchlists.py
python scripts/init/03_backfill_ohlcv.py --days 30
python scripts/init/04_validate_data.py
```

---

## 12. SPRINT 1: INFRASTRUCTURE (COMPLETED)

| Story | Points | Status |
|-------|--------|--------|
| 1.1 Dev Environment Setup | 5 | ✅ |
| 1.2 Database Setup (Migrations 001-003) | 5 | ✅ |
| 1.3 Provider Abstraction Layer | 5 | ✅ |
| 1.4 S3 OHLCV Pipeline (Basic) | 6 | ✅ |

---

## 13. SPRINT 2: WYCKOFF ENGINE & PIPELINE

**Duration:** December 14-20, 2025 | **Points:** 28  
**Structure:** Sprint 2 reordered into 2.0 (Base), 2.1 (Metrics Foundations), 2.2 (Wyckoff Events), 2.3 (Scoring/Refinement).

- **Sprint 2.0 (Dec 14-16):** Build the Base OHLCV Loader that ingests Massive daily aggregates for *all* tickers, enforces 730-day retention, and exposes deterministic data for downstream jobs. **Status:** Completed.
- **Sprint 2.1 (Metrics & Market Structure Foundations):** Introduce Technical Indicators (RSI, MACD, ADX, OBV, ATR, etc.), Dealer Metrics (GEX, DGPI, gamma flip, call/put walls), Volatility Metrics (IV term structure, skew, HV/IV). Metrics sourced from Polygon MCP or equivalent provider and stored independently of Wyckoff conclusions.
- **Sprint 2.2 (Wyckoff Event Detection Engine — Current Focus):** Wyckoff logic operates on OHLCV + enriched metrics from Sprint 2.1; events: SC, AR, ST, SPRING, TEST, SOS, SOW, BC; direction-aware ENTRY/EXIT semantics; explicit separation of event detection vs trade interpretation; research-benchmarked logic, not final trading logic.
- **Sprint 2.3 (Wyckoff Scoring & Algorithm Refinement — Future):** BC Score (0–28), Spring Score (0–12), Composite Score; scoring weights SUBJECT TO CHANGE. NOTE: Results from metrics enrichment testing in Sprint 2.1 and empirical benchmarking may require modifications to Wyckoff event logic prior to finalization of scoring in Sprint 2.3.

### 13.1 Sprint 2.0 — Base OHLCV Loader (COMPLETED)

| Story | Points | Status | Description |
|-------|--------|--------|-------------|
| 2.0.1 Base Loader Implementation | 5 | ✅ COMPLETED | Download daily Massive files, bulk insert `ohlcv`, handle ticker_id resolution |
| 2.0.2 Retention & Compression Guardrails | 3 | ✅ COMPLETED | Enforce 730-day retention, configure Timescale compression policy |

**Acceptance Criteria**
- Loads one Massive file per trading day covering the requested date range (default 730 days).  
- Inserts via COPY/`executemany` with `ON CONFLICT (ticker_id, date) DO NOTHING`.  
- Logs per-day stats (rows inserted, missing tickers, warnings).  
- Deletes (or compresses) data older than 730 trading days immediately after each run.  
- Provides deterministic data for all downstream pipelines; no watchlist job is allowed to query S3.

### 13.2 Sprint 2 — Detailed Breakdown (v3.2)

#### Sprint 2.1 — Metrics & Market Structure Foundations
- Introduce Technical Indicators (RSI, MACD, ADX, OBV, ATR, etc.).  
- Introduce Dealer Metrics (GEX, DGPI, gamma flip, call/put walls).  
- Introduce Volatility Metrics (IV term structure, skew, HV/IV).  
- Metrics sourced from Polygon MCP or equivalent provider and stored independently of Wyckoff conclusions.

#### Sprint 2.2 — Wyckoff Event Detection Engine (CURRENT FOCUS)
- Wyckoff logic operates on OHLCV + enriched metrics from Sprint 2.1.  
- Events implemented: SC, AR, ST, SPRING, TEST, SOS, SOW, BC.  
- Direction-aware ENTRY / EXIT semantics.  
- Explicit separation of event detection vs trade interpretation.  
- Uses research-benchmarked logic, not final trading logic.

#### Sprint 2.3 — Wyckoff Scoring & Algorithm Refinement (FUTURE)
- BC Score (0–28), Spring Score (0–12), Composite Score.  
- Scoring weights SUBJECT TO CHANGE.  
- NOTE: Results from metrics enrichment testing in Sprint 2.1 and empirical benchmarking may require modifications to Wyckoff event logic prior to finalization of scoring in Sprint 2.3.

#### Wyckoff Benchmark Findings (Research-Only)
- Structural Wyckoff logic showed superior precision at SPRING (UP ENTRY) and BC (DOWN / EXIT) events.  
- High-frequency signal generators (TV heuristics, VSA) produced higher volume but weaker risk-adjusted outcomes.  
- ChatGPT-derived Wyckoff logic required metric normalization to be reliable.  
- These findings inform Sprint 2.2 but do not freeze algorithm design.  
- The Wyckoff engine remains an adaptive analytical component; its rules, thresholds, and scoring may evolve based on metric validation and empirical performance prior to MVP finalization.

---

## 14. SPRINT 3: RECOMMENDATIONS & DASHBOARD

**Duration:** December 21-27, 2025 | **Points:** 18

| Story | Points | Description |
|-------|--------|-------------|
| 3.1 Recommendation Engine | 6 | Claude integration |
| 3.2 Strike Selection | 4 | Real strikes only |
| 3.3 Portfolio UI | 4 | Next.js CRUD |
| 3.4 Recommendations Dashboard | 4 | Alerts display |

---

## 15. SPRINT 4: HARDENING & ENVIRONMENT SETUP

**Duration:** December 28-31, 2025 | **Points:** 12

| Story | Points | Description |
|-------|--------|-------------|
| 4.1 Environment Configuration | 4 | dev/test/prod docker-compose |
| 4.2 Promotion Scripts | 3 | promote-to-test.sh, promote-to-prod.sh |
| 4.3 Backup & Recovery | 2 | backup-prod.sh |
| 4.4 Health Monitoring | 3 | Health endpoints, logging |

**Note:** Cloud deployment (AWS/Fly.io) removed from MVP scope.

---

## 16. CONFIGURATION REFERENCE

### Environment Variables

```bash
ENV=dev|test|prod
DATABASE_URL=postgresql://kapman:password@db:5432/kapman_${ENV}
REDIS_URL=redis://redis:6379
POLYGON_API_KEY=your_key
CLAUDE_API_KEY=sk-ant-...
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
OHLCV_HISTORY_DAYS=30|90|730
LOG_LEVEL=DEBUG|INFO|WARNING
```

---

## 17. APPENDICES

### 17.1 Wyckoff Events (MVP: 8)

| Event | Code | Detection |
|-------|------|-----------|
| Selling Climax | SC | Volume >2x avg, wide range, close near low |
| Automatic Rally | AR | Rally on declining volume |
| Secondary Test | ST | Lower volume than SC, higher low |
| Spring | SPRING | Break support, quick recovery, low volume |
| Test of Spring | TEST | Low volume retest of spring area |
| Sign of Strength | SOS | High volume rally, break resistance |
| Buying Climax | BC | Volume >2x avg, wide range at highs |
| Sign of Weakness | SOW | High volume drop, break support |

### 17.2 Signal Rules

```
ENTRY SIGNALS (🟢):
  IF SPRING + SOS confirmed → STRONG ENTRY
  IF Spring Score ≥ 9 AND BC Score < 12 → ENTRY SETUP

EXIT SIGNALS (🔴):
  IF BC Score ≥ 24 → EXIT IMMEDIATELY
  IF BC Score ≥ 20 → PREPARE EXIT
  IF SOW detected → REDUCE POSITION
```

### 17.3 Quick Reference Commands

```bash
# Environment management
./scripts/env/start-env.sh prod
./scripts/env/promote-to-test.sh
./scripts/env/backup-prod.sh

# Daily job (manual)
./scripts/run-daily-job.sh

# Testing
pytest tests/unit -v
pytest --cov=core tests/
```

---

## CHANGELOG v3.0 → v3.1

### Added
- **Two-Layer Data Model** - Base Market Data Layer (all tickers) plus Analytical Layer (watchlists only).
- **Base OHLCV Policy** - Rolling 730 trading days, ingest-all daily files, retention + compression guidance.
- **Base OHLCV Loader Sprint** - Sprint 2.0 dedicated to building the loader; Sprint 2.1+ consume base data only.
- **Documentation Refresh** - v3.1 references, Base OHLCV loader workflow, and deterministic analytics guidance.

### Changed
- **Watchlist Processing** - Explicitly consumes only persisted base ohlcv data; S3 access centralized in base loader.
- **Sprint Roadmap** - Sprint 2 reorganized into 2.0 (base loader) and 2.1+ (analytical pipelines).
- **Data Retention** - Universe table retention clarified to rolling 730 trading days (instead of 3-year blanket).

### Removed
- Direct S3 references inside watchlist/analytics workflows (now routed through base layer).

---

**END OF ARCHITECTURE DOCUMENT v3.1**

*Load this file at the start of each Windsurf session for full context.*
