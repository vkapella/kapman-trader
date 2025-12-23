[A4] Volatility Metrics Computation & Persistence (IV, IV Rank, P/C)

Owner: @vkapella
Roadmap Reference: S-MET-02
Closes: FR-005

⸻

Objective

Compute and persist daily option-implied volatility metrics for all watchlist tickers. These metrics provide volatility regime and sentiment context used by Wyckoff analysis and downstream recommendations.

This story also defines CLI behavior and logging semantics consistent with existing KapMan batch modules (A2, A3), including batch start/end summaries, heartbeat logging, and verbosity controls.

⸻

Scope

In Scope

Daily, deterministic, batch computation and persistence of:
	•	Average IV (OI-weighted; fallback to simple mean)
	•	IV Rank (252-day lookback, range-based)
	•	Put/Call Ratio (open interest)
	•	Open Interest Ratio (volume ÷ open interest)
	•	IV Skew (25Δ put − 25Δ call, with fallbacks)
	•	IV Term Structure (IV_long − IV_short, 90 vs 30 DTE)

Operational scope:
	•	CLI flags aligned with run_a2_local_ta
	•	Structured logging summaries at batch start and end
	•	Heartbeat logging
	•	Logging-level control via flags (no custom help output)

Persistence target:
	•	daily_snapshots.volatility_metrics_json

Reference implementation:
	•	research_inputs/volatility_metrics.py (algorithmic baseline)

Schema references:
	•	db/migrations/0003_mvp_schema.sql
	•	db/migrations/0006_options_chains_timescaledb.sql

Out of Scope
	•	Options ingestion
	•	Schema changes
	•	Realized volatility
	•	Recommendation logic
	•	Custom CLI UX beyond argparse defaults
	•	Event-driven execution

⸻

Acceptance Criteria
	•	All volatility metrics computed daily for all watchlist tickers
	•	Metrics persisted to daily_snapshots.volatility_metrics_json
	•	No missing watchlist tickers per batch
	•	Deterministic, idempotent execution
	•	Batch start and end summaries logged at INFO
	•	CLI flags and logging behavior consistent with A2/A3 modules

⸻

PHASE 1 — Story Framing & Intent

Volatility context is required to correctly interpret Wyckoff phases and dealer positioning. Operationally, this batch must be observable, rerunnable, and controllable using the same CLI and logging conventions as the rest of the KapMan pipeline.

⸻

PHASE 2 — Inputs, Outputs, Invariants

(unchanged; locked in prior phases)

⸻

PHASE 3 — Data Flow & Control Flow

(unchanged; locked in prior phases)

⸻

PHASE 4 — Failure Modes & Idempotency

(unchanged; locked in prior phases)

⸻

PHASE 5 — Testing Strategy

Unit Tests

Location:
	•	tests/unit/volatility_metrics/

In addition to metric correctness tests:
	•	CLI argument parsing (date vs range precedence)
	•	Logging level behavior (debug / verbose / quiet)
	•	Heartbeat triggering logic

Integration Tests

Location:
	•	tests/integration/test_a4_volatility_metrics.py

Must validate:
	•	No missing watchlist tickers
	•	Idempotent upserts
	•	Non-clobbering of other daily_snapshots fields
	•	Deterministic options snapshot selection
	•	Batch start/end summaries emitted at INFO

⸻

PHASE 6 — Operational Considerations (FINAL)

CLI Interface (MANDATORY)

The A4 batch must match the CLI style of run_a2_local_ta.

Invocation:

python -m scripts.run_a4_volatility_metrics

CLI Flags (EXACT)

usage: run_a4_volatility_metrics.py [-h]
  [--db-url DB_URL]
  [--date DATE]
  [--start-date START_DATE]
  [--end-date END_DATE]
  [--fill-missing]
  [--verbose]
  [--debug]
  [--quiet]
  [--heartbeat HEARTBEAT]

Flag Semantics
Date Control
	•	--date YYYY-MM-DD
	•	--start-date YYYY-MM-DD
	•	--end-date YYYY-MM-DD

Rules:
	•	--date overrides start/end
	•	Start/end iterates deterministically by trading day
	•	Default = pipeline-supplied snapshot date (today)

Completeness
	•	--fill-missing
	•	Ensures a daily_snapshots row exists for every watchlist ticker
	•	Metrics may be null if inputs missing

Verbosity / Logging
	•	--verbose → INFO per-ticker progress
	•	--debug → DEBUG per-indicator detail (implies verbose)
	•	--quiet → suppress INFO except summaries

Heartbeat
	•	--heartbeat N
	•	Emit INFO heartbeat every N tickers
	•	Default aligned with A2 (e.g., 50)

Help
	•	No custom help output
	•	Use argparse defaults only

⸻

Logging Rules (LOCKED)
	•	Use existing logging framework
	•	No print() to stdout

Event	Level
Batch start summary	INFO
Batch end summary	INFO
Heartbeat	INFO
Expected data gaps	INFO
Unexpected indicator failure	WARNING
Fatal DB / batch failure	ERROR
Per-indicator computation	DEBUG (only with --debug)

Batch Start Summary (INFO)
Must include:
	•	Snapshot date or date range
	•	Number of tickers
	•	Active flags (debug / verbose / quiet / heartbeat / fill-missing)

Batch End Summary (INFO)
Must include:
	•	Snapshot date or date range
	•	Total tickers processed
	•	Counts:
	•	fully successful
	•	missing options data
	•	partial/null metrics
	•	errors
	•	Total execution time

⸻

PHASE 7 — Implementation Checklist
	1.	Promote volatility metrics logic from research to production module
	2.	Add IV Rank computation per locked definition
	3.	Implement deterministic options snapshot selection
	4.	Implement idempotent upsert to daily_snapshots
	5.	Implement CLI matching A2 conventions
	6.	Implement logging:
	•	start/end summaries
	•	heartbeat
	•	debug-level indicator detail
	7.	Add unit + integration tests (discoverable by default pytest)

⸻

Definition of Done
	•	All acceptance criteria met
	•	CLI flags visible via --help and consistent with other modules
	•	Batch summaries logged at INFO
	•	Debug flag enables per-indicator detail
	•	Deterministic reruns verified
	•	All tests pass via default pytest

⸻