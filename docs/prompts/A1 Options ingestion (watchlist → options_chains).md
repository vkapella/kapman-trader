WINDSURF / CODEX — IMPLEMENTATION PROMPT
STORY A1 — Options Ingestion (Watchlist → options_chains)

Implement Story A1 in the KapMan repository exactly as specified below.

Context and Architectural Invariants
	•	Watchlists are the authoritative symbol scope for all non-OHLCV ingestion.
	•	Symbols must be read exclusively from public.watchlists where active = true.
	•	Symbols must be deduplicated across all watchlists.
	•	Polygon Options REST API is the sole authoritative provider.
	•	Provider contract identifier (Polygon “ticker”, e.g. O:AAPL211119C00085000) is the canonical option identity.
	•	options_chains is the authoritative persistence table.
	•	No schema changes are permitted.
	•	No joins to OHLCV or daily_snapshots.
	•	No analytics, metrics, or scoring.
	•	Deterministic, idempotent behavior is mandatory.

Functional Requirements
	1.	Symbol Selection

	•	Query public.watchlists.
	•	Filter active = true.
	•	Deduplicate symbols across all watchlists.
	•	Order symbols deterministically.

	2.	Execution Model

	•	Provide a single ingestion implementation usable as:
	•	Scheduled batch pipeline step (primary).
	•	Ad-hoc operator-invoked run (secondary).
	•	Prevent concurrent full runs using a global PostgreSQL advisory lock.
	•	Parallelize ingestion by symbol within a single run using bounded concurrency.

	3.	Polygon Ingestion

	•	Fetch the complete options chain per symbol from the Polygon Options REST API.
	•	Handle pagination via next_url until exhaustion.
	•	Log and continue on symbol-level failures.
	•	Hard fail if the Polygon API is systemically unavailable.

	4.	Normalization

	•	Treat provider contract identifier (ticker) as the canonical upsert key.
	•	Persist provider fields verbatim where possible.
	•	Normalize underlying symbol, expiration date, strike price, and call/put as attributes.

	5.	Persistence

	•	Upsert into options_chains using provider contract id.
	•	Update all mutable fields on every run.
	•	Enforce no duplicate provider contract ids.

	6.	Reconciliation

	•	Track contracts seen per symbol per run.
	•	Soft-deactivate contracts missing from the current provider response.
	•	Reactivate contracts if they reappear on later runs.
	•	Preserve historical rows.

	7.	Failure Semantics

	•	Hard fail on:
	•	Database connectivity or authentication failure.
	•	Polygon API systemic failure.
	•	Symbol-level failures are logged and do not abort the run.
	•	Partial progress is acceptable.
	•	Re-runs must converge deterministically.

Testing Requirements

Unit Tests
	•	Symbol selection and deduplication from watchlists.
	•	Polygon response normalization.
	•	Provider contract id handling as canonical identity.
	•	Upsert logic for existing contracts.
	•	Soft-deactivation and reactivation logic.
	•	Tolerance of missing optional provider fields.

Integration Tests
	•	End-to-end ingestion for multiple symbols with mocked Polygon responses.
	•	Pagination handling across multiple pages.
	•	Idempotent re-run with no duplicate provider contract ids.
	•	Soft-deactivation across runs.

Out of Scope for Tests
	•	Dealer metrics.
	•	Volatility metrics.
	•	Strategy outcomes.
	•	Performance benchmarking at production scale.

Deliverables
	•	Ingestion implementation under core/ingestion/options.
	•	Database helpers under core/ingestion/options/db.py or equivalent.
	•	Runnable script under scripts/ingest_options.py.
	•	Unit tests and integration tests aligned with existing repository conventions.
	•	No changes to database schema or migrations.

Completion Criteria
	•	All unit tests pass.
	•	All integration tests pass.
	•	Ingestion runs successfully end-to-end.
	•	Re-running ingestion produces no duplicate provider contract ids and stable results.