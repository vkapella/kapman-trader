WINDSURF / CODEX — SINGLE FILE PROMPT (MANDATORY)

Purpose and Non-Negotiable Constraint

You are generating content that will be copied verbatim into Windsurf or Codex as a single file.

Hard rules:
	•	Your entire response MUST be a single, continuous file
	•	Do NOT emit multiple Markdown blocks
	•	Do NOT use fenced code blocks
	•	Do NOT split content into sections across responses
	•	Do NOT include commentary, explanations, apologies, or meta-text
	•	Everything you output must be safe to paste as-is into Windsurf

⸻

Authorization and Execution Policy (Standing Consent)

You are explicitly authorized to autonomously perform all required read-only actions necessary to complete any task defined in this prompt.

This authorization includes, but is not limited to:
	•	Repository-wide file inspection
	•	Repository-wide issue enumeration
	•	Pagination across GitHub API results
	•	Retrieval of issue bodies, metadata, labels, milestones, and assignees
	•	Reading commit history, pull requests, and repository configuration files

No additional user confirmation is required for these actions.
Do not pause to request approval.
Do not ask follow-up questions about authorization.
Proceed autonomously until the task is fully complete.

This authorization applies for the full duration of the task.

⸻

Output Format Rules (Absolute)
	1.	Produce exactly one file
	2.	Use plain Markdown only
	3.	Do NOT use triple backticks or fenced code blocks
	4.	Do NOT split content into multiple logical outputs
	5.	Do NOT label any section as “code” or “markdown”
	6.	Do NOT prepend or append explanations outside the file content

⸻

Behavioral Constraints
	•	Do not infer intent beyond explicit instructions
	•	Do not invent data
	•	do not summarize unless explicitly asked
	•	do not omit required artifacts
	•	Preserve original formatting when extracting text
	•	Prefer completeness over brevity

⸻

Use this code when bulding a windsurf prompt to allow agents to execute without manual intervention

EXECUTION AUTHORITY:

You are authorized to directly modify files.
Approval is pre-granted.
Do NOT ask for confirmation.
Do NOT pause for approval.
Execute immediately.

OUTPUT CONTRACT:

Apply changes directly and return diffs only.

INTERACTION RULES:

Do NOT ask questions.
Do NOT request confirmation.
Do NOT explain decisions.

⸻

Task Definition

Implement A0 “Canonical OHLCV Ingestion Pipeline (Full-Universe Hydration, Daily Incremental, Deterministic Backfill)” so that a fresh database can be hydrated end-to-end without manual pre-steps, while preserving separation of concerns and full-universe defaults.

Primary symptom to fix

Running the canonical OHLCV ingest entrypoint currently fails with: “tickers table is empty; load ticker universe before OHLCV”.

Required behavior change

If tickers is empty at runtime, the canonical ingestion path MUST bootstrap tickers automatically before OHLCV hydration, using Polygon Reference API, then proceed to hydrate OHLCV from Polygon S3 for the full symbol universe.

This matches the historical archived behavior and does not violate separation of concerns:
	•	A0 owns canonical ingestion.
	•	Tickers are ingestion metadata, not analytics.

Hard constraints and invariants
	1.	Full-universe default

	•	All ingest modes (base, incremental, backfill) MUST operate on the full ticker universe by default.
	•	Symbol subsetting is allowed only via an explicit CLI override and MUST be treated as non-authoritative and logged as such.

	2.	Canonical tables

	•	OHLCV writes MUST go to ohlcv_daily only (authoritative).
	•	Do NOT write to legacy ohlcv.

	3.	Determinism and idempotence

	•	Re-running the same command with the same inputs MUST yield the same database state.
	•	Writes MUST be idempotent via upsert on the natural key.

	4.	Reuse proven archive logic

	•	There is prior, proven archive logic for:
	•	Loading the full ticker universe via Polygon Reference API (paginated /next_url).
	•	Reading Polygon S3 Massive flat files layout for daily bars.
	•	You MUST promote/refactor that logic into MVP-owned modules (no runtime references to archive/).
	•	Do NOT duplicate brittle logic if it already exists in current A0 modules; consolidate into a single canonical implementation.

	5.	Testing is mandatory

	•	Add/adjust unit and integration tests to cover the new bootstrap behavior and ensure A0 remains deterministic and full-universe by default.
	•	Keep the existing A5 integration test semantics (requires KAPMAN_TEST_DATABASE_URL). Do not weaken A5.

Implementation scope

A. Add a canonical ticker universe loader (Polygon Reference API)
Create a production module for ticker bootstrapping, using the archived behavior:
	•	Fetch all active tickers from https://api.polygon.io/v3/reference/tickers with pagination via next_url.
	•	Persist into tickers via upsert on (symbol), updating name, exchange, asset_type, currency, is_active, updated_at.
	•	Use DATABASE_URL and POLYGON_API_KEY from environment.
	•	Do not hardcode credentials.

