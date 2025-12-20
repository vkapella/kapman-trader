A7 — Persist MVP Watchlist

Roadmap ID: S-WL-01
Slice: Slice A — Data Ingress & Core Analytics

⸻

Summary

Persist deterministic MVP watchlists as first-class data artifacts that define the authoritative symbol universe for all downstream options ingestion and analytical pipelines.

Watchlists are treated as data, not configuration, and are scoped by a stable watchlist_id. This story introduces no analytics or enrichment and explicitly unblocks S-OPT-02 and all Slice A metric stories.

⸻

Problem Statement

The MVP currently has no live, authoritative watchlist in the runtime. Symbol scope has been implied via archived scripts or ad-hoc lists, which violates determinism and blocks downstream pipelines.

This story establishes an explicit, persisted watchlist contract and removes all hidden assumptions about symbol scope.

⸻

Scope

In Scope
	•	Load MVP watchlists from external, version-controlled files
	•	Persist watchlists to the database as first-class data
	•	Support multiple watchlists, each identified by watchlist_id
	•	Reconcile persisted symbols to match the source exactly:
	•	Add missing symbols
	•	Soft-deactivate symbols removed from the source
	•	Deterministic, idempotent execution
	•	Same symbol set across dev / test / prod for MVP

Out of Scope
	•	Options ingestion
	•	Metrics or analytics
	•	Recommendations
	•	UI or CRUD interfaces
	•	Dynamic or API-sourced watchlists
	•	Capital, positions, or P&L semantics

⸻

Terminology

For MVP, Portfolio ≡ Watchlist.
Both terms refer to a persisted symbol set only. No financial, capital, or holdings semantics are implied.

⸻

Watchlist Source Convention (MVP Standard)

Source Location

All MVP watchlists MUST be loaded from the following repository location:

data/watchlists/

File Format
	•	File type: .txt
	•	Encoding: UTF-8
	•	One symbol per line
	•	No header row
	•	Blank lines and comment lines (#) are ignored

Example content:

AAPL
MSFT
NVDA
AMD

Watchlist Identification
	•	The filename (without extension) is the authoritative watchlist_id

Example:

data/watchlists/ai_growth.txt

Results in:

watchlist_id = ai_growth

Validation Rules
	•	Symbols are normalized to uppercase
	•	Whitespace is trimmed
	•	Duplicate symbols in a file are deduplicated and logged
	•	An empty effective symbol set results in a hard failure

⸻

Constraints & Invariants
	•	Deterministic: Same input files produce the same persisted state
	•	Persisted: Watchlists are stored in the database and consumed by downstream jobs
	•	Idempotent: Safe to re-run without duplicating rows
	•	Explicit dependency: Downstream pipelines must query watchlists directly
	•	Environment-scoped: Same symbol set across environments for MVP

⸻

Data Model & Contract

Primary Entity

watchlists

Multiplicity

A symbol may belong to multiple watchlists.

Lifecycle Semantics

Symbols removed from the source are soft-deactivated, not deleted.

Required Columns (Minimum)
	•	watchlist_id
	•	symbol
	•	active
	•	source
	•	created_at
	•	updated_at
	•	effective_date

Uniqueness Constraint

watchlist_id + symbol

No analytics or enrichment fields are introduced.

⸻

Execution Semantics

Invocation

Executed as a pipeline step during MVP.
In the future, watchlists will be CRUD-managed via UI.

Seeding Behavior
	•	watchlist_id is derived from the source filename
	•	If a watchlist does not exist, it is created implicitly

Reconciliation Behavior
	•	All watchlists present in data/watchlists/ are reconciled on each run
	•	Symbols not present in the source are soft-deactivated

Concurrency

Must not run concurrently with:
	•	Options ingestion
	•	Metrics or analytics pipelines

Logging (Required)
	•	Symbols added per watchlist
	•	Symbols soft-deactivated per watchlist
	•	Total active symbols per watchlist
	•	watchlist_id processed

⸻

Testing & Validation

Unit Tests (Required)
	•	File parsing
	•	Symbol normalization and deduplication
	•	Reconciliation logic
	•	Soft-deactivation behavior

Integration Tests (Required)
	•	Run against the dev database
	•	Validate multiple watchlists in one execution
	•	Verify idempotency across re-runs

Failure Cases to Test
	•	Empty watchlist file
	•	Missing watchlist file
	•	Duplicate symbols in file
	•	Invalid ticker symbols

Test Isolation

Watchlist rows are cleaned up after test execution.

Acceptance Signal

All tests green.

⸻

Acceptance Criteria
	•	Watchlists loaded exclusively from data/watchlists/*.txt
	•	watchlist_id derived from filename
	•	Deterministic reconciliation verified
	•	Soft-deactivation works as specified
	•	Hard failure on empty or missing files
	•	Multiple watchlists supported
	•	All unit and integration tests pass
	•	Downstream jobs can query watchlists successfully

⸻

Definition of Done
	•	Persisted MVP watchlists exist as authoritative data
	•	Symbol scope assumptions are explicit and testable
	•	Slice A can proceed to S-OPT-02 without hacks
	•	Architecture and roadmap terminology are aligned

⸻

Downstream Dependencies Unblocked
	•	S-OPT-02 — Options ingestion
	•	S-MET-01 — Dealer metrics
	•	S-MET-02 — Volatility metrics
	•	S-MET-03 — Derived analytics