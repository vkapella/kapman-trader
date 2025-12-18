# WINDSURF IMPLEMENTATION PROMPT — A0
# Canonical OHLCV Ingestion Pipeline
# FULL MINIMAL CONTROL — NO INTERACTION REQUIRED

## ROLE

You are an execution agent operating inside the KapMan codebase.

Your task is to IMPLEMENT story **[A0] Canonical OHLCV Ingestion Pipeline** exactly as specified.
You must not reinterpret scope, invent requirements, or weaken constraints.

This prompt is authoritative.
Do not ask clarifying questions.
If a requirement cannot be satisfied, fail explicitly.

---

## AUTHORITATIVE CONTEXT (LOCKED)

- **A6 is COMPLETE and FROZEN**
  - Schema truth lives exclusively in `db/migrations`
  - A0 must not modify schema or migrations

- **A5 is COMPLETE and FROZEN**
  - Deterministic rebuild and baseline validation exist
  - A0 must satisfy A5 invariants
  - A0 must not perform database teardown or wipes

- **Ingestion Ownership**
  - A0 exclusively owns OHLCV ingestion
  - No other story owns ingestion logic

- **Data Sources**
  - Polygon S3 flat files are the authoritative source for OHLCV
  - Polygon API is OUT OF SCOPE for A0

- **Existing State**
  - Partial / fragmented OHLCV ingestion code exists
  - Some of this code lives under `archive/`
  - That archived code contains hard-won, correct Polygon S3 access logic

---

## OBJECTIVE

Implement a **single canonical, deterministic OHLCV ingestion pipeline** that:

- Hydrates the existing A6-defined `ohlcv` table
- Uses Polygon S3 flat files as the source of truth
- Supports:
  - full-universe base loads
  - incremental daily ingestion
  - bounded historical backfills
- Converges deterministically on re-run
- Fails loudly if ingestion is incomplete or inconsistent

A0 closes the gap between:
- an empty-but-valid database (A5)
- and a hydrated, reliable database for downstream systems

---

## STRICT SCOPE BOUNDARIES

### YOU MAY:
- Create a single canonical OHLCV ingestion entry point
- Read Polygon S3 flat files
- Insert or upsert into the existing `ohlcv` table
- Validate date and symbol coverage
- Reuse and PROMOTE archived Polygon S3 ingestion logic

### YOU MUST NOT:
- Modify schema or migrations
- Drop, truncate, or wipe database tables
- Insert data into any table other than `ohlcv`
- Ingest non-OHLCV data
- Compute metrics, indicators, or analytics
- Reference `archive/` at runtime after promotion
- Hide partial success or missing data

Violating scope is a hard failure.

---

## REUSE OF ARCHIVED CODE (MANDATORY, EXPLICIT)

Archived Polygon S3 ingestion logic is a **source of proven behavior**, not a runtime dependency.

You MUST:

- Identify reusable Polygon S3 OHLCV logic under `archive/`
- Extract and relocate that logic into A0-owned modules
- Normalize imports, paths, and assumptions
- Ensure all execution flows through the canonical A0 entry point
- Ensure `archive/` is NOT referenced at runtime after promotion

Do NOT rediscover or reimplement solved S3 access problems.

---

## REQUIRED DELIVERABLES

### 1. Canonical Ingestion Entry Point

- Exactly ONE authoritative entry point to run OHLCV ingestion
- Discoverable and explicit (script or module)
- Supports:
  - full-universe base load
  - incremental runs
  - explicit date-range backfills
- All legacy ingestion paths are non-authoritative

---

### 2. Deterministic Write Semantics

- Natural key: `(ticker_id, date)`
- Writes MUST be idempotent
- Re-running the same ingestion:
  - does not change row counts
  - does not introduce duplicates
  - converges to the same final state
- Ordering (files, symbols, batches) must not affect results

---

### 3. Validation and Failure Semantics

A0 MUST explicitly validate and enforce:

- `ohlcv` transitions from empty → non-empty after ingestion
- Date coverage matches requested range
- Symbol coverage is complete OR explicitly reported as missing
- Foreign key integrity holds

If validation fails:
- Exit non-zero
- Surface actionable errors
- No silent or partial success is allowed

---

### 4. Compatibility with A5

- Running A5 → then A0 must succeed without modification
- A0 must not bypass or weaken A5 guarantees
- Absence of OHLCV data must be visible and testable

---

## EXPECTED FILE PLACEMENT (GUIDANCE, NOT OPTIONAL)

Unless a clearly superior structure already exists, use: