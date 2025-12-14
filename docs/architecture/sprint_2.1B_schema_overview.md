# File: docs/architecture/sprint_2.1B_schema_overview.md

# SPIKE 2.1.B — Table-Level Schema Overview (Authoritative)

## Purpose
This document defines the table-level schema design for Sprint 2.1.B Metric Schema & Storage Design. It is free of embedded interpretation, scoring, ranking, or regime logic. Column-level definitions are maintained in SQL migrations.

This document is authoritative at the table responsibility and grain level.

---

## Scope (Metric Families)
Sprint 2.1 metric families in scope:
- OHLCV
- Dealer / options-derived market structure metrics
- Volatility (split into realized and implied)

---

## Cross-Cutting Requirements
All tables and storage contracts MUST support:
- Deterministic, reproducible recomputation
- Orthogonality across metric families
- Event-driven hydration + batch updates + async backfill
- Explicit NULLs (no zero-fill)
- Versioning (algorithm + source identity)
- Idempotency via primary keys

---

## Table Set Overview

### 1) Shared / Cross-Cutting

#### `dim_symbol`
**Purpose:** Canonical instrument identity.  
**Notes:** No strategy logic. Used by all fact tables.

**Grain:** one row per instrument/symbol.

---

#### `config_set`
**Purpose:** Frozen configuration contracts used by derived metric computations.  
**Notes:** Prevents hard-coded numeric parameters. Instances are immutable and deduplicated by hash.

**Grain:** one row per configuration instance.

---

#### `etl_run`
**Purpose:** Execution provenance for hydration / batch updates / async backfills.  
**Notes:** Provides auditability and supports deterministic replays.

**Grain:** one row per run.

---

### 2) OHLCV Family (Versioned Inputs)

#### `fact_ohlcv_daily`
**Purpose:** Versioned daily OHLCV facts.  
**Notes:** Multi-source/versioned OHLCV is a locked decision; canonicalization is not performed by overwriting stored facts.

**Primary Key Grain:**
- `(symbol_id, trading_date, source_version)`

**Implications:**
- Multiple OHLCV versions may coexist per symbol/date.
- Backfills are additive when source identity differs.
- Downstream derived metrics must bind deterministically to a chosen OHLCV source identity (captured via run metadata and/or computation inputs).

---

### 3) Volatility Family (Orthogonal Split)

#### `fact_realized_volatility_daily`
**Purpose:** Realized volatility metrics derived from OHLCV (e.g., HV, ATR) per contractual scope.  
**Notes:** Derived table; must reference `config_id` and algorithm identity. NULLs preserved.

**Primary Key Grain:**
- `(symbol_id, trading_date, config_id, algo_version)`

---

#### `fact_implied_volatility_daily`
**Purpose:** Implied volatility summary metrics derived from options surfaces (e.g., IV rank/term/skew if in scope per docs).  
**Notes:** Derived table; must reference `config_id` and algorithm identity. NULLs preserved.

**Primary Key Grain:**
- `(symbol_id, trading_date, config_id, algo_version)`

---

### 4) Dealer / Market Structure Family

#### `fact_dealer_metrics_daily`
**Purpose:** Daily dealer/market-structure descriptive metrics computed from options data, consistent with Dealer Metrics Methodology.  
**Notes:** No embedded interpretation; only raw/minimally normalized metrics defined by the contract. NULLs preserved.

**Primary Key Grain:**
- `(symbol_id, trading_date, config_id, algo_version)`

---

#### `fact_options_chain_snapshot_meta`
**Purpose:** Lightweight provenance and observability metadata for the option chain snapshot used to compute derived dealer/IV metrics.  
**Notes:** This table intentionally does NOT store raw option chains in Sprint 2.1. It stores enough metadata to validate completeness and enable deterministic backfills.

**Primary Key Grain:**
- `(symbol_id, trading_date, source_version)`

---

## Relationships (Conceptual)
- `dim_symbol` is referenced by all fact tables via `symbol_id`.
- `config_set` is referenced by:
  - `fact_realized_volatility_daily`
  - `fact_implied_volatility_daily`
  - `fact_dealer_metrics_daily`
- `etl_run` is referenced by all fact tables to link rows to the producing run.
- OHLCV `source_version` and options `source_version` represent distinct upstream identities (both are explicitly versioned).

---

## Idempotency and Recomputation Rules (By Table)

### `fact_ohlcv_daily`
- Idempotency key: `(symbol_id, trading_date, source_version)`
- Re-running ingestion for the same source_version must not create duplicates.
- New source_version may be appended without touching prior versions.

### Derived Fact Tables (`fact_realized_volatility_daily`, `fact_implied_volatility_daily`, `fact_dealer_metrics_daily`)
- Idempotency key: `(symbol_id, trading_date, config_id, algo_version)`
- Re-runs overwrite by PK only (upsert).
- New versions are created only when `config_id` or algorithm identity changes.

### `fact_options_chain_snapshot_meta`
- Idempotency key: `(symbol_id, trading_date, source_version)`
- Backfills for a given source_version overwrite by PK only (upsert).

---

## Notes on “Clean Queries”
To maintain clean consumer queries while preserving provenance:
- Provide convenience views (optional, non-authoritative), such as:
  - `ohlcv_latest` (select latest ingested_at per symbol/date)
- Views must be explicit about selection rules and MUST NOT replace the underlying versioned facts.

---

## Next Artifacts (Not in This File)
- Column-level schemas: `db/schema/*.sql` migrations
- Config JSON contracts: `config/contracts/*.schema.json`
- Tests enforcing invariants: `tests/db/*`

End of document.