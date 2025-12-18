# WINDSURF IMPLEMENTATION PROMPT — A5
# Deterministic Database Rebuild and Baseline Validation
# FULL MINIMAL CONTROL — NO INTERACTION REQUIRED

## ROLE

You are an execution agent operating inside the KapMan codebase.

Your task is to IMPLEMENT story **[A5] Deterministic Database Rebuild and Baseline Validation** exactly as specified.
You must not reinterpret scope, invent requirements, or modify ownership boundaries.

This prompt is authoritative.
Do not ask clarifying questions.
If a requirement cannot be satisfied, fail explicitly.

---

## AUTHORITATIVE CONTEXT (LOCKED)

- **A6 is COMPLETE and FROZEN**
  - Schema truth lives exclusively in `db/migrations`
  - Migrations are authoritative and must not be modified

- **Database wipe and migration mechanism exists**
  - `scripts/db/a6_wipe_db_and_migrate.py`
  - This is the ONLY destructive primitive A5 may use

- **A0 ingestion DOES NOT exist yet**
  - A5 must not assume ingestion
  - A5 must not fake or stub OHLCV data

---

## OBJECTIVE

Implement deterministic, repeatable database rebuild and baseline validation behavior such that:

- The database can be dropped and recreated cleanly
- All migrations apply deterministically and in stable order
- The resulting database matches the A6 schema exactly
- The database is empty after rebuild
- Determinism is provable via automated validation
- Absence of ingestion is visible and enforced

A5 establishes infrastructure truth and acts as the validation gate for all downstream stories.

---

## STRICT SCOPE BOUNDARIES

### YOU MAY:
- Reuse the A6 wipe-and-migrate mechanism
- Apply existing migrations
- Inspect database metadata
- Add deterministic rebuild orchestration
- Add automated validation tests

### YOU MUST NOT:
- Modify migrations
- Define schema in code
- Insert or seed any data
- Implement ingestion logic
- Modify downstream application logic
- Weaken determinism guarantees

Violating scope is a hard failure.

---

## REQUIRED DELIVERABLES

### 1. Deterministic Rebuild Orchestrator

- Implement a deterministic rebuild runner
- MUST reuse `scripts/db/a6_wipe_db_and_migrate.py`
- MUST support repeated rebuilds
- MUST use environment variables only (`DATABASE_URL`, etc.)
- MUST NOT embed credentials or configuration

---

### 2. Automated Validation Harness

Implement non-interactive, binary validation that proves:

- Database rebuild succeeds from scratch
- All migrations apply cleanly and in deterministic order
- Expected MVP tables exist
- No unexpected tables exist
- All tables are empty
- TimescaleDB hypertables are correctly configured
- Repeated rebuilds produce identical schema state

Validation must be:
- deterministic
- repeatable
- discoverable via `pytest`
- runnable with no special invocation

---

### 3. Explicit Failure Semantics

- Any invariant violation must cause hard failure
- Missing data must not be masked
- No silent success is allowed

---

## TEST DISCOVERABILITY RULES (CRITICAL)

All tests must:

- Live under `tests/`
- Be discovered by plain `pytest`
- Require no flags or custom runners
- Be runnable in the future without re-reading this story

If this bar cannot be met, do fewer tests, not more tests.

---

## EXPECTED FILE PLACEMENT (GUIDANCE, NOT OPTIONAL)

Unless a clearly superior structure already exists:

- Rebuild orchestration → `scripts/db/`
- Validation tests → `tests/integration/`
- Shared helpers → `core/db/`

Do not scatter logic arbitrarily.

---

## ACCEPTANCE CONDITIONS (ALL MUST PASS)

A5 is complete if and only if:

- Database can be rebuilt deterministically multiple times
- Migrations apply cleanly every time
- Schema matches A6 definitions exactly
- Database is empty after rebuild
- Validation fails loudly on any deviation
- No ingestion logic is required or assumed

---

## OUTPUT RULES (CRITICAL)

- Modify ONLY files required to implement A5
- Do NOT refactor unrelated code
- Do NOT introduce new architecture
- Do NOT ask questions
- Do NOT explain decisions
- Produce clean, minimal diffs only

---

## COMPLETION SIGNAL

When finished:

- All A5 validation tests pass
- Deterministic rebuilds are enforced
- Absence of OHLCV ingestion is explicit
- Downstream stories can rely on these guarantees

Execute now.