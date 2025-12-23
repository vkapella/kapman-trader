[A3] Dealer Metrics Computation & Persistence (GEX, Flip, Walls)

Status: Planned
Roadmap Reference: S-MET-01
Owner: vkapella
Scope: MVP
Touches Schema: daily_snapshots.dealer_metrics_json (no schema changes)

⸻

1. Story Framing & Intent

Why this issue exists

This story implements deterministic dealer positioning metrics computed from persisted options data so that Wyckoff analysis and downstream recommendation logic can be contextualized with market-structure signals (volatility regime, hedging pressure, and strike congestion). The output is persisted, reproducible, and suitable for reruns and backfills.

What this story delivers
	•	Deterministic, batch computation of dealer metrics from options_chains
	•	Metrics computed per (ticker_id, snapshot_time)
	•	Metrics include:
	•	Total GEX
	•	Net GEX
	•	Gamma Flip (interpolated zero-crossing)
	•	Call/Put Walls (arrays of strikes; primary at index 0; top 3 retained)
	•	GEX Slope (rate of change of GEX vs price)
	•	DGPI
	•	Dealer position (long/short/neutral gamma) and confidence
	•	Idempotent persistence to daily_snapshots.dealer_metrics_json
	•	Callable module (pipeline-owned) with optional CLI invocation
	•	pytest-discoverable unit and integration tests

What this story explicitly does not do
	•	No trade decisions or recommendations
	•	No Wyckoff interpretation or readiness scoring
	•	No changes to options ingestion or schemas
	•	No intraday or real-time metrics
	•	No parameter tuning beyond codifying existing logic

⸻

2. Inputs, Outputs, and Invariants

Tables Read
	•	tickers
	•	options_chains
	•	ohlcv (spot price only; snapshot date close)

Tables Written
	•	daily_snapshots.dealer_metrics_json only

External APIs / Services
	•	None (all inputs are persisted)

Snapshot Time Semantics
	•	Uses the same snapshot_time as the daily pipeline (authoritative)
	•	Optional CLI override for backfill/debug

Invariants
	•	Deterministic: same inputs produce same outputs
	•	Soft-fail per ticker on insufficient/low-quality data
	•	Per-ticker failures do not halt the batch
	•	JSON schema is stable; versioned via model_version

⸻

3. Data Flow & Control Flow

Entry Point
	•	Callable module invoked by the daily pipeline
	•	Optional CLI entrypoint calls the same module (no separate runner)

Batch Scope
	•	Iterate over watchlist tickers
	•	No cross-ticker aggregation or dependencies

Option Chain Selection Rules (Defaults; all overrideable via CLI)

Mandatory (default ON):
	•	Exclude expired contracts
	•	Require gamma IS NOT NULL
	•	Require open_interest > 0
	•	Max DTE ≤ 90 days
	•	Min open interest per contract ≥ 100

Liquidity / Realism (default ON):
	•	Min volume ≥ 1

Spot Price (Authoritative)
	•	ohlcv.close for the snapshot date
	•	Optional CLI override for diagnostics

Computation Order (Per Ticker)
	1.	Load option contracts for ticker and snapshot context
	2.	Apply selection filters
	3.	Compute per-contract GEX
	4.	Aggregate strike-level GEX
	5.	Compute Total GEX and Net GEX
	6.	Compute Gamma Flip (zero-crossing interpolation)
	7.	Identify Top 3 Call and Put Walls by OI (arrays; primary at index 0)
	8.	Compute GEX Slope (windowed around spot; default ±2%)
	9.	Compute DGPI
	10.	Derive dealer position and confidence
	11.	Validate outputs and log diagnostics
	12.	Emit JSON payload

Persistence Semantics
	•	One atomic write per (ticker_id, snapshot_time)
	•	Replace dealer_metrics_json idempotently
	•	No coupling to other JSON blobs

CLI Parameters (Defaults + Overrides)
	•	--log-level (default: INFO)
	•	--snapshot-time (default: pipeline time)
	•	--max-dte-days (default: 90)
	•	--min-open-interest (default: 100)
	•	--min-volume (default: 1)
	•	--walls-top-n (default: 3)
	•	--gex-slope-range-pct (default: 0.02)
	•	--spot-override (optional)

