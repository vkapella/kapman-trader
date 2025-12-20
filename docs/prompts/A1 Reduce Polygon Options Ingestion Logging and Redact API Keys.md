WINDSURF TASK — Reduce Polygon Options Ingestion Logging and Redact API Keys

Objective

Modify the options ingestion logging so that runtime output is concise, non-repetitive, and safe for local development and CI execution. Current logging is excessively verbose and leaks sensitive credentials via full request URLs.

This task is a logging-only change. No ingestion behavior, data correctness, concurrency, or persistence semantics may be altered.

⸻

Scope of Changes

In Scope
	•	Logging emitted during Polygon options ingestion
	•	Redaction of API keys from all logs
	•	Reduction of per-request noise
	•	Replacement of repetitive request logs with aggregated summaries

Out of Scope
	•	Changes to ingestion logic
	•	Changes to retry, pagination, concurrency, or locking behavior
	•	Changes to database schema or persistence
	•	Changes to test assertions unrelated to logging output

⸻

Files in Scope

Primary targets:
	•	core/providers/market_data/polygon_options.py
	•	core/ingestion/options/pipeline.py

Secondary (if required for shared logging utilities):
	•	core/logging/*
	•	core/utils/*

Do not modify unrelated ingestion paths.

⸻

Required Logging Behavior

API Key Redaction (Mandatory)
	•	API keys must never appear in logs
	•	Full request URLs must not be logged if they include credentials
	•	If URLs are logged, query parameters must be stripped or redacted
	•	API key values must never be interpolated into log strings

This applies to:
	•	httpx logging
	•	provider-level logging
	•	pipeline-level logging

⸻

HTTP Request Logging

Replace per-request logging like:

HTTP Request: GET https://api.polygon.io/v3/snapshot/options/AAPL?apiKey=…

With one of the following:
	•	No per-request logging at INFO level
	•	OR a sanitized, non-credentialed form such as:
	•	Polygon options request issued for symbol=AAPL page=1
	•	Polygon options page fetched (symbol=AAPL)

Under no circumstances should the full URL with query parameters be logged.

⸻

Pagination Logging

Current behavior logs “Fetched Polygon options page” for every page and every symbol.

Required behavior:
	•	Do not log per-page fetches at INFO
	•	Track pagination internally
	•	Emit a single per-symbol summary log at INFO, for example:
	•	symbol=AAPL pages=4 contracts=312 snapshot_time=2025-12-19T22:29:17Z

Optional:
	•	Page-level logs may exist at DEBUG level only

⸻

Per-Symbol Summary (Required)

For each symbol processed, emit exactly one INFO-level log containing:
	•	symbol
	•	number of pages fetched
	•	number of option contracts normalized
	•	number of rows written
	•	elapsed time
	•	success or failure indicator

Failures must still emit a summary log with error classification.

⸻

Run-Level Summary (Required)

At the end of ingestion, emit a single INFO-level run summary:
	•	mode (batch / adhoc)
	•	snapshot_time
	•	symbols attempted
	•	symbols succeeded
	•	symbols failed
	•	total rows written
	•	total elapsed time

⸻

Logging Levels
	•	INFO: run-level and per-symbol summaries only
	•	DEBUG: pagination, retries, low-level request details (sanitized)
	•	WARNING: recoverable per-symbol failures
	•	ERROR: systemic failures (DB unavailable, Polygon unavailable)

No INFO-level logs should appear inside tight loops.

⸻

Tests and Validation
	•	Existing unit and integration tests must continue to pass
	•	No tests should assert on raw log content that includes URLs or API keys
	•	If any tests rely on log messages, update them to match the new summarized format
	•	Manually verify that running:
./venv/bin/python scripts/ingest_options.py
does not emit API keys or excessive per-request logs

⸻

Acceptance Criteria
	•	API keys never appear in logs
	•	No full Polygon URLs with query strings are logged
	•	Per-request logging noise is eliminated at INFO level
	•	Exactly one INFO log per symbol and one per run
	•	DEBUG logs remain available for troubleshooting
	•	All tests pass without modification to ingestion behavior

⸻

Constraints
	•	Do not change functional ingestion behavior
	•	Do not add new dependencies
	•	Prefer small, localized changes
	•	Preserve existing logging structure where possible

⸻

End of Task