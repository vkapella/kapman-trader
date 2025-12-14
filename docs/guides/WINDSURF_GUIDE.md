# KAPMAN TRADING SYSTEM – WINDSURF DEVELOPMENT GUIDE
**Version:** 3.2  
**Date:** December 2025  
**Purpose:** Provide a predictable, high-quality workflow for using Windsurf (Cascade) with the Kapman Trading System architecture during all development sprints.

---

# TABLE OF CONTENTS
1. Quick Start  
2. Required Documents  
3. Directory Structure (v3.1 Standard)  
4. Environment Model (dev / test / prod)  
5. Daily Windsurf Session Initialization  
6. Base OHLCV Loader Workflow (NEW in v3.1)  
7. Sprint Workflow (0.5 → 4)  
8. Coding Prompts  
9. Testing Workflow (TDD & Coverage Rules)  
10. Common Tasks & Commands  
11. Troubleshooting  
12. Quick Reference Card  

---

# 1. QUICK START

Before each development session:

1. Open Windsurf  
2. Open your `kapman-trader` folder  
3. Start Docker (if using containers)  
4. **Tell Cascade to read both:**
   - `docs/architecture/KAPMAN_ARCHITECTURE.md`
   - `docs/guides/WINDSURF_GUIDE.md`  
5. Wait for Cascade to confirm  
6. Begin working on your chosen Sprint Story

---

# 2. REQUIRED DOCUMENTS

| Document | Purpose |
|----------|----------|
| **KAPMAN_ARCHITECTURE.md** | Defines system architecture, data layers, DB schema, sprints |
| **WINDSURF_GUIDE.md** | Defines development workflow, prompts, coding procedures |

Uploading both files ensures Cascade has full project context.

---

# 3. DIRECTORY STRUCTURE (v3.1 STANDARD)

```
kapman-trader/
├── docs/
│   ├── architecture/
│   │   └── KAPMAN_ARCHITECTURE.md
│   └── guides/
│   |   └── WINDSURF_GUIDE.md
│   └──sprints/
│   |   └── sprint_2.1_metrics_and_market_structure.md
├── core/
│   ├── providers/
│   ├── pipeline/
│   ├── wyckoff/
│   ├── recommendations/
│   ├── models/
│   ├── db/
│   └── app/
├── api/
├── frontend/
├── scripts/
│   ├── init/
│   └── env/
├── environments/
│   ├── dev/
│   ├── test/
│   └── prod/
├── db/
│   └── migrations/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   │   ├── wyckoff/
│   │   └── pipeline/
│   └── integration/
└── README.md
```

---

# 4. ENVIRONMENT MODEL (FULL VERSION)

Kapman uses **three local environments**, running **one at a time**:

| Environment | Purpose | OHLCV Depth | Ticker Set |
|-------------|---------|-------------|-------------|
| **dev** | Active development | 30 days | 10–20 tickers |
| **test** | Pre-production validation | 90 days | 50 tickers |
| **prod** | Live analysis & daily runs | 730 days | Full 140-ticker watchlist |

### Environment Assumptions:
- Each environment has its own Postgres+TimescaleDB instance.  
- Code is **promoted**, but **data is not**.  
- DATABASE_URL format:

```
postgresql://kapman:password@localhost:5432/kapman_<env>
```

### Required scripts in `scripts/env/`:
- `start-env.sh dev|test|prod`
- `stop-env.sh dev|test|prod`
- `promote-to-test.sh`
- `promote-to-prod.sh`
- `backup-prod.sh`

---

# 5. DAILY WINDSURF SESSION INITIALIZATION

Paste this at the start of **every Windsurf session**:

```
Before we begin, load BOTH documents:

1. docs/KAPMAN_ARCHITECTURE_v3.1.md
2. docs/WINDSURF_GUIDE_v3.1.md

Confirm you understand:
- The base-first pipeline (Massive S3 → Base OHLCV Loader → Options → Metrics → Wyckoff → Recommendations)
- The dev/test/prod environment workflow
- The 45+ metrics stored in daily_snapshots
- Sprint statuses for Sprints 0.5 → 4
- Watchlist analytics **only** read from the base `ohlcv` table (never S3)
- No MCP tooling; all metrics computed internally

Wait for my instructions after loading both documents.
```