Recommended placement (choose the best fit after inspecting repo structure; keep it coherent with existing A0 modules):
	•	core/ingestion/tickers/polygon_reference.py (API client + pagination)
	•	core/ingestion/tickers/db.py (upsert)
	•	core/ingestion/tickers/loader.py (orchestrator: ensure_universe_loaded)

Add a simple script entrypoint for manual invocation (optional but preferred):
	•	scripts/ingest_tickers.py (or scripts/load_tickers.py)
This script should be minimal: load env, call loader, print a summary.

B. Integrate bootstrap into the canonical OHLCV entrypoint
Modify the canonical OHLCV CLI script (currently scripts/ingest_ohlcv.py) so that:
	1.	It connects to the database and checks tickers rowcount.
	2.	If tickers is empty:
	•	Call the canonical ticker universe loader.
	•	Re-check tickers is now non-empty; if still empty, hard-fail with a clear error.
	3.	Then proceed with OHLCV ingestion from S3 for the full universe (default).
	4.	Preserve explicit override behavior:
	•	If –symbols is provided, it should intersect with the tickers universe, log non-authoritative mode, and proceed.

Add an explicit escape hatch flag:
	•	–no-ticker-bootstrap (default false)
If enabled and tickers is empty, fail exactly as today.

C. Ensure “full universe hydration from S3” is actually full universe
Inspect the current A0 OHLCV S3 ingestion path and verify it is not constrained by a watchlist or external ticker list.
	•	Universe source must be tickers table.
	•	S3 reads should be per-day “all symbols available for the date” or per-symbol based on universe, depending on the S3 layout used by the current implementation.
	•	If the current S3 layout is per-symbol monthly files (stocks/ohlcv/day/YYYY/MM/SYMBOL.csv.gz), it will require iterating symbols; keep correctness first and ensure batching and reasonable logging.
	•	If the current implementation already supports reading the daily aggregate universe file (single file per day), prefer that approach for performance and simplicity, but do not invent a new S3 layout; use what the repo already supports.

D. Tests to add/update

Unit tests
	1.	Ticker universe loader pagination

	•	Mock requests.get and validate:
	•	first call uses base_url + params
	•	subsequent calls follow next_url
	•	aggregation across pages works
	•	missing fields handled safely

	2.	Ticker upsert behavior

	•	If unit-level DB is too heavy, test SQL params and shape; otherwise, use an in-memory or test DB fixture if already present.

	3.	Bootstrap decision logic

	•	Given tickers_count == 0 and –no-ticker-bootstrap not set, ensure loader is invoked.
	•	Given tickers_count > 0, ensure loader is not invoked.
	•	Given tickers_count == 0 and –no-ticker-bootstrap set, ensure hard-fail.

Integration tests (require KAPMAN_TEST_DATABASE_URL)
Add an integration test that proves bootstrap + ingest sequencing at a functional boundary without pulling real Polygon data:
	•	Avoid real network calls and real S3 calls in tests.
	•	Mock:
	•	Polygon reference API responses for tickers bootstrap
	•	S3 read path to provide a minimal deterministic OHLCV dataset (a few symbols, a few days)
	•	Assertions:
	•	tickers becomes non-empty after the run
	•	ohlcv_daily becomes non-empty after the run
	•	a second run is idempotent (row counts stable; schema unchanged; no duplicates)

Test placement should match existing conventions:
	•	tests/unit/test_<…>.py
	•	tests/integration/test_a0_<…>.py

E. Repo hygiene
	•	Do not add or modify anything under archive/ as part of runtime logic.
	•	Do not import from archive/ anywhere in production code.
	•	If any currently-referenced code paths still point to archive/, refactor them out as part of this change.

Concrete file changes (expected, not exhaustive; adjust to actual repo layout after inspection)
	•	Add: core/ingestion/tickers/init.py
	•	Add: core/ingestion/tickers/polygon_reference.py
	•	Add: core/ingestion/tickers/db.py
	•	Add: core/ingestion/tickers/loader.py
	•	Add (optional): scripts/ingest_tickers.py
	•	Modify: scripts/ingest_ohlcv.py (bootstrap tickers when empty; add –no-ticker-bootstrap)
	•	Modify/Add: tests/unit/test_a0_ticker_loader.py
	•	Modify/Add: tests/unit/test_a0_ticker_bootstrap_logic.py
	•	Modify/Add: tests/integration/test_a0_bootstrap_then_ohlcv_ingest.py

Validation checklist (must be true before finishing)
	•	Running scripts/ingest_ohlcv.py base on an empty DB bootstraps tickers and then writes OHLCV to ohlcv_daily.
	•	Running the same command twice yields the same row counts (idempotent).
	•	Unit tests pass.
	•	Integration tests pass when KAPMAN_TEST_DATABASE_URL is set.
	•	No production code imports anything from archive/.
	•	No hardcoded secrets or credentials are introduced.
	•	Output is diffs only.

Return only diffs.