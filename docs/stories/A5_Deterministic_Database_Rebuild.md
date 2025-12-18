# [A5] Deterministic Database Rebuild and Baseline Validation

## Summary

A5 establishes deterministic, repeatable database teardown and rebuild behavior and validates the schema baseline established by A6. This story converts schema truth into enforceable infrastructure guarantees by proving that migrations can be applied cleanly from scratch and that the resulting database satisfies baseline structural invariants.

A5 does **not** implement ingestion logic. Instead, it defines and enforces the contract that future ingestion (A0) must satisfy.

---

## Problem Statement

Although A6 establishes authoritative schema definitions and migrations, the system currently lacks a formal, repeatable mechanism to prove that:

- the database can be rebuilt deterministically,
- migrations apply cleanly and in a stable order,
- the resulting database satisfies baseline structural invariants on every run.

Without this, downstream stories rely on assumptions rather than guarantees, and regressions in migrations or schema ordering may go undetected.

---

## Scope

### In Scope

A5 owns:

- Deterministic database teardown and rebuild using the existing A6 wipe-and-migrate mechanism
- Repeated application of existing migrations from a clean database state
- Automated validation that, after each rebuild:
  - all expected MVP tables exist
  - no unexpected tables exist
  - all tables are empty
  - TimescaleDB hypertables are correctly created
- A repeatable validation harness (tests or scripted checks) that produces binary pass/fail results

---

### Out of Scope (Non-Goals)

A5 must **not**:

- Author, modify, reorder, or delete migrations
- Implement, invoke, stub, or simulate ingestion logic
- Backfill or hydrate OHLCV or market data
- Validate data correctness, completeness, or ranges
- Modify schema definitions, indexes, triggers, or performance characteristics
- Encode business logic, trading logic, or metrics

---

## Destructive Authority

### Allowed

- Drop and recreate the target database specified via environment variables
- Terminate active connections to that database as required
- Reapply migrations from a clean state
- Repeat teardown and rebuild multiple times

All destructive actions must be explicit, intentional, and scoped to the target database only.

### Forbidden

- Dropping or modifying roles, users, passwords, clusters, or volumes
- Touching non-target databases
- Redefining destructive semantics established by A6

A5 reuses the **A6 wipe-and-migrate mechanism** as its destructive primitive.

---

## Determinism Definition

Given:

- the same migration set,
- the same reset mechanism,
- the same environment variables,

A5 must guarantee:

- identical database structure after every rebuild,
- identical table set and constraints,
- identical TimescaleDB hypertable configuration,
- an empty database state.

Any variability across runs is a failure.

---

## Validation

A5 must prove, via automated validation:

- the database can be rebuilt from scratch repeatedly,
- all migrations apply cleanly and in deterministic order,
- the resulting database matches the A6 schema exactly,
- no unexpected tables or artifacts exist,
- the absence of ingestion (A0) is visible and does not result in silent success.

Partial success is not acceptable. All failures must be explicit and actionable.

---

## Acceptance Criteria

A5 is complete if and only if:

- The database can be rebuilt deterministically multiple times using the A6 wipe mechanism
- All existing migrations apply cleanly from a fresh database
- Schema baseline invariants are validated successfully
- Failures surface explicitly and halt execution
- Validation runs non-interactively and repeatably
- No ingestion logic is required for success

---

## Anti-Goals

A5 explicitly does **not**:

- Validate market data
- Guarantee ingestion correctness
- Act as a substitute for A0
- Perform schema optimization or enhancement

---

## Dependencies

### Depends On
- **A6 — Schema Baseline (complete and frozen)**

### Blocks
- **A0 — Canonical OHLCV Ingestion**
- Any downstream story that assumes deterministic rebuilds or schema stability

### Guarantees to Downstream Stories

Once A5 is complete, downstream stories may assume:

- deterministic database rebuilds,
- stable and validated schema structure,
- early, explicit failure on schema regressions.

No downstream story may assume data presence or ingestion correctness.