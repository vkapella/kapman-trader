# WINDSURF EXECUTION PROMPT — ISSUE A6

## Wipe DB and Establish MVP Database Schema Baseline

### EXECUTION AUTHORITY

You are authorized to directly modify repository files.
Approval is pre-granted.
Do NOT ask for confirmation.
Do NOT pause for approval.
Execute immediately.

### OUTPUT CONTRACT

Apply changes directly to the repository.
Return **diffs only**.
Do NOT include explanations, commentary, or summaries.

### INTERACTION RULES

Do NOT ask questions.
Do NOT request confirmation.
Do NOT explain decisions.

---

## TASK OBJECTIVE

Implement **Issue A6**: establish the authoritative MVP database schema baseline by performing a one-time destructive reset of the target Postgres/TimescaleDB database and creating a clean schema derived directly from `KAPMAN_ARCHITECTURE.md`.

This task makes the architecture executable and resolves the absence of valid migrations.

---

## HARD CONSTRAINTS (NON-NEGOTIABLE)

* Operate only on the **database**, not the Postgres cluster
* Do NOT modify or recreate roles, users, passwords, volumes, or auth config
* Do NOT add ingestion logic, backfills, metrics, analytics, or refactors
* Do NOT preserve existing data
* Do NOT redesign schema beyond what the architecture already defines
* Do NOT introduce forward-looking or speculative schema
* Use **migrations only** as the source of schema truth
* All actions must be deterministic and re-runnable

---

## SCOPE

### In-Scope Tables (MVP only)

* tickers
* ohlcv (TimescaleDB hypertable)
* options_chains
* daily_snapshots
* recommendations
* recommendation_outcomes
* minimal reference tables strictly required for foreign-key integrity

### Out of Scope

* Any metric computation or metric schema beyond architecture-locked MVP
* Any data insertion or seeding
* Any triggers, background jobs, compression, or retention policies

---

## REQUIRED IMPLEMENTATION STEPS

1. **Database Reset**

   * Drop the target database for the active environment
   * Recreate the database with the same owner
   * Do not touch roles, users, or passwords

2. **Migrations**

   * Create an initial, ordered migration set that:

     * Enables TimescaleDB
     * Creates all in-scope MVP tables
     * Converts `ohlcv` into a TimescaleDB hypertable
     * Applies primary keys and foreign keys
   * Migrations must succeed on a fresh database with no manual steps

3. **Verification (Structural Only)**

   * All expected tables exist
   * All tables are empty
   * `ohlcv` is registered as a hypertable
   * No unexpected tables are present

---

## TESTING REQUIREMENTS (ENFORCED)

If tests are introduced, they MUST:

* Live under the `tests/` directory
* Be discoverable by default `pytest`
* Require no special flags, scripts, or runners
* Be runnable in the future without re-reading this prompt

If this bar cannot be met, **reduce test scope** rather than introduce ad-hoc tests.

### Required Integration Tests (if implemented)

Location: `tests/integration/`

* test_schema_applies_from_scratch
* test_tables_exist
* test_tables_are_empty
* test_ohlcv_is_hypertable
* test_no_extra_tables

No unit tests are required unless helper code is introduced.

---

## ACCEPTANCE CRITERIA

* A fresh database can be created from migrations alone
* Schema matches `KAPMAN_ARCHITECTURE.md`
* Database is empty after migration
* Migrations are deterministic and re-runnable
* `ohlcv` is a TimescaleDB hypertable
* Tests (if present) run via default `pytest`
* A0 ingestion can target the schema without modification

---

## DEPENDENCIES

* Blocks: A0 (Canonical OHLCV Ingestion)
* Precedes: A5 (Deterministic DB Rebuild & Validation)

---

## FINAL INSTRUCTION

Execute this task immediately.
Apply changes directly.
Return **diffs only**.