---

# 6. BASE OHLCV LOADER WORKFLOW (NEW IN v3.1)

1. Run `scripts/init/load_ohlcv_base.py` first. It pulls Massive daily aggregate files (`us_stocks_sip/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz`) and bulk-loads **all tickers** into `ohlcv` with `ON CONFLICT (ticker_id, date) DO NOTHING`.
2. Watchlist jobs (Wyckoff, options, indicators) **never** hit S3. They read only from the persisted base `ohlcv` table and other local tables.
3. Analytics are deterministic and repeatable: rerunning the same date range over the same base data yields identical outputs. Retention trims data older than 730 trading days after each run.

Key command:
```bash
python scripts/init/load_ohlcv_base.py --days 730
```

---

# 7. SPRINT WORKFLOW (COMPLETE)

## Sprint Smoke Tests (Architecture Gate)
- Purpose: Fast, read-only SQL checks that guard sprint-specific architectural invariants (not business logic).  
- When: Mandatory before advancing past the protected sprints (currently Sprint 2.0.1 and 2.0.2).  
- How they differ: Unit tests validate code paths; integration tests validate end-to-end flows; **smoke tests** validate infrastructure contracts (hypertables, retention, compression) and fail hard on drift.  
- Run locally:
```bash
DATABASE_URL=postgres://... ./scripts/env/run_smoke_tests.sh
```
- Scope covered now:
  - Sprint 2.0.1: `ohlcv_daily` exists and is a Timescale hypertable.
  - Sprint 2.0.2: Retention policy drop_after=730d; compression enabled; compression policy ≈365d.

---

## SPRINT 0.5 — INITIAL DATA SEEDING

| Story | Description | Output |
|--------|-------------|--------|
| **0.5.1** | Load full Polygon ticker universe (~15k) | `scripts/init/01_load_ticker_universe.py` |
| **0.5.2** | Create AI_STOCKS watchlist | `scripts/init/02_create_watchlists.py` |
| **0.5.3** | Backfill OHLCV history | `scripts/init/03_backfill_ohlcv.py` |
| **0.5.4** | Validate counts & spot checks | `scripts/init/04_validate_data.py` |

---

## SPRINT 1 — INFRASTRUCTURE SETUP (Completed)

Completed tasks:
- Base directory structure  
- Migrations 001–003  
- Provider abstraction layer  
- Minimal S3 loader stub  

---

## SPRINT 2 — WYCKOFF ENGINE & PIPELINE

Stories:

### **2.1 – S3 Universe Loader (Final)**
- Bulk-load OHLCV daily files from S3  
- COPY into `ohlcv_daily`  
- Update `tickers.last_ohlcv_date`

### **2.2 – Options Chain Pipeline**
- Fetch options for watchlist tickers  
- Store contracts + daily summaries  
- Compute strike walls

### **2.3 – Internal Metrics Calculator**
- Compute 45+ metrics (no MCP)  
- Populate JSONB blobs  
- Write into `daily_snapshots`

### **2.4 – Wyckoff Engine**
- Detect 8 MVP events  
- Compute BC Score, Spring Score  
- Phase classification  
- Event sequencing

### **2.5 – Daily Job Orchestrator**
Runs: OHLCV → Options → Metrics → Wyckoff → Recommendations

---

## SPRINT 3 — RECOMMENDATIONS & DASHBOARD

- Claude-based recommendation engine  
- Validate real strikes  
- Frontend dashboard  
- Alerts panel (BC≥24, Spring+SOS)

---

## SPRINT 4 — HARDENING & ENVIRONMENT SETUP

- Add environment scripts  
- Health endpoints  
- Backup/restore  
- Logging & error handling  
- Enforce coverage ≥80%  

---

# 8. CODING PROMPTS (FULL TEMPLATES)

### 8.1 Pipeline Component Prompt

