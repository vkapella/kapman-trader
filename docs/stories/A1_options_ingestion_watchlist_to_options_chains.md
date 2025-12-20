docs/stories/A1_options_ingestion_watchlist_to_options_chains.md

STORY A1 — Options Ingestion (Watchlist → options_chains)

Story ID: A1
Roadmap Reference: S-OPT-02
Status: Planned

⸻

Story Intent

Downstream MVP capabilities (dealer positioning, options-based volatility, and recommendation validation) require real, persisted options snapshot data. Although the options_chains hypertable exists, there is currently no production ingestion path that hydrates it deterministically from the authoritative symbol scope.

This story establishes the single authoritative ingestion mechanism for options snapshot chains so all downstream analytics operate on persisted data rather than live API calls. It consumes the persisted watchlists introduced in A7 and produces a stable, idempotent options snapshot substrate.

⸻

Scope

In Scope
	•	Ingest full option-chain snapshots for watchlist symbols only
	•	Two invocation modes using a single shared execution path:
	•	Batch (primary): end-of-day ingestion for all active watchlist symbols
	•	Ad-hoc (secondary): operator-invoked re-runs using the same code path
	•	Source: Polygon Options Snapshot REST API only
	•	Persist raw provider snapshot rows into options_chains
	•	Deterministic, idempotent execution with safe re-runs (upserts)
	•	Bounded parallelism by symbol with a global run lock

Out of Scope
	•	Dealer metrics
	•	Options-based volatility metrics
	•	Strategy, strike, or expiration selection logic
	•	Joins to OHLCV or daily_snapshots
	•	Historical backfills across prior days
	•	Schema changes
	•	UI or API exposure
	•	Triggering downstream pipelines

⸻

Inputs and Outputs

Inputs
	•	watchlists table
	•	active = true
	•	Symbols deduplicated across all watchlists
	•	Polygon Options REST API (per-underlying options snapshot, paginated)

Outputs
	•	options_chains table

Persistence semantics:
	•	One row per contract per snapshot_time
	•	Upsert key is the composite (time, ticker_id, expiration_date, strike_price, option_type)
	•	Re-ingesting the same snapshot_time is idempotent (no duplicates, deterministic updates)

⸻

Invariants
	•	Watchlists are the authoritative symbol scope for all options ingestion
	•	Polygon Snapshot REST API is the sole provider
	•	Option contracts are implicit facts derived from snapshot rows only
	•	Idempotent upserts keyed by the snapshot composite key; safe re-runs
	•	No ingestion logic performs deletions
	•	No analytical interpretation or enrichment
	•	Schema is owned by A6.1 (this story does not modify schema)

⸻

Execution Flow

Shared interface:
	•	ingest_options_chains(symbols: list[str], run_mode: “batch” | “adhoc”)

Batch flow (primary)
	1.	Acquire a global advisory lock to prevent concurrent runs
	2.	Query all active symbols from watchlists
	3.	Deduplicate symbols across watchlists
	4.	For each symbol (bounded concurrency):
	•	Fetch the full options snapshot chain from Polygon (paginate using next_url)
	•	Normalize provider fields required by the composite key
	•	Upsert snapshot rows into options_chains keyed by the composite key
	6.	Release advisory lock
	7.	Emit run summary (symbols attempted, succeeded, failed; rows written)

Ad-hoc flow (secondary)
	1.	Acquire the same global advisory lock
	2.	Accept an explicit symbol subset or default to all active watchlist symbols
	3.	Invoke the same shared ingestion logic
	4.	Release advisory lock
	5.	Emit run summary

⸻

Failure Handling and Idempotency

Failure isolation
	•	Failures are isolated per symbol
	•	API, pagination, or data-shape failures for one symbol do not block others

Hard failures (fail the run)
	•	Inability to access Polygon API (systemic failure)
	•	Inability to connect to the database

Soft failures (log and continue)
	•	Individual symbol failures
	•	Partial provider responses

Idempotency
	•	Upserts are keyed by (time, ticker_id, expiration_date, strike_price, option_type)
	•	Re-running ingestion for the same snapshot_time produces no duplicates
	•	Later runs at new snapshot_time append new time-series rows
	•	Partial progress is acceptable; re-runs converge to the intended state

⸻

Testing Requirements

Unit tests
	•	Symbol selection and deduplication from watchlists
	•	Normalization of Polygon responses
	•	Upsert behavior for existing contracts
	•	Tolerance of missing optional fields

Integration tests
	•	End-to-end ingestion for multiple symbols with mocked Polygon responses
	•	Pagination handling
	•	Idempotent re-run with no duplicate composite keys

Out of scope for this story’s tests:
	•	Financial correctness of dealer or volatility metrics
	•	Strategy outcomes
	•	Performance benchmarking at production scale

⸻

Operational Notes
	•	Manual re-runs are safe and deterministic
	•	Multiple runs per day converge to the same end state
	•	Logging minimum:
	•	Run start (mode, symbol count)
	•	Per-symbol summary (contracts, rows, elapsed, errors)
	•	Run end (success/failure counts, total rows)
	•	Use bounded concurrency and bulk upserts to protect API and DB
	•	Retention is enforced outside this story (DB policies, not ingestion code)

⸻

Acceptance Criteria
	•	Options chains fetched for all active watchlist symbols
	•	Data persisted to options_chains
	•	Idempotent upserts with no duplicate composite keys
	•	Polygon Snapshot REST API only
	•	No schema changes (schema owned by A6.1)
	•	All unit and integration tests green

END OF STORY A1
