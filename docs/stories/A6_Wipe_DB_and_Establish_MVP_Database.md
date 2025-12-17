# [A6] Wipe DB and Establish MVP Database Schema Baseline

## Summary

Establish the authoritative MVP database schema by performing a one-time destructive reset of the existing Postgres/TimescaleDB database and creating a clean schema baseline derived directly from **KAPMAN_ARCHITECTURE.md**. This story makes the architecture executable and resolves the absence of valid migrations.

---

## Phase 1 — Intent & Boundaries

### Why this exists

* Current database state is non-authoritative and subject to drift.
* Downstream work (A0 ingestion, A5 rebuild/validation) requires a deterministic, migration-defined baseline.

### What this delivers

* A clean, empty database created **solely via migrations**.
* TimescaleDB enabled.
* MVP schema present and structurally correct.
* Deterministic, re-runnable migrations.

### What this does NOT do

* No ingestion, backfills, metrics, analytics, or refactors.
* No data preservation.
* No role/user/password changes.
* No schema redesign beyond the architecture.

---

## Phase 2 — Inputs, Outputs, Invariants

### Inputs

* **Authoritative schema contract:** KAPMAN_ARCHITECTURE.md
* **Migration framework:** existing repo mechanism
* **Database engine:** PostgreSQL 15 + TimescaleDB 2.x

### Outputs

* Empty, structurally correct MVP database produced from migrations alone.

### In-scope tables (MVP only)

* `tickers`
* `ohlcv` (TimescaleDB hypertable)
* `options_chains`
* `daily_snapshots`
* `recommendations`
* `recommendation_outcomes`
* Minimal reference tables strictly required for integrity (FKs only)

### Invariants

* Zero data after migration.
* Schema fidelity to architecture.
* Deterministic, re-runnable migrations.
* Downstream compatibility (A0 can target without modification).

---

## Phase 3 — Data Flow & Control Flow

### Execution (single batch)

1. **Declare non-authoritative state** (conceptual precondition).
2. **Drop and recreate the target database** (entire DB, not schema).
3. **Enable required extensions** via migration (TimescaleDB only).
4. **Apply initial migrations** in deterministic order:

   * Reference tables
   * Base table `ohlcv` → convert to hypertable
   * Analytical containers
   * Recommendation tables
   * Constraints last
5. **Verify structure**:

   * Tables exist
   * Row counts are zero
   * `ohlcv` registered as hypertable

### Forbidden

* Inserts of any data
* Triggers, jobs, retention/compression policies
* Invoking ingestion or services

---

## Phase 4 — Failure Modes & Idempotency

### Failure handling

* **Active connections:** terminate connections, retry drop.
* **Privileges:** run with admin-capable role (environment prerequisite).
* **Missing TimescaleDB:** fail fast; fix environment.
* **Migration errors:** treat as hard failure; re-run from scratch after fix.

### Authentication boundary (explicit)

* A6 drops/recreates the **database only**.
* Roles, users, passwords, cluster init, Docker volumes, and auth config are **out of scope** and must not be touched.

### Idempotency

* Re-running A6 always yields the same empty schema.
* Recovery path is always: drop DB → recreate → migrate.

---

## Phase 5 — Testing Strategy

### Test philosophy

* Validate **schema correctness**, not business logic.

### Required integration tests

Location (non-negotiable): `tests/integration/`

* `test_schema_applies_from_scratch`
* `test_tables_exist`
* `test_tables_are_empty`
* `test_ohlcv_is_hypertable`
* `test_no_extra_tables`

### Rules

* Tests are discoverable via default `pytest`.
* No special flags, scripts, or runners.
* No seed data.

---

## Phase 6 — Operational Considerations

### Execution safety

* Run against the intended environment database only.
* Ensure dependent services are stopped.
* Do **not** remove Postgres volumes or reinitialize the cluster.

### Environments

* Baseline migrations apply to **all environments** (dev/test/prod).
* Execution may occur in dev initially; migrations remain universal.

### Documentation

* This is a **one-time destructive** operation to establish schema truth.
* Repeatable wipes and end-to-end validation are handled by **A5**.

---

## Acceptance Criteria

* A fresh database can be created from migrations alone.
* Schema matches KAPMAN_ARCHITECTURE.md.
* Database is empty after migration.
* Migrations are deterministic and re-runnable.
* `ohlcv` is a TimescaleDB hypertable.
* Tests run via default `pytest` with no special invocation.
* A0 ingestion can target the schema without modification.

---

## Dependencies

* **Blocks:** A0 (Canonical OHLCV Ingestion)
* **Precedes:** A5 (Deterministic DB rebuild & validation)

---

## Notes

* Metric tables/columns are introduced by their owning stories (A2/A3/A4).
* No forward-looking schema enumeration is included here by design.