```
We are building Kapman Trading System v3.1.

Use architecture + guide.

Task:
Implement core/pipeline/[component].py.
Follow TDD:
1. Write tests in tests/unit/pipeline/
2. Implement logic
3. Ensure ≥80% test coverage
4. Compute metrics internally (no MCP)
```

---

### 8.2 Wyckoff Engine Prompt

```
Implement Wyckoff engine:

Files:
- core/wyckoff/events.py
- core/wyckoff/scoring.py
- core/wyckoff/phase.py
- core/wyckoff/analyzer.py

Implement event detection:
SC, AR, ST, SPRING, TEST, SOS, BC, SOW.

Implement scoring:
BC Score (0-28)
Spring Score (0-12)

Use TDD and update daily_snapshots rows.
```

---

### 8.3 Daily Orchestrator Prompt

```
Implement core/pipeline/daily_job.py:

Run:
1. S3 OHLCV loader
2. Options loader
3. Metrics calculator
4. Wyckoff analyzer
5. Recommendations engine

Create job_runs audit entries.
Update tickers.last_analysis_date.
```

---

### 7.4 Frontend Dashboard Prompt

```
Implement dashboard in frontend/src/app/dashboard/.

Requirements:
- Show recommendations
- Show alerts (BC >= 24, Spring+SOS)
- Edit portfolio
- Use Next.js 14 + Shadcn UI
```

---

# 9. TESTING WORKFLOW (TDD & COVERAGE)

### TDD STEPS
1. Write test  
2. Test fails  
3. Implement code  
4. Test passes  
5. Refactor

### COVERAGE REQUIREMENTS
- **≥80% for all new code**
- **100%** for:
  - Wyckoff scoring  
  - Wyckoff event detectors  
  - Daily orchestrator branching logic  

### RUNNING TESTS
```
pytest -v
pytest tests/unit -v
pytest --cov=core --cov-report=html
```

---

# 10. COMMON TASKS & COMMANDS

### Start environment:
```
./scripts/env/start-env.sh dev
```

### Stop:
```
./scripts/env/stop-env.sh dev
```

### Run daily job:
```
python core/pipeline/daily_job.py
```

### Validate tickers:
```
SELECT COUNT(*) FROM tickers;
```

### Check snapshots:
```
SELECT * FROM daily_snapshots ORDER BY time DESC LIMIT 10;
```

### Promote code to test:
```
./scripts/env/promote-to-test.sh
```

---

# 11. TROUBLESHOOTING

| Issue | Cause | Fix |
|-------|--------|------|
| Missing folders | Repo not aligned with v3.1 | Rebuild directory tree |
| Cascade confusion | Not loading docs | Re-run init prompt |
| Missing snapshot columns | Migrations incomplete | Apply 001–003 |
| Wrong metrics | Using MCP logic | Replace with internal metrics |
| Slow S3 load | Not using COPY | Update loader |

---

# 12. QUICK REFERENCE CARD

```
KAPMAN – WINDSURF QUICK REFERENCE v3.1

Load Both:
1. docs/KAPMAN_ARCHITECTURE_v3.1.md
2. docs/WINDSURF_GUIDE_v3.1.md

Pipeline:
S3 OHLCV → Options → Metrics → Wyckoff → Recommendations

Sprint 0.5:
- Load tickers
- Create watchlist
- Backfill OHLCV
- Validate data

Testing:
pytest, TDD, coverage ≥ 80%

Environments:
dev = small data
test = medium data
prod = full data

DB:
TimescaleDB
daily_snapshots contains 45+ metrics
```

# END OF WINDSURF_GUIDE_v3.1.md
# Sprint 2 Execution Guidance (v3.2)
- For Sprint 2.2 work: implement Wyckoff logic cleanly, avoid premature optimization, and treat metrics as inputs rather than conclusions.  
- Metric testing may invalidate assumptions; keep Wyckoff logic modular and refactorable.

> **NOTE (Story 2.3):** Do not lock scoring weights, thresholds, or signal semantics prior to completing metric enrichment validation. Changes to Wyckoff logic are expected.
