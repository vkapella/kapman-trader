# KAPMAN TRADING SYSTEM - WINDSURF DEVELOPMENT GUIDE
**Version:** 2.0  
**Date:** December 9, 2025  
**Purpose:** Instructions for using architecture documents with Windsurf Cascade AI

---

## TABLE OF CONTENTS

1. [Quick Start](#1-quick-start)
2. [Document Organization](#2-document-organization)
3. [Pre-Sprint 2 Setup](#3-pre-sprint-2-setup)
4. [Session Initialization](#4-session-initialization)
5. [Sprint 2 Development Workflow](#5-sprint-2-development-workflow)
6. [Prompt Templates](#6-prompt-templates)
7. [Common Tasks](#7-common-tasks)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. QUICK START

### 1.1 Before Starting Any Session

1. **Open Windsurf** and navigate to your `kapman-trader` project
2. **Start Docker** containers if not running:
   ```bash
   docker-compose up -d
   ```
3. **Open Cascade** (Windsurf's AI assistant)
4. **Load the architecture document** using the initialization prompt below

### 1.2 Essential Files

| File | Purpose | When to Reference |
|------|---------|-------------------|
| `KAPMAN_ARCHITECTURE_v2.0.md` | Master architecture | Every session start |
| `db/migrations/004_enhanced_metrics_schema.sql` | Database schema | When working on DB/models |
| `docs/SPRINT_2_REVISED.md` | Current sprint tasks | During Sprint 2 work |
| `docs/DATA_MODEL_v1.1.md` | Detailed data model | When working on data layer |

---

## 2. DOCUMENT ORGANIZATION

### 2.1 File Locations

```
kapman-trader/
├── KAPMAN_ARCHITECTURE_v2.0.md      ← PRIMARY: Load this first
├── docs/
│   ├── DATA_MODEL_v1.1.md           ← Reference for data layer
│   ├── SPRINT_2_REVISED.md          ← Current sprint details
│   └── WINDSURF_GUIDE.md            ← This file
├── db/
│   └── migrations/
│       └── 004_enhanced_metrics_schema.sql  ← Schema reference
```

### 2.2 Document Hierarchy

```
                    ┌─────────────────────────────┐
                    │  KAPMAN_ARCHITECTURE_v2.0   │
                    │  (Master Document)          │
                    └──────────────┬──────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  DATA_MODEL      │    │  SPRINT docs     │    │  Migration SQL   │
│  (Data details)  │    │  (Task details)  │    │  (Schema DDL)    │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## 3. PRE-SPRINT 2 SETUP

**⚠️ IMPORTANT:** Complete these steps BEFORE starting Sprint 2 development.

### 3.1 Setup Checklist

| Step | Task | Status |
|------|------|--------|
| 1 | Verify Sprint 1 complete (migrations 001-003 applied) | ☐ |
| 2 | Copy new files to project (see 3.2) | ☐ |
| 3 | Backup database | ☐ |
| 4 | Apply Migration 004 | ☐ |
| 5 | Verify migration success | ☐ |
| 6 | Ready for Sprint 2! | ☐ |

### 3.2 Copy Files to Your Project

Copy these files from Claude's output to your `kapman-trader` project:

```
From Claude Output              →  Your Project Location
─────────────────────────────────────────────────────────────────
KAPMAN_ARCHITECTURE_v2.0.md     →  kapman-trader/KAPMAN_ARCHITECTURE_v2.0.md
004_enhanced_metrics_schema.sql →  kapman-trader/db/migrations/004_enhanced_metrics_schema.sql
WINDSURF_GUIDE.md               →  kapman-trader/docs/WINDSURF_GUIDE.md
DATA_MODEL_v1.1.md              →  kapman-trader/docs/DATA_MODEL_v1.1.md
SPRINT_2_REVISED.md             →  kapman-trader/docs/SPRINT_2_REVISED.md
```

### 3.3 Backup Database

```bash
# Create timestamped backup BEFORE migration
docker exec kapman-db pg_dump -U kapman kapman > backup_pre_migration_004_$(date +%Y%m%d_%H%M%S).sql

# Verify backup exists and has content
ls -la backup_pre_migration_004_*.sql
```

### 3.4 Apply Migration 004

```bash
# Apply the enhanced metrics schema
docker exec -i kapman-db psql -U kapman kapman < db/migrations/004_enhanced_metrics_schema.sql

# Expected output (many lines):
# ALTER TABLE
# CREATE INDEX
# CREATE TABLE
# SELECT 1  (for hypertable creation)
# CREATE VIEW
# INSERT 0 12  (seed data)
```

### 3.5 Verify Migration Success

Run these verification queries to confirm everything is in place:

```bash
# ─────────────────────────────────────────────────────────────────
# CHECK 1: daily_snapshots has new metric columns
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'daily_snapshots' 
  AND column_name IN ('rsi_14', 'gex_total', 'iv_skew_25d', 'rvol', 'dgpi')
ORDER BY column_name;
"
# Expected: 5 rows (dgpi, gex_total, iv_skew_25d, rvol, rsi_14)

# ─────────────────────────────────────────────────────────────────
# CHECK 2: options_daily_summary table exists
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT COUNT(*) as column_count FROM information_schema.columns 
WHERE table_name = 'options_daily_summary';
"
# Expected: ~30 columns

# ─────────────────────────────────────────────────────────────────
# CHECK 3: Alert and event views created
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT viewname FROM pg_views 
WHERE schemaname = 'public' AND viewname LIKE 'v_%'
ORDER BY viewname;
"
# Expected: v_alerts, v_entry_signals, v_exit_signals, 
#           v_latest_snapshots, v_watchlist_tickers, v_wyckoff_events

# ─────────────────────────────────────────────────────────────────
# CHECK 4: Tickers table has new columns
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'tickers' 
  AND column_name IN ('universe_tier', 'last_ohlcv_date', 'options_enabled');
"
# Expected: 3 rows

# ─────────────────────────────────────────────────────────────────
# CHECK 5: Seed ETF tickers loaded
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT symbol, universe_tier, options_enabled 
FROM tickers WHERE universe_tier IN ('etf', 'index')
ORDER BY symbol;
"
# Expected: SPY, QQQ, IWM, DIA, VIX, TLT, GLD, XLF, XLK, XLE, XLV, SMH

# ─────────────────────────────────────────────────────────────────
# CHECK 6: Final summary verification
# ─────────────────────────────────────────────────────────────────
docker exec kapman-db psql -U kapman kapman -c "
SELECT 
  (SELECT COUNT(*) FROM information_schema.columns 
   WHERE table_name = 'daily_snapshots') as snapshot_cols,
  (SELECT COUNT(*) FROM pg_views 
   WHERE schemaname = 'public' AND viewname LIKE 'v_%') as views,
  (SELECT COUNT(*) FROM tickers 
   WHERE universe_tier IS NOT NULL) as seeded_tickers;
"
# Expected: snapshot_cols ~55, views 6, seeded_tickers 12
```

### 3.6 Troubleshooting Migration Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `relation does not exist` | Earlier migrations not applied | Apply 001, 002, 003 first |
| `column already exists` | Migration partially applied | Drop column or restore backup |
| `permission denied` | Wrong user | Use `-U kapman` |
| `hypertable not found` | TimescaleDB not enabled | `CREATE EXTENSION timescaledb;` |

### 3.7 Rollback If Needed

```bash
# Only if migration fails catastrophically
docker exec -i kapman-db psql -U kapman kapman < backup_pre_migration_004_YYYYMMDD_HHMMSS.sql
```

### 3.8 Ready for Sprint 2 ✅

Once all checks pass, you're ready to start Sprint 2 development!

---

## 4. SESSION INITIALIZATION

### 4.1 Standard Session Start Prompt

Copy and paste this prompt at the start of EVERY Windsurf Cascade session:

```
I'm working on the Kapman Trading System v2. Please read the architecture document to understand the project context.

Key points:
- This is a trading decision-support system using Wyckoff methodology
- Database: TimescaleDB with hypertables for time-series data
- Backend: Python FastAPI (core) + TypeScript Express (API gateway)
- Current Sprint: Sprint 2 (Wyckoff Engine & Pipeline)

Please read: KAPMAN_ARCHITECTURE_v2.0.md

After reading, confirm you understand:
1. The 45+ column daily_snapshots schema
2. The daily pipeline phases (S3 OHLCV → Options → Metrics → Wyckoff)
3. The 8 MVP Wyckoff events and ENTRY/EXIT signal classification
4. That we're currently working on Sprint 2

Then I'll tell you what I need help with.
```

### 4.2 Sprint 2 Specific Start Prompt

```
I'm working on Kapman Trading System Sprint 2. Please read these files:

1. KAPMAN_ARCHITECTURE_v2.0.md (master architecture)
2. docs/SPRINT_2_REVISED.md (current sprint tasks)
3. db/migrations/004_enhanced_metrics_schema.sql (database schema)

Current Sprint 2 status:
- Story 2.0 (Migration 004): [DONE/IN PROGRESS/NOT STARTED]
- Story 2.1 (S3 Universe Loader): [DONE/IN PROGRESS/NOT STARTED]
- Story 2.2 (Options Chain Pipeline): [DONE/IN PROGRESS/NOT STARTED]
- Story 2.3 (Metrics Integration): [DONE/IN PROGRESS/NOT STARTED]
- Story 2.4 (Wyckoff Engine): [DONE/IN PROGRESS/NOT STARTED]
- Story 2.5 (Daily Orchestrator): [DONE/IN PROGRESS/NOT STARTED]

I need help with: [YOUR SPECIFIC TASK]
```

### 4.3 Quick Reference Start (For Follow-up Sessions)

```
Continuing Kapman Trading System development. Context refresh:
- TimescaleDB with 45+ column daily_snapshots table
- Python FastAPI core service on port 5000
- Polygon S3 for OHLCV (~15K tickers), Polygon API for options (watchlist only)
- Polygon MCP for technical indicators, dealer metrics, volatility metrics
- 8 Wyckoff events: SC, AR, ST, SPRING, TEST, SOS, BC, SOW
- ENTRY signals: SPRING, SOS, Spring Score >= 9
- EXIT signals: BC Score >= 24 (critical), BC >= 20 (warning)

Working on: [YOUR SPECIFIC TASK]
```

---

## 5. SPRINT 2 DEVELOPMENT WORKFLOW

### 5.1 Story-by-Story Prompts

#### Story 2.0: Apply Migration 004
```
I need to apply migration 004 to add the enhanced metrics schema.

Please help me:
1. Verify the migration file is correct: db/migrations/004_enhanced_metrics_schema.sql
2. Create a backup command
3. Apply the migration
4. Verify the new columns exist in daily_snapshots
5. Verify the new views (v_alerts, v_wyckoff_events, v_entry_signals, v_exit_signals)

The migration adds:
- 15 technical indicator columns (rsi_14, macd_*, sma_*, etc.)
- 9 dealer metric columns (gex_*, dgpi, dealer_position, etc.)
- 7 volatility columns (iv_skew_25d, put_call_ratio_oi, etc.)
- 8 price metric columns (rvol, vsi, hv_*, etc.)
- options_daily_summary table
- Enhanced v_alerts view with ENTRY/EXIT signals
```

#### Story 2.1: S3 Universe Loader
```
I need to implement the S3 Universe Loader (Story 2.1).

Requirements from architecture:
- Load full Polygon universe (~15K tickers) from S3 flat files
- File path: s3://flatfiles/us_stocks_sip/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
- Single file contains ALL tickers for one day
- Target: < 60 seconds for full daily load
- Must update tickers.last_ohlcv_date after load
- Auto-create tickers with universe_tier='polygon_full'

Please create: core/pipeline/s3_universe_loader.py

Include:
1. S3UniverseLoader class
2. load_daily() method
3. backfill() method for historical data
4. Bulk INSERT using COPY for performance
```

#### Story 2.2: Options Chain Pipeline
```
I need to implement the Options Chain Pipeline (Story 2.2).

Requirements from architecture:
- Fetch options ONLY for watchlist tickers (from portfolio_tickers)
- Use Polygon API: /v3/snapshot/options/{symbol}
- Rate limit: 100 RPS max (use semaphore)
- Store individual contracts in options_chains table
- Aggregate to options_daily_summary table
- Calculate top 3 call/put walls by OI

Please create: core/pipeline/options_loader.py

Include:
1. OptionsChainLoader class
2. load_watchlist_options() method
3. _fetch_options_chain() with pagination
4. _store_contracts() for raw data
5. _create_daily_summary() for aggregation
```

#### Story 2.3: Metrics Integration
```
I need to implement the Metrics Calculator (Story 2.3).

Requirements from architecture:
- Call Polygon MCP server for all metrics
- Tools to call:
  - get_all_ta_indicators (84 indicators)
  - get_dealer_metrics (GEX, DGPI, walls)
  - get_volatility_metrics (IV skew, term structure, P/C ratio)
  - get_price_metrics (RVOL, VSI, HV)
- Map MCP responses to daily_snapshots columns
- Store both extracted columns AND full JSONB

Please create: core/pipeline/metrics_calculator.py

Include:
1. MetricsCalculator class
2. calculate_all_metrics(symbol) method
3. _call_mcp(tool, params) helper
4. _map_to_snapshot() for column mapping

Refer to the daily_snapshots column reference in the architecture doc.
```

#### Story 2.4: Wyckoff Engine
```
I need to implement the Wyckoff Engine (Story 2.4).

Requirements from architecture:
- Migrate logic from existing kapman-wyckoff-module-v2
- Detect 8 MVP events: SC, AR, ST, SPRING, TEST, SOS, BC, SOW
- Calculate BC score (0-28) and Spring score (0-12)
- Classify phase (A-E) with confidence
- Track event sequence progression
- Generate signal classification (ENTRY_SIGNAL, EXIT_CRITICAL, etc.)

Please create:
1. core/wyckoff/phase.py - Phase classification
2. core/wyckoff/events.py - Event detection
3. core/wyckoff/scoring.py - BC/Spring scoring
4. core/wyckoff/analyzer.py - Main analyzer class

Event detection signals from architecture appendix:
- SC: Volume >2x avg, wide range, close near low
- SPRING: Break support, quick recovery, low volume
- SOS: High volume rally, break resistance
- BC: Volume >2x avg, wide range at highs
```

#### Story 2.5: Daily Orchestrator
```
I need to implement the Daily Batch Orchestrator (Story 2.5).

Requirements from architecture:
- Coordinate all pipeline phases in sequence
- Phase 1: S3 OHLCV (full universe) - ~30 sec
- Phase 2: Options (watchlist only) - ~5 min
- Phase 3: Metrics via MCP (watchlist only) - ~3 min
- Phase 4: Wyckoff analysis (watchlist only) - ~3 min
- Total target: < 15 minutes for 100 watchlist tickers
- Create job_runs audit trail
- Update tickers.last_analysis_date

Please create: core/pipeline/daily_job.py

Include:
1. DailyBatchJob class
2. run(target_date) orchestrator method
3. _analyze_watchlist() for metrics + Wyckoff
4. _store_snapshot() for all 45+ columns
5. Job audit methods (_create_job_run, _complete_job_run)
```

### 5.2 Testing Prompts

```
I've implemented [COMPONENT]. Please help me test it.

Create test file: tests/test_[component].py

Test cases needed:
1. [List specific test cases]
2. Mock external dependencies (S3, Polygon API, MCP)
3. Verify database writes
4. Check error handling

Use pytest with async support (pytest-asyncio).
```

---

## 6. PROMPT TEMPLATES

### 6.1 Schema Reference Prompt
```
I need to work with the daily_snapshots table. Here are the relevant columns:

Technical-Momentum: rsi_14, macd_line, macd_signal, macd_histogram, stoch_k, stoch_d, mfi_14
Technical-Trend: sma_20, sma_50, sma_200, ema_12, ema_26, adx_14
Technical-Volatility: atr_14, bbands_upper, bbands_middle, bbands_lower, bbands_width
Technical-Volume: obv, vwap
Dealer: gex_total, gex_net, gamma_flip_level, call_wall_primary, put_wall_primary, dgpi, dealer_position
Volatility: iv_skew_25d, iv_term_structure, put_call_ratio_oi, average_iv
Price: rvol, vsi, hv_20, hv_60, iv_hv_diff

Plus JSONB columns for full data: technical_indicators_json, dealer_metrics_json, volatility_metrics_json, price_metrics_json

[YOUR SPECIFIC QUESTION]
```

### 6.2 Wyckoff Event Reference Prompt
```
I need to work with Wyckoff events. Here's the reference:

8 MVP Events:
- SC (Selling Climax): Volume >2x avg, wide range, close near low
- AR (Automatic Rally): Rally on declining volume after SC
- ST (Secondary Test): Lower volume than SC, higher low
- SPRING: Break support, quick recovery, low volume
- TEST: Low volume retest of spring area
- SOS (Sign of Strength): High volume rally, break resistance
- BC (Buying Climax): Volume >2x avg, wide range at highs
- SOW (Sign of Weakness): High volume drop, break support

Signal Classification:
- ENTRY_SIGNAL: SPRING + SOS, or Spring Score >= 9
- ENTRY_SETUP: SPRING detected
- EXIT_CRITICAL: BC Score >= 24
- EXIT_WARNING: BC Score >= 20, or SOW detected

[YOUR SPECIFIC QUESTION]
```

### 6.3 Debug Prompt
```
I'm encountering an error in [COMPONENT].

Error message:
```
[PASTE ERROR]
```

Relevant code:
```python
[PASTE CODE]
```

Expected behavior: [DESCRIBE]
Actual behavior: [DESCRIBE]

Please help me debug this. Consider:
1. The Kapman architecture constraints
2. The TimescaleDB schema
3. The async/await patterns we're using
```

---

## 7. COMMON TASKS

### 7.1 Database Operations

**Check table structure:**
```bash
docker exec kapman-db psql -U kapman kapman -c "\d daily_snapshots"
```

**Query latest snapshots:**
```bash
docker exec kapman-db psql -U kapman kapman -c "SELECT * FROM v_latest_snapshots LIMIT 5;"
```

**Check alerts:**
```bash
docker exec kapman-db psql -U kapman kapman -c "SELECT * FROM v_alerts ORDER BY priority;"
```

**Check entry signals:**
```bash
docker exec kapman-db psql -U kapman kapman -c "SELECT * FROM v_entry_signals;"
```

### 7.2 Service Operations

**Start all services:**
```bash
docker-compose up -d
```

**View core service logs:**
```bash
docker-compose logs -f core
```

**Restart core after code changes:**
```bash
docker-compose restart core
```

**Run daily pipeline manually:**
```bash
curl -X POST http://localhost:5000/pipeline/daily
```

### 7.3 Development Commands

**Run Python tests:**
```bash
docker-compose exec core pytest tests/ -v
```

**Format Python code:**
```bash
docker-compose exec core black core/
```

**Type check Python:**
```bash
docker-compose exec core mypy core/
```

---

## 8. TROUBLESHOOTING

### 8.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Migration fails | Missing extension | Run `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";` |
| S3 download fails | Credentials | Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY |
| MCP connection refused | Service not running | Start Polygon MCP server on port 5001 |
| Options API 429 | Rate limit | Reduce concurrency in semaphore |
| Column not found | Migration not applied | Run migration 004 |

### 8.2 Reset Development Database

```bash
# Stop services
docker-compose down

# Remove volume
docker volume rm kapman-trader_pgdata

# Start fresh
docker-compose up -d

# Wait for DB to initialize, then apply migrations
docker exec -i kapman-db psql -U kapman kapman < db/migrations/001_initial_schema.sql
docker exec -i kapman-db psql -U kapman kapman < db/migrations/002_create_hypertables.sql
docker exec -i kapman-db psql -U kapman kapman < db/migrations/003_retention_policies.sql
docker exec -i kapman-db psql -U kapman kapman < db/migrations/004_enhanced_metrics_schema.sql
```

### 8.3 Getting Help from Cascade

If Cascade seems confused or gives incorrect suggestions:

```
Let me clarify the Kapman project context:

1. Database: TimescaleDB (PostgreSQL + time-series extensions)
2. Schema: daily_snapshots has 45+ columns, see migration 004
3. Architecture: Python FastAPI core + TypeScript Express gateway
4. Current work: Sprint 2 - Wyckoff Engine & Pipeline

Please re-read KAPMAN_ARCHITECTURE_v2.0.md section [X] and try again.
```

---

## QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KAPMAN WINDSURF QUICK REFERENCE                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FIRST TIME SETUP (before Sprint 2):                                │
│  1. Copy files to project (architecture, migration, docs)           │
│  2. docker exec kapman-db pg_dump ... > backup.sql                  │
│  3. docker exec -i kapman-db psql ... < 004_enhanced_*.sql          │
│  4. Run verification queries (see Section 3.5)                      │
│                                                                     │
│  SESSION START:                                                     │
│  1. docker-compose up -d                                            │
│  2. Load KAPMAN_ARCHITECTURE_v2.0.md in Cascade                     │
│  3. State current sprint/story                                      │
│                                                                     │
│  KEY FILES:                                                         │
│  • KAPMAN_ARCHITECTURE_v2.0.md    (master doc)                      │
│  • db/migrations/004_*.sql         (schema)                         │
│  • docs/SPRINT_2_REVISED.md        (current sprint)                 │
│                                                                     │
│  SIGNAL REFERENCE:                                                  │
│  🟢 ENTRY: SPRING, SOS, Spring Score >= 9                           │
│  🔴 EXIT:  BC Score >= 24 (critical), >= 20 (warning)               │
│  🟡 CAUTION: SOW, BC warning                                        │
│                                                                     │
│  8 WYCKOFF EVENTS (MVP):                                            │
│  Accumulation: SC → AR → ST → SPRING → TEST → SOS                   │
│  Distribution: BC → SOW                                             │
│                                                                     │
│  PIPELINE PHASES:                                                   │
│  1. S3 OHLCV (15K tickers)  →  ~30 sec                              │
│  2. Options API (watchlist) →  ~5 min                               │
│  3. Metrics MCP (watchlist) →  ~3 min                               │
│  4. Wyckoff (watchlist)     →  ~3 min                               │
│                                                                     │
│  USEFUL COMMANDS:                                                   │
│  docker-compose logs -f core                                        │
│  docker exec kapman-db psql -U kapman kapman -c "..."               │
│  curl -X POST http://localhost:5000/pipeline/daily                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

**END OF WINDSURF GUIDE**
