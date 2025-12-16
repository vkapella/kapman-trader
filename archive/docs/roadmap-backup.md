## 10. IMPLEMENTATION ROADMAP

### 10.1 Timeline Overview

```
Sprint 0.5: Dec 11-12   │ Initial Data Seeding ✅ COMPLETED
Sprint 1: Dec 7-13      │ Infrastructure ✅ COMPLETED
Sprint 2.0: Dec 14-16   │ Base OHLCV Loader ✅ COMPLETED
Sprint 2.1+: Dec 17-20  │ Wyckoff Engine & Pipeline (analytics consume base data)
Sprint 3: Dec 21-27     │ Recommendations & Dashboard
Sprint 4: Dec 28-31     │ Hardening & Environment Setup
```

### 10.2 Sprint Summary

| Sprint | Points | Status |
|--------|--------|--------|
| Sprint 0.5: Data Seeding | 8 | ✅ COMPLETED |
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

### 13.2 Sprint Smoke Tests (Architectural Contracts)

- **Definition:** Sprint smoke tests are mandatory, read-only, shell-invoked SQL checks that guard architectural invariants. They fail hard on drift and gate progression past the relevant sprint.
- **Scope:** Architecture-only; they do not validate business logic or analytics outputs.
- **Sprint 2.0.1 — Base OHLCV Foundation Invariants**
  - `ohlcv_daily` table exists.
  - `ohlcv_daily` is a Timescale hypertable.
- **Sprint 2.0.2 — Base OHLCV Lifecycle Invariants**
  - Retention policy exists on `ohlcv_daily` with `drop_after = 730 days`.
  - Compression is enabled on `ohlcv_daily`.
  - Compression policy exists on `ohlcv_daily` with `compress_after ≈ 365 days`.
- **Execution:** Run `scripts/env/run_smoke_tests.sh` (uses SQL files in `scripts/db/`) before advancing past the protected sprint boundary. Tests are read-only and must exit non-zero on any invariant violation.

### 13.3 Sprint 2 — Detailed Breakdown (v3.2)

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