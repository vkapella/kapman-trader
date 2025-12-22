Implement GitHub Issue [A3] — Dealer Metrics Computation & Persistence (GEX, Flip, Walls)

This is an execution task. Architecture, schema, and intent are frozen and authoritative. Do not redesign, refactor architecture, or introduce new abstractions.

Objective

Implement deterministic dealer-positioning metrics computed from persisted options data and persist results idempotently into daily snapshots. The output is used to contextualize Wyckoff analysis and downstream recommendation logic.

Scope Summary (Authoritative)

Implement a callable Python module, owned by the daily pipeline, that computes dealer metrics from options_chains for all watchlist tickers and writes results to daily_snapshots.dealer_metrics_json. The same module must be optionally invokable via CLI with defaults and overrideable flags. Do not introduce a separate runner.

Authoritative Calculation Source

All dealer-metric calculations MUST conform to the authoritative definitions, semantics, and examples in:

docs/research_inputs/dealer_metrics.py
ignore files in the archive/ directory

This directory is the single source of truth for dealer-metrics math, normalization, and interpretation, including GEX, Net GEX, Gamma Flip, Walls, GEX Slope, DGPI, position, and confidence.

The DataFrame-based example and the Schwab-equivalent dataclass implementation provided during planning are compliant reference implementations as long as outputs are equivalent in meaning and scale.

Do not invent new formulas, reinterpret metrics, or alter normalization beyond what is defined in the authoritative research inputs.

Metrics to Compute (Required)

For each (ticker_id, snapshot_time):
	•	Total GEX
	•	Net GEX
	•	Gamma Flip (interpolated zero-crossing of cumulative strike-level GEX)
	•	Call Walls: array of top 3 strikes by open interest (descending), primary at index 0
	•	Put Walls: array of top 3 strikes by open interest (descending), primary at index 0
	•	GEX Slope: rate of change of GEX with respect to price, windowed around spot
	•	DGPI (Dealer Gamma Pressure Index)
	•	Dealer position: long_gamma | short_gamma | neutral
	•	Confidence: high | medium | low | invalid

All metrics must be deterministic and derived only from persisted data.

Inputs (Read Only)
	•	tickers
	•	options_chains
	•	ohlcv (spot price only)

Spot Price Rule (Authoritative)
	•	Use ohlcv.close for the snapshot date.
	•	Allow CLI override for diagnostics only.
	•	Persist the spot used in metadata.

Option Chain Selection Rules (Defaults; Overrideable via CLI)

Mandatory filters (default ON):
	•	Exclude expired contracts
	•	gamma IS NOT NULL
	•	open_interest > 0
	•	max DTE <= 90
	•	min open interest per contract >= 100
	•	min volume >= 1
	•	max bid-ask spread <= 10%

All thresholds must have defaults and be overrideable via CLI flags.

Computation Order (Per Ticker; Fixed)
	1.	Load option contracts for ticker and snapshot context
	2.	Apply selection filters
	3.	Compute per-contract GEX
	4.	Aggregate strike-level GEX
	5.	Compute Total GEX and Net GEX
	6.	Compute Gamma Flip (interpolated zero-crossing)
	7.	Identify Call and Put Walls (top 3 by open interest)
	8.	Compute GEX Slope (default window ±2% around spot)
	9.	Compute DGPI
	10.	Derive dealer position and confidence
	11.	Validate outputs and log diagnostics
	12.	Emit JSON payload

Persistence Rules
	•	Write only to daily_snapshots.dealer_metrics_json
	•	Idempotent UPSERT keyed by (time, ticker_id)
	•	Replace dealer_metrics_json atomically
	•	Do not mutate other JSON blobs or fields
	•	Per-ticker writes only

CLI Requirements

The module must be optionally invokable via CLI and accept:
	•	–log-level DEBUG|INFO|WARNING (default INFO)

Key parameters must have defaults and be overrideable via CLI flags, including:
	•	–snapshot-time
	•	–max-dte-days (default 90)
	•	–min-open-interest (default 100)
	•	–min-volume (default 1)
	•	–max-spread-pct (default 10.0)
	•	–walls-top-n (default 3)
	•	–gex-slope-range-pct (default 0.02)
	•	–spot-override (optional)

Logging & Observability (Mandatory)

Logging must be non-blocking and low overhead.

RUN HEADER (INFO, once):
	•	Snapshot time
	•	Effective parameters (defaults vs overrides)
	•	Number of tickers

HEARTBEAT (INFO):
	•	Every 60 seconds AND every 25 tickers
	•	Progress count and percent

FINAL SUMMARY (INFO, once):
	•	Snapshot time processed
	•	Total tickers processed
	•	Success and soft-fail counts
	•	Average per-ticker duration
	•	Total duration

DEBUG mode (CLI-enabled):
	•	Per-ticker details
	•	Filter statistics
	•	Intermediate metric values
	•	Full exception traces (do not abort batch)

Failure Handling & Idempotency
	•	Soft-fail per ticker on insufficient or malformed data
	•	Write valid JSON with confidence=“invalid” and diagnostics
	•	Continue processing remaining tickers
	•	Retry transient DB write errors up to 3 times with backoff, then soft-fail ticker
	•	No job-level abort on single-ticker failure

Determinism Guardrails
	•	No dependence on wall-clock time for calculations
	•	Any CLI overrides must be logged and persisted in metadata
	•	Effective filters and thresholds must be recorded in payload metadata

Testing Requirements (Non-Negotiable)

Unit Tests

Location: tests/unit/dealer_metrics/

Must cover:
	•	Per-contract GEX
	•	Strike-level aggregation
	•	Total and Net GEX
	•	Gamma Flip (including interpolation)
	•	Call/Put Walls ordering
	•	GEX Slope
	•	DGPI
	•	Dealer position classification
	•	Confidence logic

Constraints:
	•	Pure Python or DataFrames
	•	No database access
	•	No external APIs

Edge cases must include empty chains, all contracts filtered, missing gamma, single-strike chains, no zero-crossing, spot outside strike range, and near-zero Net GEX.

Integration Tests

Location: tests/integration/test_dealer_metrics_pipeline.py

Must:
	•	Insert minimal fixtures into tickers, ohlcv, options_chains
	•	Invoke the module pipeline-style
	•	Assert a row exists in daily_snapshots with populated dealer_metrics_json
	•	Validate primary walls and arrays
	•	Validate position and confidence
	•	Include one negative case where data is insufficient and confidence=“invalid”
	•	Run under default pytest with no flags
	•	Use a real test database

Coverage
	•	Minimum 80% coverage for all new code
	•	Critical math paths must have direct assertions
	•	No coverage exclusions to meet targets

Operational Constraints
	•	Support reruns and backfills for arbitrary snapshot dates with available data
	•	No today-only assumptions
	•	Runtime must scale linearly with watchlist size
	•	No cross-ticker aggregation
	•	No additional DB tuning or indexing required
	•	Soft-failed tickers must be visible via logs and JSON confidence
	•	Downstream pipeline phases must not be blocked

Deliverables
	•	Dealer metrics computation module integrated into the daily pipeline
	•	Optional CLI invocation using the same module
	•	Unit and integration tests as specified
	•	No new schemas, tables, or runners
	•	All code must pass pytest and meet coverage requirements

Proceed autonomously until the task is fully complete.