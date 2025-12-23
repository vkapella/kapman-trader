WINDSURF / CODEX — SINGLE FILE PROMPT

Model Target
Use GPT-5.1-Codex-Mini at MEDIUM reasoning level.

⸻

ROLE & MISSION

You are acting as an autonomous senior Python engineer and execution-focused technical lead for the KapMan trading system.

Your task is to IMPLEMENT story [A4] Volatility Metrics Computation & Persistence (IV, IV Rank, P/C) exactly as specified in the authoritative story document located at:

docs/stories/A4_volatility_metrics.md

This is an IMPLEMENTATION task, not planning, research, or redesign.

You must:
	•	Read the story in full
	•	Inspect the repository to understand existing conventions
	•	Implement production-ready code
	•	Add required tests
	•	Preserve architectural and operational invariants

⸻

NON-NEGOTIABLE GUARDRAILS
	1.	Architecture and story text are authoritative
	•	Do NOT reinterpret scope
	•	Do NOT expand scope
	•	Do NOT introduce new abstractions, tables, or services
	2.	Determinism is mandatory
	•	Same inputs + same snapshot_time MUST yield identical outputs
	•	No nondeterministic ordering, sampling, or “latest row” ambiguity
	3.	Idempotency is mandatory
	•	Writes must be safe to rerun
	•	Only update daily_snapshots.volatility_metrics_json
	•	Do NOT clobber any other snapshot fields
	4.	Batch-oriented execution only
	•	No event-driven logic
	•	No background workers
	•	No streaming or async pipelines beyond existing patterns
	5.	Testing discipline
	•	Tests MUST live under tests/
	•	Tests MUST be discoverable by default pytest
	•	No custom runners, flags, or scripts
	•	If a test cannot meet this bar, do not add it
	6.	CLI and logging MUST match existing KapMan modules
	•	Match run_a2_local_ta conventions exactly
	•	Use argparse default help only
	•	Use existing logging framework (no print)

⸻

PRIMARY IMPLEMENTATION OBJECTIVES
	1.	Implement a production volatility metrics module derived from:
research_inputs/volatility_metrics.py
	2.	Compute, per watchlist ticker per snapshot_time:
	•	average_iv (OI-weighted, fallback to simple mean)
	•	iv_rank (252 trading-day lookback, range-based)
	•	put_call_ratio_oi
	•	oi_ratio
	•	iv_skew (25Δ put − 25Δ call, with fallbacks)
	•	iv_term_structure (IV_long − IV_short; 90 vs 30 DTE)
	3.	Deterministically select options snapshot:
	•	options_snapshot_time = max(options_chains.time) <= snapshot_time
	4.	Persist results via UPSERT into:
daily_snapshots.volatility_metrics_json
	5.	Ensure:
	•	No missing watchlist tickers per run
	•	Explicit null metrics + status when data missing
	•	Deterministic behavior on reruns

⸻

CLI REQUIREMENTS (MUST MATCH A2)

Implement a CLI entrypoint:

python -m scripts.run_a4_volatility_metrics

Required argparse flags (EXACT):
	•	–db-url DB_URL
	•	–date DATE
	•	–start-date START_DATE
	•	–end-date END_DATE
	•	–fill-missing
	•	–verbose
	•	–debug
	•	–quiet
	•	–heartbeat HEARTBEAT

Rules:
	•	–date overrides start/end
	•	Default date behavior aligns with pipeline “today”
	•	–debug implies –verbose
	•	–quiet suppresses INFO except summaries
	•	–heartbeat emits INFO every N tickers
	•	Do NOT custom-print help; rely on argparse

⸻

LOGGING RULES (MANDATORY)

Use the existing logging framework.

Logging levels:
	•	INFO
	•	Batch start summary
	•	Batch end summary
	•	Heartbeat messages
	•	Expected data gaps (no options data, insufficient history)
	•	WARNING
	•	Unexpected indicator computation failures
	•	ERROR
	•	Fatal DB or batch failures
	•	DEBUG
	•	Per-indicator and per-metric computation details
	•	Enabled ONLY when –debug is set

Batch start summary (INFO) MUST include:
	•	Date or date range
	•	Ticker count
	•	Active flags (debug/verbose/quiet/heartbeat/fill-missing)

Batch end summary (INFO) MUST include:
	•	Date or date range
	•	Total tickers processed
	•	Counts:
	•	successful
	•	missing options data
	•	partial/null metrics
	•	errors
	•	Total runtime

⸻

DATA & SCHEMA CONSTRAINTS

Read from:
	•	options_chains (per 0006_options_chains_timescaledb.sql)
	•	daily_snapshots (for IV Rank history)
	•	existing watchlist source

Write to:
	•	daily_snapshots.volatility_metrics_json ONLY

Primary key:
	•	(time, ticker_id)

Do NOT:
	•	Modify schema
	•	Add tables
	•	Change existing migrations

⸻

IV RANK DEFINITION (LOCKED)

IV Rank = (IV_current − IV_min) / (IV_max − IV_min) × 100

Where:
	•	IV_current = today’s computed average_iv
	•	IV_min / IV_max = min/max of historical average_iv over prior 252 trading days

Fallbacks (deterministic):
	•	If IV_current is null → iv_rank = null
	•	If < 20 historical points → iv_rank = null
	•	If IV_max == IV_min → iv_rank = null

Clamp result to [0, 100].

⸻

FAILURE HANDLING RULES

Per-ticker failures:
	•	Must NOT abort the batch
	•	Must still upsert a snapshot row with null metrics and status

Batch-level failures (DB connectivity, schema issues):
	•	MUST abort the batch with ERROR

No silent skips. Ever.

⸻

TESTING REQUIREMENTS

Add:

Unit tests:
	•	tests/unit/volatility_metrics/
	•	Validate each metric independently
	•	Validate fallback behavior

Integration tests:
	•	tests/integration/test_a4_volatility_metrics.py
	•	Validate:
	•	No missing watchlist tickers
	•	Idempotent reruns
	•	Non-clobbering of other snapshot fields
	•	Deterministic options snapshot selection
	•	Presence of batch summaries (logged, not printed)

All tests must pass with:
pytest

⸻

EXECUTION INSTRUCTIONS

Proceed autonomously.
	1.	Inspect the repository for existing patterns (A2, A3).
	2.	Implement A4 in production code.
	3.	Add required tests.
	4.	Ensure style, logging, and CLI consistency.
	5.	Do NOT ask clarifying questions unless an ambiguity blocks implementation.
	6.	Do NOT output explanations — produce code and tests only.

⸻

END OF PROMPT