Heartbeat & Progress
	•	INFO heartbeat every 60 seconds and every 25 tickers
	•	Reports progress count and percent

⸻

4. Failure Modes & Idempotency

Expected Failure Modes
	•	Missing or insufficient options_chains
	•	All contracts filtered out
	•	Missing ohlcv spot for snapshot date
	•	Malformed numeric fields
	•	Transient DB write errors

Behavior
	•	Soft-fail per ticker: write valid JSON with confidence="invalid" and diagnostics
	•	Continue processing remaining tickers
	•	Retry transient DB write errors up to 3 times with backoff, then soft-fail ticker

Idempotency
	•	UPSERT keyed by (time, ticker_id)
	•	Only dealer_metrics_json (and metadata fields like model_version) updated
	•	Per-ticker writes (no multi-ticker transaction)

Determinism Guardrails
	•	No dependence on wall-clock time for calculations
	•	Any spot_override is logged and recorded in metadata
	•	Effective filters and thresholds recorded in payload metadata

⸻

5. Testing Strategy

Unit Tests

Location: tests/unit/dealer_metrics/

Coverage:
	•	Per-contract GEX
	•	Strike-level aggregation
	•	Total/Net GEX
	•	Gamma Flip (including interpolation)
	•	Call/Put Walls (Top 3 ordering)
	•	GEX Slope
	•	DGPI
	•	Dealer position classification
	•	Confidence determination

Constraints:
	•	Pure Python/DataFrames
	•	No DB, no external APIs

Edge Cases:
	•	Empty chains
	•	All contracts filtered
	•	Missing gamma
	•	Single-strike chains
	•	No zero-crossing
	•	Spot outside strike range
	•	Near-zero Net GEX

Integration Tests

Location: tests/integration/test_dealer_metrics_pipeline.py

Responsibilities:
	•	Insert minimal fixtures into tickers, ohlcv, options_chains
	•	Invoke module pipeline-style
	•	Assert:
	•	Row exists in daily_snapshots
	•	dealer_metrics_json populated
	•	Primary walls and arrays correct
	•	Position and confidence present
	•	Real test DB; default pytest invocation

Negative Case:
	•	Insufficient option data → job completes; confidence="invalid"; no exception

Coverage
	•	≥ 80% for new code
	•	Critical math paths asserted directly
	•	No exclusions to meet coverage

⸻

6. Operational Considerations

Reruns & Backfills
	•	Idempotent reruns for the same snapshot_time
	•	Backfills supported for historical dates with available data
	•	Invoked via CLI flags or caller-provided snapshot time
	•	No today-only assumptions

Logging & Observability

RUN HEADER (INFO, once):
	•	Snapshot time
	•	Effective parameters (defaults vs overrides)
	•	Tickers to process

HEARTBEAT (INFO):
	•	Every 60s and every 25 tickers
	•	Progress count and percent

FINAL SUMMARY (INFO, once):
	•	Snapshot time processed
	•	Total tickers processed
	•	Success/soft-fail counts
	•	Average per-ticker duration
	•	Total duration

DEBUG (CLI-enabled):
	•	Per-ticker details
	•	Filter stats
	•	Intermediate metrics
	•	Full exception traces (non-blocking)

Performance
	•	Linear scaling with watchlist size
	•	No cross-ticker aggregation
	•	Fits existing daily metrics window
	•	No special DB tuning required

Failure Visibility
	•	Soft-fails visible via logs and JSON confidence
	•	No additional alerting required for MVP
	•	Downstream phases not blocked

⸻

7. Acceptance Criteria
	•	Dealer metrics computed from options_chains for all watchlist tickers
	•	Total GEX, Net GEX, Gamma Flip, Call/Put Walls (Top 3), GEX Slope, DGPI populated
	•	Results persisted idempotently to daily_snapshots.dealer_metrics_json
	•	CLI flags supported with defaults and overrides
	•	Unit and integration tests pass under default pytest with ≥80% coverage
