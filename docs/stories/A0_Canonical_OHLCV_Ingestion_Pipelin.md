# [A0] Canonical OHLCV Ingestion Pipeline

## Summary

Establish a single, authoritative, deterministic OHLCV ingestion pipeline that hydrates the existing MVP schema using Polygon S3 flat files. This story owns ingestion logic only. It closes the gap between an empty-but-valid database (A5) and a hydrated database that downstream analytics can rely on.

A0 does not redefine schema, infrastructure, or validation guarantees. It consumes the outputs of A6 (schema) and A5 (deterministic rebuild & validation) and makes OHLCV data presence reliable and repeatable.

---

## Problem Statement

OHLCV ingestion currently exists only as partial, fragmented, or experimental scripts. As a result:

- There is no single canonical entry point for OHLCV ingestion.
- Full-universe base loads, incremental updates, and backfills are not deterministic.
- Different paths may drift in symbol scope, date handling, or write semantics.
- Downstream systems cannot rely on OHLCV completeness.
- A5 explicitly surfaces the absence of data, but no story owns resolving it.

A0 exists to establish clear ownership of OHLCV ingestion and make data presence deterministic, auditable, and enforceable.

---

## Scope (In Scope)

A0 owns **OHLCV ingestion logic only**.

### 1. Reuse and Promotion of Archived Polygon S3 Logic

A0 explicitly reuses and promotes previously developed Polygon S3 OHLCV ingestion logic that was archived after earlier experimentation.

- This logic may be extracted, refactored, and must be relocated into the canonical A0 ingestion path.
- The archived location is a source of proven logic, not a runtime dependency.
- All reused code must ultimately live under A0-owned modules and participate in the canonical ingestion entry point.
- The `archive/` directory must not be referenced at runtime after promotion.

### 2. Full-Universe Base Load
- Hydrate OHLCV for the entire symbol universe.
- Use Polygon **S3 flat files** as the source of truth.
- Insert data into the existing A6-defined `ohlcv` table only.

### 3. Incremental Updates
- Support daily incremental ingestion.
- Must be idempotent and safe to re-run for the same date range.

### 4. Deterministic Backfills
- Support explicit, bounded historical backfills.
- Backfills must be repeatable and converge to the same final state.

### 5. Contract with A5
- A0 must satisfy A5 invariants.
- After A5 → A0, the database transitions from “empty but valid” to “hydrated and valid.”
- Absence or incompleteness of data must be visible and cause failure.

---

## Out of Scope (Non-Goals)

A0 must **not**:

- Modify schema, migrations, or Timescale configuration (A6-owned).
- Perform database teardown, wipes, or truncation (A5-owned).
- Ingest non-OHLCV data (options, fundamentals, targeted Polygon API pulls).
- Compute metrics, indicators, or analytics.
- Populate `daily_snapshots`, `recommendations`, or outcomes.
- Run ingestion implicitly (on import, startup, or background jobs).

---

## Destructive Authority

- A0 is **not** allowed to perform destructive database operations.
- No dropping, truncating, or mass deletion of data.
- If a clean slate is required, A5/A6 must be run explicitly first.
- A0 assumes a valid schema and operates only via idempotent writes.

---
### Ticker Universe Constraints

The canonical ticker universe is restricted to instruments that:
- Represent tradeable equity underlyings
- Have daily OHLCV data available in Polygon S3

Specifically:
- Included: Common Stock (CS), ETF, ADR
- Excluded: Options, crypto, FX, indices, warrants, structured products

Option contracts are intentionally excluded and will be ingested separately
via the options chain pipeline.



## Determinism Requirements

A0 is deterministic if:

- Given the same symbol universe, date range, and Polygon S3 inputs,
  repeated executions converge to the same `ohlcv` table contents.
- Natural key is `(ticker_id, date)`.
- Re-ingesting the same range:
  - does not create duplicates
  - does not change values
- Order of ingestion (files, symbols, batches) does not affect results.
- Partial failures can be re-run without manual cleanup.

Determinism applies to **final state**, not execution path.

---

## Validation Requirements

A0 must make it possible to prove:

- `ohlcv` transitions from empty to non-empty after ingestion.
- Date coverage matches the requested range.
- Symbol coverage is complete or explicitly reported as missing.
- Foreign key integrity holds.
- Re-running the same ingestion does not change row counts or values.

Validation must be:
- explicit
- automatable
- non-interactive
- fail-fast

Silent success is forbidden.

---

## Acceptance Criteria (Binary)

A0 is complete if and only if:

1. Exactly one canonical OHLCV ingestion entry point exists.
2. Full-universe base load from Polygon S3 succeeds.
3. Incremental ingestion is idempotent.
4. Explicit validation of date and symbol coverage is performed.
5. Re-running A0 with identical inputs produces identical results.
6. A5 → A0 runs succeed without modification.
7. No out-of-scope behavior is present.

Any violation is a failure.

---

## Anti-Goals (Hard Exclusions)

A0 must not:
- Redefine schema or determinism rules.
- Act as a general market data service.
- Hide partial ingestion or missing data.
- Expand scope into analytics or modeling.
- Introduce implicit or background execution.

---

## Dependencies

- **Depends on**:
  - A6 — MVP schema and migrations
  - A5 — deterministic rebuild and baseline validation

- **Blocks**:
  - Metrics, snapshots, and recommendation stories
  - Any downstream logic that assumes OHLCV presence

---

## Notes

This story establishes ingestion as a first-class, deterministic system component. It intentionally stays narrow to prevent drift and preserve layered ownership:

- A6 → schema truth  
- A5 → rebuild & validation  
- A0 → data hydration  

Everything else builds on top.