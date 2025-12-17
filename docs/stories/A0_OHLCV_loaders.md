# STORY: Canonical OHLCV Ingestion Pipeline (Full-Universe Hydration, Daily Incremental, Deterministic Backfill)

## Context
OHLCV ingestion is currently fragmented across multiple scripts and pipeline classes with different schemas (`ohlcv` vs `ohlcv_daily`), sources, and symbol scopes. There is no single authoritative entrypoint that guarantees OHLCV availability for the full symbol universe in the table expected by downstream consumers. This blocks metrics snapshot persistence and integration tests.

This story establishes **one canonical, deterministic OHLCV ingestion path** that downstream systems can rely on.

---

## Phase 1 — Story Framing & Intent

### Why This Story Exists
- Multiple overlapping OHLCV loaders create ambiguity and drift.
- Downstream logic expects OHLCV in `ohlcv_daily`, but ingestion paths are inconsistent.
- There is no deterministic, idempotent command to hydrate, incrementally update, and backfill OHLCV for the full universe.

### What This Story Delivers
- A single canonical OHLCV ingestion entrypoint.
- Full-universe default behavior for all runs.
- Deterministic support for:
  - Initial hydration
  - Daily incremental ingestion
  - Arbitrary backfill over a date range
- Idempotent, re-runnable writes to `ohlcv_daily`.
- Removal, deprecation, or quarantine of overlapping/legacy ingestion paths.

### What This Story Does NOT Do
- No changes to metric computation logic.
- No redesign of provider abstractions beyond wiring.
- No new event-driven or streaming mechanisms.
- No performance optimization beyond correctness.

---

## Phase 2 — Inputs, Outputs, and Invariants

### Tables Read
- `tickers`
  - Authoritative symbol universe.
  - Loaded once per run.

### Tables Written
- `ohlcv_daily` (authoritative)
  - Idempotent upsert on `(symbol_id, time)`.
- Explicitly NOT written:
  - `ohlcv` (legacy).

### External Sources
- Massive S3 OHLCV daily aggregates (canonical historical source).
- Optional provider abstraction only if wired into the same canonical path.

### Invariants
- OHLCV ingestion always operates on the **full universe by default**.
- Symbol subsetting is allowed only via explicit override and is non-authoritative.
- Downstream systems never fetch raw OHLCV externally.
- Batch-oriented, deterministic execution only.

---

## Phase 3 — Data Flow & Control Flow

### Entry Point
Single CLI/script (e.g., `load_ohlcv_daily.py`) with:
- Date controls:
  - `--start YYYY-MM-DD --end YYYY-MM-DD`
  - OR `--days N`
- Optional override:
  - `--symbols SYMBOL1,SYMBOL2,...` (explicit, logged warning)

### Execution Steps
1. Parse inputs and resolve date range.
2. Load full symbol universe from `tickers` and build `symbol → symbol_id` map.
3. If `--symbols` provided, intersect with universe and log non-authoritative mode.
4. For each date in range (outer loop):
   - Fetch OHLCV data for that date from the canonical source.
   - Parse rows and filter to universe (and optional override).
   - Map symbols to `symbol_id`.
   - Bulk upsert rows into `ohlcv_daily`.
   - Commit per-date transaction.
5. Emit completion summary.

### Batch Boundaries
- Per-date atomicity: each date is an independent batch.

---

## Phase 4 — Failure Modes & Idempotency

### Failure Modes
- Missing source data for a date: ingest available symbols, log missing count.
- Source read failure for a date: skip date, no DB writes for that date.
- Database write failure: rollback date batch, continue with next date.
- Unknown symbols: skip rows, aggregate warning.

### Idempotency
- Upsert on `(symbol_id, time)` with overwrite semantics.
- Re-running the same parameters yields the same database state.
- Manual re-run is the retry mechanism for MVP.

---

## Phase 5 — Testing Strategy

### Unit Tests
- Date range resolution.
- Universe loading and override filtering.
- Parsing and normalization of OHLCV rows.
- Symbol mapping behavior.

### Integration Tests
- Full-universe hydration writes to `ohlcv_daily`.
- Daily incremental ingestion.
- Deterministic backfill over a range.
- Idempotent re-runs.
- Partial source coverage handling.
- Explicit symbol override behavior with warning.

Integration tests for metrics snapshot persistence must pass after this story.

---

## Phase 6 — Operational Considerations

### Reruns and Backfills
- Same command supports hydrate, daily, and backfill.
- Safe to re-run at any time.
- Backfills default to full universe.

### Logging
- Job start with parameters.
- Per-date progress.
- Warnings for missing data and symbol overrides.
- Completion summary.

### Performance
- Sequential, batch-oriented execution.
- Bulk writes per date.
- No parallelization required for MVP.

---

## Phase 7 — Definition of Done

- One canonical OHLCV ingestion entrypoint exists.
- Default behavior ingests the full symbol universe.
- Writes exclusively to `ohlcv_daily`.
- Supports hydrate, daily, and backfill via parameters.
- Idempotent and deterministic.
- Legacy/duplicate ingestion paths are removed, deprecated, or clearly quarantined.
- Integration tests depending on OHLCV presence pass without modification.