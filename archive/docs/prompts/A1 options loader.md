# WINDSURF IMPLEMENTATION PROMPT — STORY A1 (FROZEN, CORE-ALIGNED)

Story: A1_options_ingestion_watchlist_to_options_chains  
Role: Strict execution planner and implementation lead  
Repo reality: kapman-trader uses `core/` as the primary code root, with Polygon under `core/providers/market_data/`  
Status: Authoritative, frozen, non-negotiable

This file is a literal Windsurf / Codex execution prompt. Treat it as a file artifact. Do not add commentary, explanations, or scope beyond what is written here.

---

## OBJECTIVE

Implement the end-to-end ingestion path that:
- reads symbols from the existing watchlist
- fetches options chains from Polygon REST
- normalizes raw provider data into the existing internal shape
- performs idempotent upserts into existing database tables

The implementation must support:
- batch execution
- event-driven execution

Both execution modes MUST share the same core code path.

No analytics.  
No metrics logic.  
No schema changes.  
No architectural redesign.

---

## HARD CONSTRAINTS

- Do NOT change any database schema, migrations, constraints, or table definitions.
- Do NOT introduce options analytics, greeks, scoring, or metrics.
- Do NOT refactor unrelated ingestion, loader, or pipeline modules.
- Do NOT add new infrastructure patterns or abstractions.
- Implement ONLY what STORY A1 requires.

Violation of any constraint invalidates the implementation.

---

## CODE PLACEMENT (STRICT — CORE-ALIGNED)

Create or modify ONLY the following files. Create directories if missing. Do not relocate unrelated code.

core/providers/market_data/
- polygon_options.py

core/pipeline/
- options_ingestion.py
- options_normalizer.py

core/db/
- options_upsert.py

core/pipeline/events/   (ONLY if an events pattern already exists)
- option_chain_events.py

tests/unit/options/
- test_polygon_provider.py
- test_normalizer.py
- test_upsert.py
- test_runner.py

---

## IMPLEMENTATION REQUIREMENTS

### 1. Polygon Provider (REST Only)
File: core/providers/market_data/polygon_options.py

Implement a provider responsible for retrieving options chains from Polygon REST.

Requirements:
- Inputs: symbol (str), optional as_of_date
- Call Polygon options chain endpoint(s)
- Fully handle pagination
- Return raw provider payloads only (no transformation)
- Use existing config/env handling for the Polygon API key
- Retry transient failures (timeouts, 429, 5xx) with bounded retries
- Emit structured logs with:
  - stage = "provider"
  - symbol
  - request_count
  - pagination progress
  - HTTP errors (status + message)

No caching.  
No persistence.  
No normalization.

---

### 2. Normalization Layer
File: core/pipeline/options_normalizer.py

Implement pure, deterministic normalization functions that:
- Convert raw Polygon option contracts into the existing internal option-chain representation
- Normalize:
  - underlying symbol
  - expiration date
  - strike price
  - call/put classification
- Drop malformed or incomplete contracts with warning logs

Rules:
- No database access
- No I/O other than logging
- Deterministic output for identical input

Logging must include:
- stage = "normalize"
- symbol
- counts: raw, normalized, dropped

---

### 3. Idempotent Upserts
File: core/db/options_upsert.py

Implement idempotent upserts into existing option-chain tables.

Requirements:
- No duplicate records on re-ingestion
- No deletes
- No truncation
- Use existing unique keys and constraints
- Idempotency must be guaranteed across repeated runs

Idempotency keys must include, as supported by the existing schema:
- underlying symbol
- expiration
- strike
- call/put
- contract identifier (if present)

Logging must include:
- stage = "upsert"
- symbol
- counts: inserted, updated, skipped, total

Use existing DB/session utilities already present in the repo.

---

### 4. Shared Runner (Batch + Event)
File: core/pipeline/options_ingestion.py

Implement a single core ingestion function that executes:
provider → normalizer → upsert

Expose:
- a batch runner that:
  - pulls symbols from the existing watchlist source
  - processes symbols deterministically (sorted)
- a callable function reused by event handlers

Logging must include:
- stage = "runner"
- symbol
- per-symbol duration
- total duration
- symbols processed
- error count

Batch and event execution MUST share the same core code path.

---

### 5. Event Entry Point (If Applicable)
File: core/pipeline/events/option_chain_events.py

ONLY if an events pattern already exists in the repo:

- Implement a minimal handler that accepts an existing “symbol added” event
- Extract the symbol
- Invoke the shared runner ingestion function for that symbol

Do NOT create new event frameworks or schemas.

---

## TESTING REQUIREMENTS (UNIT ONLY)

No live Polygon calls.  
No integration tests.

test_polygon_provider.py:
- Mock HTTP responses
- Verify pagination handling
- Verify retry behavior
- Verify required logging fields

test_normalizer.py:
- Validate expiration parsing
- Validate strike parsing
- Validate call/put classification
- Validate malformed contract rejection

test_upsert.py:
- Verify insert on first run
- Verify idempotency on second run (no duplicates)
- Verify update when mutable fields change

test_runner.py:
- Batch processes multiple symbols deterministically
- Event handler invokes runner correctly
- One-symbol failure does not corrupt subsequent symbols (follow existing repo conventions)

---

## DEFINITION OF DONE

- All unit tests pass
- Batch and event paths share identical ingestion logic
- No schema changes
- No metrics or analytics logic
- Logs include stage, symbol, duration, and counts as specified

---

EXECUTE STORY A1 EXACTLY AS WRITTEN.